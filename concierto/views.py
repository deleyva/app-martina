from django.contrib import messages
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from .models import Acto
from .models import Tarea
from .models import Voluntario


class ProgramaView(TemplateView):
    template_name = "concierto/programa.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["actos"] = Acto.objects.prefetch_related("tareas_grabacion__voluntarios").all()
        context["tareas_generales"] = (
            Tarea.objects.filter(acto__isnull=True).prefetch_related("voluntarios").all()
        )
        context["tareas_grabacion"] = (
            Tarea.objects.filter(acto__isnull=False)
            .select_related("acto")
            .prefetch_related("voluntarios")
            .order_by("acto__orden")
        )
        return context


class ApuntarseView(View):
    def post(self, request, tarea_id):
        tarea = get_object_or_404(Tarea, pk=tarea_id)
        username = request.POST.get("username", "").strip().lower()

        if not username:
            messages.error(request, "Debes introducir tu usuario.")
            return redirect("concierto:programa")

        if tarea.esta_llena():
            messages.warning(request, f"Lo sentimos, '{tarea.nombre}' ya no tiene plazas disponibles.")
            return redirect("concierto:programa")

        try:
            Voluntario.objects.create(username=username, tarea=tarea)
            messages.success(request, f"Te has apuntado a '{tarea.nombre}'.")
        except IntegrityError:
            messages.info(request, f"Ya estabas apuntado/a a '{tarea.nombre}'.")

        return redirect("concierto:programa")


class DesapuntarseView(View):
    def post(self, request, voluntario_id):
        voluntario = get_object_or_404(Voluntario, pk=voluntario_id)
        username = request.POST.get("username", "").strip().lower()

        if voluntario.username != username:
            messages.error(request, "El usuario no coincide.")
            return redirect("concierto:programa")

        nombre_tarea = voluntario.tarea.nombre
        voluntario.delete()
        messages.success(request, f"Te has desapuntado de '{nombre_tarea}'.")
        return redirect("concierto:programa")
