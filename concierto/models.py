from django.db import models
from django.utils.translation import gettext_lazy as _


class Acto(models.Model):
    """Un acto/actuacion del concierto."""

    orden = models.PositiveIntegerField(_("Orden"))
    artistas = models.CharField(_("Artistas"), max_length=500)
    canciones = models.TextField(_("Canciones"), help_text="Una cancion por linea")
    autores = models.CharField(_("Autores"), max_length=500, blank=True, default="")
    material = models.TextField(_("Material necesario"), blank=True, default="")
    duracion_minutos = models.PositiveIntegerField(_("Duracion (min)"), default=5)

    class Meta:
        verbose_name = _("Acto")
        verbose_name_plural = _("Actos")
        ordering = ["orden"]

    def __str__(self):
        return f"{self.orden}. {self.artistas}"

    def canciones_lista(self):
        return [c.strip() for c in self.canciones.split("\n") if c.strip()]


class Tarea(models.Model):
    """Una tarea de voluntariado para el concierto."""

    nombre = models.CharField(_("Nombre"), max_length=200)
    descripcion = models.TextField(_("Descripcion"), blank=True, default="")
    max_voluntarios = models.PositiveIntegerField(_("Max voluntarios"), default=3)
    acto = models.ForeignKey(
        Acto,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tareas_grabacion",
        help_text="Solo para tareas de grabacion vinculadas a un acto",
    )

    class Meta:
        verbose_name = _("Tarea")
        verbose_name_plural = _("Tareas")
        ordering = ["id"]

    def __str__(self):
        return self.nombre

    def plazas_disponibles(self):
        return max(0, self.max_voluntarios - self.voluntarios.count())

    def esta_llena(self):
        return self.voluntarios.count() >= self.max_voluntarios


class Voluntario(models.Model):
    """Un profesor que se apunta a una tarea."""

    username = models.CharField(
        _("Usuario IES"),
        max_length=100,
        help_text="Tu usuario sin @iesmartinabescos.es (ej: jlopez)",
    )
    tarea = models.ForeignKey(
        Tarea,
        on_delete=models.CASCADE,
        related_name="voluntarios",
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Voluntario")
        verbose_name_plural = _("Voluntarios")
        unique_together = ("username", "tarea")

    def __str__(self):
        return f"{self.username} -> {self.tarea}"
