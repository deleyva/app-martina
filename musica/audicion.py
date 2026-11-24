"""Editar fichas de audición desde la propia página (fase 111).

El permiso es el de Wagtail sobre la página, como el botón ✎ de las letras
(`musica/letras.py`): quien puede editarla en el administrador puede editar sus
ejercicios aquí, y nadie más. Si además puede publicar, el cambio se publica al
momento; si no, queda como revisión pendiente.

Cada vista responde con la ficha repintada (`musica/partials/ficha.html`), que
HTMX coloca en su sitio. Sin HTMX, vuelve a la página.
"""

import re

from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from musica.models import DictadoPage, LibroPage
from musica.services import audicion, patrones


def _puede_editar(page, user):
    return bool(
        getattr(user, "is_authenticated", False)
        and page.permissions_for_user(user).can_edit()
    )


def _ficha_editable(request, page_id):
    """(ficha, None) o (None, respuesta de error)."""
    ficha = get_object_or_404(DictadoPage, pk=page_id)
    if not _puede_editar(ficha, request.user):
        return None, HttpResponseForbidden("No puedes editar esta ficha.")
    return audicion.ficha_para_editar(ficha), None


def _responder(request, ficha):
    if request.headers.get("HX-Request"):
        return render(
            request,
            "musica/partials/ficha.html",
            {"ficha": ficha, "puede_editar": True, "modo": "pagina"},
        )
    # `get_url(request)` y no `.url`: con varios sitios, `.url` da la dirección
    # absoluta del sitio, y en local mandaba a producción.
    return redirect(ficha.get_url(request) or "/")


@require_POST
def crear_ficha(request, libro_id):
    libro = get_object_or_404(LibroPage, pk=libro_id)
    permisos = libro.permissions_for_user(request.user)
    if not (request.user.is_authenticated and permisos.can_add_subpage()):
        return HttpResponseForbidden("No puedes añadir fichas a este libro.")

    titulo = (request.POST.get("titulo") or "").strip()[:255]
    if not titulo:
        return HttpResponseBadRequest("Falta el título.")

    base = slugify(titulo)[:70] or "ficha"
    slug, n = base, 2
    hermanas = set(libro.get_children().values_list("slug", flat=True))
    while slug in hermanas:
        slug, n = f"{base}-{n}", n + 1

    ficha = DictadoPage(title=titulo, slug=slug, owner=request.user)
    libro.add_child(instance=ficha)
    revision = ficha.save_revision(user=request.user, log_action=True)
    if permisos.can_publish_subpage():
        revision.publish(user=request.user)
        return redirect(ficha.get_url(request))
    # Sin permiso de publicar, la ficha nace como borrador y solo se ve en el
    # administrador.
    return redirect("wagtailadmin_pages:edit", ficha.pk)


@require_POST
def anadir_audiometrico(request, page_id):
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    try:
        cents, _ = audicion.distancia(request.POST.get("distancia", ""))
        cuantos = int(request.POST.get("cuantos") or 1)
    except ValueError:
        return HttpResponseBadRequest("Distancia o número de tests no válidos.")
    cuantos = max(1, min(cuantos, audicion.MAX_TESTS_DE_GOLPE))
    for _ in range(cuantos):
        audicion.anadir(ficha, "audiometrico", audicion.generar_audiometrico(cents))
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)


@require_POST
def regenerar_ejercicio(request, page_id, bloque_id):
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    try:
        audicion.regenerar(ficha, bloque_id)
    except audicion.EjercicioNoEncontrado:
        return HttpResponseNotFound("Ese ejercicio ya no está en la ficha.")
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)


@require_POST
def borrar_ejercicio(request, page_id, bloque_id):
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    try:
        audicion.borrar(ficha, bloque_id)
    except audicion.EjercicioNoEncontrado:
        return HttpResponseNotFound("Ese ejercicio ya no está en la ficha.")
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)


@require_POST
def mover_ejercicio(request, page_id, bloque_id):
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    delta = -1 if request.POST.get("hacia") == "arriba" else 1
    try:
        audicion.mover(ficha, bloque_id, delta)
    except audicion.EjercicioNoEncontrado:
        return HttpResponseNotFound("Ese ejercicio ya no está en la ficha.")
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)


# --- Dictados en ABC (fase 111, tramo 2) --------------------------------------

