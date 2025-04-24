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
    """Selecciona aleatoriamente estudiantes para una evaluación"""
    item = get_object_or_404(EvaluationItem, id=item_id)
    group = request.GET.get("group")
    num_students = request.GET.get("num_students", "3")  # Valor por defecto: 3
    
    # Convertir num_students a entero
    try:
        num_students = int(num_students)
        # Limitar entre 1 y 10 estudiantes
        num_students = max(1, min(10, num_students))
    except (ValueError, TypeError):
        num_students = 3  # Valor por defecto si hay error

    if not group:
        return HttpResponse("Se requiere especificar un grupo", status=400)

    # Get students without evaluation for this item
    available_students = (
        Student.objects.filter(group=group)
        .exclude(evaluations__evaluation_item=item)
        .exclude(pending_statuses__evaluation_item=item)  # Excluir los que ya tienen un estado pendiente
        .select_related("user")
    )

    if not available_students:
        return HttpResponse(
            render_to_string("evaluations/partials/no_students.html"), status=200
        )

    # Randomly select students
    selected_students = random.sample(
        list(available_students), min(num_students, len(available_students))
    )

    # Mark them as pending evaluation
    for student in selected_students:
        PendingEvaluationStatus.objects.create(
            student=student,
            evaluation_item=item,
            classroom_submission=False
        )

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
        # Obtener parámetros de la solicitud
        group = self.request.GET.get("group")
        show_classroom = self.request.GET.get("show_classroom") == "true"

        # Usar el método del modelo para obtener los estudiantes pendientes
        pending_statuses = PendingEvaluationStatus.get_pending_students(
            group=group,
            include_classroom=show_classroom
        )

        # Extraer los estudiantes únicos de los estados pendientes
        students = []
        student_ids = set()
        for status in pending_statuses:
            if status.student.id not in student_ids:
                students.append(status.student)
                student_ids.add(status.student.id)

        return students

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["groups"] = Student.objects.values_list("group", flat=True).distinct().order_by("group")
        context["selected_group"] = self.request.GET.get("group")
        context["show_classroom"] = self.request.GET.get("show_classroom") == "true"

        # Preparar un diccionario con las rúbricas y estados pendientes para cada estudiante
        student_rubrics = {}
        student_pending_items = {}

        for student in context["students"]:
            # Obtener todos los estados pendientes para este estudiante
            pending_statuses = PendingEvaluationStatus.objects.filter(
                student=student
            ).select_related('evaluation_item')

            # Guardar los items de evaluación pendientes para este estudiante
            student_pending_items[student.id] = [status.evaluation_item for status in pending_statuses]

            # Para cada item pendiente, obtener sus categorías de rúbrica
            for status in pending_statuses:
                if status.evaluation_item:
                    student_rubrics.setdefault(student.id, {})
                    student_rubrics[student.id][status.evaluation_item.id] = RubricCategory.objects.filter(
                        evaluation_item=status.evaluation_item
                    ).order_by('order')

        context["student_rubrics"] = student_rubrics
        context["student_pending_items"] = student_pending_items
        return context


@require_http_methods(["POST"])
def save_evaluation(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    evaluation_item_id = request.POST.get('evaluation_item_id')
    
    if not evaluation_item_id:
        return HttpResponse("No se ha especificado un item de evaluación", status=400)
        
    evaluation_item = get_object_or_404(EvaluationItem, id=evaluation_item_id)
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
        student=student, evaluation_item=evaluation_item
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
        evaluation_item=evaluation_item,
        defaults={
            "score": direct_score,
            "classroom_submission": classroom_submission,
            "max_score": max_score,
        },
    )

    # Procesar las puntuaciones de la rúbrica
    categories = RubricCategory.objects.filter(evaluation_item=evaluation_item)
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

    # Verificar si la solicitud viene de HTMX
    if request.headers.get('HX-Request') == 'true':
        # Si es una solicitud HTMX, devolver solo el fragmento HTML necesario
        group = request.GET.get('group')
        show_classroom = request.GET.get('show_classroom') == 'true'
        
        # Obtener los estudiantes pendientes para actualizar la vista
        pending_statuses = PendingEvaluationStatus.get_pending_students(
            group=group,
            include_classroom=show_classroom
        )
        
        # Extraer los estudiantes únicos
        students = []
        student_ids = set()
        for status in pending_statuses:
            if status.student.id not in student_ids:
                students.append(status.student)
                student_ids.add(status.student.id)
        
        # Preparar el contexto para la respuesta HTMX
        context = {
            "students": students,
            "groups": Student.objects.values_list("group", flat=True).distinct().order_by("group"),
            "selected_group": group,
            "show_classroom": show_classroom
        }
        
        # Preparar un diccionario con las rúbricas y estados pendientes para cada estudiante
        student_rubrics = {}
        student_pending_items = {}

        for student in students:
            # Obtener todos los estados pendientes para este estudiante
            pending_statuses = PendingEvaluationStatus.objects.filter(
                student=student
            ).select_related('evaluation_item')

            # Guardar los items de evaluación pendientes para este estudiante
            student_pending_items[student.id] = [status.evaluation_item for status in pending_statuses]

            # Para cada item pendiente, obtener sus categorías de rúbrica
            for status in pending_statuses:
                if status.evaluation_item:
                    student_rubrics.setdefault(student.id, {})
                    student_rubrics[student.id][status.evaluation_item.id] = RubricCategory.objects.filter(
                        evaluation_item=status.evaluation_item
                    ).order_by('order')

        context["student_rubrics"] = student_rubrics
        context["student_pending_items"] = student_pending_items
        
        # Si no hay estudiantes pendientes, mostrar un mensaje
        if not students:
            return HttpResponse(
                "<div class='alert alert-info'><div class='flex items-center'>"
                "<svg xmlns='http://www.w3.org/2000/svg' class='stroke-current flex-shrink-0 h-6 w-6 mr-2' fill='none' viewBox='0 0 24 24'><path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' /></svg>"
                "<span>No hay evaluaciones pendientes.</span>"
                "</div></div>"
            )
        
        return HttpResponse(
            render_to_string("evaluations/partials/evaluation_list.html", context, request=request)
        )
    else:
        # Si no es HTMX, redirigir a la página completa
        return redirect("pending_evaluations")


