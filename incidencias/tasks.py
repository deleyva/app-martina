# ruff: noqa: ERA001, E501
"""
Huey periodic tasks for email-to-incidencia processing.

Fetches emails from the configured IMAP mailbox, processes them with Gemini AI,
and creates Incidencia objects automatically.
"""

import imaplib
import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, lock_task

from incidencias.services.email_parser import EmailIncidenciaParser

logger = logging.getLogger(__name__)

# Madrid timezone for business hour checks
MADRID_TZ = ZoneInfo("Europe/Madrid")

# Cache the last fetch timestamp (Huey worker-level)
_last_fetch_timestamp = None


def _is_business_hours() -> bool:
    """Check if current time is within business hours (L-V 8:00-14:30 Europe/Madrid)."""
    now_madrid = timezone.now().astimezone(MADRID_TZ)
    weekday = now_madrid.weekday()  # 0=Monday, 6=Sunday
    hour = now_madrid.hour
    minute = now_madrid.minute

    # Monday to Friday
    if weekday > 4:
        return False

    # 8:00 to 14:30
    if hour < 8 or hour > 14:
        return False
    if hour == 14 and minute > 30:
        return False

    return True


def _should_fetch_now() -> bool:
    """
    Determine if we should fetch emails right now.

    During business hours (L-V 8:00-14:30): always fetch (every 5 min).
    Outside business hours: only fetch if ≥60 min since last fetch.
    """
    global _last_fetch_timestamp  # noqa: PLW0603

    if _is_business_hours():
        return True

    # Outside business hours — check if 60 min have passed
    if _last_fetch_timestamp is None:
        return True

    elapsed = timezone.now() - _last_fetch_timestamp
    return elapsed >= timedelta(minutes=60)


def _move_to_processed_gmail(message):
    """
    Move processed email in Gmail: remove 'INBOX' label, add 'Procesados' label.

    Uses IMAP STORE commands with Gmail X-GM-LABELS extension.
    """
    if not all([
        settings.MAILBOX_IMAP_HOST,
        settings.MAILBOX_IMAP_USER,
        settings.MAILBOX_IMAP_PASSWORD,
    ]):
        return

    try:
        # Get the message_id to find it on the server
        message_id = message.message_id
        if not message_id:
            return

        mail = imaplib.IMAP4_SSL(
            settings.MAILBOX_IMAP_HOST,
            settings.MAILBOX_IMAP_PORT,
        )
        mail.login(settings.MAILBOX_IMAP_USER, settings.MAILBOX_IMAP_PASSWORD)
        mail.select("INBOX")

        # Search for the message by Message-ID header
        status, data = mail.search(None, f'HEADER Message-ID "{message_id}"')
        if status == "OK" and data[0]:
            uid = data[0].split()[0]
            # Add "Procesados" label (Gmail will create it if it doesn't exist)
            mail.store(uid, "+X-GM-LABELS", "Procesados")
            # Remove from Inbox
            mail.store(uid, "-X-GM-LABELS", "\\Inbox")

        mail.logout()
    except Exception:
        logger.exception("Error moving email to 'Procesados' in Gmail: %s", message_id)


def _extract_message_body(message) -> str:
    """Extract the text body from a django-mailbox Message."""
    # django-mailbox stores the body as text
    body = message.text or ""

    # If HTML body is available and text body is empty, use HTML
    if not body.strip() and hasattr(message, "html") and message.html:
        # Basic HTML stripping (Gemini can handle some HTML too)
        import re
        body = re.sub(r"<[^>]+>", " ", message.html)
        body = re.sub(r"\s+", " ", body).strip()

    return body


