from typing import List
from pathlib import Path

from fastapi import UploadFile
from fastapi_mail.errors import ConnectionErrors
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType

from app.logger import logger
from app.settings import Settings


settings = Settings()

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
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
        recipients=receipients,
        subtype=MessageType.html,
        attachments=attachments,
        template_body=payload,
    )

    fm = FastMail(conf)

    try:
        await fm.send_message(message, template_name=template)
        logger.info("mail sent")

    except ConnectionErrors as e:
        logger.error(f"mail failed to send for {payload}, with subject: {subject}")
