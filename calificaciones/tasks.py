"""Lo que se hace con las evidencias en segundo plano: comprimir vídeos y fotocopiar fotos.

**Vídeo.** Misma receta que `evaluations.tasks.process_video_compression`:
720p, h264, `faststart` para que el navegador empiece a reproducir sin bajarlo
entero. El original se borra al terminar, que un minuto de vídeo de móvil son
100 MB. Una grabación de grupo (fase 62·2) es UN fichero que comparten hasta
tres evidencias: se comprime una vez y todas pasan a apuntar al mismo MP4.

**Foto (fase 84).** El folio enderezado, como fotocopia en color y en WebP
(`documento.py`). El original se borra solo después de guardar el WebP: si
algo falla por el camino, la foto sigue ahí.
"""

import logging
import os
import subprocess
import tempfile
import uuid

from datetime import timedelta

from django.core.files.base import ContentFile, File
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from . import documento
from .models import Evidencia

logger = logging.getLogger(__name__)


@db_task()
def comprimir_video(evidencia_id):
    evidencia = Evidencia.objects.filter(pk=evidencia_id).first()
    if evidencia is None or not evidencia.archivo:
        return
    # Ella y las de su grabación de grupo, que comparten el fichero original.
    grupo = Evidencia.objects.filter(pk=evidencia.pk) | evidencia.hermanas().filter(archivo=evidencia.archivo.name)
    grupo.update(estado=Evidencia.PROCESANDO)

    salida = os.path.join(tempfile.gettempdir(), f"evidencia_{uuid.uuid4().hex}.mp4")
    comando = [
        "ffmpeg", "-i", evidencia.archivo.path, "-y",
        "-vf", "scale=-2:720", "-r", "30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "26",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", salida,
    ]
    try:
        resultado = subprocess.run(comando, check=False, capture_output=True, text=True)
        if resultado.returncode != 0:
            grupo.update(estado=Evidencia.FALLIDO, error=resultado.stderr[-2000:])
            logger.error("ffmpeg falló en la evidencia %s", evidencia_id)
            return
        with open(salida, "rb") as f:
            evidencia.archivo_comprimido.save("video.mp4", File(f), save=False)
        original = evidencia.archivo.path
        # Todas las del grupo apuntan al MP4 y sueltan el original, que se
        # borra una sola vez.
        grupo.update(
            archivo="",
            archivo_comprimido=evidencia.archivo_comprimido.name,
            tipo_mime="video/mp4",
            tamano=evidencia.archivo_comprimido.size,
            estado=Evidencia.LISTO,
            error="",
        )
        if os.path.exists(original):
            os.remove(original)
    except Exception as e:  # noqa: BLE001
        logger.exception("Error comprimiendo la evidencia %s", evidencia_id)
        grupo.update(estado=Evidencia.FALLIDO, error=str(e))
    finally:
        if os.path.exists(salida):
            os.remove(salida)


def _soltar(almacen, nombre):
    """Borra un fichero que ya no es de nadie; si falla, lo deja escrito y sigue."""
    try:
        almacen.delete(nombre)
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo borrar %s", nombre)


@db_task()
def procesar_foto(evidencia_id):
    evidencia = Evidencia.objects.filter(pk=evidencia_id, tipo=Evidencia.FOTO).first()
    if evidencia is None or not evidencia.archivo:
        return
    original = evidencia.archivo.name
    almacen = evidencia.archivo.storage
    # Todo se escribe solo si la fila sigue apuntando a ESTE original: si la
    # borraron o la procesó otra pasada mientras tanto, no se pisa nada.
    esta = Evidencia.objects.filter(pk=evidencia.pk, archivo=original)
    esta.update(estado=Evidencia.PROCESANDO)
    webp_guardado = ""
    try:
        with evidencia.archivo.open("rb") as f:
            webp, hecho = documento.procesar(f.read())
        evidencia.archivo_comprimido.save("foto.webp", ContentFile(webp), save=False)
        webp_guardado = evidencia.archivo_comprimido.name
        actualizadas = esta.update(
            archivo="",
            archivo_comprimido=webp_guardado,
            tipo_mime="image/webp",
            tamano=evidencia.archivo_comprimido.size,
            estado=Evidencia.LISTO,
            error="",
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Error procesando la foto %s", evidencia_id)
        esta.update(estado=Evidencia.FALLIDO, error=str(e)[-2000:])
        if webp_guardado and not Evidencia.objects.filter(archivo_comprimido=webp_guardado).exists():
            _soltar(almacen, webp_guardado)
        return
    if not actualizadas:
        _soltar(almacen, webp_guardado)
        return
    # El WebP ya está servido: si borrar el original falla, la evidencia sigue
    # lista y solo queda un fichero de más en disco.
    _soltar(almacen, original)
    logger.info("Foto %s procesada: %s, %s bytes", evidencia_id, hecho, len(webp))


@db_periodic_task(crontab(minute="*/15"))
def rescatar_fotos():
    """Las fotos que se quedaron sin procesar vuelven a la cola.

    Pasa si Redis no contestaba al subir (el encolado va con `robust=True` y
    no tumba la subida) o si el consumidor se reinició a media tarea en un
    despliegue. Lo que falló de verdad (`fallido`) no se reintenta.
    """
    hace_un_rato = timezone.now() - timedelta(minutes=10)
    atascadas = (
        Evidencia.objects.filter(tipo=Evidencia.FOTO, estado__in=[Evidencia.PENDIENTE, Evidencia.PROCESANDO])
        .exclude(archivo="")
        .filter(created_at__lt=hace_un_rato)
        .values_list("pk", flat=True)
    )
    for pk in atascadas:
        procesar_foto(pk)
