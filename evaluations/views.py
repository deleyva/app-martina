from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
import random

from .models import Student, EvaluationItem, RubricCategory, Evaluation, RubricScore

class EvaluationItemListView(ListView):
    model = EvaluationItem
    template_name = 'evaluations/item_list.html'
    context_object_name = 'items'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['groups'] = Student.objects.values_list('group', flat=True).distinct()
        return context

@require_http_methods(["GET"])
def select_students(request, item_id):
    item = get_object_or_404(EvaluationItem, id=item_id)
    group = request.GET.get('group')
    
    if not group:
        return HttpResponse("Se requiere especificar un grupo", status=400)
    
    # Get students without evaluation for this item
    available_students = Student.objects.filter(
        group=group
    ).exclude(
        evaluations__evaluation_item=item
    ).select_related('user')  # Añadimos select_related para optimizar las consultas
    
    if not available_students:
        return HttpResponse(
            render_to_string('evaluations/partials/no_students.html'),
            status=200
        )
    
    # Randomly select students
    selected_students = random.sample(list(available_students), min(3, len(available_students)))
    
    # Mark them as pending evaluation
    for student in selected_students:
        student.pending_evaluation = item
        student.save()
    
    return HttpResponse(
        render_to_string(
            'evaluations/partials/selected_students.html',
            {'students': selected_students}
        )
    )

class PendingEvaluationsView(ListView):
    template_name = 'evaluations/pending_evaluations.html'
    context_object_name = 'students'
    
    def get_queryset(self):
        queryset = Student.objects.filter(pending_evaluation__isnull=False).select_related('user')  # Añadimos select_related
        if group := self.request.GET.get('group'):
            queryset = queryset.filter(group=group)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # No pasamos las categorías de rúbrica aquí, las pasaremos en la plantilla para cada estudiante
        context['groups'] = Student.objects.values_list('group', flat=True).distinct()
        context['selected_group'] = self.request.GET.get('group')
        
        # Preparar un diccionario con las rúbricas para cada estudiante
        student_rubrics = {}
        for student in context['students']:
            if student.pending_evaluation:
                student_rubrics[student.id] = RubricCategory.objects.filter(
                    evaluation_item=student.pending_evaluation
                ).order_by('order')
        
        context['student_rubrics'] = student_rubrics
        return context

@require_http_methods(["POST"])
def save_evaluation(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    item = student.pending_evaluation
    
    # Check if direct score was provided
    if direct_score := request.POST.get('direct_score'):
        try:
            score = float(direct_score)
            if 0 <= score <= 10:
                # Crear evaluación con puntuación directa
                evaluation = Evaluation.objects.create(
                    student=student,
                    evaluation_item=item,
                    score=score
                )
            else:
                return HttpResponse("La nota debe estar entre 0 y 10", status=400)
        except ValueError:
            return HttpResponse("La nota debe ser un número válido", status=400)
    else:
        # Crear evaluación con puntuación inicial 0
        evaluation = Evaluation.objects.create(
            student=student,
            evaluation_item=item,
            score=0  # Se actualizará después de guardar las puntuaciones de la rúbrica
        )
        
        # Guardar puntuaciones de la rúbrica
        rubric_categories = RubricCategory.objects.filter(evaluation_item=item).order_by('order')
        for category in rubric_categories:
            points_value = request.POST.get(f'rubric_{category.order}', '0')
            try:
                points = float(points_value)
                # Asegurarse de que los puntos estén en el rango correcto
                if 0 <= points <= category.max_points:
                    RubricScore.objects.create(
                        evaluation=evaluation,
                        category=category,
                        points=points
                    )
            except ValueError:
                # Si hay un error, asignar 0 puntos
                RubricScore.objects.create(
                    evaluation=evaluation,
                    category=category,
                    points=0
                )
        
        # Calcular y actualizar la puntuación total
        total_score = evaluation.calculate_score()
        evaluation.score = total_score
        evaluation.save()
    
    # Clear pending evaluation
    student.pending_evaluation = None
    student.save()
    
    # Get remaining students with the same group filter if it was applied
    remaining_query = Student.objects.filter(pending_evaluation__isnull=False)
    if group := request.GET.get('group'):
        remaining_query = remaining_query.filter(group=group)
    
    # Preparar un diccionario con las rúbricas para cada estudiante
    student_rubrics = {}
    for student in remaining_query:
        if student.pending_evaluation:
            student_rubrics[student.id] = RubricCategory.objects.filter(
                evaluation_item=student.pending_evaluation
            ).order_by('order')
    
    return HttpResponse(
        render_to_string(
            'evaluations/partials/evaluation_list.html',
            {
                'students': remaining_query,
                'student_rubrics': student_rubrics
            }
        )
    )
