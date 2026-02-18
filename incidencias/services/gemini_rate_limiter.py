# ruff: noqa: ERA001, E501
"""
Gemini API Rate Limiter — project-wide.

Tracks and limits Gemini API calls across the entire Django project.
Sends email alerts when usage exceeds configured thresholds.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


class GeminiRateLimiter:
    """
    Centralized rate limiter for Gemini API calls.

    Tracks usage via the GeminiAPIUsage model and enforces hourly limits.
    When limits are exceeded, sends an alert email to the configured address.
    """

    def __init__(self):
        self.hourly_limit = getattr(settings, "GEMINI_RATE_LIMIT_HOURLY", 2)
        self.alert_email = getattr(settings, "GEMINI_ALERT_EMAIL", "")

    def can_call(self) -> bool:
        """Check if a Gemini API call is allowed within the rate limit."""
        from incidencias.models import GeminiAPIUsage

        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_calls = GeminiAPIUsage.objects.filter(
            timestamp__gte=one_hour_ago,
            success=True,
        ).count()

        if recent_calls >= self.hourly_limit:
            logger.warning(
                "Gemini API rate limit reached: %d/%d calls in the last hour",
                recent_calls,
                self.hourly_limit,
            )
            self._send_alert_if_needed(recent_calls)
            return False
        return True

    def register_call(
        self,
        caller: str,
        success: bool = True,
        tokens_used: int = 0,
        error_message: str = "",
    ):
        """Register a Gemini API call for tracking."""
        from incidencias.models import GeminiAPIUsage

        GeminiAPIUsage.objects.create(
            caller=caller,
            success=success,
            tokens_used=tokens_used,
            error_message=error_message,
        )

    def get_recent_usage(self, hours: int = 1) -> int:
        """Get the number of successful calls in the last N hours."""
        from incidencias.models import GeminiAPIUsage

        since = timezone.now() - timedelta(hours=hours)
        return GeminiAPIUsage.objects.filter(
            timestamp__gte=since,
            success=True,
        ).count()

    def _send_alert_if_needed(self, current_count: int):
        """Send email alert if usage exceeds limit. Only sends once per hour."""
        if not self.alert_email:
            logger.warning("GEMINI_ALERT_EMAIL not configured, skipping alert.")
            return

        from incidencias.models import GeminiAPIUsage

        one_hour_ago = timezone.now() - timedelta(hours=1)
        # Check if we already sent an alert in the last hour (avoid spam)
        recent_alerts = GeminiAPIUsage.objects.filter(
            timestamp__gte=one_hour_ago,
            caller="rate_limiter_alert",
        ).exists()

        if recent_alerts:
            logger.info("Alert already sent in the last hour, skipping.")
            return

        try:
            send_mail(
                subject="⚠️ Gemini API: Límite de uso excedido",
                message=(
                    f"Se han realizado {current_count} llamadas a Gemini API "
                    f"en la última hora (límite configurado: {self.hourly_limit}/hora).\n\n"
                    f"Revisa el panel de administración para más detalles.\n"
                    f"Configuración: GEMINI_RATE_LIMIT_HOURLY={self.hourly_limit}"
                ),
                from_email=None,  # Uses DEFAULT_FROM_EMAIL
                recipient_list=[self.alert_email],
                fail_silently=True,
            )
            # Register the alert as a special call to avoid re-sending
            GeminiAPIUsage.objects.create(
                caller="rate_limiter_alert",
                success=True,
                tokens_used=0,
                error_message=f"Alert sent: {current_count} calls/hour",
            )
            logger.info("Rate limit alert sent to %s", self.alert_email)
        except Exception:
            logger.exception("Failed to send rate limit alert email")
