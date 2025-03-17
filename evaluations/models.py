from django.db import models

# Create your models here.

class EvaluationItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class Student(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    group = models.CharField(max_length=50)
    pending_evaluation = models.ForeignKey(EvaluationItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='pending_students')
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class RubricItem(models.Model):
    name = models.CharField(max_length=100)
    order = models.IntegerField()
    
    def __str__(self):
        return self.name

class Evaluation(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='evaluations')
    evaluation_item = models.ForeignKey(EvaluationItem, on_delete=models.CASCADE, related_name='evaluations')
    score = models.DecimalField(max_digits=4, decimal_places=2)
    date_evaluated = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['student', 'evaluation_item']
        ordering = ['-date_evaluated']

    def __str__(self):
        return f"{self.student} - {self.evaluation_item}: {self.score}"
