# ruff: noqa: ERA001, E501
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Ubicacion(models.Model):
    """Ubicación física del instituto (aula + grupo + planta)."""

    class Planta(models.TextChoices):
        PLANTA_BAJA = "PB", _("Planta Baja")
        PRIMERA = "P1", _("Primera Planta")
        SEGUNDA = "P2", _("Segunda Planta")

    nombre = models.CharField(_("Aula"), max_length=100)
    grupo = models.CharField(_("Grupo"), max_length=100, blank=True, default="")
    planta = models.CharField(_("Planta"), max_length=2, choices=Planta.choices)

    class Meta:
        verbose_name = _("Ubicación")
        verbose_name_plural = _("Ubicaciones")
        ordering = ["planta", "nombre"]
        unique_together = ("nombre", "planta")

    def __str__(self):
        parts = [self.nombre]
        if self.grupo:
            parts.append(f"— {self.grupo}")
        parts.append(f"({self.get_planta_display()})")
        return " ".join(parts)


class Etiqueta(models.Model):
    """Etiqueta para clasificar incidencias (ej: internet, proyectar, ratón)."""

    nombre = models.CharField(_("Nombre"), max_length=100)
    slug = models.SlugField(_("Slug"), max_length=100, unique=True)

    class Meta:
        verbose_name = _("Etiqueta")
        verbose_name_plural = _("Etiquetas")
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Incidencia(models.Model):
    """Incidencia informática reportada por un profesor."""

    class Urgencia(models.TextChoices):
        BAJA = "baja", _("Baja")
        MEDIA = "media", _("Media")
        ALTA = "alta", _("Alta")
        CRITICA = "critica", _("Crítica")

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", _("Pendiente")
        EN_PROGRESO = "en_progreso", _("En progreso")
        RESUELTA = "resuelta", _("Resuelta")

    titulo = models.CharField(_("Título"), max_length=255)
    descripcion = models.TextField(_("Descripción"), blank=True, default="")
    urgencia = models.CharField(
        _("Urgencia"),
        max_length=10,
        choices=Urgencia.choices,
        default=Urgencia.MEDIA,
    )
    estado = models.CharField(
        _("Estado"),
        max_length=12,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    es_privada = models.BooleanField(_("Es privada"), default=False)
    reportero_nombre = models.CharField(
        _("Reportado por"),
        max_length=150,
        help_text=_("Usuario de Google Workspace (sin @iesmartinabescos)"),
    )
    ubicacion = models.ForeignKey(
        Ubicacion,
        verbose_name=_("Ubicación"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidencias",
    )
    etiquetas = models.ManyToManyField(
        Etiqueta,
        verbose_name=_("Etiquetas"),
        blank=True,
        related_name="incidencias",
    )
    asignado_a = models.ForeignKey(
        "Tecnico",
        verbose_name=_("Asignado a"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidencias_asignadas",
    )
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Última actualización"), auto_now=True)

    class Meta:
        verbose_name = _("Incidencia")
        verbose_name_plural = _("Incidencias")
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_urgencia_display()}] {self.titulo}"



class Comentario(models.Model):
    """Comentario en una incidencia."""

    incidencia = models.ForeignKey(
        Incidencia,
        verbose_name=_("Incidencia"),
        on_delete=models.CASCADE,
        related_name="comentarios",
    )
    autor_nombre = models.CharField(
        _("Autor"),
        max_length=150,
        help_text=_("Usuario de Google Workspace (sin @iesmartinabescos)"),
    )
    texto = models.TextField(_("Comentario"))
    created_at = models.DateTimeField(_("Fecha"), auto_now_add=True)

    class Meta:
        verbose_name = _("Comentario")
        verbose_name_plural = _("Comentarios")
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.autor_nombre}: {self.texto[:50]}"


def adjunto_upload_path(instance, filename):
    return f"incidencias/{instance.incidencia_id}/{filename}"


