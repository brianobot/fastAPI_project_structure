import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import bcrypt
import jwt
from fastapi import BackgroundTasks, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic.networks import EmailStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.logger import logger
from app.mailer import send_mail
from app.models import User as UserDB
from app.redis_manager import redis_manager
from app.schemas import auth as auth_schema
from app.settings import settings

JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = settings.JWT_ALGORITHM

ACCESS_TOKEN_LIFESPAN = timedelta(minutes=settings.ACCESS_TOKEN_LIFESPAN_MIN)
REFRESH_TOKEN_LIFESPAN = timedelta(days=settings.REFRESH_TOKEN_LIFESPAN_DAYS)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/token")

# Per-user token version. Bumped on logout / password change to invalidate
# every token issued before it. Failure counters gate code brute-forcing.
MAX_CODE_ATTEMPTS = 5
CODE_LOCKOUT_SECONDS = 15 * 60
# Minimum gap between code emails to the same account (anti email-bombing).
CODE_EMAIL_COOLDOWN_SECONDS = 60

# Signup responds identically whether or not the email is already registered,
# so an attacker can't enumerate accounts through the signup endpoint.
GENERIC_SIGNUP_MESSAGE = "Please check your email to activate your account."


# --- Redis key builders (single source of truth for key formats) ------------
def token_version_key(email: str) -> str:
    return f"token-version-{email}"


def activation_code_key(email: str) -> str:
    return f"activation-code-{email}"


def reset_code_key(email: str) -> str:
    return f"reset-code-{email}"


def failed_attempts_key(scope: str, email: str) -> str:
    return f"failed-{scope}-{email}"


def email_cooldown_key(scope: str, email: str) -> str:
    return f"cooldown-{scope}-{email}"


async def email_cooldown_active(scope: str, email: str) -> bool:
    """
    Rate-limit code emails per account: True if one was sent within the last
    CODE_EMAIL_COOLDOWN_SECONDS (and the caller should skip sending another).
    """
    key = email_cooldown_key(scope, email)
    if await redis_manager.get_int(key):
        return True
    await redis_manager.increment(key, ttl=CODE_EMAIL_COOLDOWN_SECONDS)
    return False


async def invalidate_all_sessions(email: str) -> None:
    """Bump the user's token version so every existing token is rejected."""
    await redis_manager.increment(token_version_key(email))


async def guard_code_attempts(scope: str, email: str) -> str:
    """
    Throttle brute-forcing of the 6-digit codes: after MAX_CODE_ATTEMPTS wrong
    submissions for (scope, email), lock the account out for CODE_LOCKOUT_SECONDS.
    Returns the counter key so the caller can register a failure or clear it.
    """
    key = failed_attempts_key(scope, email)
    if await redis_manager.get_int(key) >= MAX_CODE_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )
    return key


def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(
        bytes(plain_password, encoding="utf-8"),
        bytes(hashed_password, encoding="utf-8"),
    )


def get_password_hash(password: str):
    return bcrypt.hashpw(
        bytes(password, encoding="utf-8"),
        bcrypt.gensalt(),
    ).decode()


# A real hash to verify against when the account doesn't exist, so a missing
# user costs the same bcrypt work as a wrong password - defeating timing-based
# user enumeration on the login endpoint.
_DUMMY_PASSWORD_HASH = get_password_hash(secrets.token_urlsafe(32))


def generate_random_code(n: int = 4) -> str:
    # secrets.choice is cryptographically secure - important for OTP / reset
    # / activation codes that gate account access.
    return "".join(secrets.choice("0123456789") for _ in range(n))


