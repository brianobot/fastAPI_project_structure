from pathlib import Path
from typing import List

from fastapi import UploadFile
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors

from app.logger import logger
from app.settings import Settings

settings = Settings()  # type: ignore

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,  # type: ignore
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,  # type: ignore
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=False,
    TEMPLATE_FOLDER=Path(__file__).parent / "templates/",
)


async def send_mail(
    subject: str,
    receipients: List[str],
    payload: dict,
    template: str,
    attachments: List[UploadFile] = [],
):
    message = MessageSchema(
        subject=subject,
        recipients=receipients,  # type: ignore
        subtype=MessageType.html,
        attachments=attachments,  # type: ignore
        template_body=payload,
    )

    fm = FastMail(conf)

    try:
        await fm.send_message(message, template_name=template)
        logger.info("mail sent")

    except ConnectionErrors as e:  # noqa
        logger.error(f"mail failed to send for {payload}, with subject: {subject}")
