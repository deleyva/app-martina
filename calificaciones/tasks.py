"""Compresión de los vídeos de evidencia, en segundo plano.

Misma receta que `evaluations.tasks.process_video_compression`: 720p, h264,
`faststart` para que el navegador empiece a reproducir sin bajarlo entero. El
original se borra al terminar, que un minuto de vídeo de móvil son 100 MB.

Una grabación de grupo (fase 62·2) es UN fichero que comparten hasta tres
evidencias: se comprime una vez y todas pasan a apuntar al mismo MP4.
"""

import logging
import os
import subprocess
import tempfile
import uuid

from django.core.files.base import File
from huey.contrib.djhuey import db_task

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
