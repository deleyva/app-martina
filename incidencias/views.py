# ruff: noqa: ERA001, E501
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case
from django.db.models import IntegerField
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models import Value
from django.db.models import When
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import TemplateView
from django.views.generic import UpdateView

from .forms import AdjuntoForm
from .forms import CerrarDerivacionForm
from .forms import ComentarioForm
from .forms import DerivacionEditarForm
from .forms import DerivacionForm
from .forms import IncidenciaForm
from .forms import RespuestaForm
from .models import Derivacion
from .models import Etiqueta
from .models import Incidencia
from .models import Servicio
from .models import Tecnico
from .models import TransicionInvalida
from .models import Ubicacion
from .services import acciones


def _is_tecnico(user):
    """Check if user is an active technician or superuser."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return hasattr(user, "perfil_tecnico") and user.perfil_tecnico.activo


def _safe_redirect(request, default_url="incidencias:panel"):
    """Redirect to POST 'next' param if it's a safe internal URL, else default."""
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(default_url)


def _tecnico_de(user) -> Tecnico | None:
    """El perfil de técnico del usuario, con el mismo fallback que usaba asignar."""
    perfil = getattr(user, "perfil_tecnico", None)
    if perfil is not None:
        return perfil
    return Tecnico.objects.filter(user=user, activo=True).first()


def _prefetch_derivaciones_abiertas() -> Prefetch:
    return Prefetch(
        "derivaciones",
        queryset=Derivacion.objects.abiertas().select_related("servicio"),
        to_attr="derivaciones_abiertas",
    )


def _volver_al_detalle(incidencia_pk: int, derivacion_pk: int | None = None):
    url = reverse("incidencias:detalle", args=[incidencia_pk])
    if derivacion_pk:
        url += f"#derivacion-{derivacion_pk}"
    return redirect(url)