PLANTILLAS_ABC = {
    "melodico": (
        "X:1\nM:4/4\nL:1/4\nK:C\n"
        "C D E F | G2 G2 | A G F E | D4 |\n"
        "E F G A | G2 E2 | D E D C | C4 |"
    ),
    # Una sola línea de pentagrama: lo que se escribe es el ritmo. Suena en do.
    "ritmico": (
        "X:1\nM:4/4\nL:1/4\nK:C clef=perc stafflines=1\n"
        "B B B B | B2 B2 | B B/B/ B B | B4 |\n"
        "B B B2 | B/B/ B B2 | B B B B | B4 |"
    ),
}

TAMANO_MAXIMO_ABC = 5000
TIMBRES = ("piano", "epiano", "flauta", "sinte")


def _entero(valor, defecto, minimo, maximo):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return defecto
    return max(minimo, min(n, maximo))


def _valor_dictado(post, anterior=None):
    """El valor de un bloque `dictado_abc` a partir de un formulario."""
    anterior = anterior or {}
    tipo = post.get("tipo", anterior.get("tipo", "melodico"))
    if tipo not in PLANTILLAS_ABC:
        tipo = "melodico"
    abc = post.get("abc")
    if abc is None:
        abc = anterior.get("abc") or PLANTILLAS_ABC[tipo]
    abc = abc.replace("\r\n", "\n").strip()
    timbre = post.get("timbre", anterior.get("timbre", ""))
    return {
        "titulo": (post.get("titulo", anterior.get("titulo", "")) or "")[:120],
        "tipo": tipo,
        "abc": abc,
        "tempo": _entero(post.get("tempo"), anterior.get("tempo", 60), 30, 200),
        "timbre": timbre if timbre in TIMBRES else "",
        "repeticiones": _entero(post.get("repeticiones"), anterior.get("repeticiones", 2), 1, 4),
        "silencio": _entero(post.get("silencio"), anterior.get("silencio", 10), 0, 60),
        # Un checkbox desmarcado no viaja: en el formulario de editar, su
        # ausencia es «no».
        "cuenta_previa": bool(post.get("cuenta_previa")) if "abc" in post else anterior.get("cuenta_previa", True),
        "audio": anterior.get("audio"),
    }


@require_POST
def anadir_dictado(request, page_id):
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    audicion.anadir(ficha, "dictado_abc", _valor_dictado(request.POST))
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)


@require_POST
def editar_dictado(request, page_id, bloque_id):
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    if len(request.POST.get("abc", "")) > TAMANO_MAXIMO_ABC:
        return HttpResponseBadRequest("El ABC es demasiado largo.")
    try:
        anterior = audicion.valor_crudo(ficha, bloque_id)
        audicion.reemplazar(ficha, bloque_id, _valor_dictado(request.POST, anterior))
    except audicion.EjercicioNoEncontrado:
        return HttpResponseNotFound("Ese ejercicio ya no está en la ficha.")
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)


# --- Patrones de piano (fase 114) ----------------------------------------------


def _no_guardado(request, ficha, donde, error):
    """No se guarda nada, y la ficha vuelve con el motivo junto al formulario.

    Con HTMX la respuesta es un 200 con la ficha repintada: un 400 no se
    intercambia, y quien escribió «I V7» se quedaría mirando un botón que no
    hace nada. `donde` es el `id` del bloque, o «nuevo» en el formulario de añadir.
    """
    if not request.headers.get("HX-Request"):
        return HttpResponseBadRequest(str(error))
    return render(
        request,
        "musica/partials/ficha.html",
        {
            "ficha": ficha,
            "puede_editar": True,
            "modo": "pagina",
            "no_guardado": {"donde": donde, "motivo": str(error), "intento": request.POST},
        },
    )


@require_POST
def anadir_patron(request, page_id):
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    try:
        valor = patrones.valor_de_patron(request.POST)
    except patrones.PatronNoValido as e:
        return _no_guardado(request, ficha, "nuevo", e)
    audicion.anadir(ficha, "patron_piano", valor)
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)


@require_POST
def editar_patron(request, page_id, bloque_id):
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    try:
        # Solo un patrón: con el `id` de un dictado, esto le dejaría dentro
        # los datos de un patrón.
        if audicion.tipo_de(ficha, bloque_id) != "patron_piano":
            raise audicion.EjercicioNoEncontrado(bloque_id)
        anterior = audicion.valor_crudo(ficha, bloque_id)
    except audicion.EjercicioNoEncontrado:
        return HttpResponseNotFound("Ese patrón ya no está en la ficha.")
    try:
        valor = patrones.valor_de_patron(request.POST, anterior)
    except patrones.PatronNoValido as e:
        return _no_guardado(request, ficha, bloque_id, e)
    audicion.reemplazar(ficha, bloque_id, valor)
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)


