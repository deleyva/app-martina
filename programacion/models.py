"""
Programación didáctica: planificación de un trimestre/periodo por grupo.

- CoursePlan: la programación de un periodo (p.ej. "2º Trimestre 2025-26") para un grupo.
- PlanItem: cada recurso programado (artículo, libro, capítulo, partitura...).
  Los libros (BlogIndexPage) generan hijos automáticamente, uno por capítulo.
- ContentCoverage: cuánto ha visto un grupo de cada página (calculado a partir
  de los ClassSessionItem, que guardan la página de origen de cada elemento).

Filosofía FAT MODEL: la lógica vive aquí y en services.py; las vistas son tiny.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from clases.models import Group


class CoursePlan(models.Model):
    """Programación de un periodo (trimestre, unidad...) para un grupo."""

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_plans",
        verbose_name="Profesor",
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="course_plans",
        verbose_name="Grupo",
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Nombre",
        help_text="Ej: 2º Trimestre 2025-26",
    )
    start_date = models.DateField(null=True, blank=True, verbose_name="Inicio")
    end_date = models.DateField(null=True, blank=True, verbose_name="Fin")
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "-start_date", "-created_at"]
        verbose_name = "Programación"
        verbose_name_plural = "Programaciones"
        indexes = [
            models.Index(fields=["teacher", "-created_at"]),
            models.Index(fields=["group", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.group.name}"

    # === FAT MODEL ===

    def get_items_ordered(self):
        """Items de primer nivel, ordenados."""
        return (
            self.items.filter(parent__isnull=True)
            .prefetch_related("children")
            .order_by("order")
        )

    def get_next_order(self):
        last = self.items.filter(parent__isnull=True).order_by("-order").first()
        return (last.order + 1) if last else 0

    def get_progress(self):
        """Progreso global del plan (media de items de primer nivel)."""
        items = list(self.get_items_ordered())
        if not items:
            return 0
        return round(sum(i.get_progress() for i in items) / len(items))

    def get_next_step(self):
        """Primer item (recorriendo capítulos en orden) no completado ni saltado."""
        for item in self.get_items_ordered():
            if item.status == PlanItem.Status.SKIPPED:
                continue
            children = list(item.children.order_by("order"))
            if children:
                for child in children:
                    if child.status == PlanItem.Status.SKIPPED:
                        continue
                    if child.get_progress() < 100:
                        return child
                continue
            if item.get_progress() < 100:
                return item
        return None

    def reorder_items(self, item_ids):
        for index, item_id in enumerate(item_ids):
            self.items.filter(pk=item_id).update(order=index)


class PlanItem(models.Model):
    """Recurso programado dentro de un CoursePlan."""

    class Status(models.TextChoices):
        AUTO = "auto", "Automático (según cobertura)"
        SKIPPED = "skipped", "Saltado"
        DONE = "done", "Completado (manual)"

    plan = models.ForeignKey(
        CoursePlan,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Programación",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Padre",
        help_text="Para capítulos de un libro",
    )

    # Contenido programado (BlogPage, BlogIndexPage-libro, ScorePage...)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    sessions_estimate = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Sesiones estimadas",
        help_text="Número de clases que estimas dedicar a este recurso",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.AUTO,
        verbose_name="Estado",
    )
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Item de Programación"
        verbose_name_plural = "Items de Programación"
        unique_together = ["plan", "content_type", "object_id"]
        indexes = [models.Index(fields=["plan", "order"])]

    def __str__(self):
        return f"{self.get_content_title()} ({self.plan.name})"

    # === FAT MODEL ===

    def get_content_title(self):
        obj = self.content_object
        if obj is None:
            return "(contenido eliminado)"
        return getattr(obj, "title", None) or getattr(obj, "name", None) or str(obj)

    def get_content_type_label(self):
        mapping = {
            "blogpage": "Artículo",
            "blogindexpage": "Libro",
            "scorepage": "Partitura",
            "dictadopage": "Dictado",
        }
        return mapping.get(self.content_type.model, self.content_type.model.title())

    def get_icon(self):
        icons = {
            "blogpage": "📝",
            "blogindexpage": "📚",
            "scorepage": "🎼",
            "dictadopage": "🎧",
        }
        return icons.get(self.content_type.model, "📁")

    @property
    def is_book(self):
        return self.content_type.model == "blogindexpage"

    def sync_chapters(self):
        """
        Si este item es un libro (BlogIndexPage), crear PlanItems hijos para
        cada capítulo (BlogPage hijo publicado) que aún no esté en el plan.
        """
        if not self.is_book or self.content_object is None:
            return []
        from cms.models import BlogPage

        chapters = (
            BlogPage.objects.child_of(self.content_object).live().order_by("path")
        )
        ct = ContentType.objects.get_for_model(BlogPage)
        created = []
        existing_ids = set(
            self.children.filter(content_type=ct).values_list("object_id", flat=True)
        )
        next_order = self.children.count()
        for chapter in chapters:
            if chapter.pk in existing_ids:
                continue
            created.append(
                PlanItem.objects.create(
                    plan=self.plan,
                    parent=self,
                    content_type=ct,
                    object_id=chapter.pk,
                    order=next_order,
                )
            )
            next_order += 1
        return created

    def get_coverage(self):
        """ContentCoverage del grupo para este contenido (o None)."""
        if self.is_book:
            return None
        return ContentCoverage.objects.filter(
            group=self.plan.group,
            content_type=self.content_type,
            object_id=self.object_id,
        ).first()

    def get_progress(self):
        """
        Progreso 0-100:
        - Estados manuales tienen prioridad (done=100, skipped=0).
        - Libros: media de capítulos.
        - Páginas: cobertura calculada (elementos vistos / totales).
        """
        if self.status == self.Status.DONE:
            return 100
        if self.status == self.Status.SKIPPED:
            return 0
        children = list(self.children.all())
        if children:
            relevant = [c for c in children if c.status != self.Status.SKIPPED]
            if not relevant:
                return 0
            return round(sum(c.get_progress() for c in relevant) / len(relevant))
        coverage = self.get_coverage()
        if coverage is None:
            return 0
        return coverage.percent

    def get_status_label(self):
        if self.status == self.Status.SKIPPED:
            return "Saltado"
        progress = self.get_progress()
        if progress >= 100:
            return "Completado"
        if progress > 0:
            return "En curso"
        return "Pendiente"

    def get_pending_elements(self):
        """Elementos de la página aún no vistos por el grupo (lista de dicts)."""
        from .services import get_pending_elements

        if self.is_book or self.content_object is None:
            return []
        return get_pending_elements(self.plan.group, self.content_object)


class ContentCoverage(models.Model):
    """
    Cobertura de una página (artículo/partitura/capítulo) por un grupo:
    qué proporción de sus elementos se han usado ya en sesiones de clase.
    Se recalcula automáticamente al añadir/quitar items de sesión (signals)
    y al cerrar una clase.
    """

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="content_coverage",
        verbose_name="Grupo",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    elements_total = models.PositiveIntegerField(default=0)
    elements_seen = models.PositiveIntegerField(default=0)
    seen_element_keys = models.JSONField(
        default=list,
        blank=True,
        help_text='Claves de elementos vistos, p.ej. ["document:12", "image:3"]',
    )
    page_presented = models.BooleanField(
        default=False,
        help_text="La página completa se ha mostrado en alguna sesión",
    )
    last_session = models.ForeignKey(
        "clases.ClassSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["group", "content_type", "object_id"]
        verbose_name = "Cobertura de Contenido"
        verbose_name_plural = "Coberturas de Contenido"
        indexes = [
            models.Index(fields=["group", "content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.group.name} · {self.content_object} ({self.percent}%)"

    @property
    def percent(self):
        if self.elements_total == 0:
            return 100 if self.page_presented else 0
        pct = round(100 * self.elements_seen / self.elements_total)
        # Si la página se presentó entera pero faltan elementos, mínimo 5%
        if pct == 0 and self.page_presented:
            return 5
        return min(pct, 100)
