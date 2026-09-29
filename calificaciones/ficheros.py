"""Qué es cada fichero de evidencia y cómo se sirve.

**El tipo lo decide la extensión, nunca el navegador.** Hasta la fase 60 la
vista servía en línea el `Content-Type` que el cliente había declarado al subir:
un `.html` subido como evidencia se habría ejecutado dentro de la aplicación.
Aquí hay una lista corta de lo que se puede enseñar en línea (imagen, audio,
vídeo, PDF) y todo lo demás baja como adjunto.

**Rangos de bytes.** `FileResponse` no contesta a `Range`, y sin respuestas 206
el reproductor de iOS no toca audio ni vídeo. Es un rango simple, que es lo
único que piden los navegadores.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.http import FileResponse, HttpResponse

IMAGEN = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".heic": "image/heic",
}
AUDIO = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".mp4": "audio/mp4",
}
VIDEO = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".m4v": "video/mp4",
    ".ogg": "video/ogg",
}
PDF = {".pdf": "application/pdf"}

FAMILIAS = {"foto": IMAGEN, "audio": AUDIO, "video": VIDEO}


def extension(nombre: str) -> str:
    return Path(nombre or "").suffix.lower()


def clasificar(tipo: str, nombre: str) -> str | None:
    """El tipo con el que se guarda, o `None` si lo declarado no casa con el fichero.

    Una grabación dice lo que es (`audio`, `video`, `foto`) y se le cree si la
    extensión es de esa familia: un `.webm` puede ser las dos cosas, y si se
    decidiera por la extensión cada audio acabaría en ffmpeg. Un `archivo`
    subido a mano sí se mira: una foto es una foto aunque llegue por «Subir
    archivo».
    """
    ext = extension(nombre)
    if tipo in FAMILIAS:
        return tipo if ext in FAMILIAS[tipo] else None
    if tipo != "archivo":
        return None
    if ext in IMAGEN:
        return "foto"
    if ext in {".mp3", ".m4a", ".wav"}:
        return "audio"
    if ext in VIDEO:
        return "video"
    return "archivo"


def tipo_de_contenido(tipo: str, nombre: str) -> str | None:
    """El `Content-Type` para servir en línea, o `None` si tiene que bajar como adjunto."""
    ext = extension(nombre)
    if tipo in FAMILIAS:
        return FAMILIAS[tipo].get(ext)
    return PDF.get(ext)


RANGO = re.compile(r"^bytes=(\d*)-(\d*)$")


def _trozos(fichero, inicio: int, longitud: int, bloque: int = 64 * 1024):
    fichero.seek(inicio)
    quedan = longitud
    try:
        while quedan > 0:
            datos = fichero.read(min(bloque, quedan))
            if not datos:
                break
            quedan -= len(datos)
            yield datos
    finally:
        fichero.close()


def servir(request, campo, tipo: str, nombre_original: str = ""):
    """El fichero, en línea si se puede enseñar y como adjunto si no. Atiende `Range`."""
    contenido = tipo_de_contenido(tipo, campo.name)
    tamano = campo.size
    cabecera = RANGO.match(request.headers.get("Range", "").strip())

    if contenido and cabecera and (cabecera.group(1) or cabecera.group(2)):
        if cabecera.group(1):
            inicio = int(cabecera.group(1))
            fin = int(cabecera.group(2)) if cabecera.group(2) else tamano - 1
        else:  # `bytes=-500`: los últimos 500
            inicio = max(tamano - int(cabecera.group(2)), 0)
            fin = tamano - 1
        fin = min(fin, tamano - 1)
        if inicio > fin or inicio >= tamano:
            respuesta = HttpResponse(status=416)
            respuesta["Content-Range"] = f"bytes */{tamano}"
            return respuesta
        from django.http import StreamingHttpResponse

        longitud = fin - inicio + 1
        respuesta = StreamingHttpResponse(
            _trozos(campo.open("rb"), inicio, longitud), status=206, content_type=contenido
        )
        respuesta["Content-Range"] = f"bytes {inicio}-{fin}/{tamano}"
        respuesta["Content-Length"] = str(longitud)
    elif contenido:
        respuesta = FileResponse(campo.open("rb"), content_type=contenido)
    else:
        nombre = nombre_original or f"evidencia{extension(campo.name)}"
        respuesta = FileResponse(
            campo.open("rb"),
            as_attachment=True,
            filename=nombre,
            content_type="application/octet-stream",
        )

    respuesta["Accept-Ranges"] = "bytes" if contenido else "none"
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, max-age=3600"
    if contenido != "application/pdf":
        # Aunque algo se colara, no ejecuta nada. El PDF se queda fuera porque
        # el visor del navegador no arranca dentro de un sandbox.
        respuesta["Content-Security-Policy"] = "sandbox; default-src 'none'; media-src 'self'; img-src 'self'"
    return respuesta
