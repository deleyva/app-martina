from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
import random
from django.db.models import F, Q
from decimal import Decimal, InvalidOperation

from .models import (
    Student,
    EvaluationItem,
    RubricCategory,
    Evaluation,
    RubricScore,
    PendingEvaluationStatus,
)


class EvaluationItemListView(ListView):
    model = EvaluationItem
    template_name = "evaluations/item_list.html"
    context_object_name = "items"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["groups"] = Student.objects.values_list("group", flat=True).distinct().order_by("group")
        return context


@require_http_methods(["GET"])
def select_students(request, item_id):
    item = get_object_or_404(EvaluationItem, id=item_id)
    group = request.GET.get("group")

    if not group:
        return HttpResponse("Se requiere especificar un grupo", status=400)

    # Get students without evaluation for this item
    available_students = (
        Student.objects.filter(group=group)
        .exclude(evaluations__evaluation_item=item)
        .select_related("user")
    )  # Añadimos select_related para optimizar las consultas

    if not available_students:
        return HttpResponse(
            render_to_string("evaluations/partials/no_students.html"), status=200
        )

    # Randomly select students
    selected_students = random.sample(
        list(available_students), min(3, len(available_students))
    )

    # Mark them as pending evaluation
    for student in selected_students:
        student.pending_evaluation = item
        student.save()

    return HttpResponse(
        render_to_string(
            "evaluations/partials/selected_students.html",
            {"students": selected_students},
        )
    )


class PendingEvaluationsView(ListView):
    template_name = "evaluations/pending_evaluations.html"
    context_object_name = "students"

    def get_queryset(self):
        queryset = Student.objects.filter(
            pending_evaluation__isnull=False
        ).select_related("user").prefetch_related('pending_statuses')

        # Filtrar por grupo si se especifica
        if group := self.request.GET.get("group"):
            queryset = queryset.filter(group=group)

        # Por defecto, excluir estudiantes que tienen evaluaciones con classroom_submission=True
        show_classroom = self.request.GET.get("show_classroom") == "true"
        if not show_classroom:
            # Excluir estudiantes que tienen un estado de evaluación pendiente con classroom_submission=True
            queryset = queryset.exclude(
                pending_statuses__evaluation_item=F("pending_evaluation"),
                pending_statuses__classroom_submission=True,
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # No pasamos las categorías de rúbrica aquí, las pasaremos en la plantilla para cada estudiante
        context["groups"] = Student.objects.values_list("group", flat=True).distinct().order_by("group")
        context["selected_group"] = self.request.GET.get("group")
        context["show_classroom"] = self.request.GET.get("show_classroom") == "true"

        # Preparar un diccionario con las rúbricas para cada estudiante
        student_rubrics = {}
        for student in context["students"]:
            if student.pending_evaluation:
                student_rubrics[student.id] = RubricCategory.objects.filter(
                    evaluation_item=student.pending_evaluation
                ).order_by("order")

        context["student_rubrics"] = student_rubrics
        return context


@require_http_methods(["POST"])
def save_evaluation(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    item = student.pending_evaluation
    direct_score = request.POST.get("direct_score")
    classroom_submission = request.POST.get("classroom_submission") == "on"
    max_score = request.POST.get("max_score", "10")

    if not direct_score:
        return HttpResponse("No se ha proporcionado una puntuación", status=400)

    # Convertir a decimal
    try:
        direct_score = Decimal(direct_score)
        max_score = Decimal(max_score)
    except InvalidOperation:
        return HttpResponse("La puntuación debe ser un número", status=400)

    # Verificar si existe un estado de evaluación pendiente con classroom_submission
    pending_status = PendingEvaluationStatus.objects.filter(
        student=student, evaluation_item=item
    ).first()

    # Si existe un estado pendiente, usar su valor de classroom_submission
    if pending_status:
        classroom_submission = pending_status.classroom_submission

    # Aplicar penalización si es entrega por classroom
    if classroom_submission and direct_score > 1:
        direct_score = max(1, direct_score - 1)  # Restar 1 punto pero no bajar de 1

    # Guardar la evaluación
    evaluation, created = Evaluation.objects.update_or_create(
        student=student,
        evaluation_item=item,
        defaults={
            "score": direct_score,
            "classroom_submission": classroom_submission,
            "max_score": max_score,
        },
    )

    # Procesar las puntuaciones de la rúbrica
    categories = RubricCategory.objects.filter(evaluation_item=item)
    for category in categories:
        points = request.POST.get(f"category_{category.id}")
        if points:
            RubricScore.objects.update_or_create(
                evaluation=evaluation,
                category=category,
                defaults={"points": Decimal(points)},
            )

    # Eliminar el estado de evaluación pendiente si existe
    if pending_status:
        pending_status.delete()

    # Eliminar la evaluación pendiente del estudiante
    student.pending_evaluation = None
    student.save()

    return redirect("pending_evaluations")


@require_http_methods(["POST"])
def toggle_classroom_submission(request, student_id):
    """Actualiza el estado de classroom_submission para un estudiante pendiente de evaluación"""
    student = get_object_or_404(Student, id=student_id)
    item = student.pending_evaluation

    if not item:
        return HttpResponse(
            "Este estudiante no tiene una evaluación pendiente", status=400
        )

    # Buscar o crear un registro de estado para esta evaluación pendiente
    status, created = PendingEvaluationStatus.objects.get_or_create(
        student=student, evaluation_item=item, defaults={"classroom_submission": True}
    )

    # Si el estado ya existía, actualizar el campo classroom_submission
    if not created:
        status.classroom_submission = True
        status.save()

    return HttpResponse(status=200)
