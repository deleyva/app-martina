# ruff: noqa: ERA001, E501
import secrets

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
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

    class Ambito(models.TextChoices):
        """De qué va la incidencia: decide quién la atiende, no solo qué es."""

        INFORMATICA = "informatica", _("Informática")
        MANTENIMIENTO = "mantenimiento", _("Mantenimiento y obra")
        GESTION = "gestion", _("Gestión interna")
        OTRO = "otro", _("Otro")

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
    ambito = models.CharField(
        _("Ámbito"),
        max_length=15,
        choices=Ambito.choices,
        default=Ambito.INFORMATICA,
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

    @property
    def aula_o_sin_aula(self) -> str:
        return self.ubicacion.nombre if self.ubicacion else "Sin aula"



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
    comentario = models.ForeignKey(
        "Comentario",
        verbose_name=_("Comentario"),
        on_delete=models.CASCADE,
        related_name="adjuntos",
        null=True,
        blank=True,
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


# =============================================================================
# Derivaciones a servicios externos
# =============================================================================


def nuevo_token() -> str:
    """Token de enlace público. Función con nombre a propósito: `default=` la
    evalúa por fila y la migración la serializa; una llamada directa daría el
    MISMO token a todas las filas y rompería `unique`."""
    return secrets.token_urlsafe(32)


class Servicio(models.Model):
    """Destino externo de una derivación: 4100, Redes, Vitalinux, CATEDU…

    Es la tabla «¿A quién va cada incidencia tecnológica?» de BookStack, en
    base de datos, para que el botón de ayuda y las derivaciones lean de un
    solo sitio. El token da la página pública del servicio.
    """

    slug = models.SlugField(_("Slug"), max_length=60, unique=True)
    nombre = models.CharField(_("Nombre"), max_length=120)
    que_va_aqui = models.TextField(_("Qué va aquí"), blank=True, default="")
    correos = models.CharField(
        _("Correos"), max_length=255, blank=True, default="",
        help_text=_("Separados por coma"),
    )
    telefono = models.CharField(_("Teléfono"), max_length=100, blank=True, default="")
    url_formulario = models.URLField(_("Formulario o web"), blank=True, default="")
    activo = models.BooleanField(_("Activo"), default=True)
    token = models.CharField(_("Token público"), max_length=64, unique=True, default=nuevo_token)
    orden = models.PositiveSmallIntegerField(_("Orden"), default=100)

    class Meta:
        verbose_name = _("Servicio")
        verbose_name_plural = _("Servicios")
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre

    @property
    def lista_correos(self) -> list[str]:
        return [c.strip() for c in self.correos.split(",") if c.strip()]

    @property
    def url_publica(self) -> str:
        return f"{settings.INCIDENCIAS_SITE_URL}/servicio/{self.token}/"

    def regenerar_token(self) -> None:
        self.token = nuevo_token()
        self.save(update_fields=["token"])


class TransicionInvalida(Exception):  # noqa: N818 — nombre de dominio, no «Error»
    """La derivación no admite esa operación en su estado actual."""


class DerivacionQuerySet(models.QuerySet):
    def abiertas(self):
        return self.exclude(estado=Derivacion.Estado.CERRADA)


class Derivacion(models.Model):
    """Una incidencia enviada (o a punto de enviarse) a un servicio externo.

    Lleva dentro el correo redactado: secretaría lo copia y lo manda desde su
    cuenta corporativa. Las transiciones son métodos; las vistas y la API no
    tocan `estado` a mano.
    """

    class Estado(models.TextChoices):
        BORRADOR = "borrador", _("Borrador")
        ENVIADA = "enviada", _("Enviada")
        RESPONDIDA = "respondida", _("Respondida")
        CERRADA = "cerrada", _("Cerrada")

    class Resultado(models.TextChoices):
        RESUELTA = "resuelta", _("Resuelta")
        SIN_SOLUCION = "sin_solucion", _("Sin solución")
        DUPLICADA = "duplicada", _("Duplicada")

    incidencia = models.ForeignKey(
        Incidencia, verbose_name=_("Incidencia"), on_delete=models.CASCADE, related_name="derivaciones",
    )
    servicio = models.ForeignKey(
        Servicio, verbose_name=_("Servicio"), on_delete=models.PROTECT, related_name="derivaciones",
    )
    estado = models.CharField(_("Estado"), max_length=12, choices=Estado.choices, default=Estado.BORRADOR)
    resultado = models.CharField(_("Resultado"), max_length=12, choices=Resultado.choices, blank=True, default="")
    asunto = models.CharField(_("Asunto"), max_length=255)
    cuerpo = models.TextField(_("Cuerpo del correo"), blank=True, default="")
    ticket_externo = models.CharField(_("Ticket externo"), max_length=100, blank=True, default="")
    creada_por = models.ForeignKey(
        Tecnico, verbose_name=_("Creada por"), on_delete=models.SET_NULL,
        null=True, blank=True, related_name="derivaciones_creadas",
    )
    enviada_por = models.ForeignKey(
        Tecnico, verbose_name=_("Enviada por"), on_delete=models.SET_NULL,
        null=True, blank=True, related_name="derivaciones_enviadas",
    )
    enviada_at = models.DateTimeField(_("Enviada el"), null=True, blank=True)
    created_at = models.DateTimeField(_("Creada"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Actualizada"), auto_now=True)

    objects = DerivacionQuerySet.as_manager()

    class Meta:
        verbose_name = _("Derivación")
        verbose_name_plural = _("Derivaciones")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.asunto} → {self.servicio}"

    @staticmethod
    def asunto_por_defecto(incidencia: Incidencia) -> str:
        return f"[INC-{incidencia.pk}] {incidencia.aula_o_sin_aula} — {incidencia.titulo}"

    @property
    def abierta(self) -> bool:
        return self.estado != self.Estado.CERRADA

    @property
    def texto_correo(self) -> str:
        """Lo que copia el botón: asunto, línea en blanco, cuerpo."""
        return f"{self.asunto}\n\n{self.cuerpo}"

    # --- transiciones ---------------------------------------------------------

    def _exigir(self, *estados: str, accion: str) -> None:
        if self.estado not in estados:
            msg = f"No se puede {accion} una derivación en estado «{self.get_estado_display()}»"
            raise TransicionInvalida(msg)

    def editar(self, *, asunto: str | None = None, cuerpo: str | None = None, ticket_externo: str | None = None) -> None:
        if asunto is not None or cuerpo is not None:
            self._exigir(self.Estado.BORRADOR, accion="editar el correo de")
        if asunto is not None:
            self.asunto = asunto
        if cuerpo is not None:
            self.cuerpo = cuerpo
        if ticket_externo is not None:
            self.ticket_externo = ticket_externo
        self.save()

    def marcar_enviada(self, tecnico: "Tecnico | None") -> "Comunicacion":
        self._exigir(self.Estado.BORRADOR, accion="marcar como enviada")
        self.estado = self.Estado.ENVIADA
        self.enviada_por = tecnico
        self.enviada_at = timezone.now()
        self.save()
        return self.comunicaciones.create(
            sentido=Comunicacion.Sentido.ENVIADA,
            canal=Comunicacion.Canal.CORREO,
            autor_nombre=str(tecnico) if tecnico else "",
            texto=self.texto_correo,
            fecha=self.enviada_at,
        )

    def registrar_respuesta(
        self,
        *,
        autor: str,
        texto: str,
        fecha=None,
        canal: str = "correo",
        ticket_externo: str = "",
    ) -> "Comunicacion":
        self._exigir(self.Estado.ENVIADA, self.Estado.RESPONDIDA, accion="registrar una respuesta en")
        self.estado = self.Estado.RESPONDIDA
        if ticket_externo:
            self.ticket_externo = ticket_externo
        self.save()
        return self.comunicaciones.create(
            sentido=Comunicacion.Sentido.RECIBIDA,
            canal=canal,
            autor_nombre=autor,
            texto=texto,
            fecha=fecha or timezone.now(),
        )

    def anotar(self, *, autor: str, texto: str, canal: str = "otro", fecha=None) -> "Comunicacion":
        """Una llamada, una visita, un apunte: no cambia el estado."""
        self._exigir(self.Estado.BORRADOR, self.Estado.ENVIADA, self.Estado.RESPONDIDA, accion="anotar en")
        return self.comunicaciones.create(
            sentido=Comunicacion.Sentido.NOTA, canal=canal, autor_nombre=autor, texto=texto,
            fecha=fecha or timezone.now(),
        )

    def cerrar(self, *, resultado: str, autor: str = "", nota: str = "") -> None:
        if resultado not in self.Resultado.values:
            msg = "Para cerrar una derivación hace falta un resultado"
            raise TransicionInvalida(msg)
        if resultado == self.Resultado.DUPLICADA:
            self._exigir(self.Estado.BORRADOR, self.Estado.ENVIADA, self.Estado.RESPONDIDA, accion="cerrar")
        else:
            self._exigir(self.Estado.ENVIADA, self.Estado.RESPONDIDA, accion="cerrar")
        self.estado = self.Estado.CERRADA
        self.resultado = resultado
        self.save()
        if nota:
            self.comunicaciones.create(
                sentido=Comunicacion.Sentido.NOTA, canal=Comunicacion.Canal.OTRO,
                autor_nombre=autor, texto=nota, fecha=timezone.now(),
            )


class Comunicacion(models.Model):
    """Una entrada del histórico de una derivación: lo enviado, lo recibido, una nota."""

    class Sentido(models.TextChoices):
        ENVIADA = "enviada", _("Enviada")
        RECIBIDA = "recibida", _("Recibida")
        NOTA = "nota", _("Nota")

    class Canal(models.TextChoices):
        CORREO = "correo", _("Correo")
        TELEFONO = "telefono", _("Teléfono")
        FORMULARIO = "formulario", _("Formulario web")
        VISITA = "visita", _("Visita")
        OTRO = "otro", _("Otro")

    derivacion = models.ForeignKey(
        Derivacion, verbose_name=_("Derivación"), on_delete=models.CASCADE, related_name="comunicaciones",
    )
    sentido = models.CharField(_("Sentido"), max_length=10, choices=Sentido.choices)
    canal = models.CharField(_("Canal"), max_length=12, choices=Canal.choices, default=Canal.CORREO)
    autor_nombre = models.CharField(_("Autor"), max_length=150, blank=True, default="")
    texto = models.TextField(_("Texto"))
    fecha = models.DateTimeField(_("Fecha"), help_text=_("Cuándo ocurrió, no cuándo se apuntó"))
    created_at = models.DateTimeField(_("Apuntada"), auto_now_add=True)

    class Meta:
        verbose_name = _("Comunicación")
        verbose_name_plural = _("Comunicaciones")
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"{self.get_sentido_display()} {self.fecha:%d/%m/%Y}: {self.texto[:50]}"
