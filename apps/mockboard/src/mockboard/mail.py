"""Sends the login OTP by email (Mailpit locally and on the demo server)."""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from fw_core.settings import BoardSettings


async def send_otp(cfg: BoardSettings, to: str, code: str, board_name: str) -> None:
    msg = EmailMessage()
    msg["From"] = cfg.mail_from
    msg["To"] = to
    msg["Subject"] = f"{board_name} sign-in code"
    msg.set_content(f"Your {board_name} sign-in code is {code}. It expires in {cfg.otp_ttl_s // 60} minutes.\n")
    await aiosmtplib.send(msg, hostname=cfg.smtp_host, port=cfg.smtp_port, timeout=10, start_tls=False)
