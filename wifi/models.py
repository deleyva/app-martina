from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class DispositivoWifi(models.Model):
    """Un dispositivo cuya MAC hay que dar de alta en la red del centro.

    El ciclo de vida es una máquina de estados, no un par de booleanos: un
    dispositivo no puede estar a la vez «añadido» y «pendiente de añadir», y con
    banderas sueltas esa combinación imposible sí se puede escribir.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", _("Pendiente de dar de alta")
        ANADIDA = "anadida", _("Dada de alta")
        BAJA_PENDIENTE = "baja_pendiente", _("Pendiente de dar de baja")
        DADA_DE_BAJA = "dada_de_baja", _("Dada de baja")

    #: Estados en los que la MAC sigue ocupando sitio en la red.
    ESTADOS_ACTIVOS = (Estado.PENDIENTE, Estado.ANADIDA, Estado.BAJA_PENDIENTE)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Solicitante"),
        on_delete=models.CASCADE,
        related_name="dispositivos_wifi",
    )
    mac = models.CharField(
        _("Dirección MAC"),
        max_length=17,
        db_index=True,
        help_text=_("Forma canónica AA:BB:CC:DD:EE:FF, en mayúsculas."),
    )
    descripcion = models.CharField(
        _("Dispositivo"),
        max_length=120,
        blank=True,
        default="",
        help_text=_("Para reconocerlo después: «móvil personal», «portátil del aula 12»…"),
    )
    estado = models.CharField(
        _("Estado"),
        max_length=16,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True,
    )

    created_at = models.DateTimeField(_("Solicitado"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Actualizado"), auto_now=True)

    anadida_at = models.DateTimeField(_("Dado de alta"), null=True, blank=True)
    anadida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Dado de alta por"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="altas_wifi_realizadas",
    )
    baja_at = models.DateTimeField(_("Dado de baja"), null=True, blank=True)
    baja_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Dado de baja por"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bajas_wifi_realizadas",
    )
    notificado_at = models.DateTimeField(
        _("Aviso enviado"),
        null=True,
        blank=True,
        help_text=_("Sello del correo con la clave. Impide enviarlo dos veces."),
    )

    class Meta:
        verbose_name = _("Dispositivo WiFi")
        verbose_name_plural = _("Dispositivos WiFi")
        ordering = ["created_at"]
        constraints = [
            # Una MAC solo puede estar registrada una vez *mientras siga activa*.
            # Si se dio de baja, se puede volver a registrar: un portátil vuelve
            # al centro, o alguien recupera un móvil que había dado por perdido.
            models.UniqueConstraint(
                fields=["mac"],
                condition=~models.Q(estado="dada_de_baja"),
                name="wifi_mac_unica_mientras_activa",
            ),
        ]

    def __str__(self):
        return f"{self.mac} — {self.usuario}"

    @property
    def email_destino(self) -> str:
        return (self.usuario.email or "").strip()

    def marcar_anadida(self, por=None) -> bool:
        """Sella el alta. Devuelve True solo si el estado cambió de verdad.

        Devolver el cambio real es lo que impide que marcar dos veces mande dos
        correos: quien llama solo notifica si esto dice True.
        """
        if self.estado != self.Estado.PENDIENTE:
            return False
        self.estado = self.Estado.ANADIDA
        self.anadida_at = timezone.now()
        self.anadida_por = por
        self.save(update_fields=["estado", "anadida_at", "anadida_por", "updated_at"])
        return True

    def marcar_para_baja(self, por=None) -> bool:
        if self.estado not in (self.Estado.PENDIENTE, self.Estado.ANADIDA):
            return False
        self.estado = self.Estado.BAJA_PENDIENTE
        self.baja_por = por
        self.save(update_fields=["estado", "baja_por", "updated_at"])
        return True

    def marcar_dada_de_baja(self, por=None) -> bool:
        if self.estado != self.Estado.BAJA_PENDIENTE:
            return False
        self.estado = self.Estado.DADA_DE_BAJA
        self.baja_at = timezone.now()
        self.baja_por = por
        self.save(update_fields=["estado", "baja_at", "baja_por", "updated_at"])
        return True
