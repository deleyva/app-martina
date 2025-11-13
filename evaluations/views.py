from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, View
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
import random
from django.db.models import F, Q
from django.db import DatabaseError
from django.core.exceptions import ObjectDoesNotExist
from decimal import Decimal, InvalidOperation
import os
import re

# Intentar importar google-genai, pero no fallar si no está disponible
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False

from .models import (
    Group,
    Student,
    EvaluationItem,
    RubricCategory,
    Evaluation,
    RubricScore,
    PendingEvaluationStatus,
    GroupLibraryItem,
    ClassSession,
    ClassSessionItem,
)
from .submission_models import ClassroomSubmission
from django.contrib.contenttypes.models import ContentType
import json


# Helper function to check if user is staff
def is_staff(user):
    return user.is_staff


class EvaluationItemListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = EvaluationItem
    template_name = "evaluations/item_list.html"
    context_object_name = "items"
    login_url = "/accounts/login/"

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        messages.error(
            self.request, "Solo el personal autorizado puede acceder a esta sección."
        )
        return redirect("home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["groups"] = (
            Student.objects.values_list("group", flat=True).distinct().order_by("group")
        )
        return context


@require_http_methods(["GET"])
@login_required
@user_passes_test(is_staff, login_url="/accounts/login/", redirect_field_name=None)
def select_students(request, item_id):
    """Selecciona aleatoriamente estudiantes para una evaluación"""
    item = get_object_or_404(EvaluationItem, id=item_id)
    group = request.GET.get("group")
    num_students = request.GET.get("num_students", "3")  # Valor por defecto: 3

    # Convertir num_students a entero
    try:
        num_students = int(num_students)
        # Limitar entre 1 y 25 estudiantes
        num_students = max(1, min(25, num_students))
    except (ValueError, TypeError):
        num_students = 3  # Valor por defecto si hay error

    if not group:
        return HttpResponse("Se requiere especificar un grupo", status=400)

    # Get students without evaluation for this item
    available_students = (
        Student.objects.filter(group=group)
        .exclude(evaluations__evaluation_item=item)
        .exclude(
            pending_statuses__evaluation_item=item
        )  # Excluir los que ya tienen un estado pendiente
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
        # Si force_web_submission está activado, aseguramos que classroom_submission sea True
        classroom_submission = False
        if item.force_web_submission:
            # Si se fuerza entrega por web, establecer classroom_submission a True
            classroom_submission = True
            
        PendingEvaluationStatus.objects.create(
            student=student, 
            evaluation_item=item, 
            classroom_submission=classroom_submission
        )

    return HttpResponse(
        render_to_string(
            "evaluations/partials/selected_students.html",
            {"students": selected_students},
        )
    )


class PendingEvaluationsTableView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "evaluations/pending_table.html"
    context_object_name = "students"
    login_url = "/accounts/login/"

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        messages.error(
            self.request, "Solo el personal autorizado puede acceder a esta sección."
        )
        return redirect("home")

    def get_queryset(self):
        query = Student.objects.filter(pending_statuses__isnull=False).distinct().select_related("user")

        # Filtro por grupo si está presente
        group = self.request.GET.get("group")
        if group:
            query = query.filter(group=group)

        # Filtro por estado de classroom_submission
        show_classroom = self.request.GET.get("show_classroom", "true")
        if show_classroom.lower() != "true":
            query = query.filter(
                pending_statuses__classroom_submission=False
            )

        # Filtro por evaluation_item si está presente
        evaluation_item_id = self.request.GET.get("evaluation_item")
        if evaluation_item_id:
            query = query.filter(pending_statuses__evaluation_item_id=evaluation_item_id)

        return query.order_by("group", F("user__name").asc(nulls_last=True))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Parámetros de filtrado
        group = self.request.GET.get("group")
        evaluation_item_id = self.request.GET.get("evaluation_item")
        show_classroom = self.request.GET.get("show_classroom", "true")

        # Obtener todos los estados pendientes que coincidan con los filtros
        pending_query = PendingEvaluationStatus.objects.select_related(
            "student", "student__user", "evaluation_item"
        ).prefetch_related(
            "submission", "submission__videos", "submission__images"
        )
        
        if group:
            pending_query = pending_query.filter(student__group=group)
        
        if show_classroom.lower() != "true":
            pending_query = pending_query.filter(classroom_submission=False)
            
        if evaluation_item_id:
            pending_query = pending_query.filter(evaluation_item_id=evaluation_item_id)
            
        # Lista de estados pendientes para la tabla
        context["pending_statuses"] = pending_query.order_by(
            "student__group", F("student__user__name").asc(nulls_last=True), "evaluation_item__name"
        )
        
        # Listados para los filtros
        context["groups"] = Student.objects.values_list("group", flat=True).distinct().order_by("group")
        context["evaluation_items"] = EvaluationItem.objects.all().order_by("name")
        
        # Parámetros actuales para la construcción de URLs
        context["selected_group"] = group
        context["selected_evaluation_item"] = evaluation_item_id
        context["show_classroom"] = show_classroom.lower() == "true"
        
        return context


class StudentEvaluationDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "evaluations/student_evaluation_detail.html"
    login_url = "/accounts/login/"
    
    def test_func(self):
        return self.request.user.is_staff
        
    def handle_no_permission(self):
        messages.error(
            self.request, "Solo el personal autorizado puede acceder a esta sección."
        )
        return redirect("home")
    
    def get(self, request, student_id, evaluation_item_id):
        try:
            student = get_object_or_404(Student, id=student_id)
            evaluation_item = get_object_or_404(EvaluationItem, id=evaluation_item_id)
            
            # Verificar que exista un estado pendiente para este estudiante y evaluación
            pending_status = get_object_or_404(
                PendingEvaluationStatus, student=student, evaluation_item=evaluation_item
            )
            
            # Intentar encontrar la entrega (submission) asociada directamente desde PendingEvaluationStatus
            try:
                # Log de información inicial
                print(f"Buscando submission para student_id={student_id}, evaluation_item_id={evaluation_item_id}")
                print(f"PendingEvaluationStatus ID: {pending_status.id if pending_status else 'No encontrado'}")
                
                # Intentamos obtener la submission con todas sus relaciones precargas para un mejor rendimiento
                submissions = ClassroomSubmission.objects.filter(
                    pending_status=pending_status
                ).prefetch_related('videos', 'images')
                
                submission = submissions.first()
                print(f"Método 1 - Submission encontrada: {submission is not None}")
                
                # Si no se encuentra, intentar con la relación inversa
                if not submission:
                    print("Intentando búsqueda alternativa por relación inversa")
                    submissions = ClassroomSubmission.objects.filter(
                        pending_status__student=student, 
                        pending_status__evaluation_item=evaluation_item
                    ).prefetch_related('videos', 'images')
                    
                    submission = submissions.first()
                    print(f"Método 2 - Submission encontrada: {submission is not None}")
                
                # Información detallada sobre la submission si existe
                if submission:
                    print(f"Submission ID: {submission.id}")
                    print(f"Videos: {submission.videos.count()}, Imágenes: {submission.images.count()}, Notas: {'Sí' if submission.notes else 'No'}")
                    
                    # Listar detalles de cada archivo para depuración
                    if submission.images.count() > 0:
                        print("Detalle de imágenes:")
                        for i, image in enumerate(submission.images.all()):
                            print(f"  - Imagen {i+1}: {image.original_filename}, URL: {image.image.url if image.image else 'Sin imagen'}")
                else:
                    print("¡ALERTA! No se encontró ninguna submission asociada")
            except ObjectDoesNotExist as e:
                print(f"Error: Objeto no encontrado - {str(e)}")
                submission = None
            except Exception as e:
                print(f"Error crítico al cargar submission: {type(e).__name__}: {str(e)}")
                submission = None
            
            # Obtener todas las categorías de rúbrica para esta evaluación
            rubric_categories = RubricCategory.objects.filter(
                evaluation_item=evaluation_item
            ).order_by("order")
            
            # Obtener evaluación existente si la hay
            existing_evaluation = Evaluation.objects.filter(
                student=student,
                evaluation_item=evaluation_item
            ).first()
            
            context = {
                "student": student,
                "evaluation_item": evaluation_item,
                "pending_status": pending_status,
                "submission": submission,  # Pasar la submission directamente al contexto
                "rubric_categories": rubric_categories,
                "existing_evaluation": existing_evaluation
            }
        except (ObjectDoesNotExist, DatabaseError) as e:
            messages.error(request, f"Error al cargar los datos de evaluación: {str(e)}")
            return redirect('pending_evaluations_table')
            
        except Exception as e:
            print(f"Error crítico al cargar detalles de evaluación: {type(e).__name__}: {str(e)}")
            messages.error(request, "Ha ocurrido un error al cargar los datos de evaluación")
            return redirect('pending_evaluations_table')
        
        return render(request, self.template_name, context)


class PendingEvaluationsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "evaluations/pending_evaluations.html"
    context_object_name = "students"
    login_url = "/accounts/login/"

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        messages.error(
            self.request, "Solo el personal autorizado puede acceder a esta sección."
        )
        return redirect("home")

    def get_queryset(self):
        # Obtener parámetros de la solicitud
        group = self.request.GET.get("group")
        show_classroom = self.request.GET.get("show_classroom") == "true"
        evaluation_item_id = self.request.GET.get("evaluation_item")

        # Construir una consulta para obtener students con evaluaciones pendientes
        query = (
            Student.objects.filter(pending_statuses__isnull=False)
            .distinct()
            .select_related("user")
        )

        # Aplicar filtros según los parámetros
        if group:
            query = query.filter(group=group)

        if not show_classroom:
            query = query.filter(pending_statuses__classroom_submission=False)

        if evaluation_item_id:
            query = query.filter(
                pending_statuses__evaluation_item_id=evaluation_item_id
            )

        return query

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["groups"] = (
            Student.objects.values_list("group", flat=True).distinct().order_by("group")
        )
        context["selected_group"] = self.request.GET.get("group")
        context["show_classroom"] = self.request.GET.get("show_classroom") == "true"
        context["evaluation_items"] = EvaluationItem.objects.all().order_by("name")
        context["selected_evaluation_item"] = self.request.GET.get("evaluation_item")

        # Get group and classroom filter parameters
        group = self.request.GET.get("group")
        show_classroom = self.request.GET.get("show_classroom") == "true"
        evaluation_item_id = self.request.GET.get("evaluation_item")

        # Fetch all pending statuses directly with proper filtering
        pending_query = PendingEvaluationStatus.objects.select_related(
            "student", "student__user", "evaluation_item"
        )

        if group:
            pending_query = pending_query.filter(student__group=group)

        if not show_classroom:
            pending_query = pending_query.filter(classroom_submission=False)

        if evaluation_item_id:
            pending_query = pending_query.filter(evaluation_item_id=evaluation_item_id)

        # Process all pending evaluations
        student_rubrics = {}
        student_pending_items = {}

        for status in pending_query:
            student_id = status.student.id

            # Initialize dictionaries for this student if not already done
            student_pending_items.setdefault(student_id, [])
            student_rubrics.setdefault(student_id, {})

            # Add this evaluation item to the student's pending items if not already there
            if not any(
                item.id == status.evaluation_item.id
                for item in student_pending_items[student_id]
            ):
                student_pending_items[student_id].append(status.evaluation_item)

            # Get rubric categories for this evaluation item
            student_rubrics[student_id][status.evaluation_item.id] = (
                RubricCategory.objects.filter(
                    evaluation_item=status.evaluation_item
                ).order_by("order")
            )

        context["student_rubrics"] = student_rubrics
        context["student_pending_items"] = student_pending_items
        return context


@login_required
@user_passes_test(is_staff)
def teacher_view_student_dashboard(request, student_id):
    """
    Dashboard view for teachers to see a specific student's dashboard.
    """
    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        messages.error(request, "El estudiante solicitado no existe.")
        return redirect('pending_evaluations')

    # Get all evaluations for this student
    evaluations = Evaluation.objects.filter(student=student).select_related('evaluation_item')
    
    # Get pending submissions
    pending_statuses = PendingEvaluationStatus.objects.filter(student=student).select_related('evaluation_item')
    
    # Group evaluations by term
    evaluations_by_term = {}
    for evaluation in evaluations:
        term = evaluation.evaluation_item.term or 'Sin periodo'
        if term not in evaluations_by_term:
            evaluations_by_term[term] = []
        evaluations_by_term[term].append(evaluation)
    
    # Check which pending items have submissions
    has_submission = {}
    for status in pending_statuses:
        has_submission[status.id] = hasattr(status, 'submission')
    
    context = {
        'student': student,
        'evaluations_by_term': evaluations_by_term,
        'pending_statuses': pending_statuses,
        'has_submission': has_submission,
        'viewing_as_teacher': True, # Flag to indicate teacher view
    }
    
    return render(request, 'evaluations/student_dashboard.html', context)

@require_http_methods(["POST"])
@login_required
@user_passes_test(is_staff, login_url="/accounts/login/", redirect_field_name=None)
def save_evaluation(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    evaluation_item_id = request.POST.get("evaluation_item_id") or request.GET.get("evaluation_item_id")

    if not evaluation_item_id:
        return HttpResponse("No se ha especificado un item de evaluación", status=400)

    evaluation_item = get_object_or_404(EvaluationItem, id=evaluation_item_id)
    classroom_submission_str = request.POST.get("classroom_submission") or request.GET.get("classroom_submission", "false")
    classroom_submission = classroom_submission_str.lower() == "true" or request.POST.get("classroom_submission") == "on"
    max_score = request.POST.get("max_score", "10")
    direct_score = request.POST.get("direct_score")

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

    # Si existe un estado pendiente, usar su valor de classroom_submission y feedback
    pending_feedback = ""
    if pending_status:
        classroom_submission = pending_status.classroom_submission
        pending_feedback = pending_status.feedback or ""
        
    # Si force_web_submission está habilitado, forzar classroom_submission a True
    if evaluation_item.force_web_submission:
        classroom_submission = True

    # Aplicar penalización si es entrega por classroom y classroom_reduces_points está habilitado
    if classroom_submission and evaluation_item.classroom_reduces_points and direct_score > 1:
        direct_score = max(1, direct_score - 1)  # Restar 1 punto pero no bajar de 1

    # Obtener la retroalimentación del formulario y combinarla con la pendiente si existe
    feedback_text = request.POST.get("feedback_text", "")

    # Si hay feedback pendiente y no hay nuevo feedback en el formulario, usar el pendiente
    if pending_feedback and not feedback_text:
        feedback_text = pending_feedback
    # Si hay ambos, podríamos mostrar un mensaje informativo
    elif pending_feedback and feedback_text:
        messages.info(
            request,
            "Se ha encontrado retroalimentación guardada previamente y se ha combinado con la nueva.",
        )

    ai_processed = request.POST.get("use_ai_processing") == "on"

    # Procesar la retroalimentación con Gemini si está activado
    final_feedback = feedback_text

    if ai_processed and feedback_text and evaluation_item.ai_prompt:
        # Verificar si la biblioteca está disponible
        if not GEMINI_AVAILABLE:
            messages.warning(
                request,
                "La biblioteca google-genai no está instalada. Ejecuta 'pip install google-genai' para habilitarla.",
            )
        else:
            try:
                # Configurar la API de Gemini
                if os.getenv("GEMINI_API_KEY"):
                    # Configurar genai con la API key
                    api_key = os.getenv("GEMINI_API_KEY")
                    client = genai.Client(api_key=api_key)

                    # Construir el prompt completo
                    prompt = f"{evaluation_item.ai_prompt}\n\nEvaluación original: {feedback_text}"

                    # Generar respuesta
                    response = client.models.generate_content(
                        model='gemini-2.0-flash-001', contents=prompt
                    )

                    # La respuesta es directamente el texto
                    if response:
                        final_feedback = response.text
                    else:
                        messages.warning(
                            request, "No se pudo procesar la retroalimentación con IA."
                        )
                else:
                    messages.warning(
                        request,
                        "No se ha configurado la clave API de Gemini en settings.GEMINI_API_KEY.",
                    )

            except (ValueError, RuntimeError, ConnectionError, TimeoutError) as e:
                messages.error(request, f"Error al procesar con IA: {str(e)}")
            except (KeyError, TypeError, AttributeError) as e:
                # Excepciones de programación más comunes
                messages.error(request, f"Error en el formato de datos de IA: {str(e)}")
                print(f"Error de formato en procesamiento IA: {type(e).__name__}: {str(e)}")
            except DatabaseError as e:
                # Errores específicos de la base de datos
                messages.error(request, f"Error de base de datos en procesamiento IA: {str(e)}")
                print(f"Error de base de datos en procesamiento IA: {type(e).__name__}: {str(e)}")
            except Exception as e:
                # Mantenemos un catch-all final, pero con logging adecuado
                messages.error(request, f"Error inesperado al procesar con IA")
                print(f"Error crítico en procesamiento IA: {type(e).__name__}: {str(e)}")

    # Guardar la evaluación
    evaluation, _ = Evaluation.objects.update_or_create(
        student=student,
        evaluation_item=evaluation_item,
        defaults={
            "score": direct_score,
            "classroom_submission": classroom_submission,
            "max_score": max_score,
            "feedback": final_feedback,
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
    if request.headers.get("HX-Request") == "true":
        # Si es una solicitud HTMX, devolver solo el fragmento HTML necesario
        group = request.GET.get("group")
        show_classroom = request.GET.get("show_classroom") == "true"

        # Obtener los estudiantes pendientes para actualizar la vista
        pending_statuses = PendingEvaluationStatus.get_pending_students(
            group=group, include_classroom=show_classroom
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
            "groups": Student.objects.values_list("group", flat=True)
            .distinct()
            .order_by("group"),
            "selected_group": group,
            "show_classroom": show_classroom,
        }

        # Preparar un diccionario con las rúbricas y estados pendientes para cada estudiante
        student_rubrics = {}
        student_pending_items = {}

        for student in students:
            # Obtener todos los estados pendientes para este estudiante
            pending_statuses = PendingEvaluationStatus.objects.filter(
                student=student
            ).select_related("evaluation_item")

            # Guardar los items de evaluación pendientes para este estudiante
            student_pending_items[student.id] = [
                status.evaluation_item for status in pending_statuses
            ]

            # Para cada item pendiente, obtener sus categorías de rúbrica
            for status in pending_statuses:
                if status.evaluation_item:
                    student_rubrics.setdefault(student.id, {})
                    student_rubrics[student.id][status.evaluation_item.id] = (
                        RubricCategory.objects.filter(
                            evaluation_item=status.evaluation_item
                        ).order_by("order")
                    )

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
            render_to_string(
                "evaluations/partials/evaluation_list.html", context, request=request
            )
        )
    else:
        # Si no es HTMX, redirigir a la página completa
        return redirect("pending_evaluations")


@require_http_methods(["POST"])
@login_required
@user_passes_test(is_staff, login_url="/accounts/login/", redirect_field_name=None)
def toggle_classroom_submission(request, student_id):
    """Actualiza el estado de classroom_submission para un estudiante pendiente de evaluación"""
    student = get_object_or_404(Student, id=student_id)

    # Try to get evaluation_item_id from POST data or from JSON body
    try:
        data = request.POST
        evaluation_item_id = data.get("evaluation_item_id")
        # Obtener el valor del parámetro classroom_submission y convertirlo a booleano
        is_checked = data.get("classroom_submission") == "true"

        # Log for debugging
        print(
            f"Received toggle request for student {student_id}, item {evaluation_item_id}, checked: {is_checked}"
        )
        print(f"POST data: {request.POST}")

    except (ValueError, KeyError, TypeError) as e:
        print(f"Error al procesar datos de la solicitud: {e}")
        return HttpResponse(f"Error en los datos de la solicitud: {e}", status=400)

    if not evaluation_item_id:
        return HttpResponse("No se ha especificado un item de evaluación", status=400)

    try:
        evaluation_item = get_object_or_404(EvaluationItem, id=evaluation_item_id)
        
        # Verificar si el item fuerza entrega por web
        if evaluation_item.force_web_submission and not is_checked:
            return HttpResponse(
                "Este ítem de evaluación requiere entrega por web y debe estar marcado para entrega por classroom",
                status=400
            )

        # Buscar o crear un registro de estado para esta evaluación pendiente específica
        _, _ = PendingEvaluationStatus.objects.update_or_create(
            student=student,
            evaluation_item=evaluation_item,
            defaults={"classroom_submission": is_checked},
        )

        print(
            f"Updated status for student {student.id}, item {evaluation_item.id}, classroom: {is_checked}"
        )

        if request.headers.get("HX-Request"):
            # Si es una solicitud HTMX, devolvemos el HTML del checkbox con su estado actualizado
            checkbox_html = f'''<input 
                type="checkbox" 
                class="toggle toggle-primary" 
                {"checked" if is_checked else ""} 
                hx-post="{reverse('toggle_classroom_submission', args=[student.id])}" 
                hx-vals='{{"evaluation_item_id": "{evaluation_item.id}", "classroom_submission": {"false" if is_checked else "true"}}}' 
                hx-target="#toggle-container-{student.id}-{evaluation_item.id}" 
                hx-swap="innerHTML" 
                hx-trigger="change" 
            />'''
            return HttpResponse(checkbox_html, status=200)
        else:
            return HttpResponse(status=200)
    except (ValueError, TypeError) as e:
        print(f"Error de valor o tipo al actualizar estado: {e}")
        return HttpResponse(f"Error en los datos: {str(e)}", status=400)
    except ObjectDoesNotExist as e:
        print(f"Objeto no encontrado: {e}")
        return HttpResponse(f"Estudiante o evaluación no encontrados", status=404)
    except DatabaseError as e:
        print(f"Error de base de datos: {e}")
        return HttpResponse(f"Error de base de datos", status=500)


@require_http_methods(["GET"])
@login_required
@user_passes_test(is_staff, login_url="/accounts/login/", redirect_field_name=None)
def search_students(request):
    """Busca estudiantes por nombre o apellido"""
    query = request.GET.get("query", "").strip()
    item_id = request.GET.get("item_id")  # Obtener el ID del ítem

    if not query or len(query) < 3:
        return HttpResponse(
            "Se requieren al menos 3 caracteres para la búsqueda", status=400
        )

    # Buscar estudiantes por nombre o apellido
    students = Student.objects.filter(Q(user__name__icontains=query)).select_related(
        "user"
    )[
        :25
    ]  # Limitar a 25 resultados

    # Pasar el contexto a la plantilla con el ID del ítem
    context = {"students": students, "item_id": item_id}

    return HttpResponse(
        render_to_string(
            "evaluations/partials/student_search_results.html",
            context,
            request=request,  # Pasar el objeto request para acceder a request.GET en la plantilla
        )
    )


@require_http_methods(["POST"])
@login_required
@user_passes_test(is_staff, login_url="/accounts/login/", redirect_field_name=None)
def add_student_to_pending(request):
    """Añade un estudiante específico a una evaluación pendiente"""
    student_id = request.POST.get("student_id")
    item_id = request.POST.get("item_id")

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
        if PendingEvaluationStatus.objects.filter(
            student=student, evaluation_item=item
        ).exists():
            error_msg = f"El estudiante {student.user.name} ya está pendiente para el ítem {item.name}"
            print(error_msg)
            return HttpResponse(error_msg, status=400)

        # Añadir a pendiente
        pending_status = PendingEvaluationStatus.objects.create(
            student=student, evaluation_item=item, classroom_submission=False
        )

        print(
            f"Estudiante añadido correctamente a evaluaciones pendientes con ID: {pending_status.id}"
        )

        return HttpResponse(
            render_to_string(
                "evaluations/partials/student_added_confirmation.html",
                {"student": student, "item": item},
            )
        )
    except Exception as e:
        error_msg = f"Error al añadir estudiante: {str(e)}"
        print(error_msg)
        print(f"Detalles del error: {e.__class__.__name__}")
        import traceback

        traceback.print_exc()
        return HttpResponse(error_msg, status=500)


@require_http_methods(["POST"])
@login_required
@user_passes_test(is_staff, login_url="/accounts/login/", redirect_field_name=None)
def process_feedback_with_ai(request):
    """Procesa un texto de retroalimentación con IA y devuelve el resultado"""
    # Obtener el texto y datos de identificación
    feedback_text = request.POST.get("feedback_text", "")
    student_id = request.POST.get("student_id")
    evaluation_item_id = request.POST.get("evaluation_item_id")

    if not feedback_text or not evaluation_item_id:
        return HttpResponse("Se requiere texto y item de evaluación", status=400)

    # Obtener información del estudiante si se proporciona el ID
    # Inicializar variable para el estudiante
    student = None
    if student_id:
        try:
            student = get_object_or_404(Student, id=student_id)
        except (ValueError, TypeError):
            # Si hay algún error con el ID del estudiante, continuamos sin él
            pass

    try:
        # Obtener el item de evaluación que contiene el prompt
        evaluation_item = get_object_or_404(EvaluationItem, id=evaluation_item_id)
        
        # El prompt está en el campo ai_prompt del EvaluationItem
        ai_prompt = evaluation_item.ai_prompt
        
        if not ai_prompt:
            return HttpResponse("No hay prompt configurado para este item", status=400)

        # Procesar con IA
        final_feedback = feedback_text

        # Verificar si la biblioteca está disponible
        if not GEMINI_AVAILABLE:
            return HttpResponse(
                "<div class='text-red-500 mb-2'>La biblioteca google-genai no está instalada.</div>"
                + feedback_text,
                status=200,
            )

        try:
            # Configurar genai con la API key
            if os.getenv("GEMINI_API_KEY"):
                # Configurar genai con la API key
                api_key = os.getenv("GEMINI_API_KEY")
                client = genai.Client(api_key=api_key)

                # Construir el prompt completo
                prompt = f"{evaluation_item.ai_prompt}\n\nEvaluación original: {feedback_text}"

                # Generar respuesta
                response = client.models.generate_content(
                    model='gemini-2.0-flash-001', contents=prompt
                )

                # La respuesta es directamente el texto
                if response:
                    text = response.text
                    
                    # Limpiar el texto para quitar introducciones
                    if '"' in text:
                        # Buscar contenido entre comillas (suponiendo que es el feedback real)
                        quoted_content = re.search(r'"(.+?)"', text, re.DOTALL)
                        if quoted_content:
                            text = quoted_content.group(1)
                    
                    # Buscar patrones de introducción comunes y eliminarlos
                    intro_patterns = [
                        "Okay, here's some assertive and positive feedback",
                        "Here is some feedback",
                        "Here's the feedback",
                        "Here is the feedback",
                        "I would provide this feedback",
                        "Here's my feedback"
                    ]
                    
                    for pattern in intro_patterns:
                        if text.startswith(pattern):
                            text = text[len(pattern):].lstrip(' :,-')
                    
                    # Eliminar "Hi [Student's Name]," o similar al principio
                    text = re.sub(r'^Hi\s+\[?Student(\'s)?\s*Name\]?,\s*', '', text)
                    
                    # Eliminar firma al final como "Thanks, [Student's Name]" o similar
                    text = re.sub(r'Thanks,\s+\[?Student(\'s)?\s*Name\]?!?\s*$', '', text)
                    
                    final_feedback = text.strip()
                else:
                    return HttpResponse(
                        f"<textarea id='feedback-text-{student_id}-{evaluation_item.id}' class='textarea textarea-bordered h-24 w-full' name='feedback_text'>{feedback_text}</textarea>"
                        + "<div class='text-yellow-500 text-sm mt-1'>No se pudo procesar la retroalimentación con IA.</div>",
                        status=200,
                    )
            else:
                return HttpResponse(
                    f"<textarea id='feedback-text-{student_id}-{evaluation_item.id}' class='textarea textarea-bordered h-24 w-full' name='feedback_text'>{feedback_text}</textarea>"
                    + "<div class='text-yellow-500 mb-2'>No se ha configurado la clave API de Google (GOOGLE_API_KEY).</div>",
                    status=200,
                )
        except Exception as e:
            return HttpResponse(
                f"<textarea id='feedback-text-{student_id}-{evaluation_item.id}' class='textarea textarea-bordered h-24 w-full' name='feedback_text'>{feedback_text}</textarea>"
                + f"<div class='text-red-500 mb-2'>Error al procesar con IA: {str(e)}</div>",
                status=200,
            )

        # Guardar el feedback generado en el estado pendiente si existe
        if student_id:
            try:
                pending_status = PendingEvaluationStatus.objects.filter(
                    student_id=student_id, evaluation_item=evaluation_item
                ).first()

                if pending_status:
                    pending_status.feedback = final_feedback
                    pending_status.save()
            except (DatabaseError, ValueError) as e:
                print(f"Error de base de datos al guardar feedback en estado pendiente: {e}")

        # Devolver el texto procesado
        return HttpResponse(
            f"<textarea id='feedback-text-{student_id}-{evaluation_item.id}' class='textarea textarea-bordered h-24 w-full' name='feedback_text'>{final_feedback}</textarea>",
            status=200
        )
    except ObjectDoesNotExist as e:
        return HttpResponse(f"No se encontró el recurso solicitado: {str(e)}", status=404)
    except (ValueError, TypeError) as e:
        return HttpResponse(f"Error en los datos proporcionados: {str(e)}", status=400)
    except (DatabaseError, IOError) as e:
        print(f"Error grave al procesar la solicitud: {type(e).__name__}: {str(e)}")
        return HttpResponse(f"Error en el servidor: {str(e)}", status=500)


# =============================================================================
# VISTAS DE BIBLIOTECA DE GRUPO
# =============================================================================


@login_required
@user_passes_test(is_staff)
def group_library_index(request, group_id):
    """
    Vista principal de la biblioteca del grupo.
    TINY VIEW: solo orquesta y renderiza.
    Solo profesores del grupo pueden acceder.
    """
    group = get_object_or_404(Group, pk=group_id)
    
    # Verificar que el profesor pertenece a este grupo
    if not group.teachers.filter(pk=request.user.pk).exists():
        messages.error(request, "No tienes permiso para acceder a la biblioteca de este grupo.")
        return redirect("evaluations:evaluation_item_list")
    
    items = GroupLibraryItem.objects.filter(group=group)
    
    return render(
        request,
        "evaluations/group_library/index.html",
        {
            "group": group,
            "items": items,
            "total_items": items.count(),
        },
    )


@login_required
@user_passes_test(is_staff)
def group_library_add(request, group_id):
    """
    Endpoint HTMX para añadir item a biblioteca de grupo.
    TINY VIEW: lógica en el modelo (FAT MODEL).
    """
    if request.method == "POST":
        group = get_object_or_404(Group, pk=group_id)
        
        # Verificar que el profesor pertenece a este grupo
        if not group.teachers.filter(pk=request.user.pk).exists():
            return HttpResponse("No autorizado", status=403)
        
        content_type_id = request.POST.get("content_type_id")
        object_id = request.POST.get("object_id")
        notes = request.POST.get("notes", "")

        content_type = get_object_or_404(ContentType, id=content_type_id)
        content_object = content_type.get_object_for_this_type(pk=object_id)

        # Lógica en el modelo (FAT MODEL)
        item, created = GroupLibraryItem.add_to_library(
            group=group,
            content_object=content_object,
            added_by=request.user,
            notes=notes
        )

        # Renderizar botón actualizado (HTMX swap)
        return render(
            request,
            "evaluations/group_library/partials/add_button.html",
            {
                "group": group,
                "content_object": content_object,
                "content_type": content_type,
                "in_library": True,
            },
        )

    return HttpResponse(status=405)


@login_required
@user_passes_test(is_staff)
def group_library_remove(request, group_id, pk):
    """
    Endpoint HTMX para quitar item de biblioteca de grupo por ID.
    TINY VIEW: solo elimina y renderiza.
    """
    group = get_object_or_404(Group, pk=group_id)
    
    # Verificar que el profesor pertenece a este grupo
    if not group.teachers.filter(pk=request.user.pk).exists():
        return HttpResponse("No autorizado", status=403)
    
    item = get_object_or_404(GroupLibraryItem, pk=pk, group=group)
    content_object = item.content_object
    content_type = item.content_type
    item.delete()

    # Renderizar botón actualizado (HTMX swap)
    return render(
        request,
        "evaluations/group_library/partials/add_button.html",
        {
            "group": group,
            "content_object": content_object,
            "content_type": content_type,
            "in_library": False,
        },
    )


@login_required
@user_passes_test(is_staff)
def group_library_remove_by_content(request, group_id):
    """
    Endpoint HTMX para quitar item de biblioteca de grupo por content_type y object_id.
    TINY VIEW: solo elimina y renderiza.
    """
    if request.method in ["POST", "DELETE"]:
        group = get_object_or_404(Group, pk=group_id)
        
        # Verificar que el profesor pertenece a este grupo
        if not group.teachers.filter(pk=request.user.pk).exists():
            return HttpResponse("No autorizado", status=403)
        
        content_type_id = request.POST.get("content_type_id")
        object_id = request.POST.get("object_id")

        content_type = get_object_or_404(ContentType, id=content_type_id)
        content_object = content_type.get_object_for_this_type(pk=object_id)

        # Eliminar si existe
        GroupLibraryItem.objects.filter(
            group=group,
            content_type=content_type,
            object_id=object_id,
        ).delete()

        # Renderizar botón actualizado (HTMX swap)
        return render(
            request,
            "evaluations/group_library/partials/add_button.html",
            {
                "group": group,
                "content_object": content_object,
                "content_type": content_type,
                "in_library": False,
            },
        )

    return HttpResponse(status=405)


# =============================================================================
# VISTAS DE SESIONES DE CLASE
# =============================================================================


@login_required
@user_passes_test(is_staff)
def class_session_list(request):
    """
    Lista de sesiones de clase del profesor.
    TINY VIEW: solo orquesta y renderiza.
    """
    # Obtener grupos del profesor
    groups = request.user.teaching_groups.all()
    
    # Obtener sesiones del profesor ordenadas
    sessions = ClassSession.objects.filter(teacher=request.user).select_related("group")
    
    return render(
        request,
        "evaluations/class_sessions/list.html",
        {
            "sessions": sessions,
            "groups": groups,
        },
    )


@login_required
@user_passes_test(is_staff)
def class_session_create(request):
    """
    Crear nueva sesión de clase.
    TINY VIEW: solo crea y redirige.
    """
    if request.method == "POST":
        group_id = request.POST.get("group")
        date = request.POST.get("date")
        title = request.POST.get("title")
        notes = request.POST.get("notes", "")
        
        group = get_object_or_404(Group, pk=group_id)
        
        # Verificar que el profesor pertenece a este grupo
        if not group.teachers.filter(pk=request.user.pk).exists():
            messages.error(request, "No tienes permiso para crear sesiones en este grupo.")
            return redirect("evaluations:class_session_list")
        
        # Crear sesión
        session = ClassSession.objects.create(
            teacher=request.user,
            group=group,
            date=date,
            title=title,
            notes=notes
        )
        
        messages.success(request, f"Sesión '{title}' creada exitosamente.")
        return redirect("evaluations:class_session_edit", pk=session.pk)
    
    # GET: Mostrar formulario
    groups = request.user.teaching_groups.all()
    return render(
        request,
        "evaluations/class_sessions/create.html",
        {"groups": groups},
    )


@login_required
@user_passes_test(is_staff)
def class_session_edit(request, pk):
    """
    Editar sesión de clase con drag & drop.
    TINY VIEW: solo renderiza.
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    items = session.get_items_ordered()
    
    # Obtener elementos de la biblioteca del grupo para añadir
    library_items = GroupLibraryItem.objects.filter(group=session.group)
    
    return render(
        request,
        "evaluations/class_sessions/edit.html",
        {
            "session": session,
            "items": items,
            "library_items": library_items,
        },
    )


@login_required
@user_passes_test(is_staff)
def class_session_add_item(request, session_id):
    """
    Endpoint HTMX para añadir item a sesión.
    TINY VIEW: lógica en el modelo (FAT MODEL).
    """
    if request.method == "POST":
        session = get_object_or_404(ClassSession, pk=session_id, teacher=request.user)
        
        content_type_id = request.POST.get("content_type_id")
        object_id = request.POST.get("object_id")
        notes = request.POST.get("notes", "")
        
        content_type = get_object_or_404(ContentType, id=content_type_id)
        content_object = content_type.get_object_for_this_type(pk=object_id)
        
        # Lógica en el modelo (FAT MODEL)
        item = ClassSessionItem.add_to_session(
            session=session,
            content_object=content_object,
            notes=notes
        )
        
        # Renderizar item añadido (HTMX swap)
        return render(
            request,
            "evaluations/class_sessions/partials/session_item.html",
            {
                "item": item,
                "session": session,
            },
        )
    
    return HttpResponse(status=405)


@login_required
@user_passes_test(is_staff)
def class_session_remove_item(request, session_id, item_id):
    """
    Endpoint HTMX para quitar item de sesión.
    TINY VIEW: solo elimina.
    """
    session = get_object_or_404(ClassSession, pk=session_id, teacher=request.user)
    item = get_object_or_404(ClassSessionItem, pk=item_id, session=session)
    item.delete()
    
    return HttpResponse("")  # Empty response para swap outerHTML


@login_required
@user_passes_test(is_staff)
def class_session_reorder_items(request, session_id):
    """
    Endpoint HTMX para reordenar items con drag & drop.
    TINY VIEW: lógica en el modelo (FAT MODEL).
    """
    if request.method == "POST":
        session = get_object_or_404(ClassSession, pk=session_id, teacher=request.user)
        
        # Obtener IDs en el nuevo orden desde el POST
        item_ids_json = request.POST.get("item_ids", "[]")
        item_ids = json.loads(item_ids_json)
        
        # Lógica en el modelo (FAT MODEL)
        session.reorder_items(item_ids)
        
        return HttpResponse("OK")
    
    return HttpResponse(status=405)


@login_required
@user_passes_test(is_staff)
def class_session_delete(request, pk):
    """
    Eliminar sesión de clase.
    TINY VIEW: solo elimina y redirige.
    """
    session = get_object_or_404(ClassSession, pk=pk, teacher=request.user)
    title = session.title
    session.delete()
    
    messages.success(request, f"Sesión '{title}' eliminada exitosamente.")
    return redirect("evaluations:class_session_list")


# ============================================================================
# VISTAS DE BIBLIOTECA MÚLTIPLE (Personal + Grupos)
# ============================================================================

@require_http_methods(["POST"])
@login_required
@user_passes_test(is_staff, login_url="/accounts/login/", redirect_field_name=None)
def add_to_multiple_libraries(request):
    """
    Añade un recurso a múltiples bibliotecas (personal y/o grupos).
    TINY VIEW: orquesta y delega al modelo.
    """
    from django.contrib.contenttypes.models import ContentType
    from my_library.models import LibraryItem
    
    content_type_id = request.POST.get("content_type_id")
    object_id = request.POST.get("object_id")
    personal_library = request.POST.get("personal_library") == "true"
    group_ids = request.POST.getlist("group_ids")
    
    # Validar parámetros
    if not content_type_id or not object_id:
        return HttpResponse("Error: Parámetros inválidos", status=400)
    
    content_type = get_object_or_404(ContentType, pk=content_type_id)
    model_class = content_type.model_class()
    content_object = get_object_or_404(model_class, pk=object_id)
    
    added_count = 0
    
    # Añadir a biblioteca personal
    if personal_library:
        item, created = LibraryItem.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=object_id,
        )
        if created:
            added_count += 1
    
    # Añadir a bibliotecas de grupo
    for group_id in group_ids:
        group = get_object_or_404(Group, pk=group_id)
        
        # Verificar que el profesor pertenece al grupo
        if not group.teachers.filter(pk=request.user.pk).exists():
            continue
        
        # Usar el método del modelo para añadir
        item, created = GroupLibraryItem.objects.get_or_create(
            group=group,
            content_type=content_type,
            object_id=object_id,
            defaults={"added_by": request.user}
        )
        if created:
            added_count += 1
    
    # Respuesta HTMX simple
    if added_count > 0:
        return HttpResponse(f"✓ Añadido a {added_count} biblioteca(s)", status=200)
    else:
        return HttpResponse("El recurso ya estaba en las bibliotecas seleccionadas", status=200)
