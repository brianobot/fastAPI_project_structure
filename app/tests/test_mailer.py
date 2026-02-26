from unittest.mock import AsyncMock, patch

from faker import Faker
from fastapi_mail.errors import ConnectionErrors

from app.mailer import send_mail

faker = Faker()


async def test_send_mail():
    result = await send_mail(
        subject=faker.name(),
        receipients=["brianobot9@gmail.com"],
        payload={},
        template="auth/welcome.html",
    )
    assert result is True


async def test_send_mail_success():
    # Setup test data
    payload = {"name": "John Doe"}
    subject = "Welcome Test"
    recipients = ["test@example.com"]
    template = "welcome.html"

    # Mock FastMail.send_message
    with patch("app.mailer.FastMail.send_message", new_callable=AsyncMock) as mock_send:
        result = await send_mail(subject, recipients, payload, template)

        # Assertions
        assert result is True
        mock_send.assert_called_once()
        # Verify it was called with the correct template
        assert mock_send.call_args.kwargs["template_name"] == template


async def test_send_mail_connection_error():
    payload = {"name": "John Doe"}

    # Mock FastMail.send_message to raise ConnectionErrors
    with patch(
        "app.mailer.FastMail.send_message", side_effect=ConnectionErrors("SMTP Timeout")
    ):
        result = await send_mail(
            subject="Test Error",
            receipients=["fail@example.com"],
            payload=payload,
            template="error.html",
        )

        # Assertions
        assert result is False