class TecnicoRequiredMixin(LoginRequiredMixin):
    """Mixin que requiere que el usuario sea un técnico activo."""

    def dispatch(self, request, *args, **kwargs):
        if not _is_tecnico(request.user):
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
                | Q(ubicacion__grupo__icontains=q),
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

    def get_queryset(self):
        return super().get_queryset().select_related("ubicacion", "asignado_a")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.es_privada and not request.user.is_authenticated:
            return redirect(f"{reverse('account_login')}?next={request.path}")
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        if getattr(self, "object", None) is not None:
            return self.object
        return super().get_object(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["comentarios"] = self.object.comentarios.all()
        context["adjuntos"] = self.object.adjuntos.all()
        context["comentario_form"] = ComentarioForm()
        context["historial_asignaciones"] = self.object.historial_asignaciones.all()
        # Technician context for action buttons
        is_tecnico = _is_tecnico(self.request.user)
        context["is_tecnico"] = is_tecnico
        context["derivaciones"] = (
            self.object.derivaciones.select_related("servicio").prefetch_related("comunicaciones")
        )
        if is_tecnico:
            context["tecnicos"] = Tecnico.objects.filter(activo=True).select_related("user")
            context["servicios"] = Servicio.objects.filter(activo=True)
            context["derivacion_form"] = DerivacionForm()
            context["respuesta_form"] = RespuestaForm()
            context["cerrar_form"] = CerrarDerivacionForm()
        return context


class AgregarComentarioView(View):
    """Añadir un comentario a una incidencia (POST)."""

    def post(self, request, pk):
        incidencia = get_object_or_404(Incidencia, pk=pk)
        form = ComentarioForm(request.POST)
        if form.is_valid():
            comentario = acciones.comentar(
                incidencia,
                form.cleaned_data["autor_nombre"],
                form.cleaned_data["texto"],
            )

            # Handle file attachments for the comment
            files = request.FILES.getlist("archivos")
            for f in files:
                if f.size <= 10 * 1024 * 1024:  # 10 MB
                    from .models import Adjunto
                    Adjunto.objects.create(
                        incidencia=incidencia,
                        comentario=comentario,
                        archivo=f,
                    )

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
        ubicacion = self.request.GET.get("ubicacion", "").strip()
        urgencia = self.request.GET.get("urgencia", "")
        etiqueta = self.request.GET.get("etiqueta", "").strip()
        tecnico_id = self.request.GET.get("tecnico", "")
        ambito = self.request.GET.get("ambito", "")

        qs = (
            Incidencia.objects.select_related("ubicacion", "asignado_a")
            .prefetch_related("etiquetas", _prefetch_derivaciones_abiertas())
        )

        if ubicacion:
            qs = qs.filter(
                Q(ubicacion__nombre__icontains=ubicacion)
                | Q(ubicacion__grupo__icontains=ubicacion)
                | Q(ubicacion__planta__icontains=ubicacion),
            )
        if urgencia:
            qs = qs.filter(urgencia=urgencia)
        if etiqueta:
            qs = qs.filter(etiquetas__nombre__icontains=etiqueta)
        if tecnico_id:
            if tecnico_id == "sin_asignar":
                qs = qs.filter(asignado_a__isnull=True)
            else:
                qs = qs.filter(asignado_a_id=tecnico_id)
        if ambito:
            qs = qs.filter(ambito=ambito)

        context["pendientes"] = qs.filter(estado=Incidencia.Estado.PENDIENTE).order_by("-created_at")
        context["en_progreso"] = qs.filter(estado=Incidencia.Estado.EN_PROGRESO).order_by("-created_at")
        context["resueltas"] = qs.filter(estado=Incidencia.Estado.RESUELTA).order_by("-created_at")[:20]

        # Mis incidencias (assigned to current user)
        tecnico_actual = getattr(self.request.user, "perfil_tecnico", None)
        if tecnico_actual:
            context["mis_incidencias"] = (
                Incidencia.objects.filter(asignado_a=tecnico_actual)
                .exclude(estado=Incidencia.Estado.RESUELTA)
                .select_related("ubicacion", "asignado_a")
                .prefetch_related("etiquetas", _prefetch_derivaciones_abiertas())
                .order_by("-created_at")
            )
        else:
            context["mis_incidencias"] = Incidencia.objects.none()

        context["tecnicos"] = Tecnico.objects.filter(activo=True)
        # context["etiquetas"] = Etiqueta.objects.all() # No longer needed for dropdown
        # context["plantas"] = Ubicacion.Planta.choices # No longer needed for dropdown
        context["urgencias"] = Incidencia.Urgencia.choices
        context["ambitos"] = Incidencia.Ambito.choices

        # Active filters for template
        context["filtro_ubicacion"] = ubicacion
        context["filtro_urgencia"] = urgencia
        context["filtro_etiqueta"] = etiqueta
        context["filtro_tecnico"] = tecnico_id
        context["filtro_ambito"] = ambito

        return context


class EditarIncidenciaView(TecnicoRequiredMixin, UpdateView):
    """Editar una incidencia desde el panel de técnicos."""

    model = Incidencia
    form_class = IncidenciaForm
    template_name = "incidencias/editar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        incidencia = self.object

        # Pre-fill ubicacion autocomplete
        if incidencia.ubicacion:
            context["ubicacion_actual_json"] = json.dumps({
                "id": incidencia.ubicacion.id,
                "text": str(incidencia.ubicacion),
                "nombre": incidencia.ubicacion.nombre,
                "grupo": incidencia.ubicacion.grupo,
                "planta": incidencia.ubicacion.get_planta_display(),
            })

        # Pre-fill etiquetas autocomplete
        etiquetas = incidencia.etiquetas.all()
        if etiquetas.exists():
            context["etiquetas_actuales_json"] = json.dumps([
                {"id": e.id, "text": e.nombre, "slug": e.slug}
                for e in etiquetas
            ])

        return context

    def get_success_url(self):
        return reverse("incidencias:panel")


class AsignarIncidenciaView(TecnicoRequiredMixin, View):
    """Asignar o auto-asignar una incidencia."""

    def post(self, request, pk):
        incidencia = get_object_or_404(Incidencia, pk=pk)
        tecnico_id = request.POST.get("tecnico_id", "")
        asignante = _tecnico_de(request.user)

        if tecnico_id == "self":
            if asignante is None:
                return _safe_redirect(request)
            acciones.asignar(incidencia, asignante, asignante)
        elif tecnico_id == "none":
            acciones.asignar(incidencia, None, asignante)
        elif tecnico_id.isdigit():
            nuevo = get_object_or_404(Tecnico, pk=int(tecnico_id), activo=True)
            acciones.asignar(incidencia, nuevo, asignante)
        return _safe_redirect(request)


class CambiarEstadoView(TecnicoRequiredMixin, View):
    """Cambiar estado de una incidencia."""

    def post(self, request, pk):
        incidencia = get_object_or_404(Incidencia, pk=pk)
        nuevo_estado = request.POST.get("estado", "")
        if nuevo_estado in Incidencia.Estado.values:
            acciones.cambiar_estado(incidencia, nuevo_estado)
        return _safe_redirect(request)


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

        acciones.cambiar_estado(incidencia, nuevo_estado)

        return JsonResponse({
            "ok": True,
            "id": incidencia.pk,
            "estado": incidencia.estado,
            "estado_display": incidencia.get_estado_display(),
        })


class EliminarIncidenciaView(TecnicoRequiredMixin, View):
    """Eliminar una incidencia (POST, requiere técnico)."""

    def post(self, request, pk):
        incidencia = get_object_or_404(Incidencia, pk=pk)
        incidencia.delete()
        return _safe_redirect(request)


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


# =============================================================================
# Derivaciones a servicios externos
# =============================================================================


class CrearDerivacionView(TecnicoRequiredMixin, View):
    """Crea la derivación en borrador, con el correo ya redactado."""

    def post(self, request, pk):
        incidencia = get_object_or_404(Incidencia, pk=pk)
        form = DerivacionForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Elige un servicio.")
            return _volver_al_detalle(pk)
        derivacion = acciones.derivar(incidencia, form.cleaned_data["servicio"], _tecnico_de(request.user))
        return _volver_al_detalle(pk, derivacion.pk)


class _DerivacionAccionView(TecnicoRequiredMixin, View):
    """Base: carga la derivación y traduce una transición ilegal a mensaje."""

    def post(self, request, pk):
        derivacion = get_object_or_404(Derivacion.objects.select_related("incidencia"), pk=pk)
        try:
            self.actuar(request, derivacion)
        except TransicionInvalida as exc:
            messages.error(request, str(exc))
        return _volver_al_detalle(derivacion.incidencia_id, derivacion.pk)

    def actuar(self, request, derivacion):  # pragma: no cover - abstract
        raise NotImplementedError


class EditarDerivacionView(_DerivacionAccionView):
    def actuar(self, request, derivacion):
        form = DerivacionEditarForm(request.POST, instance=derivacion)
        if not form.is_valid():
            messages.error(request, "Revisa el asunto y el cuerpo.")
            return
        datos = form.cleaned_data
        if derivacion.estado == Derivacion.Estado.BORRADOR:
            derivacion.editar(asunto=datos["asunto"], cuerpo=datos["cuerpo"], ticket_externo=datos["ticket_externo"])
        else:
            derivacion.editar(ticket_externo=datos["ticket_externo"])
        messages.success(request, "Derivación guardada.")


class MarcarEnviadaView(_DerivacionAccionView):
    def actuar(self, request, derivacion):
        derivacion.marcar_enviada(_tecnico_de(request.user))
        messages.success(request, f"Marcada como enviada a {derivacion.servicio}.")


class RegistrarRespuestaView(_DerivacionAccionView):
    def actuar(self, request, derivacion):
        form = RespuestaForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Escribe qué han contestado.")
            return
        datos = form.cleaned_data
        derivacion.registrar_respuesta(
            autor=str(_tecnico_de(request.user) or request.user.email),
            texto=datos["texto"],
            fecha=datos["fecha"],
            canal=datos["canal"],
            ticket_externo=datos["ticket_externo"],
        )
        messages.success(request, "Respuesta apuntada.")


class CerrarDerivacionView(_DerivacionAccionView):
    def actuar(self, request, derivacion):
        form = CerrarDerivacionForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Indica cómo ha quedado.")
            return
        derivacion.cerrar(
            resultado=form.cleaned_data["resultado"],
            autor=str(_tecnico_de(request.user) or request.user.email),
            nota=form.cleaned_data["nota"],
        )
        messages.success(request, "Derivación cerrada.")


class GestionServiciosView(TecnicoRequiredMixin, TemplateView):
    """Servicios con su enlace público; alta y edición en el admin."""

    template_name = "incidencias/panel/servicios.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["servicios"] = Servicio.objects.all()
        return context

    def post(self, request):
        servicio = get_object_or_404(Servicio, pk=request.POST.get("servicio_id", "0") or 0)
        servicio.regenerar_token()
        messages.success(request, f"Enlace de {servicio} regenerado; el anterior ya no funciona.")
        return redirect("incidencias:panel_servicios")


# =============================================================================
# Páginas públicas: la del servicio (por token) y la ayuda
# =============================================================================

DIAS_RESUELTAS_RECIENTES = 60


class PaginaServicioView(TemplateView):
    """Lo que un servicio externo tiene pendiente en el centro. Sin login; el token es la llave.

    Nunca enseña reporteros ni comentarios de la incidencia: solo la derivación y su histórico.
    En las privadas, solo id, aula y asunto.
    """

    template_name = "incidencias/servicio.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        servicio = Servicio.objects.filter(token=kwargs["token"], activo=True).first()
        if servicio is None:
            raise Http404
        base = (
            Derivacion.objects.filter(servicio=servicio)
            .select_related("incidencia__ubicacion")
            .prefetch_related("comunicaciones")
        )
        pendientes = list(base.abiertas().order_by("incidencia__ubicacion__planta", "incidencia__ubicacion__nombre", "created_at"))
        limite = timezone.now() - timedelta(days=DIAS_RESUELTAS_RECIENTES)
        cerradas = list(base.filter(estado=Derivacion.Estado.CERRADA, updated_at__gte=limite).order_by("-updated_at"))
        context["servicio"] = servicio
        context["grupos"] = _agrupar_por_planta(pendientes)
        context["cerradas"] = cerradas
        context["total_pendientes"] = len(pendientes)
        context["generada"] = timezone.now()
        return context


def _agrupar_por_planta(derivaciones):
    """[(planta_nombre, [(aula, [derivaciones])])], con «Sin ubicación» al final."""
    plantas: dict[str, dict[str, list]] = {}
    for d in derivaciones:
        u = d.incidencia.ubicacion
        planta = u.get_planta_display() if u else "Sin ubicación"
        aula = u.nombre if u else "Por concretar"
        plantas.setdefault(planta, {}).setdefault(aula, []).append(d)
    orden = [p for p in dict(Ubicacion.Planta.choices).values() if p in plantas]
    if "Sin ubicación" in plantas:
        orden.append("Sin ubicación")
    return [(p, list(plantas[p].items())) for p in orden]


class AyudaView(TemplateView):
    """«¿A quién va cada cosa?»: la tabla de servicios, desde la base de datos."""

    template_name = "incidencias/ayuda.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["servicios"] = Servicio.objects.filter(activo=True)
        return context
