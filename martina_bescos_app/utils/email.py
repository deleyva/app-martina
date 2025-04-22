"""
Email utilities for Martina Bescós App.
This module provides functions to send emails using different sender accounts.
"""
from typing import List, Optional

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string


def send_email(
    subject: str,
    body: str,
    to: List[str],
    from_email: Optional[str] = None,
    use_secondary: bool = False,
    html_content: Optional[str] = None,
    attachments: Optional[List[tuple]] = None,
):
    """
    Send an email using the configured email backend.
    
    Args:
        subject: The email subject
        body: The email body (plain text)
        to: List of recipient email addresses
        from_email: Optional custom from_email (overrides settings)
        use_secondary: Whether to use the secondary email account
        html_content: Optional HTML content for the email
        attachments: Optional list of attachments as (filename, content, mimetype) tuples
    
    Returns:
        The number of successfully delivered messages
    """
    if use_secondary and hasattr(settings, 'SECONDARY_EMAIL') and settings.SECONDARY_EMAIL:
        # Save original settings
        original_host_user = settings.EMAIL_HOST_USER
        original_host_password = settings.EMAIL_HOST_PASSWORD
        
        # Use secondary email credentials
        settings.EMAIL_HOST_USER = settings.SECONDARY_EMAIL
        settings.EMAIL_HOST_PASSWORD = settings.SECONDARY_EMAIL_PASSWORD
    
    # Set default from_email if not provided
    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    # Create email message
    if html_content:
        # Create multipart email with HTML and text
        email = EmailMultiAlternatives(subject, body, from_email, to)
        email.attach_alternative(html_content, "text/html")
    else:
        # Create plain text email
        email = EmailMessage(subject, body, from_email, to)
    
    # Add attachments if any
    if attachments:
        for attachment in attachments:
            email.attach(*attachment)
    
    # Send email
    result = email.send()
    
    # Restore original settings if we used secondary account
    if use_secondary and hasattr(settings, 'SECONDARY_EMAIL') and settings.SECONDARY_EMAIL:
        settings.EMAIL_HOST_USER = original_host_user
        settings.EMAIL_HOST_PASSWORD = original_host_password
    
    return result


def send_template_email(
    template_prefix: str,
    context: dict,
    subject: str,
    to: List[str],
    from_email: Optional[str] = None,
    use_secondary: bool = False,
    attachments: Optional[List[tuple]] = None,
):
    """
    Send an email using a template.
    
    Args:
        template_prefix: Prefix for the template (will use {prefix}.txt and {prefix}.html)
        context: Context data for template rendering
        subject: The email subject
        to: List of recipient email addresses
        from_email: Optional custom from_email (overrides settings)
        use_secondary: Whether to use the secondary email account
        attachments: Optional list of attachments as (filename, content, mimetype) tuples
    
    Returns:
        The number of successfully delivered messages
    """
    # Render email body from templates
    text_body = render_to_string(f"{template_prefix}.txt", context)
    html_body = render_to_string(f"{template_prefix}.html", context)
    
    # Send email
    return send_email(
        subject=subject,
        body=text_body,
        to=to,
        from_email=from_email,
        use_secondary=use_secondary,
        html_content=html_body,
        attachments=attachments,
    )
