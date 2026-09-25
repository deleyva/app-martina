"""Tareas en segundo plano de `clases`."""

import logging

from huey.contrib.djhuey import db_task

logger = logging.getLogger(__name__)


@db_task(retries=2, retry_delay=60, context=True)
def transcribir_nota(nota_pk: int, task=None) -> str:
    """Manda el audio de una nota de clase a Whisper y guarda lo que entienda.

    Whisper vive en su propio contenedor (`compose/production/whisper`), que
    atiende una nota cada vez. Si falla, Huey reintenta dos veces; tras el
    último fallo la nota queda en `error` con su audio intacto, y el profesor
    escribe el texto a mano en la lista de revisión. **El audio no se pierde
    nunca por culpa de la transcripción.**
    """
    import requests
    from django.conf import settings

    from clases.models import SessionNote

    nota = SessionNote.objects.filter(pk=nota_pk).first()
    if nota is None or not nota.audio:
        # Descartada antes de transcribirse: no hay nada que hacer.
        return "sin nota"

    ultimo_intento = task is None or task.retries == 0
    try:
        with nota.audio.open("rb") as f:
            datos = f.read()
        r = requests.post(settings.WHISPER_URL, data=datos, timeout=180)
        r.raise_for_status()
        texto = (r.json().get("texto") or "").strip()
    except Exception:
        if ultimo_intento:
            SessionNote.objects.filter(pk=nota_pk).update(estado=SessionNote.ERROR)
            logger.exception("Whisper no pudo transcribir la nota %s", nota_pk)
            return "error"
        raise  # Huey reintenta

    # `update` y no `save`: si el profesor la descartó mientras Whisper
    # trabajaba, no hay fila que resucitar.
    SessionNote.objects.filter(pk=nota_pk).update(
        transcripcion=texto, estado=SessionNote.TRANSCRITA
    )
    return "transcrita"
