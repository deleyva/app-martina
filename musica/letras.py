"""Editar la letra con acordes (ChordPro) de una canción sin pasar por el CMS.

Lo usa el botón ✎ del artículo y de los visores de sesión. El permiso es el de
Wagtail sobre la página: quien puede editarla en el administrador puede editar
su letra aquí, y nadie más.

Si además puede publicar, el cambio se publica al momento (es lo que se espera
al corregir un acorde en mitad de una clase). Si solo puede editar, se guarda
como revisión pendiente, igual que en el administrador.
"""

import json

from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from musica.models import RecursoPage

# Holgura de sobra para una letra: la de Perfect ocupa 2,5 kB.
TAMANO_MAXIMO = 50_000


def puede_editar(page, user):
    return bool(
        getattr(user, "is_authenticated", False)
        and page.permissions_for_user(user).can_edit()
    )


@require_POST
def guardar_chordpro(request, page_id):
    page = get_object_or_404(RecursoPage, pk=page_id).specific
    if not puede_editar(page, request.user):
        return HttpResponseForbidden("No puedes editar esta canción.")

    try:
        texto = json.loads(request.body or b"{}").get("chordpro")
    except (ValueError, AttributeError):
        return HttpResponseBadRequest("JSON no válido.")
    if not isinstance(texto, str):
        return HttpResponseBadRequest("Falta `chordpro`.")
    if len(texto) > TAMANO_MAXIMO:
        return HttpResponseBadRequest("La letra es demasiado larga.")

    page.chordpro = texto.replace("\r\n", "\n").strip()
    revision = page.save_revision(user=request.user, log_action=True)
    publicada = page.permissions_for_user(request.user).can_publish()
    if publicada:
        revision.publish(user=request.user)

    return JsonResponse({"ok": True, "publicada": publicada, "chordpro": page.chordpro})