# --- Grabaciones y dictados con imagen (fase 111, tramo 3) --------------------

# Las grabaciones del navegador: webm/opus (Chrome, Firefox) y mp4/aac (Safari).
EXTENSIONES_AUDIO = (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".webm", ".mp4")
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png", ".gif", ".webp")
# El mismo tope que las notas de voz de las sesiones (`clases.views._preparar_audio`).
TAMANO_MAXIMO_AUDIO = 20 * 1024 * 1024
TAMANO_MAXIMO_IMAGEN = 15 * 1024 * 1024
CLAVE_VALIDA = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def _extension(nombre):
    nombre = (nombre or "").lower()
    return nombre[nombre.rfind("."):] if "." in nombre else ""


def _documento_de_audio(fichero, clave, user):
    """El `Document` de una grabación. Con la misma `clave`, el mismo documento.

    La clave la pone el navegador al grabar y viaja con cada reintento: si la
    primera subida llegó pero la respuesta se perdió (la wifi del aula), el
    reintento no crea un segundo documento.
    """
    from wagtail.documents import get_document_model

    from musica.recortador import _coleccion_musical

    Documento = get_document_model()
    titulo = f"Grabación de audición {clave}" if clave else (fichero.name or "Grabación")[:255]
    if clave:
        existente = Documento.objects.filter(title=titulo).first()
        if existente:
            return existente
    documento = Documento(
        title=titulo,
        uploaded_by_user=user,
        collection=_coleccion_musical(crear=True),
    )
    documento.file.save(f"audicion-{clave or 'audio'}{_extension(fichero.name) or '.webm'}", fichero, save=True)
    return documento


@require_POST
def subir_audio(request, page_id, bloque_id):
    """La grabación (o un audio subido) de un ejercicio. Responde con la ficha."""
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    fichero = request.FILES.get("archivo")
    if fichero is None:
        return HttpResponseBadRequest("Falta el audio.")
    if fichero.size > TAMANO_MAXIMO_AUDIO:
        return HttpResponseBadRequest("El audio pasa de 20 MB.")
    if _extension(fichero.name) not in EXTENSIONES_AUDIO:
        return HttpResponseBadRequest("Ese fichero no es un audio que se pueda reproducir.")
    clave = request.POST.get("clave", "")
    if clave and not CLAVE_VALIDA.match(clave):
        return HttpResponseBadRequest("Clave no válida.")
    try:
        valor = audicion.valor_crudo(ficha, bloque_id)
    except audicion.EjercicioNoEncontrado:
        return HttpResponseNotFound("Ese ejercicio ya no está en la ficha.")
    documento = _documento_de_audio(fichero, clave, request.user)
    valor["audio"] = documento.pk
    audicion.reemplazar(ficha, bloque_id, valor)
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)


@require_POST
def quitar_audio(request, page_id, bloque_id):
    """Quita la grabación del ejercicio. El documento se queda en la colección."""
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    try:
        valor = audicion.valor_crudo(ficha, bloque_id)
    except audicion.EjercicioNoEncontrado:
        return HttpResponseNotFound("Ese ejercicio ya no está en la ficha.")
    valor["audio"] = None
    audicion.reemplazar(ficha, bloque_id, valor)
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)


@require_POST
def anadir_dictado_imagen(request, page_id):
    """Un dictado cuya respuesta es una imagen. El audio se graba después."""
    ficha, error = _ficha_editable(request, page_id)
    if error:
        return error
    from wagtail.images import get_image_model

    from musica.recortador import _coleccion_musical

    imagen = request.FILES.get("imagen")
    imagen_id = None
    if imagen is not None:
        if imagen.size > TAMANO_MAXIMO_IMAGEN:
            return HttpResponseBadRequest("La imagen pasa de 15 MB.")
        if _extension(imagen.name) not in EXTENSIONES_IMAGEN:
            return HttpResponseBadRequest("Esa imagen no es JPG, PNG, GIF ni WebP.")
        titulo = (request.POST.get("titulo") or ficha.title)[:255]
        Imagen = get_image_model()
        objeto = Imagen(title=f"Respuesta: {titulo}", uploaded_by_user=request.user,
                        collection=_coleccion_musical(crear=True))
        objeto.file.save(imagen.name, imagen, save=False)
        objeto.save()
        imagen_id = objeto.pk
    audicion.anadir(
        ficha,
        "dictado_imagen",
        {"titulo": (request.POST.get("titulo") or "")[:120], "imagen": imagen_id, "audio": None},
    )
    audicion.guardar(ficha, request.user)
    return _responder(request, ficha)
