"""SMTP email sending helper."""

import smtplib
from email.header import Header
from email.mime.text import MIMEText

from .config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME


def send_email(to: str, subject: str, content: str) -> None:
    if not SMTP_HOST:
        raise RuntimeError("SMTP_HOST 未配置，无法发送邮件")
    sender = SMTP_FROM or SMTP_USERNAME
    if not sender:
        raise RuntimeError("SMTP_FROM 或 SMTP_USERNAME 未配置")
    message = MIMEText(content, "plain", "utf-8")
    message["Subject"] = Header(subject, "utf-8")
    message["From"] = sender
    message["To"] = to
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()
        if SMTP_USERNAME:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(sender, [to], message.as_string())
