import json
from email.utils import parseaddr

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView
from django.views.generic import TemplateView

from .forms import DispositivoWifiForm
from .models import DispositivoWifi
from .permissions import es_gestor
from .permissions import puede_solicitar
from .services.mac import exportar
from .tasks import enviar_avisos_alta


class PersonalRequiredMixin(LoginRequiredMixin):
    """Identificado con Google y, además, personal del centro."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not puede_solicitar(request.user):
            msg = (
                "El alta de dispositivos en la WiFi está reservada al personal "
                "del centro. Si crees que deberías tener acceso, díselo en "
                "administración."
            )
            raise PermissionDenied(msg)
        return super().dispatch(request, *args, **kwargs)


class GestorRequiredMixin(LoginRequiredMixin):
    """Grupo «Gestión WiFi» o superusuario."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not es_gestor(request.user):
            msg = "Esta pantalla es para el personal de administración."
            raise PermissionDenied(msg)
        return super().dispatch(request, *args, **kwargs)


# =============================================================================
# Solicitud
# =============================================================================


class SolicitarView(PersonalRequiredMixin, CreateView):
    """Formulario de alta + mis dispositivos + tutoriales por sistema."""

    model = DispositivoWifi
    form_class = DispositivoWifiForm
    template_name = "wifi/solicitar.html"
    success_url = reverse_lazy("wifi:solicitar")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["mis_dispositivos"] = DispositivoWifi.objects.filter(
            usuario=self.request.user,
        ).order_by("-created_at")
        context["es_gestor"] = es_gestor(self.request.user)
        # De qué dirección sale el aviso. Se saca de `DEFAULT_FROM_EMAIL` en vez
        # de escribirla en la plantilla: si algún día cambia la cuenta de envío,
        # la página no se queda mintiendo.
        context["remitente"] = parseaddr(getattr(settings, "DEFAULT_FROM_EMAIL", ""))[1]
        return context

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        respuesta = super().form_valid(form)
        messages.success(
            self.request,
            "Recibido. Te avisaremos por correo en cuanto tu dispositivo esté "
            "dado de alta en la red.",
        )
        return respuesta


# =============================================================================
# Gestión (los «administrativos»)
# =============================================================================


def _lote(queryset):
    """Empaqueta un grupo de dispositivos con todo lo que la pantalla necesita."""
    filas = list(queryset.select_related("usuario"))
    macs = [d.mac for d in filas]
    return {
        "filas": filas,
        "total": len(filas),
        "ids": [d.pk for d in filas],
        "ids_json": json.dumps([d.pk for d in filas]),
        "macs_json": json.dumps(macs),
        "texto_por_defecto": exportar(macs, "colon", "coma"),
    }


class GestionView(GestorRequiredMixin, TemplateView):
    template_name = "wifi/gestion.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = DispositivoWifi.objects.all()

        context["alta"] = _lote(
            base.filter(estado=DispositivoWifi.Estado.PENDIENTE).order_by("created_at"),
        )
        context["baja"] = _lote(
            base.filter(estado=DispositivoWifi.Estado.BAJA_PENDIENTE).order_by("updated_at"),
        )

        buscar = self.request.GET.get("q", "").strip()
        activas = base.filter(estado=DispositivoWifi.Estado.ANADIDA)
        if buscar:
            activas = activas.filter(
                Q(mac__icontains=buscar)
                | Q(descripcion__icontains=buscar)
                | Q(usuario__email__icontains=buscar)
                | Q(usuario__name__icontains=buscar),
            )
        context["activas"] = activas.select_related("usuario").order_by("-anadida_at")
        context["total_activas"] = base.filter(estado=DispositivoWifi.Estado.ANADIDA).count()
        context["buscar"] = buscar
        # Sin clave en el entorno la app funciona, pero nadie recibe nada:
        # más vale decirlo en la pantalla que dejar que se descubra por
        # una llamada de teléfono.
        context["falta_clave"] = not getattr(settings, "WIFI_PASSWORD", "")
        return context


def _ids_del_post(request) -> list[int]:
    """Los identificadores que el administrativo copió, no «lo pendiente ahora».

    Es la diferencia que impide marcar de más: entre copiar y marcar puede haber
    entrado una solicitud nueva que nadie ha pegado en el otro software.
    """
    crudos = request.POST.getlist("ids")
    if len(crudos) == 1 and "," in crudos[0]:
        crudos = crudos[0].split(",")
    return [int(x) for x in (c.strip() for c in crudos) if x.isdigit()]


class MarcarAnadidasView(GestorRequiredMixin, View):
    """Sella el alta de los dispositivos copiados y dispara el aviso por correo."""

    def post(self, request, *args, **kwargs):
        ids = _ids_del_post(request)
        marcados = []

        with transaction.atomic():
            dispositivos = DispositivoWifi.objects.select_for_update().filter(
                pk__in=ids,
                estado=DispositivoWifi.Estado.PENDIENTE,
            )
            for dispositivo in dispositivos:
                if dispositivo.marcar_anadida(por=request.user):
                    marcados.append(dispositivo.pk)

        if not marcados:
            messages.info(request, "No había nada pendiente que marcar.")
            return redirect("wifi:gestion")

        enviar_avisos_alta(marcados)

        # El aviso solo se promete si de verdad puede salir. Decir «se ha
        # enviado» cuando falta la clave en el entorno es peor que no decir
        # nada: nadie iría a mirar por qué no llega.
        if getattr(settings, "WIFI_PASSWORD", ""):
            messages.success(
                request,
                f"{len(marcados)} dispositivo(s) dados de alta. Se ha enviado el "
                "correo con la clave a cada solicitante.",
            )
        else:
            messages.warning(
                request,
                f"{len(marcados)} dispositivo(s) dados de alta, pero NO se ha "
                "enviado ningún correo: falta configurar la clave de la WiFi "
                "(DJANGO_WIFI_PASSWORD). Avisa a quien lleve el servidor.",
            )

        return redirect("wifi:gestion")


class MarcarParaBajaView(GestorRequiredMixin, View):
    """Pasa un dispositivo a la lista de los que hay que quitar de la red."""

    def post(self, request, pk, *args, **kwargs):
        dispositivo = DispositivoWifi.objects.filter(pk=pk).first()
        if dispositivo and dispositivo.marcar_para_baja(por=request.user):
            messages.success(
                request,
                f"{dispositivo.mac} pasa a la lista de bajas pendientes.",
            )
        else:
            messages.warning(request, "Ese dispositivo no se puede dar de baja ahora.")
        return redirect("wifi:gestion")


class MarcarBajasHechasView(GestorRequiredMixin, View):
    """Cierra las bajas ya retiradas del otro software. No manda ningún correo."""

    def post(self, request, *args, **kwargs):
        ids = _ids_del_post(request)
        cerrados = 0

        with transaction.atomic():
            dispositivos = DispositivoWifi.objects.select_for_update().filter(
                pk__in=ids,
                estado=DispositivoWifi.Estado.BAJA_PENDIENTE,
            )
            for dispositivo in dispositivos:
                if dispositivo.marcar_dada_de_baja(por=request.user):
                    cerrados += 1

        if cerrados:
            messages.success(request, f"{cerrados} dispositivo(s) dados de baja.")
        else:
            messages.info(request, "No había bajas pendientes que cerrar.")

        return redirect("wifi:gestion")
