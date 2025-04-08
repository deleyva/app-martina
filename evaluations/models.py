from django.db import models

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
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    group = models.CharField(max_length=50)
    pending_evaluation = models.ForeignKey(
        EvaluationItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_students",
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class RubricCategory(models.Model):
    """Categoría de la rúbrica (ej: Plasticidad, Velocidad, Compás, etc.)"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    max_points = models.PositiveSmallIntegerField(default=2)
    order = models.PositiveSmallIntegerField(default=0)
    evaluation_item = models.ForeignKey(
        EvaluationItem, 
        on_delete=models.CASCADE, 
        related_name="rubric_categories",
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["order"]
        verbose_name = "Categoría de rúbrica"
        verbose_name_plural = "Categorías de rúbrica"

    def __str__(self):
        return self.name


class RubricCriteria(models.Model):
    """Criterios específicos para cada nivel de puntuación en una categoría"""
    category = models.ForeignKey(
        RubricCategory, 
        on_delete=models.CASCADE, 
        related_name="criteria"
    )
    points = models.PositiveSmallIntegerField()
    description = models.TextField()

    class Meta:
        ordering = ["-points"]
        verbose_name = "Criterio de rúbrica"
        verbose_name_plural = "Criterios de rúbrica"

    def __str__(self):
        return f"{self.category.name} - {self.points} puntos"


class RubricItem(models.Model):
    name = models.CharField(max_length=100)
    order = models.IntegerField()

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

    class Meta:
        unique_together = ["student", "evaluation_item"]
        ordering = ["-date_evaluated"]

    def __str__(self):
        return f"{self.student} - {self.evaluation_item}: {self.score}"


class RubricScore(models.Model):
    """Puntuación de un estudiante en una categoría específica de la rúbrica"""
    evaluation = models.ForeignKey(
        Evaluation, 
        on_delete=models.CASCADE, 
        related_name="rubric_scores"
    )
    category = models.ForeignKey(
        RubricCategory, 
        on_delete=models.CASCADE, 
        related_name="scores"
    )
    points = models.PositiveSmallIntegerField()
    
    class Meta:
        unique_together = ["evaluation", "category"]
        
    def __str__(self):
        return f"{self.evaluation.student} - {self.category.name}: {self.points} puntos"
