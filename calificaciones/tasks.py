"""Compresión de los vídeos de evidencia, en segundo plano.

Misma receta que `evaluations.tasks.process_video_compression`: 720p, h264,
`faststart` para que el navegador empiece a reproducir sin bajarlo entero. El
original se borra al terminar, que un minuto de vídeo de móvil son 100 MB.
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
    evidencia.estado = Evidencia.PROCESANDO
    evidencia.save(update_fields=["estado"])

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
            evidencia.estado = Evidencia.FALLIDO
            evidencia.error = resultado.stderr[-2000:]
            evidencia.save(update_fields=["estado", "error"])
            logger.error("ffmpeg falló en la evidencia %s", evidencia_id)
            return
        with open(salida, "rb") as f:
            evidencia.archivo_comprimido.save("video.mp4", File(f), save=False)
        original = evidencia.archivo.path
        evidencia.archivo.delete(save=False)
        evidencia.tipo_mime = "video/mp4"
        evidencia.estado = Evidencia.LISTO
        evidencia.error = ""
        evidencia.save(update_fields=["archivo", "archivo_comprimido", "tipo_mime", "estado", "error"])
        if os.path.exists(original):
            os.remove(original)
    except Exception as e:  # noqa: BLE001
        logger.exception("Error comprimiendo la evidencia %s", evidencia_id)
        evidencia.estado = Evidencia.FALLIDO
        evidencia.error = str(e)
        evidencia.save(update_fields=["estado", "error"])
    finally:
        if os.path.exists(salida):
            os.remove(salida)
