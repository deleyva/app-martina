from django.db import models
import uuid
from django.conf import settings

# Create your models here.


class EvaluationItem(models.Model):
    name = models.CharField(max_length=100)
    TERM_CHOICES = [
        ("primera", "Primera evaluación"),
        ("segunda", "Segunda evaluación"),
        ("tercera", "Tercera evaluación"),
    ]
    term = models.CharField(choices=TERM_CHOICES, null=True, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
        null=True,
        blank=True,
    )
    group = models.CharField(max_length=50)
    
    def __str__(self):
        return f"{self.user.name}" if self.user else f"Student {self.id}"

    class Meta:
        ordering = ["user__name"]


class RubricCategory(models.Model):
    """Categoría de la rúbrica (ej: Plasticidad, Velocidad, Compás, etc.)"""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    max_points = models.DecimalField(max_digits=3, decimal_places=1, default=2.0)
    order = models.PositiveSmallIntegerField(default=0)
    evaluation_item = models.ForeignKey(
        EvaluationItem,
        on_delete=models.CASCADE,
        related_name="rubric_categories",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["order"]
        verbose_name = "Categoría de rúbrica"
        verbose_name_plural = "Categorías de rúbrica"

    def __str__(self):
        return self.name


class Evaluation(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="evaluations"
    )
    evaluation_item = models.ForeignKey(
        EvaluationItem, on_delete=models.CASCADE, related_name="evaluations"
    )
    score = models.DecimalField(max_digits=4, decimal_places=2)
    date_evaluated = models.DateTimeField(auto_now_add=True)
    classroom_submission = models.BooleanField(
        default=False, verbose_name="Entrega por classroom"
    )
    max_score = models.DecimalField(
        max_digits=3, decimal_places=1, default=10.0, verbose_name="Nota máxima"
    )

    class Meta:
        unique_together = ["student", "evaluation_item"]
        ordering = ["-date_evaluated"]

    def __str__(self):
        return f"{self.student} - {self.evaluation_item}: {self.score}"

    def calculate_score(self):
        """Calcula la puntuación total basada en las puntuaciones de la rúbrica"""
        rubric_scores = self.rubric_scores.all()
        if not rubric_scores:
            return 0

        total_points = sum(score.points for score in rubric_scores)
        max_possible = sum(score.category.max_points for score in rubric_scores)

        return (total_points / max_possible) * 10 if max_possible > 0 else 0


class RubricScore(models.Model):
    """Puntuación de un estudiante en una categoría específica de la rúbrica"""

    evaluation = models.ForeignKey(
        Evaluation, on_delete=models.CASCADE, related_name="rubric_scores"
    )
    category = models.ForeignKey(
        RubricCategory, on_delete=models.CASCADE, related_name="scores"
    )
    points = models.DecimalField(max_digits=3, decimal_places=1)

    class Meta:
        unique_together = ["evaluation", "category"]

    def __str__(self):
        return f"{self.evaluation.student} - {self.category.name}: {self.points} puntos"


class PendingEvaluationStatus(models.Model):
    """Modelo para almacenar el estado de las evaluaciones pendientes"""
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="pending_statuses"
    )
    evaluation_item = models.ForeignKey(
        EvaluationItem, on_delete=models.CASCADE, related_name="pending_statuses"
    )
    classroom_submission = models.BooleanField(
        default=False, verbose_name="Entrega por classroom"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ["student", "evaluation_item"]
        verbose_name = "Estado de evaluación pendiente"
        verbose_name_plural = "Estados de evaluaciones pendientes"
        indexes = [
            models.Index(fields=['student', 'evaluation_item']),
            models.Index(fields=['evaluation_item']),
            models.Index(fields=['classroom_submission']),
        ]
    
    def __str__(self):
        return f"{self.student} - {self.evaluation_item} - {'Classroom' if self.classroom_submission else 'En clase'}"
    
    @classmethod
    def get_pending_students(cls, evaluation_item=None, group=None, include_classroom=False):
        """Obtiene los estudiantes con evaluaciones pendientes"""
        query = cls.objects.select_related('student', 'student__user', 'evaluation_item')
        
        if evaluation_item:
            query = query.filter(evaluation_item=evaluation_item)
            
        if group:
            query = query.filter(student__group=group)
            
        if not include_classroom:
            query = query.filter(classroom_submission=False)
            
        return query
