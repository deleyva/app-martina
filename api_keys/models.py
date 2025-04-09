from django.db import models
import uuid
from django.utils import timezone

# Create your models here.

class APIKey(models.Model):
    """Modelo para gestionar claves de API de forma segura"""
    name = models.CharField(max_length=100, help_text="Nombre descriptivo para esta clave de API")
    key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(
        'users.User',  # Referencia al modelo de usuario del proyecto
        on_delete=models.CASCADE,
        related_name="api_keys"
    )
    
    class Meta:
        verbose_name = "Clave de API"
        verbose_name_plural = "Claves de API"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.name} ({self.user.email})"
    
    def save(self, *args, **kwargs):
        # Si es una nueva clave, generar un nuevo UUID
        if not self.pk:
            self.key = uuid.uuid4()
        super().save(*args, **kwargs)
    
    def mark_as_used(self):
        """Marca la clave como utilizada, actualizando el timestamp de último uso"""
        self.last_used = timezone.now()
        self.save(update_fields=['last_used'])
