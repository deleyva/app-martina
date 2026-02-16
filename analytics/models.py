from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class UserSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_sessions'
    )
    session_key = models.CharField(max_length=40, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user} - {self.created_at}"

class PageVisit(models.Model):
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE, related_name='page_visits')
    url = models.URLField(max_length=500)
    title = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    duration = models.DurationField(null=True, blank=True, help_text=_("Duration of visit"))

    def __str__(self):
        return f"{self.url} at {self.timestamp}"

class Interaction(models.Model):
    visit = models.ForeignKey(PageVisit, on_delete=models.CASCADE, related_name='interactions')
    event_type = models.CharField(max_length=50, default='click')
    target_element = models.CharField(max_length=255, help_text=_("Tag name + ID/Class"))
    target_text = models.CharField(max_length=100, null=True, blank=True)
    x_coordinate = models.IntegerField(null=True, blank=True)
    y_coordinate = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} on {self.target_element}"
