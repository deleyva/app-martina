from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
import random

from .models import Student, EvaluationItem, RubricItem, Evaluation

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
        evaluations__evaluation_item=item  # Changed from evaluation to evaluations
    )
    
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
        queryset = Student.objects.filter(pending_evaluation__isnull=False)
        if group := self.request.GET.get('group'):
            queryset = queryset.filter(group=group)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['rubric_items'] = RubricItem.objects.all().order_by('order')
        context['groups'] = Student.objects.values_list('group', flat=True).distinct()
        context['selected_group'] = self.request.GET.get('group')
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
                total_score = score
            else:
                return HttpResponse("La nota debe estar entre 0 y 10", status=400)
        except ValueError:
            return HttpResponse("La nota debe ser un número válido", status=400)
    else:
        # Calculate total score from rubric items
        total_score = sum(int(request.POST.get(f'rubric_{i}', 0)) for i in range(1, 6)) * 2
    
    # Save to database
    Evaluation.objects.create(
        student=student,
        evaluation_item=item,
        score=total_score
    )
    
    # Clear pending evaluation
    student.pending_evaluation = None
    student.save()
    
    # Get remaining students with the same group filter if it was applied
    remaining_query = Student.objects.filter(pending_evaluation__isnull=False)
    if group := request.GET.get('group'):
        remaining_query = remaining_query.filter(group=group)
    
    return HttpResponse(
        render_to_string(
            'evaluations/partials/evaluation_list.html',
            {
                'students': remaining_query,
                'rubric_items': RubricItem.objects.all().order_by('order')
            }
        )
    )
