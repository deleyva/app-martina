# ruff: noqa: ERA001, E501
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case
from django.db.models import IntegerField
from django.db.models import Q
from django.db.models import Value
from django.db.models import When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import TemplateView

from .forms import AdjuntoForm
from .forms import ComentarioForm
from .forms import IncidenciaForm
from .models import Etiqueta
from .models import Incidencia
from .models import Tecnico
from .models import Ubicacion


class TecnicoRequiredMixin(LoginRequiredMixin):
    """Mixin que requiere que el usuario sea un técnico activo."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, "perfil_tecnico") or not request.user.perfil_tecnico.activo:
            if not request.user.is_superuser:
                return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


# =============================================================================
# Vistas públicas
# =============================================================================


def _get_incidencias_ordered(queryset=None):
    """Ordena incidencias: pendiente primero, en_progreso segundo, resuelta último."""
    if queryset is None:
        queryset = Incidencia.objects.all()
    return queryset.annotate(
        _estado_order=Case(
            When(estado=Incidencia.Estado.PENDIENTE, then=Value(0)),
            When(estado=Incidencia.Estado.EN_PROGRESO, then=Value(1)),
            When(estado=Incidencia.Estado.RESUELTA, then=Value(2)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    ).order_by("_estado_order", "-created_at")


def _get_visible_qs(request):
    """Devuelve queryset de incidencias visibles: públicas + privadas del propietario."""
    reportero = request.COOKIES.get("incidencias_reportero", "")
    qs = Incidencia.objects.all()
    if request.user.is_authenticated:
        # Logged-in users: see all public + their own private + technicians see everything
        if hasattr(request.user, "perfil_tecnico") and request.user.perfil_tecnico.activo:
            return qs  # Technicians see all
        if request.user.is_superuser:
            return qs  # Superusers see all
        # Regular logged-in user: public + own private
        return qs.filter(Q(es_privada=False) | Q(reportero_nombre__iexact=reportero))
    # Anonymous: public + own private (matched by cookie)
    if reportero:
        return qs.filter(Q(es_privada=False) | Q(reportero_nombre__iexact=reportero))
    return qs.filter(es_privada=False)


class LandingView(TemplateView):
    """Página principal: buscador + lista de incidencias."""

    template_name = "incidencias/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = _get_visible_qs(self.request)
        context["incidencias"] = _get_incidencias_ordered(qs)
        context["total_pendientes"] = qs.filter(estado=Incidencia.Estado.PENDIENTE).count()
        context["total_en_progreso"] = qs.filter(estado=Incidencia.Estado.EN_PROGRESO).count()
        context["total_resueltas"] = qs.filter(estado=Incidencia.Estado.RESUELTA).count()
        return context


class BuscarView(ListView):
    """Búsqueda HTMX por similitud (o icontains como fallback)."""

    template_name = "incidencias/partials/lista_incidencias.html"
    context_object_name = "incidencias"

    def get_queryset(self):
        q = self.request.GET.get("q", "").strip()
        qs = _get_visible_qs(self.request)

        if q:
            qs = qs.filter(
                Q(titulo__icontains=q)
                | Q(descripcion__icontains=q)
                | Q(etiquetas__nombre__icontains=q)
                | Q(ubicacion__nombre__icontains=q)
                | Q(ubicacion__grupo__icontains=q)
            ).distinct()

        return _get_incidencias_ordered(qs)


class CrearIncidenciaView(CreateView):
    """Formulario de creación de incidencia."""

    model = Incidencia
    form_class = IncidenciaForm
    template_name = "incidencias/crear.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["adjunto_form"] = AdjuntoForm()
        context["ubicaciones"] = Ubicacion.objects.all()
        context["etiquetas"] = Etiqueta.objects.all()
        return context

    def form_valid(self, form):
        incidencia = form.save()

        # Handle file attachments
        files = self.request.FILES.getlist("archivos")
        for f in files:
            if f.size <= 10 * 1024 * 1024:  # 10 MB
                from .models import Adjunto
                Adjunto.objects.create(incidencia=incidencia, archivo=f)

        # Set cookie so the owner can see their private incidents
        response = redirect("incidencias:detalle", pk=incidencia.pk)
        response.set_cookie(
            "incidencias_reportero",
            incidencia.reportero_nombre,
            max_age=60 * 60 * 24 * 365,  # 1 year
            httponly=True,
            samesite="Lax",
        )
        return response


class DetalleIncidenciaView(DetailView):
    """Detalle de una incidencia con comentarios."""

    model = Incidencia
    template_name = "incidencias/detalle.html"
    context_object_name = "incidencia"

    def dispatch(self, request, *args, **kwargs):
        incidencia = self.get_object()
        if incidencia.es_privada and not request.user.is_authenticated:
            return redirect(f"{reverse('account_login')}?next={request.path}")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["comentarios"] = self.object.comentarios.all()
        context["adjuntos"] = self.object.adjuntos.all()
        context["comentario_form"] = ComentarioForm()
        context["historial_asignaciones"] = self.object.historial_asignaciones.all()
        return context


class AgregarComentarioView(View):
    """Añadir un comentario a una incidencia (POST)."""

    def post(self, request, pk):
        incidencia = get_object_or_404(Incidencia, pk=pk)
        form = ComentarioForm(request.POST)
        if form.is_valid():
            comentario = form.save(commit=False)
            comentario.incidencia = incidencia
            comentario.save()
        return redirect("incidencias:detalle", pk=pk)


# =============================================================================
# API autocompletado (JSON)
# =============================================================================


class ApiUbicacionesView(View):
    """JSON endpoint para autocompletado de ubicaciones."""

    def get(self, request):
        q = request.GET.get("q", "").strip()
        qs = Ubicacion.objects.all()
        if q:
            qs = qs.filter(
                Q(nombre__icontains=q) | Q(grupo__icontains=q),
            )
        data = [
            {
                "id": u.id,
                "text": str(u),
                "nombre": u.nombre,
                "grupo": u.grupo,
                "planta": u.get_planta_display(),
            }
            for u in qs[:20]
        ]
        return JsonResponse(data, safe=False)


class ApiEtiquetasView(View):
    """JSON endpoint para autocompletado de etiquetas."""

    def get(self, request):
        q = request.GET.get("q", "").strip()
        qs = Etiqueta.objects.all()
        if q:
            qs = qs.filter(
                Q(nombre__icontains=q) | Q(slug__icontains=q),
            )
        data = [
            {
                "id": e.id,
                "text": e.nombre,
                "slug": e.slug,
            }
            for e in qs[:20]
        ]
        return JsonResponse(data, safe=False)


# =============================================================================
# Panel de administración (requiere técnico)
# =============================================================================


class PanelDashboardView(TecnicoRequiredMixin, TemplateView):
    """Dashboard del panel de administración."""

    template_name = "incidencias/panel/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Filtros
        planta = self.request.GET.get("planta", "")
        urgencia = self.request.GET.get("urgencia", "")
        etiqueta = self.request.GET.get("etiqueta", "")
        tecnico_id = self.request.GET.get("tecnico", "")

        qs = Incidencia.objects.select_related("ubicacion", "asignado_a").prefetch_related("etiquetas")

        if planta:
            qs = qs.filter(ubicacion__planta=planta)
        if urgencia:
            qs = qs.filter(urgencia=urgencia)
        if etiqueta:
            qs = qs.filter(etiquetas__slug=etiqueta)
        if tecnico_id:
            qs = qs.filter(asignado_a_id=tecnico_id)

        context["pendientes"] = qs.filter(estado=Incidencia.Estado.PENDIENTE).order_by("-created_at")
        context["en_progreso"] = qs.filter(estado=Incidencia.Estado.EN_PROGRESO).order_by("-created_at")
        context["resueltas"] = qs.filter(estado=Incidencia.Estado.RESUELTA).order_by("-created_at")[:20]

        # Mis incidencias (assigned to current user)
        tecnico_actual = getattr(self.request.user, "perfil_tecnico", None)
        if tecnico_actual:
            context["mis_incidencias"] = Incidencia.objects.filter(
                asignado_a=tecnico_actual,
            ).exclude(estado=Incidencia.Estado.RESUELTA).order_by("-created_at")
        else:
            context["mis_incidencias"] = Incidencia.objects.none()

        context["tecnicos"] = Tecnico.objects.filter(activo=True)
        context["etiquetas"] = Etiqueta.objects.all()
        context["plantas"] = Ubicacion.Planta.choices
        context["urgencias"] = Incidencia.Urgencia.choices

        # Active filters for template
        context["filtro_planta"] = planta
        context["filtro_urgencia"] = urgencia
        context["filtro_etiqueta"] = etiqueta
        context["filtro_tecnico"] = tecnico_id

        return context


class AsignarIncidenciaView(TecnicoRequiredMixin, View):
    """Asignar o auto-asignar una incidencia."""

    def post(self, request, pk):
        from .models import HistorialAsignacion

        incidencia = get_object_or_404(Incidencia, pk=pk)
        tecnico_id = request.POST.get("tecnico_id", "")
        asignante = getattr(request.user, "perfil_tecnico", None)
        nuevo_tecnico = None

        if tecnico_id == "self":
            nuevo_tecnico = asignante
        elif tecnico_id == "none":
            nuevo_tecnico = None
        elif tecnico_id.isdigit():
            nuevo_tecnico = get_object_or_404(Tecnico, pk=int(tecnico_id), activo=True)

        # Log history
        if tecnico_id == "none":
            nota = f"Desasignada (antes: {incidencia.asignado_a or '—'})"
        elif nuevo_tecnico:
            nota = f"Asignada a {nuevo_tecnico}"
        else:
            nota = ""

        if nota:
            HistorialAsignacion.objects.create(
                incidencia=incidencia,
                asignado_por=asignante,
                asignado_a=nuevo_tecnico,
                nota=nota,
            )

        incidencia.asignado_a = nuevo_tecnico
        incidencia.save()
        return redirect("incidencias:panel")


class CambiarEstadoView(TecnicoRequiredMixin, View):
    """Cambiar estado de una incidencia."""

    def post(self, request, pk):
        incidencia = get_object_or_404(Incidencia, pk=pk)
        nuevo_estado = request.POST.get("estado", "")
        if nuevo_estado in dict(Incidencia.Estado.choices):
            incidencia.estado = nuevo_estado
            incidencia.save()
        return redirect("incidencias:panel")


class CambiarEstadoApiView(TecnicoRequiredMixin, View):
    """API para cambiar estado via AJAX (drag-and-drop)."""

    def post(self, request, pk):
        incidencia = get_object_or_404(Incidencia, pk=pk)
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

        nuevo_estado = body.get("estado", "")
        if nuevo_estado not in dict(Incidencia.Estado.choices):
            return JsonResponse({"ok": False, "error": "Estado inválido"}, status=400)

        incidencia.estado = nuevo_estado
        incidencia.save()
        return JsonResponse({
            "ok": True,
            "id": incidencia.pk,
            "estado": incidencia.estado,
            "estado_display": incidencia.get_estado_display(),
        })


class GestionTecnicosView(TecnicoRequiredMixin, TemplateView):
    """Gestión de técnicos: alta y baja."""

    template_name = "incidencias/panel/tecnicos.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tecnicos"] = Tecnico.objects.all()
        return context

    def post(self, request):
        action = request.POST.get("action", "")

        if action == "add":
            from django.contrib.auth import get_user_model
            User = get_user_model()
            email = request.POST.get("email", "").strip()
            nombre = request.POST.get("nombre", "").strip()
            if email:
                user, _created = User.objects.get_or_create(
                    email=email,
                    defaults={"name": nombre},
                )
                Tecnico.objects.get_or_create(
                    user=user,
                    defaults={"nombre_display": nombre, "activo": True},
                )

        elif action == "toggle":
            tecnico_id = request.POST.get("tecnico_id", "")
            if tecnico_id.isdigit():
                try:
                    tecnico = Tecnico.objects.get(pk=int(tecnico_id))
                    tecnico.activo = not tecnico.activo
                    tecnico.save()
                except Tecnico.DoesNotExist:
                    pass

        return redirect("incidencias:panel_tecnicos")
