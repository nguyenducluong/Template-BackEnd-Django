"""
SMTP/Email service for sending transactional and marketing emails.
Supports SMTP, SendGrid, Mailgun, SES providers.
"""
import logging
from typing import List, Optional

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending emails with provider abstraction.
    Supports HTML templates, attachments, and async sending via Celery.
    """

    @staticmethod
    def send_simple(
        subject: str,
        message: str,
        recipient_list: List[str],
        from_email: Optional[str] = None,
    ) -> int:
        """Send a simple text email."""
        return send_mail(
            subject=subject,
            message=message,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )

    @staticmethod
    def send_html(
        subject: str,
        html_content: str,
        recipient_list: List[str],
        from_email: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[List[str]] = None,
    ) -> int:
        """Send an HTML email."""
        email = EmailMultiAlternatives(
            subject=subject,
            body=html_content,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
            cc=cc or [],
            bcc=bcc or [],
            reply_to=reply_to or [],
        )
        email.attach_alternative(html_content, "text/html")
        return email.send(fail_silently=False)

    @staticmethod
    def send_templated(
        subject: str,
        template_name: str,
        context: dict,
        recipient_list: List[str],
        from_email: Optional[str] = None,
    ) -> int:
        """Send email using Django template."""
        html_content = render_to_string(template_name, context)
        return EmailService.send_html(subject, html_content, recipient_list, from_email)

    @staticmethod
    def send_with_attachment(
        subject: str,
        message: str,
        recipient_list: List[str],
        attachment_path: str,
        from_email: Optional[str] = None,
    ) -> int:
        """Send email with file attachment."""
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )
        email.attach_file(attachment_path)
        return email.send(fail_silently=False)