async def get_user(email: EmailStr, session: AsyncSession) -> UserDB | None:
    stmt = select(UserDB).where(func.lower(UserDB.email) == email.lower())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    user_data: auth_schema.UserSignUpData,
    session: AsyncSession,
):
    user = await get_user(user_data.email, session)
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)
    new_user = UserDB(
        email=user_data.email,
        password_hash=hashed_password,
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user


async def initiate_password_reset(
    email: str, session: AsyncSession, background_task: BackgroundTasks
):
    user = await get_user(email, session)
    if not user or await email_cooldown_active("reset", email):
        return {"detail": "Password Reset Code Sent"}

    code = generate_random_code(6)
    await redis_manager.cache_json_item(
        reset_code_key(email), {"code": code}, ttl=60 * 30
    )

    background_task.add_task(
        send_mail,
        subject="Password Reset",
        receipients=[user.email],
        payload={"username": user.email.split("@")[0], "code": code},
        template="auth/initiate_password_reset.html",
    )

    return {"detail": "Password Reset Code Sent"}


async def reset_password(
    reset_data: auth_schema.PasswordResetData, session: AsyncSession
):
    attempt_key = await guard_code_attempts("reset", reset_data.email)
    data = await redis_manager.get_json_item(reset_code_key(reset_data.email))
    if not data or data.get("code") != reset_data.code:
        await redis_manager.increment(attempt_key, ttl=CODE_LOCKOUT_SECONDS)
        raise HTTPException(status_code=400, detail="Invalid Reset Code")

    user = await get_user(reset_data.email, session)
    if not user:
        raise HTTPException(status_code=404, detail="Invalid Reset Code")

    hashed_password = get_password_hash(reset_data.new_password)
    stmt = (
        update(UserDB)
        .where(UserDB.email == reset_data.email)
        .values(password_hash=hashed_password)
        .execution_options(synchronize_session="fetch")
    )

    await session.execute(stmt)
    await session.commit()

    # Consume the code and clear the failure counter on success.
    await redis_manager.delete_key(reset_code_key(reset_data.email))
    await redis_manager.delete_key(attempt_key)
    # A password reset must revoke every existing session (the point of a reset
    # is often that the old credentials/tokens are compromised).
    await invalidate_all_sessions(reset_data.email)

    return {"detail": "Password Reset Successfully"}


async def update_user(
    email: str, update_data: auth_schema.UpdateUserModel, session: AsyncSession
):
    data = update_data.model_dump(exclude_none=True, exclude_unset=True)

    old_password: str | None = data.pop("old_password", None)
    new_password: str | None = data.pop("new_password", None)
    if new_password:
        user = await authenticate_user(
            username=email,
            # NOTE: This can not fail since there's a validation on pydantic model to ensure old_password
            # is passed when the new_passowrd field is passed too
            password=cast(str, old_password),
            session=session,
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect Old Password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        data.update({"password_hash": get_password_hash(new_password)})

    stmt = (
        update(UserDB)
        .where(UserDB.email == email)
        .values(**data)
        .returning(UserDB)
        .execution_options(synchronize_session="fetch")
    )
    result = await session.execute(stmt)
    await session.commit()
    # Changing the password revokes existing sessions on other devices.
    if new_password:
        await invalidate_all_sessions(email)
    return result.scalar_one()


def create_access_token(
    data: dict[str, str | int | datetime], expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or ACCESS_TOKEN_LIFESPAN)
    # jti makes every token unique (so distinct logins never collide); type and
    # the caller-supplied ver drive access/refresh and global-logout checks.
    to_encode.update({"exp": expire, "type": "access", "jti": secrets.token_hex(16)})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    data: dict[str, str | int | datetime], expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or REFRESH_TOKEN_LIFESPAN)
    to_encode.update({"exp": expire, "type": "refresh", "jti": secrets.token_hex(16)})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def authenticate_user(
    username: EmailStr | str, password: str, session: AsyncSession
) -> UserDB | Literal[False]:
    user: UserDB | None = await get_user(username, session)
    if not user:
        # Spend the same bcrypt time as a real comparison so response timing
        # doesn't reveal whether the account exists.
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user


async def signup_user(
    data: auth_schema.UserSignUpData,
    session: AsyncSession,
    bg_task: BackgroundTasks,
):
    # Non-enumerable: respond identically whether or not the email is taken.
    existing = await get_user(data.email, session)
    if existing:
        # Match the bcrypt cost of a real signup so timing doesn't leak, and
        # send nothing (the real owner already has an account).
        get_password_hash(data.password)
        return {"detail": GENERIC_SIGNUP_MESSAGE}

    user = await create_user(data, session)

    code = generate_random_code(6)
    await redis_manager.cache_json_item(
        activation_code_key(data.email), {"code": code}, ttl=60 * 30
    )

    bg_task.add_task(
        send_mail,
        subject="Activation Code",
        receipients=[user.email],
        payload={"username": user.email.split("@")[0], "code": code},
        template="auth/verification.html",
    )
    return {"detail": GENERIC_SIGNUP_MESSAGE}


async def resend_activation_code(
    email: str, bg_task: BackgroundTasks, session: AsyncSession
):
    user = await get_user(email, session)

    if not user or await email_cooldown_active("activation", email):
        return {"detail": "Activation Code Sent"}

    code = generate_random_code(6)
    await redis_manager.cache_json_item(
        activation_code_key(email), {"code": code}, ttl=60 * 30
    )

    bg_task.add_task(
        send_mail,
        subject="Activation Code",
        receipients=[user.email],
        payload={"username": user.email.split("@")[0], "code": code},
        template="auth/verification.html",
    )
    return {"detail": "Activation Code Sent"}


async def activate_user(
    verification_data: auth_schema.UserVerificationModel,
    session: AsyncSession,
    bg_task: BackgroundTasks,
):
    attempt_key = await guard_code_attempts("activation", verification_data.email)
    data = await redis_manager.get_json_item(
        activation_code_key(verification_data.email)
    )

    if not data or data.get("code") != verification_data.code:
        await redis_manager.increment(attempt_key, ttl=CODE_LOCKOUT_SECONDS)
        raise HTTPException(status_code=400, detail="Invalid Activation Code")

    user = await get_user(verification_data.email, session)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid Activation Code")

    user.is_verified = True
    session.add(user)
    await session.commit()

    # Consume the code and clear the failure counter on success.
    await redis_manager.delete_key(activation_code_key(verification_data.email))
    await redis_manager.delete_key(attempt_key)

    bg_task.add_task(
        send_mail,
        subject="Welcome to {{ project_name }}",
        receipients=[user.email],
        payload={"username": user.email.split("@")[0].title()},
        template="auth/welcome.html",
    )

    return {"detail": "Email Activation Successful"}


async def signin_user(data: auth_schema.UserSignInData, session: AsyncSession):
    user = await authenticate_user(
        password=data.password, username=data.email, session=session
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
        )
    version = await redis_manager.get_int(token_version_key(data.email))
    access_token = create_access_token(
        data={"sub": data.email, "ver": version}, expires_delta=ACCESS_TOKEN_LIFESPAN
    )
    refresh_token = create_refresh_token(
        data={"sub": data.email, "ver": version}, expires_delta=REFRESH_TOKEN_LIFESPAN
    )

    return auth_schema.Token(
        token_type="Bearer",
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=datetime.now(UTC) + ACCESS_TOKEN_LIFESPAN,
        refresh_expires_at=datetime.now(UTC) + REFRESH_TOKEN_LIFESPAN,
    )


async def blacklist_token(token: str) -> None:
    """
    Blacklist a token for the remainder of its lifetime so it cannot be reused.
    A fixed TTL would either expire the entry early (re-enabling the token) or
    linger long after the token itself has expired, so the TTL is derived from
    the token's own `exp` claim.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except InvalidTokenError:
        # Already invalid; get_current_user / refresh_token will reject it anyway.
        return

    exp = payload.get("exp")
    ttl = int(exp - datetime.now(UTC).timestamp()) if exp else 0
    if ttl > 0:
        await redis_manager.cache_json_item(
            token, {"timestamp": str(datetime.now(UTC))}, ttl=ttl
        )


async def refresh_token(
    token_data: auth_schema.RefreshTokenModel, session: AsyncSession
):
    # A refresh token already blacklisted (by logout or a prior rotation) but
    # presented again is a reuse signal - a rotated token should never come back.
    # Treat it as possible theft and kill the whole session family.
    if await redis_manager.get_json_item(token_data.refresh_token):
        try:
            stale = jwt.decode(
                token_data.refresh_token,
                JWT_SECRET,
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            stale_sub = stale.get("sub")
            if isinstance(stale_sub, str):
                await invalidate_all_sessions(stale_sub)
        except InvalidTokenError:
            pass
        raise HTTPException(status_code=401, detail="Invalid Refresh Token")

    try:
        payload = jwt.decode(
            token_data.refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
    except Exception:
        logger.error("JWT Decode Failed!")
        raise HTTPException(detail="Invalid Refresh Token", status_code=400)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid Refresh Token")

    # Reject access tokens (or any non-refresh token) on the refresh endpoint.
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid Refresh Token")

    email = payload.get("sub")
    if not isinstance(email, str):
        raise HTTPException(status_code=401, detail="Invalid Refresh Token")

    user = await get_user(email, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Refresh Token"
        )

    # Reject tokens issued before the user's last global logout.
    version = await redis_manager.get_int(token_version_key(email))
    if payload.get("ver", 0) != version:
        raise HTTPException(status_code=401, detail="Invalid Refresh Token")

    # Rotate: invalidate the presented refresh token and issue a fresh pair so a
    # leaked refresh token has a single, one-time use.
    await blacklist_token(token_data.refresh_token)
    new_access_token = create_access_token(
        data={"sub": email, "ver": version}, expires_delta=ACCESS_TOKEN_LIFESPAN
    )
    new_refresh_token = create_refresh_token(
        data={"sub": email, "ver": version}, expires_delta=REFRESH_TOKEN_LIFESPAN
    )
    return auth_schema.Token(
        token_type="Bearer",
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        access_expires_at=datetime.now(UTC) + ACCESS_TOKEN_LIFESPAN,
        refresh_expires_at=datetime.now(UTC) + REFRESH_TOKEN_LIFESPAN,
    )


async def logout(
    access_token: str, refresh_token: str | None = None, email: str | None = None
):
    # Blacklist the access token, and the refresh token too when the client
    # supplies it - otherwise the refresh token would outlive the logout and
    # could still mint new access tokens.
    await blacklist_token(access_token)
    if refresh_token:
        await blacklist_token(refresh_token)
    # Bump the user's token version so EVERY token issued before now (across all
    # devices) is invalidated, not just the pair presented here.
    if email:
        await invalidate_all_sessions(email)
    return {"detail": "User Logged Out Successfully"}