@require_http_methods(["POST"])
def toggle_classroom_submission(request, student_id):
    """Actualiza el estado de classroom_submission para un estudiante pendiente de evaluación"""
    student = get_object_or_404(Student, id=student_id)
    evaluation_item_id = request.POST.get('evaluation_item_id')
    is_checked = request.POST.get('is_checked') == 'true'
    
    if not evaluation_item_id:
        return HttpResponse("No se ha especificado un item de evaluación", status=400)
    
    evaluation_item = get_object_or_404(EvaluationItem, id=evaluation_item_id)
    
    # Buscar o crear un registro de estado para esta evaluación pendiente
    status, created = PendingEvaluationStatus.objects.update_or_create(
        student=student,
        evaluation_item=evaluation_item,
        defaults={
            'classroom_submission': is_checked
        }
    )
    
    return HttpResponse(status=200)


@require_http_methods(["GET"])
def search_students(request):
    """Busca estudiantes por nombre o apellido"""
    query = request.GET.get('query', '').strip()
    item_id = request.GET.get('item_id')  # Obtener el ID del ítem
    
    if not query or len(query) < 3:
        return HttpResponse("Se requieren al menos 3 caracteres para la búsqueda", status=400)
    
    # Buscar estudiantes por nombre o apellido
    students = Student.objects.filter(
        Q(user__name__icontains=query)
    ).select_related('user')[:10]  # Limitar a 10 resultados
    
    # Pasar el contexto a la plantilla con el ID del ítem
    context = {
        "students": students,
        "item_id": item_id
    }
    
    return HttpResponse(
        render_to_string(
            "evaluations/partials/student_search_results.html",
            context,
            request=request  # Pasar el objeto request para acceder a request.GET en la plantilla
        )
    )


@require_http_methods(["POST"])
def add_student_to_pending(request):
    """Añade un estudiante específico a una evaluación pendiente"""
    student_id = request.POST.get('student_id')
    item_id = request.POST.get('item_id')
    
    print(f"Solicitud recibida para añadir estudiante {student_id} al item {item_id}")
    print(f"POST data: {request.POST}")
    
    if not student_id or not item_id:
        error_msg = f"Se requieren el ID del estudiante y el ID del ítem. Recibido: student_id={student_id}, item_id={item_id}"
        print(error_msg)
        return HttpResponse(error_msg, status=400)
    
    try:
        student = get_object_or_404(Student, id=student_id)
        item = get_object_or_404(EvaluationItem, id=item_id)
        
        print(f"Estudiante encontrado: {student.user.name}, Item: {item.name}")
        
        # Verificar si el estudiante ya tiene esta evaluación o está pendiente
        if Evaluation.objects.filter(student=student, evaluation_item=item).exists():
            error_msg = f"El estudiante {student.user.name} ya tiene una evaluación para el ítem {item.name}"
            print(error_msg)
            return HttpResponse(error_msg, status=400)
        
        # Verificar si ya está pendiente
        if PendingEvaluationStatus.objects.filter(student=student, evaluation_item=item).exists():
            error_msg = f"El estudiante {student.user.name} ya está pendiente para el ítem {item.name}"
            print(error_msg)
            return HttpResponse(error_msg, status=400)
        
        # Añadir a pendiente
        pending_status = PendingEvaluationStatus.objects.create(
            student=student,
            evaluation_item=item,
            classroom_submission=False
        )
        
        print(f"Estudiante añadido correctamente a evaluaciones pendientes con ID: {pending_status.id}")
        
        return HttpResponse(
            render_to_string(
                "evaluations/partials/student_added_confirmation.html",
                {"student": student, "item": item}
            )
        )
    except Exception as e:
        error_msg = f"Error al añadir estudiante: {str(e)}"
        print(error_msg)
        print(f"Detalles del error: {e.__class__.__name__}")
        import traceback
        traceback.print_exc()
        return HttpResponse(error_msg, status=500)
