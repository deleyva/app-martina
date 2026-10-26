"""Banco de preguntas y pases (fase 76).

Un modelo `Pregunta` plano en lugar de páginas Wagtail: lo que hace falta es
consultar por SQL cuántas veces se ha preguntado algo y cuántas se ha fallado,
y para eso una StreamField es opaca. `TestPage` sigue existiendo y no se toca.

Las etiquetas son el mismo vocabulario facetado del resto del sitio
(`concepto:…`, `curso:…`, `my_library.facets`): así una pregunta se liga a lo
que el grupo ha visto en clase sin inventar otra taxonomía.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from taggit.managers import TaggableManager

from my_library import facets

OPCIONES = 4


class Pregunta(models.Model):
    SIN_REVISAR = "sin_revisar"
    ACTIVA = "activa"
    ARCHIVADA = "archivada"
    ESTADOS = [
        (SIN_REVISAR, "Sin revisar"),
        (ACTIVA, "Activa"),
        (ARCHIVADA, "Archivada"),
    ]

    enunciado = models.TextField(verbose_name="Enunciado")
    imagen = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Imagen",
    )
    # Exactamente 4 opciones, en orden A, B, C, D: la letra de la tarjeta ES el
    # índice. Lista JSON de cadenas en vez de cuatro columnas para que el
    # código que compone y corrige trabaje con `opciones[i]`.
    opciones = models.JSONField(default=list, verbose_name="Opciones (A, B, C, D)")
    correcta = models.PositiveSmallIntegerField(
        verbose_name="Índice de la correcta (0–3)"
    )
    explicacion = models.TextField(blank=True, verbose_name="Explicación")
    etiquetas = TaggableManager(blank=True, verbose_name="Etiquetas")
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="preguntas_creadas",
        verbose_name="Autor",
    )
    estado = models.CharField(
        max_length=12, choices=ESTADOS, default=SIN_REVISAR, verbose_name="Estado"
    )
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creada"]
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"

    def __str__(self):
        return self.enunciado[:60]

    LETRAS = "ABCD"

    def clean(self):
        if not isinstance(self.opciones, list) or len(self.opciones) != OPCIONES:
            raise ValidationError({"opciones": f"Hacen falta exactamente {OPCIONES} opciones."})
        if any(not isinstance(o, str) or not o.strip() for o in self.opciones):
            raise ValidationError({"opciones": "Ninguna opción puede estar vacía."})
        if self.correcta is None or not 0 <= self.correcta < OPCIONES:
            raise ValidationError({"correcta": "La correcta tiene que ser una de las 4 opciones."})

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["etiquetas", "autor", "imagen"])
        super().save(*args, **kwargs)

    @property
    def letra_correcta(self):
        return self.LETRAS[self.correcta]

    def conceptos(self):
        return sorted(
            facets.por_faceta(self.etiquetas.names()).get(facets.CONCEPTO, set())
        )


class Pase(models.Model):
    """Un pase de preguntas en una clase. 76·1 solo lo define; 76·2 lo usa."""

    BORRADOR = "borrador"
    ABIERTO = "abierto"
    CERRADO = "cerrado"
    ESTADOS = [(BORRADOR, "Borrador"), (ABIERTO, "Abierto"), (CERRADO, "Cerrado")]

    group = models.ForeignKey(
        "clases.Group", on_delete=models.CASCADE, related_name="pases"
    )
    session = models.ForeignKey(
        "clases.ClassSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pases",
    )
    fecha = models.DateField()
    estado = models.CharField(max_length=10, choices=ESTADOS, default=BORRADOR)
    preguntas = models.ManyToManyField(
        Pregunta, through="PasePregunta", related_name="pases"
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    creado = models.DateTimeField(auto_now_add=True)
    cerrado = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha", "-creado"]

    def __str__(self):
        return f"Pase {self.group.name} · {self.fecha}"


class PasePregunta(models.Model):
    pase = models.ForeignKey(Pase, on_delete=models.CASCADE, related_name="orden")
    pregunta = models.ForeignKey(Pregunta, on_delete=models.PROTECT)
    posicion = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["posicion"]
        unique_together = [("pase", "pregunta")]


class Respuesta(models.Model):
    """Lo que respondió un alumno a una pregunta en un pase.

    `opcion` nula = presente sin lectura. Por decisión de Jesús (2026-10-26)
    cuenta como errónea: `acierto` queda False y la marca `sin_lectura` la
    distingue de un error de verdad al revisar.
    """

    pase = models.ForeignKey(Pase, on_delete=models.CASCADE, related_name="respuestas")
    pregunta = models.ForeignKey(
        Pregunta, on_delete=models.PROTECT, related_name="respuestas"
    )
    alumno = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="respuestas_teoria"
    )
    opcion = models.PositiveSmallIntegerField(null=True, blank=True)
    acierto = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("pase", "pregunta", "alumno")]

    @property
    def sin_lectura(self):
        return self.opcion is None

    def save(self, *args, **kwargs):
        self.acierto = self.opcion is not None and self.opcion == self.pregunta.correcta
        super().save(*args, **kwargs)
