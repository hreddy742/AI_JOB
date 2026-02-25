"""Email delivery service for authentication workflows."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.message import EmailMessage

import aiosmtplib

from core.config import settings

logger = logging.getLogger(__name__)


def _mask_email(email: str) -> str:
    prefix = email[:3] if len(email) >= 3 else email
    return f"{prefix}***"


def _base_template(content: str) -> str:
    """Wrap content in reusable responsive HTML shell."""

    return f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Apex Apply</title>
</head>
<body style=\"margin:0;padding:0;background:#f3f5f9;font-family:Arial,sans-serif;\">
  <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"padding:24px 12px;\">
    <tr><td align=\"center\">
      <table width=\"600\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;\">
        <tr>
          <td style=\"padding:20px;background:linear-gradient(120deg,#0f172a,#1d4ed8);color:#fff;border-radius:12px 12px 0 0;\">
            <h1 style=\"margin:0;font-size:22px;\">Apex Apply</h1>
            <p style=\"margin:8px 0 0 0;font-size:13px;opacity:.9;\">Secure job search automation</p>
          </td>
        </tr>
        <tr>
          <td style=\"background:#fff;padding:24px;border:1px solid #e5e7eb;border-top:0;\">{content}</td>
        </tr>
        <tr>
          <td style=\"background:#f8fafc;padding:16px;border:1px solid #e5e7eb;border-top:0;border-radius:0 0 12px 12px;color:#64748b;font-size:12px;\">
            This email was sent by Apex Apply. If you did not expect this message, you can safely ignore it.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


async def _send_html_email(to_email: str, subject: str, html: str) -> bool:
    if not settings.SMTP_FROM_EMAIL:
        logger.error("email_send_failed_missing_from", extra={"to": _mask_email(to_email), "subject": subject})
        return False

    msg = EmailMessage()
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content("Please use an HTML-capable email client to view this message.")
    msg.add_alternative(html, subtype="html")
    try:
        username = settings.SMTP_USERNAME or None
        password = settings.SMTP_PASSWORD or None
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            start_tls=settings.SMTP_STARTTLS,
            use_tls=settings.SMTP_USE_TLS,
            username=username,
            password=password,
            timeout=20,
        )
        logger.info("email_sent", extra={"to": _mask_email(to_email), "subject": subject})
        return True
    except Exception:
        logger.exception("email_send_failed", extra={"to": _mask_email(to_email), "subject": subject})
        return False


async def send_verification_email(to_email: str, full_name: str, token: str) -> bool:
    first_name = full_name.split()[0] if full_name else "there"
    url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}"
    content = f"""
<p style=\"margin:0 0 12px;\">Hi {first_name},</p>
<p>Welcome to Apex Apply!</p>
<p><a href=\"{url}\" style=\"display:inline-block;background:#2563eb;color:#fff;padding:12px 18px;text-decoration:none;border-radius:8px;font-weight:700;\">Verify Email Address</a></p>
<p style=\"padding:12px;background:#fff7ed;border:1px solid #fdba74;border-radius:8px;\"><strong>This link expires in 24 hours.</strong></p>
<p>If the button does not work, use this URL:<br /><a href=\"{url}\">{url}</a></p>
<p>If you did not create an account, you can ignore this email.</p>
"""
    return await _send_html_email(to_email, "Verify your Apex Apply email address", _base_template(content))


async def send_password_reset_email(to_email: str, full_name: str, token: str, ip_address: str) -> bool:
    first_name = full_name.split()[0] if full_name else "there"
    url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
    content = f"""
<p>Hi {first_name},</p>
<p>We received a request to reset your password.</p>
<p><a href=\"{url}\" style=\"display:inline-block;background:#2563eb;color:#fff;padding:12px 18px;text-decoration:none;border-radius:8px;font-weight:700;\">Reset My Password</a></p>
<p style=\"padding:12px;background:#fff7ed;border:1px solid #fdba74;border-radius:8px;\"><strong>Expires in 1 hour. Can only be used once.</strong></p>
<p>Requesting IP address: <strong>{ip_address}</strong></p>
<p style=\"padding:12px;background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;color:#991b1b;\">If you did not request this, secure your account immediately.</p>
"""
    return await _send_html_email(to_email, "Reset your Apex Apply password", _base_template(content))


async def send_password_changed_email(to_email: str, full_name: str) -> bool:
    first_name = full_name.split()[0] if full_name else "there"
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    reset_url = f"{settings.FRONTEND_URL}/auth/forgot-password"
    content = f"""
<p>Hi {first_name},</p>
<p>Your Apex Apply password was changed on <strong>{timestamp}</strong>.</p>
<p>If this was not you, reset your password immediately.</p>
<p><a href=\"{reset_url}\">Request another password reset</a></p>
"""
    return await _send_html_email(to_email, "Your password was changed - Apex Apply", _base_template(content))


async def send_welcome_email(to_email: str, full_name: str) -> bool:
    first_name = full_name.split()[0] if full_name else "there"
    dashboard = f"{settings.FRONTEND_URL}/dashboard"
    content = f"""
<p>Hi {first_name},</p>
<p>Your email is verified. Welcome to Apex Apply.</p>
<ul>
  <li>Discover jobs with sponsorship scoring.</li>
  <li>Track applications end to end.</li>
  <li>Use AI copilot for interview prep.</li>
  <li>Find referral opportunities safely.</li>
</ul>
<p><a href=\"{dashboard}\" style=\"display:inline-block;background:#2563eb;color:#fff;padding:12px 18px;text-decoration:none;border-radius:8px;font-weight:700;\">Go to Dashboard</a></p>
"""
    return await _send_html_email(to_email, f"Welcome to Apex Apply, {first_name}!", _base_template(content))