class Adjunto(models.Model):
    """Archivo adjunto (foto o vídeo) de una incidencia."""

    ALLOWED_EXTENSIONS = [
        "jpg", "jpeg", "png", "gif", "webp",  # Imágenes
        "mp4", "mov", "avi", "webm",  # Vídeos
        "pdf",  # Documentos
    ]
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    incidencia = models.ForeignKey(
        Incidencia,
        verbose_name=_("Incidencia"),
        on_delete=models.CASCADE,
        related_name="adjuntos",
    )
    archivo = models.FileField(
        _("Archivo"),
        upload_to=adjunto_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=[
                "jpg", "jpeg", "png", "gif", "webp",
                "mp4", "mov", "avi", "webm",
                "pdf",
            ]),
        ],
    )
    created_at = models.DateTimeField(_("Fecha"), auto_now_add=True)

    class Meta:
        verbose_name = _("Adjunto")
        verbose_name_plural = _("Adjuntos")

    def __str__(self):
        return f"Adjunto para {self.incidencia.titulo}"

    @property
    def is_image(self):
        ext = self.archivo.name.rsplit(".", 1)[-1].lower()
        return ext in {"jpg", "jpeg", "png", "gif", "webp"}

    @property
    def is_video(self):
        ext = self.archivo.name.rsplit(".", 1)[-1].lower()
        return ext in {"mp4", "mov", "avi", "webm"}

    @property
    def is_pdf(self):
        ext = self.archivo.name.rsplit(".", 1)[-1].lower()
        return ext == "pdf"


class Tecnico(models.Model):
    """Técnico/encargado que gestiona incidencias."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Usuario"),
        on_delete=models.CASCADE,
        related_name="perfil_tecnico",
    )
    nombre_display = models.CharField(
        _("Nombre a mostrar"),
        max_length=200,
        blank=True,
        default="",
    )
    activo = models.BooleanField(_("Activo"), default=True)

    class Meta:
        verbose_name = _("Técnico")
        verbose_name_plural = _("Técnicos")

    def __str__(self):
        if self.nombre_display:
            return self.nombre_display
        return self.user.email or str(self.user)


class HistorialAsignacion(models.Model):
    """Registro de cada cambio de asignación de una incidencia."""

    incidencia = models.ForeignKey(
        Incidencia,
        verbose_name=_("Incidencia"),
        on_delete=models.CASCADE,
        related_name="historial_asignaciones",
    )
    asignado_por = models.ForeignKey(
        Tecnico,
        verbose_name=_("Asignado por"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asignaciones_realizadas",
    )
    asignado_a = models.ForeignKey(
        Tecnico,
        verbose_name=_("Asignado a"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asignaciones_recibidas",
    )
    nota = models.CharField(_("Nota"), max_length=255, blank=True, default="")
    created_at = models.DateTimeField(_("Fecha"), auto_now_add=True)

    class Meta:
        verbose_name = _("Historial de asignación")
        verbose_name_plural = _("Historial de asignaciones")
        ordering = ["-created_at"]

    def __str__(self):
        asignante = self.asignado_por or "Sistema"
        asignado = self.asignado_a or "Nadie"
        return f"{asignante} → {asignado} ({self.incidencia.titulo})"


class GeminiAPIUsage(models.Model):
    """Registro de uso de Gemini API para rate limiting a nivel de proyecto."""

    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True)
    caller = models.CharField(
        _("Caller"),
        max_length=100,
        help_text=_("Módulo que realizó la llamada (ej: email_parser, ai_metadata)"),
    )
    tokens_used = models.IntegerField(_("Tokens usados"), default=0)
    success = models.BooleanField(_("Éxito"), default=True)
    error_message = models.TextField(_("Mensaje de error"), blank=True, default="")

    class Meta:
        verbose_name = _("Uso de Gemini API")
        verbose_name_plural = _("Usos de Gemini API")
        ordering = ["-timestamp"]

    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.caller} @ {self.timestamp:%Y-%m-%d %H:%M}"


class ProcessedEmail(models.Model):
    """Registro de emails procesados para deduplicación."""

    message_id = models.CharField(
        _("Message-ID"),
        max_length=512,
        unique=True,
        db_index=True,
        help_text=_("Cabecera Message-ID del email original"),
    )
    incidencia = models.ForeignKey(
        Incidencia,
        verbose_name=_("Incidencia"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emails_origen",
    )
    processed_at = models.DateTimeField(_("Fecha de procesado"), auto_now_add=True)
    raw_subject = models.CharField(_("Asunto original"), max_length=512, blank=True, default="")
    raw_sender = models.EmailField(_("Remitente original"), blank=True, default="")
    skipped = models.BooleanField(
        _("Omitido"),
        default=False,
        help_text=_("True si fue omitido (duplicado, rate limit, etc.)"),
    )
    skip_reason = models.CharField(_("Razón de omisión"), max_length=200, blank=True, default="")

    class Meta:
        verbose_name = _("Email procesado")
        verbose_name_plural = _("Emails procesados")
        ordering = ["-processed_at"]

    def __str__(self):
        return f"{self.raw_subject[:60]} ({self.raw_sender})"