def _process_single_email(message, parser: EmailIncidenciaParser):
    """Process a single email message and create an Incidencia if new."""
    from incidencias.models import (
        Adjunto,
        Etiqueta,
        Incidencia,
        ProcessedEmail,
        Ubicacion,
    )

    message_id = message.message_id or ""

    # Deduplication check
    if ProcessedEmail.objects.filter(message_id=message_id).exists():
        logger.info("Skipping duplicate email: %s", message_id)
        return

    subject = message.subject or ""
    sender = message.from_address[0] if message.from_address else ""
    body = _extract_message_body(message)

    logger.info("Processing email: '%s' from %s", subject[:60], sender)

    # Parse with Gemini (or fallback)
    parsed = parser.parse_email(
        subject=subject,
        body=body,
        sender=sender,
    )

    # Resolve ubicacion
    ubicacion = None
    if parsed.get("ubicacion_nombre"):
        ubicacion = Ubicacion.objects.filter(
            nombre__iexact=parsed["ubicacion_nombre"]
        ).first()

    # Create the Incidencia
    incidencia = Incidencia.objects.create(
        titulo=parsed["titulo"][:200],
        descripcion=parsed["descripcion"],
        reportero_nombre=parsed["reportero_nombre"][:100],
        urgencia=parsed["urgencia"],
        ubicacion=ubicacion,
        es_privada=parsed.get("es_privada", True),
    )

    # Handle existing etiquetas
    for etiqueta_nombre in parsed.get("etiquetas", []):
        etiqueta = Etiqueta.objects.filter(nombre__iexact=etiqueta_nombre).first()
        if etiqueta:
            incidencia.etiquetas.add(etiqueta)

    # Handle new etiquetas
    for etiqueta_nombre in parsed.get("etiquetas_nuevas", []):
        etiqueta, _ = Etiqueta.objects.get_or_create(
            nombre=etiqueta_nombre,
        )
        incidencia.etiquetas.add(etiqueta)

    # Process attachments
    if hasattr(message, "attachments") and message.attachments:
        for attachment in message.attachments.all():
            try:
                filename = attachment.headers.get("Content-Disposition", "attachment")
                # Extract filename from Content-Disposition if available
                import re
                fname_match = re.search(r'filename="?([^";\n]+)"?', filename)
                fname = fname_match.group(1) if fname_match else f"adjunto_{attachment.pk}"

                # Check extension
                ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
                allowed = {e.lower() for e in Adjunto.ALLOWED_EXTENSIONS}
                if ext in allowed:
                    content = ContentFile(attachment.document.read(), name=fname)
                    if content.size <= Adjunto.MAX_FILE_SIZE:
                        Adjunto.objects.create(
                            incidencia=incidencia,
                            archivo=content,
                        )
                        logger.info("Attached file: %s", fname)
                    else:
                        logger.warning("Attachment too large: %s (%d bytes)", fname, content.size)
                else:
                    logger.info("Skipping attachment with unsupported extension: %s", fname)
            except Exception:
                logger.exception("Error processing attachment")

    # Record as processed
    ProcessedEmail.objects.create(
        message_id=message_id,
        incidencia=incidencia,
        raw_subject=subject[:512],
        raw_sender=sender[:254] if sender else "",
    )

    # Move email in Gmail
    _move_to_processed_gmail(message)

    logger.info(
        "Created incidencia #%d: '%s' from email %s",
        incidencia.pk,
        incidencia.titulo,
        message_id,
    )


@db_periodic_task(crontab(minute="*/5"))
@lock_task("fetch-and-process-emails")
def fetch_and_process_emails():
    """
    Periodic task: fetch and process emails every 5 minutes.

    Internally applies adaptive scheduling:
    - Business hours (L-V 8:00-14:30 Madrid): runs every 5 min
    - Outside business hours: runs only if ≥60 min since last fetch
    """
    global _last_fetch_timestamp  # noqa: PLW0603

    if not _should_fetch_now():
        logger.debug("Skipping email fetch (outside business hours, not enough time elapsed)")
        return

    # Check IMAP configuration
    if not settings.MAILBOX_IMAP_USER or not settings.MAILBOX_IMAP_PASSWORD:
        logger.warning("MAILBOX_IMAP_USER or MAILBOX_IMAP_PASSWORD not configured, skipping.")
        return

    try:
        from django_mailbox.models import Mailbox

        import urllib.parse

        encoded_user = urllib.parse.quote(settings.MAILBOX_IMAP_USER, safe="")
        encoded_password = urllib.parse.quote(settings.MAILBOX_IMAP_PASSWORD, safe="")

        # Get or create the mailbox
        mailbox, created = Mailbox.objects.update_or_create(
            name="cofotap-incidencias",
            defaults={
                "uri": (
                    f"imaps://{encoded_user}:{encoded_password}"
                    f"@{settings.MAILBOX_IMAP_HOST}:{settings.MAILBOX_IMAP_PORT}"
                ),
            },
        )
        if created:
            logger.info("Created mailbox: %s", mailbox.name)

        # Fetch new messages
        new_messages = mailbox.get_new_mail()
        _last_fetch_timestamp = timezone.now()

        if not new_messages:
            logger.debug("No new emails found")
            return

        logger.info("Fetched %d new email(s)", len(new_messages))

        # Initialize parser once
        try:
            parser = EmailIncidenciaParser()
        except ValueError:
            logger.error("Cannot initialize EmailIncidenciaParser — GEMINI_API_KEY not set")
            return

        # Process each message
        for message in new_messages:
            try:
                _process_single_email(message, parser)
            except Exception:
                logger.exception(
                    "Error processing email '%s'",
                    message.subject[:60] if message.subject else "no-subject",
                )

    except Exception:
        logger.exception("Error in fetch_and_process_emails task")
