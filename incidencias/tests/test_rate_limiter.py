# ruff: noqa: E501
"""Tests for GeminiRateLimiter service."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from incidencias.models import GeminiAPIUsage
from incidencias.services.gemini_rate_limiter import GeminiRateLimiter


@pytest.fixture
def rate_limiter(settings):
    """Create a rate limiter with test settings."""
    settings.GEMINI_RATE_LIMIT_HOURLY = 3
    settings.GEMINI_ALERT_EMAIL = "alert@test.com"
    return GeminiRateLimiter()


@pytest.mark.django_db
class TestGeminiRateLimiterCanCall:
    """Test rate limit checking."""

    def test_can_call_when_under_limit(self, rate_limiter):
        """Should allow calls when under the hourly limit."""
        assert rate_limiter.can_call() is True

    def test_cannot_call_when_at_limit(self, rate_limiter):
        """Should block calls when at the hourly limit."""
        # Create 3 usage records in the last hour
        for _ in range(3):
            GeminiAPIUsage.objects.create(caller="test", success=True)

        assert rate_limiter.can_call() is False

    def test_old_calls_dont_count(self, rate_limiter):
        """Calls older than 1 hour should not count toward the limit."""
        old_time = timezone.now() - timedelta(hours=2)
        for _ in range(5):
            usage = GeminiAPIUsage.objects.create(caller="test", success=True)
            GeminiAPIUsage.objects.filter(pk=usage.pk).update(timestamp=old_time)

        assert rate_limiter.can_call() is True

    def test_failed_calls_dont_count(self, rate_limiter):
        """Failed calls should not count toward the limit."""
        for _ in range(5):
            GeminiAPIUsage.objects.create(caller="test", success=False)

        assert rate_limiter.can_call() is True


@pytest.mark.django_db
class TestGeminiRateLimiterRegister:
    """Test call registration."""

    def test_register_successful_call(self, rate_limiter):
        """Should create a usage record for a successful call."""
        rate_limiter.register_call(caller="email_parser", success=True, tokens_used=100)

        usage = GeminiAPIUsage.objects.latest("timestamp")
        assert usage.caller == "email_parser"
        assert usage.success is True
        assert usage.tokens_used == 100

    def test_register_failed_call(self, rate_limiter):
        """Should create a usage record for a failed call."""
        rate_limiter.register_call(
            caller="email_parser",
            success=False,
            error_message="Connection timeout",
        )

        usage = GeminiAPIUsage.objects.latest("timestamp")
        assert usage.success is False
        assert usage.error_message == "Connection timeout"


@pytest.mark.django_db
class TestGeminiRateLimiterAlert:
    """Test email alert functionality."""

    @patch("incidencias.services.gemini_rate_limiter.send_mail")
    def test_sends_alert_when_limit_exceeded(self, mock_send_mail, rate_limiter):
        """Should send an email alert when the rate limit is exceeded."""
        # Exceed the limit
        for _ in range(3):
            GeminiAPIUsage.objects.create(caller="test", success=True)

        rate_limiter.can_call()  # This should trigger the alert

        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        assert "Límite de uso excedido" in call_args[1]["subject"] or "Límite de uso excedido" in call_args[0][0]
        assert "alert@test.com" in (call_args[1].get("recipient_list") or call_args[0][3])

    @patch("incidencias.services.gemini_rate_limiter.send_mail")
    def test_does_not_resend_alert_within_hour(self, mock_send_mail, rate_limiter):
        """Should not send duplicate alerts within the same hour."""
        for _ in range(3):
            GeminiAPIUsage.objects.create(caller="test", success=True)
        # Mark an alert as already sent
        GeminiAPIUsage.objects.create(caller="rate_limiter_alert", success=True)

        rate_limiter.can_call()

        mock_send_mail.assert_not_called()

    def test_no_alert_when_email_not_configured(self, settings):
        """Should not crash when GEMINI_ALERT_EMAIL is not set."""
        settings.GEMINI_ALERT_EMAIL = ""
        settings.GEMINI_RATE_LIMIT_HOURLY = 1
        limiter = GeminiRateLimiter()

        GeminiAPIUsage.objects.create(caller="test", success=True)

        # Should not raise, just log a warning
        assert limiter.can_call() is False


@pytest.mark.django_db
class TestGeminiRateLimiterUsage:
    """Test usage reporting."""

    def test_get_recent_usage(self, rate_limiter):
        """Should return count of successful calls in the specified window."""
        GeminiAPIUsage.objects.create(caller="test", success=True)
        GeminiAPIUsage.objects.create(caller="test", success=True)
        GeminiAPIUsage.objects.create(caller="test", success=False)

        assert rate_limiter.get_recent_usage(hours=1) == 2
