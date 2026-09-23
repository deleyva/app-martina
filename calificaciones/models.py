"""Calificaciones: criterios de evaluación × instrumentos, notas y evidencias.

**Qué es cada cosa.**

- `MarcoEvaluacion` es la programación en lo que toca a calificar: los
  criterios de evaluación de una materia y nivel con su peso legal, y cómo se
  ponderan los trimestres.
- `Plan` es el plan de calificación de un trimestre: qué instrumentos se usan
  (lectura rítmica, dictado, cuaderno…) y cómo reparten su porcentaje entre
  los criterios. Un plan lo comparten los grupos que lo usan.
- `Reparto` es la tabla intermedia muchos-a-muchos, con el porcentaje en la
  celda. Es la única verdad: el peso de un instrumento es la suma de su
  columna y el peso de un criterio, la suma de su fila.
- `Prueba` es una observación datada de un instrumento. Crear un instrumento
  crea su prueba por defecto; con una sola, la capa no se ve.
- `Nota` es la nota de un alumno en una prueba. `valor` nulo es «sin nota»,
  distinto de cero.
- `Evidencia` es lo que se recoge en clase: foto, audio, vídeo, texto o
  enlace, atado a un alumno y una prueba.

**El alumno es `User` vía `Enrollment`**, nunca el `Student` heredado de
`clases`: es el modelo actual y el que rellenan las invitaciones.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from clases.models import Enrollment, Group, Subject

from . import calculo

TRIMESTRES = [(1, "1ª evaluación"), (2, "2ª evaluación"), (3, "3ª evaluación")]


def alumnos_del_grupo(group):
    """El alumnado matriculado y activo, en el orden en que se pasa lista."""
    from django.contrib.auth import get_user_model

    return (
        get_user_model()
        .objects.filter(enrollments__group=group, enrollments__is_active=True)
        .distinct()
        .order_by("name", "email")
    )


class MarcoEvaluacion(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="marcos_evaluacion"
    )
    nivel = models.CharField(max_length=50, verbose_name="Nivel", help_text="Ej: 3º ESO")
    modalidad = models.CharField(
        max_length=50, blank=True, verbose_name="Modalidad", help_text="Ej: bilingüe"
    )
    academic_year = models.CharField(max_length=20, verbose_name="Curso académico")
    # Pesos de los tres trimestres en la nota final del curso. Claves como
    # texto porque JSON no tiene claves enteras.
    peso_trimestres = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Peso de los trimestres",
        help_text='Ej: {"1": 20, "2": 30, "3": 50}. Vacío = a partes iguales',
    )

    class Meta:
        unique_together = ["subject", "nivel", "modalidad", "academic_year"]
        ordering = ["academic_year", "nivel", "modalidad"]
        verbose_name = "Marco de evaluación"
        verbose_name_plural = "Marcos de evaluación"

    def __str__(self):
        modalidad = f" {self.modalidad}" if self.modalidad else ""
        return f"{self.subject.name} · {self.nivel}{modalidad} ({self.academic_year})"

    def pesos_trimestre(self) -> dict[int, Decimal]:
        if self.peso_trimestres:
            return {int(k): Decimal(str(v)) for k, v in self.peso_trimestres.items()}
        return {1: Decimal(1), 2: Decimal(1), 3: Decimal(1)}

    def pesos_criterio(self) -> dict[int, Decimal]:
        return {c.pk: c.peso for c in self.criterios.all()}

    @property
    def peso_total(self) -> Decimal:
        return sum((c.peso for c in self.criterios.all()), Decimal(0))


class Criterio(models.Model):
    marco = models.ForeignKey(
        MarcoEvaluacion, on_delete=models.CASCADE, related_name="criterios"
    )
    codigo = models.CharField(max_length=10, verbose_name="Código", help_text="Ej: 3.1")
    competencia = models.CharField(
        max_length=20, blank=True, verbose_name="Competencia específica", help_text="Ej: CE.MU.3"
    )
    descripcion = models.TextField(verbose_name="Descripción")
    peso = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="Peso (%)", help_text="El de la programación"
    )
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ["marco", "codigo"]
        ordering = ["marco", "orden", "codigo"]
        verbose_name = "Criterio de evaluación"
        verbose_name_plural = "Criterios de evaluación"

    def __str__(self):
        return f"{self.codigo} ({self.peso} %)"

    @property
    def resumen(self) -> str:
        texto = self.descripcion.strip()
        return texto if len(texto) <= 90 else texto[:87].rstrip() + "…"


class Plan(models.Model):
    marco = models.ForeignKey(MarcoEvaluacion, on_delete=models.PROTECT, related_name="planes")
    trimestre = models.PositiveSmallIntegerField(choices=TRIMESTRES)
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    groups = models.ManyToManyField(
        Group, blank=True, related_name="planes_calificacion", verbose_name="Grupos"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["marco", "trimestre", "nombre"]
        verbose_name = "Plan de calificación"
        verbose_name_plural = "Planes de calificación"

    def __str__(self):
        return f"{self.nombre} · {self.get_trimestre_display()}"

    # ----- acceso ---------------------------------------------------------

    @staticmethod
    def del_profesor(user):
        """Los planes que este profesor puede editar: los de sus grupos."""
        if user.is_staff:
            return Plan.objects.all()
        return Plan.objects.filter(groups__teachers=user).distinct()

    @staticmethod
    def para_grupo(group, trimestre):
        return group.planes_calificacion.filter(trimestre=trimestre).first()

    @staticmethod
    def elegibles_para(group, trimestre):
        """Planes que un grupo podría adoptar: misma materia, mismo curso, mismo trimestre."""
        return Plan.objects.filter(
            marco__subject=group.subject,
            marco__academic_year=group.academic_year,
            trimestre=trimestre,
        ).select_related("marco")

    # ----- el reparto ------------------------------------------------------

    def celdas(self) -> dict[tuple[int, int], Decimal]:
        return {
            (r.criterio_id, r.instrumento_id): r.porcentaje
            for r in Reparto.objects.filter(instrumento__plan=self)
        }

    def cuadre(self):
        """Totales de fila y de columna, y si cada fila coincide con el peso legal."""
        celdas = self.celdas()
        criterios = list(self.marco.criterios.all())
        instrumentos = list(self.instrumentos.all())
        filas = []
        for criterio in criterios:
            total = sum(
                (celdas.get((criterio.pk, i.pk), Decimal(0)) for i in instrumentos),
                Decimal(0),
            )
            filas.append(
                {
                    "criterio": criterio,
                    "total": total,
                    "cuadra": total == criterio.peso,
                    "celdas": [celdas.get((criterio.pk, i.pk)) for i in instrumentos],
                }
            )
        columnas = []
        for instrumento in instrumentos:
            columnas.append(
                sum(
                    (celdas.get((c.pk, instrumento.pk), Decimal(0)) for c in criterios),
                    Decimal(0),
                )
            )
        total = sum(columnas, Decimal(0))
        return {
            "criterios": criterios,
            "instrumentos": instrumentos,
            "filas": filas,
            "columnas": columnas,
            "total": total,
            "cuadra": total == self.marco.peso_total and all(f["cuadra"] for f in filas),
        }

    @transaction.atomic
    def guardar_reparto(self, valores: dict[tuple[int, int], Decimal]):
        """Sustituye el reparto entero por `valores`; una celda a cero desaparece."""
        Reparto.objects.filter(instrumento__plan=self).delete()
        Reparto.objects.bulk_create(
            [
                Reparto(criterio_id=c, instrumento_id=i, porcentaje=p)
                for (c, i), p in valores.items()
                if p and p > 0
            ]
        )

    @transaction.atomic
    def copiar(self, trimestre: int, nombre: str) -> "Plan":
        """Un plan nuevo con los mismos instrumentos y reparto, sin grupos ni pruebas."""
        nuevo = Plan.objects.create(marco=self.marco, trimestre=trimestre, nombre=nombre)
        for instrumento in self.instrumentos.all():
            copia = Instrumento.objects.create(
                plan=nuevo,
                nombre=instrumento.nombre,
                abreviatura=instrumento.abreviatura,
                orden=instrumento.orden,
                escala=instrumento.escala,
                opciones=instrumento.opciones,
                agregacion=instrumento.agregacion,
            )
            Reparto.objects.bulk_create(
                [
                    Reparto(instrumento=copia, criterio_id=r.criterio_id, porcentaje=r.porcentaje)
                    for r in instrumento.repartos.all()
                ]
            )
        return nuevo

    # ----- las notas -------------------------------------------------------

    def resultados(self, alumnos) -> dict[int, calculo.Resultado]:
        """La nota de cada alumno en este trimestre, en dos consultas."""
        instrumentos = list(self.instrumentos.prefetch_related("pruebas"))
        pruebas_por_instrumento = {
            i.pk: [p for p in i.pruebas.all() if p.activa] for i in instrumentos
        }
        ids_prueba = [p.pk for lista in pruebas_por_instrumento.values() for p in lista]
        notas = Nota.objects.filter(prueba_id__in=ids_prueba, alumno__in=alumnos)
        valor = {(n.prueba_id, n.alumno_id): n.valor for n in notas}

        celdas = self.celdas()
        pesos = self.marco.pesos_criterio()
        salida = {}
        for alumno in alumnos:
            por_instrumento = {}
            for instrumento in instrumentos:
                valores = [
                    valor.get((p.pk, alumno.pk)) for p in pruebas_por_instrumento[instrumento.pk]
                ]
                por_instrumento[instrumento.pk] = calculo.nota_instrumento(
                    valores, instrumento.agregacion
                )
            salida[alumno.pk] = calculo.calcular(celdas, pesos, por_instrumento)
        return salida

    def resultado_de(self, alumno) -> calculo.Resultado:
        return self.resultados([alumno])[alumno.pk]

    def filas_cuadro(self, group, alumnos) -> dict:
        """Todo lo que pinta el cuadro: una fila por alumno, una celda por instrumento.

        Una celda es editable en línea solo si su instrumento tiene UNA prueba
        activa; con varias, enseña la nota agregada y se califica prueba a
        prueba desde el panel.
        """
        from django.db.models import Count

        instrumentos = list(self.instrumentos.prefetch_related("pruebas"))
        resultados = self.resultados(alumnos)
        unicas = {i.pk: i.prueba_unica() for i in instrumentos}
        opciones = {i.pk: i.opciones_normalizadas() for i in instrumentos}
        ids_prueba = [p.pk for i in instrumentos for p in i.pruebas.all()]
        notas_unica = {
            (n.prueba_id, n.alumno_id): n
            for n in Nota.objects.filter(
                prueba_id__in=[p.pk for p in unicas.values() if p], alumno__in=alumnos
            )
        }
        recuento = {}
        for fila in (
            Evidencia.objects.filter(prueba_id__in=ids_prueba, alumno__in=alumnos)
            .values("prueba__instrumento_id", "alumno_id")
            .annotate(n=Count("id"))
        ):
            recuento[(fila["prueba__instrumento_id"], fila["alumno_id"])] = fila["n"]
        filas = []
        for alumno in alumnos:
            r = resultados[alumno.pk]
            celdas = []
            for i in instrumentos:
                prueba = unicas[i.pk]
                nota = notas_unica.get((prueba.pk, alumno.pk)) if prueba else None
                celdas.append(
                    {
                        "instrumento": i,
                        "prueba": prueba,
                        "valor": r.instrumentos.get(i.pk),
                        "texto": CambioNota.texto(nota.valor) if nota else "",
                        "evidencias": recuento.get((i.pk, alumno.pk), 0),
                        "opciones": opciones[i.pk],
                    }
                )
            filas.append({"alumno": alumno, "resultado": r, "celdas": celdas})
        return {
            "instrumentos": [
                {"obj": i, "prueba": unicas[i.pk], "opciones": opciones[i.pk]}
                for i in instrumentos
            ],
            "filas": filas,
            "criterios": list(self.marco.criterios.all()),
        }


class Instrumento(models.Model):
    ESCALA_NUMERICA = "numerica"
    ESCALA_OPCIONES = "opciones"
    ESCALAS = [(ESCALA_NUMERICA, "Numérica 0-10"), (ESCALA_OPCIONES, "Lista de opciones")]
    AGREGACIONES = [
        (calculo.AGREGACION_MEDIA, "Media de las pruebas"),
        (calculo.AGREGACION_ULTIMA, "La última prueba"),
        (calculo.AGREGACION_MEJOR, "La mejor prueba"),
    ]

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="instrumentos")
    nombre = models.CharField(max_length=80, verbose_name="Nombre")
    abreviatura = models.CharField(max_length=12, verbose_name="Abreviatura")
    orden = models.PositiveSmallIntegerField(default=0)
    escala = models.CharField(max_length=10, choices=ESCALAS, default=ESCALA_NUMERICA)
    # Para la escala de opciones: [{"etiqueta": "Bien", "valor": 6}, …]. El valor
    # es siempre una nota 0-10, así la nota se guarda igual sea cual sea la escala.
    opciones = models.JSONField(default=list, blank=True)
    agregacion = models.CharField(
        max_length=10, choices=AGREGACIONES, default=calculo.AGREGACION_MEDIA
    )

    class Meta:
        ordering = ["plan", "orden", "pk"]
        verbose_name = "Instrumento de evaluación"
        verbose_name_plural = "Instrumentos de evaluación"

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        nuevo = self.pk is None
        if not self.abreviatura:
            self.abreviatura = self.nombre[:12]
        super().save(*args, **kwargs)
        # Un instrumento nace con su prueba, para que la capa no se vea hasta
        # que hace falta una segunda.
        if nuevo:
            Prueba.objects.create(instrumento=self, nombre=self.nombre)

    @property
    def peso(self) -> Decimal:
        return sum((r.porcentaje for r in self.repartos.all()), Decimal(0))

    def criterios_ids(self) -> set[int]:
        return set(self.repartos.values_list("criterio_id", flat=True))

    def prueba_unica(self):
        """La prueba si solo hay una activa; si hay varias, `None` (se califica por prueba)."""
        activas = [p for p in self.pruebas.all() if p.activa]
        return activas[0] if len(activas) == 1 else None

    def opciones_normalizadas(self) -> list[dict]:
        return [
            {"etiqueta": str(o.get("etiqueta", o.get("valor"))), "valor": Decimal(str(o["valor"]))}
            for o in (self.opciones or [])
            if "valor" in o
        ]


class Reparto(models.Model):
    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE, related_name="repartos")
    criterio = models.ForeignKey(Criterio, on_delete=models.CASCADE, related_name="repartos")
    porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )

    class Meta:
        unique_together = ["instrumento", "criterio"]
        verbose_name = "Reparto"
        verbose_name_plural = "Reparto"

    def __str__(self):
        return f"{self.instrumento} → {self.criterio.codigo}: {self.porcentaje} %"


class Prueba(models.Model):
    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE, related_name="pruebas")
    nombre = models.CharField(max_length=100)
    fecha = models.DateField(default=timezone.localdate)
    activa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "pk"]
        verbose_name = "Prueba"
        verbose_name_plural = "Pruebas"

    def __str__(self):
        return f"{self.nombre} ({self.fecha:%d/%m})"

    @property
    def plan(self):
        return self.instrumento.plan

    def notas_de(self, alumnos) -> dict[int, "Nota"]:
        return {n.alumno_id: n for n in self.notas.filter(alumno__in=alumnos)}


class Nota(models.Model):
    prueba = models.ForeignKey(Prueba, on_delete=models.CASCADE, related_name="notas")
    alumno = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notas_calificaciones"
    )
    valor = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal(0)), MaxValueValidator(Decimal(10))],
        help_text="Vacío = sin nota. No es lo mismo que cero",
    )
    comentario = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["prueba", "alumno"]
        verbose_name = "Nota"
        verbose_name_plural = "Notas"

    def __str__(self):
        return f"{self.alumno} · {self.prueba}: {self.valor if self.valor is not None else '—'}"

    @staticmethod
    @transaction.atomic
    def poner(prueba, alumno, valor: Decimal | None, user, comentario: str | None = None):
        """Escribe la nota y deja el cambio en el historial. `None` borra la nota."""
        nota, _ = Nota.objects.select_for_update().get_or_create(prueba=prueba, alumno=alumno)
        antes = nota.valor
        if antes == valor and (comentario is None or comentario == nota.comentario):
            return nota
        nota.valor = valor
        if comentario is not None:
            nota.comentario = comentario
        nota.updated_by = user
        nota.save()
        if antes != valor:
            CambioNota.objects.create(
                nota=nota, antes=CambioNota.texto(antes), despues=CambioNota.texto(valor), user=user
            )
        return nota


def ruta_evidencia(instance, filename):
    """`calificaciones/<plan>/<alumno>/<uuid>.<ext>`: privado y no adivinable."""
    extension = Path(filename).suffix.lower()[:8] or ".bin"
    plan_id = instance.prueba.instrumento.plan_id
    return f"calificaciones/{plan_id}/{instance.alumno_id}/{uuid.uuid4().hex}{extension}"


class Evidencia(models.Model):
    FOTO, AUDIO, VIDEO, TEXTO, ENLACE = "foto", "audio", "video", "texto", "enlace"
    TIPOS = [
        (FOTO, "Foto"),
        (AUDIO, "Audio"),
        (VIDEO, "Vídeo"),
        (TEXTO, "Nota de texto"),
        (ENLACE, "Enlace"),
    ]
    PENDIENTE, PROCESANDO, LISTO, FALLIDO = "pendiente", "procesando", "listo", "fallido"
    ESTADOS = [
        (PENDIENTE, "Pendiente"),
        (PROCESANDO, "Procesando"),
        (LISTO, "Listo"),
        (FALLIDO, "Fallido"),
    ]

    prueba = models.ForeignKey(Prueba, on_delete=models.CASCADE, related_name="evidencias")
    alumno = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="evidencias_calificaciones"
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    archivo = models.FileField(upload_to=ruta_evidencia, blank=True, max_length=255)
    archivo_comprimido = models.FileField(upload_to=ruta_evidencia, blank=True, max_length=255)
    tipo_mime = models.CharField(max_length=80, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=LISTO)
    error = models.TextField(blank=True)
    texto = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Evidencia"
        verbose_name_plural = "Evidencias"

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.alumno} · {self.prueba}"

    @property
    def fichero(self):
        """El que se sirve: el comprimido si ya existe, si no el original."""
        return self.archivo_comprimido if self.archivo_comprimido else self.archivo

    @property
    def icono(self) -> str:
        return {
            self.FOTO: "📷",
            self.AUDIO: "🎤",
            self.VIDEO: "🎥",
            self.TEXTO: "✏️",
            self.ENLACE: "🔗",
        }[self.tipo]

    def delete(self, *args, **kwargs):
        for campo in (self.archivo, self.archivo_comprimido):
            if campo:
                campo.delete(save=False)
        return super().delete(*args, **kwargs)


class NotaManual(models.Model):
    """La nota que el profesor pone a mano por encima de la calculada.

    Se guarda al lado del cálculo, nunca lo sustituye en silencio: el cuadro
    enseña las dos.
    """

    AMBITOS = [("1", "1ª evaluación"), ("2", "2ª evaluación"), ("3", "3ª evaluación"), ("curso", "Final de curso")]
    CALIFICACIONES = [(k, v) for k, v in calculo.CUALITATIVAS.items()]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="notas_manuales")
    alumno = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notas_manuales"
    )
    ambito = models.CharField(max_length=5, choices=AMBITOS)
    calificacion = models.CharField(max_length=2, choices=CALIFICACIONES)
    motivo = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["group", "alumno", "ambito"]
        verbose_name = "Nota manual"
        verbose_name_plural = "Notas manuales"

    def __str__(self):
        return f"{self.alumno} · {self.get_ambito_display()}: {self.calificacion}"


class CambioNota(models.Model):
    """Cada cambio de una nota, con antes y después. Deshacer añade otro cambio; nunca borra."""

    nota = models.ForeignKey(Nota, on_delete=models.CASCADE, related_name="cambios")
    antes = models.CharField(max_length=20, blank=True)
    despues = models.CharField(max_length=20, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    ts = models.DateTimeField(auto_now_add=True)
    revertido_de = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="reversiones"
    )

    class Meta:
        ordering = ["-ts", "-pk"]
        verbose_name = "Cambio de nota"
        verbose_name_plural = "Historial de notas"

    def __str__(self):
        return f"{self.nota}: {self.antes or '—'} → {self.despues or '—'}"

    @staticmethod
    def texto(valor: Decimal | None) -> str:
        if valor is None:
            return ""
        texto = f"{valor:.2f}".rstrip("0").rstrip(".")
        return texto or "0"

    @staticmethod
    def valor(texto: str) -> Decimal | None:
        return Decimal(texto) if texto != "" else None

    @transaction.atomic
    def revertir(self, user) -> "CambioNota":
        nota = Nota.objects.select_for_update().get(pk=self.nota_id)
        actual = nota.valor
        nota.valor = self.valor(self.antes)
        nota.updated_by = user
        nota.save()
        return CambioNota.objects.create(
            nota=nota,
            antes=self.texto(actual),
            despues=self.antes,
            user=user,
            revertido_de=self,
        )
