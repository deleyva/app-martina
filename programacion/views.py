"""
Vistas de programación didáctica. TINY VIEWS: la lógica está en models/services.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from clases.models import Group, GroupLibraryItem

from .models import CoursePlan, PlanItem
from .services import create_session_from_plan_item, recompute_coverage


def is_staff(user):
    return user.is_staff


def _get_plan(request, pk):
    return get_object_or_404(CoursePlan, pk=pk, teacher=request.user)


# =============================================================================
# PLANES
# =============================================================================


@login_required
@user_passes_test(is_staff)
def plan_list(request):
    """Listado de programaciones del profesor, agrupadas por grupo."""
    plans = CoursePlan.objects.filter(teacher=request.user).select_related(
        "group", "group__subject"
    )
    groups = request.user.teaching_groups.select_related("subject").all()
    return render(
        request,
        "programacion/plan_list.html",
        {"plans": plans, "groups": groups},
    )


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def plan_create(request):
    group = get_object_or_404(Group, pk=request.POST.get("group"))
    if not group.teachers.filter(pk=request.user.pk).exists():
        messages.error(request, "No tienes permiso sobre este grupo.")
        return redirect("programacion:plan_list")

    plan = CoursePlan.objects.create(
        teacher=request.user,
        group=group,
        name=request.POST.get("name", "").strip() or "Nueva programación",
        start_date=request.POST.get("start_date") or None,
        end_date=request.POST.get("end_date") or None,
    )
    messages.success(request, f"Programación '{plan.name}' creada.")
    return redirect("programacion:plan_detail", pk=plan.pk)


@login_required
@user_passes_test(is_staff)
def plan_detail(request, pk):
    """
    Vista principal: timeline del plan con progreso por item,
    panel "siguiente paso" y añadir recursos desde la biblioteca del grupo.
    """
    plan = _get_plan(request, pk)
    items = list(plan.get_items_ordered())

    # Contenido de la biblioteca del grupo que se puede programar
    programmable = GroupLibraryItem.objects.filter(
        group=plan.group,
        content_type__model__in=["blogpage", "blogindexpage", "scorepage"],
    ).select_related("content_type")
    # Excluir los ya programados
    existing = {(i.content_type_id, i.object_id) for i in plan.items.all()}
    library_choices = [
        gli
        for gli in programmable
        if (gli.content_type_id, gli.object_id) not in existing
        and gli.content_object is not None
    ]

    # Libros disponibles (BlogIndexPage con capítulos) aunque no estén en la biblioteca
    from cms.models import BlogIndexPage

    books = BlogIndexPage.objects.live().order_by("title")
    book_ct = ContentType.objects.get_for_model(BlogIndexPage)
    book_choices = [
        b for b in books if (book_ct.pk, b.pk) not in existing
    ]

    next_step = plan.get_next_step()
    pending_elements = next_step.get_pending_elements() if next_step else []

    return render(
        request,
        "programacion/plan_detail.html",
        {
            "plan": plan,
            "items": items,
            "progress": plan.get_progress(),
            "library_choices": library_choices,
            "book_choices": book_choices,
            "next_step": next_step,
            "pending_elements": pending_elements,
            "today": timezone.localdate,
        },
    )


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def plan_delete(request, pk):
    plan = _get_plan(request, pk)
    name = plan.name
    plan.delete()
    messages.success(request, f"Programación '{name}' eliminada.")
    return redirect("programacion:plan_list")


# =============================================================================
# ITEMS DEL PLAN
# =============================================================================


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def plan_item_add(request, pk):
    """Añadir un recurso al plan. Espera content_type_id + object_id."""
    plan = _get_plan(request, pk)
    ct = get_object_or_404(ContentType, pk=request.POST.get("content_type_id"))
    object_id = int(request.POST.get("object_id"))

    item, created = PlanItem.objects.get_or_create(
        plan=plan,
        content_type=ct,
        object_id=object_id,
        defaults={"order": plan.get_next_order()},
    )
    if created:
        # Si es un libro, generar capítulos automáticamente
        chapters = item.sync_chapters()
        # Calcular cobertura inicial (aprovecha el historial de sesiones)
        if not item.is_book and item.content_object is not None:
            recompute_coverage(plan.group, item.content_object)
        for chapter_item in chapters:
            if chapter_item.content_object is not None:
                recompute_coverage(plan.group, chapter_item.content_object)
        messages.success(request, f"'{item.get_content_title()}' añadido al plan.")
    return redirect("programacion:plan_detail", pk=plan.pk)


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def plan_item_remove(request, pk, item_id):
    plan = _get_plan(request, pk)
    item = get_object_or_404(PlanItem, pk=item_id, plan=plan)
    item.delete()
    return redirect("programacion:plan_detail", pk=plan.pk)


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def plan_item_status(request, pk, item_id):
    """Cambiar estado manual: auto / skipped / done."""
    plan = _get_plan(request, pk)
    item = get_object_or_404(PlanItem, pk=item_id, plan=plan)
    status = request.POST.get("status")
    if status in PlanItem.Status.values:
        item.status = status
        item.save(update_fields=["status"])
    return redirect("programacion:plan_detail", pk=plan.pk)


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def plan_reorder(request, pk):
    plan = _get_plan(request, pk)
    try:
        item_ids = json.loads(request.body).get("item_ids", [])
    except (json.JSONDecodeError, AttributeError):
        item_ids = []
    plan.reorder_items(item_ids)
    from django.http import JsonResponse

    return JsonResponse({"ok": True})


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def plan_item_sync_chapters(request, pk, item_id):
    """Re-sincronizar capítulos de un libro (nuevos capítulos publicados)."""
    plan = _get_plan(request, pk)
    item = get_object_or_404(PlanItem, pk=item_id, plan=plan)
    created = item.sync_chapters()
    for chapter_item in created:
        if chapter_item.content_object is not None:
            recompute_coverage(plan.group, chapter_item.content_object)
    messages.success(request, f"{len(created)} capítulos nuevos añadidos.")
    return redirect("programacion:plan_detail", pk=plan.pk)


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def plan_item_refresh_coverage(request, pk, item_id):
    """Recalcular cobertura de un item (y sus capítulos) bajo demanda."""
    plan = _get_plan(request, pk)
    item = get_object_or_404(PlanItem, pk=item_id, plan=plan)
    targets = [item] + list(item.children.all())
    for t in targets:
        if not t.is_book and t.content_object is not None:
            recompute_coverage(plan.group, t.content_object)
    return redirect("programacion:plan_detail", pk=plan.pk)


# =============================================================================
# RECOMENDACIÓN → CREAR CLASE
# =============================================================================


@login_required
@user_passes_test(is_staff)
@require_http_methods(["POST"])
def create_session_from_item(request, pk, item_id):
    """Crear una ClassSession prellenada con los elementos pendientes del item."""
    plan = _get_plan(request, pk)
    item = get_object_or_404(PlanItem, pk=item_id, plan=plan)

    session = create_session_from_plan_item(
        plan_item=item,
        teacher=request.user,
        date=request.POST.get("date") or timezone.localdate(),
        title=request.POST.get("title", "").strip() or None,
    )
    messages.success(
        request,
        f"Clase '{session.title}' creada con {session.items.count()} elementos pendientes.",
    )
    return redirect("clases:class_session_edit", pk=session.pk)


# =============================================================================
# COMPARATIVA DE GRUPOS
# =============================================================================


@login_required
@user_passes_test(is_staff)
def overview(request):
    """
    Vista comparativa: para cada grupo del profesor, sus planes activos
    con progreso y siguiente paso. Un vistazo de por dónde va cada grupo.
    """
    groups = request.user.teaching_groups.select_related("subject").all()
    rows = []
    for group in groups:
        plans = CoursePlan.objects.filter(
            teacher=request.user, group=group, is_active=True
        )
        for plan in plans:
            next_step = plan.get_next_step()
            rows.append(
                {
                    "group": group,
                    "plan": plan,
                    "progress": plan.get_progress(),
                    "items": list(plan.get_items_ordered()),
                    "next_step": next_step,
                }
            )
    return render(request, "programacion/overview.html", {"rows": rows})
