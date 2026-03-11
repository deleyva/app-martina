import logging

from django.conf import settings

from ..models import Incidencia

logger = logging.getLogger(__name__)


def _username_to_email(username: str) -> str | None:
    """Convierte un username (ej. 'eromero') a email corporativo."""
    if not username or not username.strip():
        return None
    username = username.strip().lower()
    if "@" in username:
        return username
    
    domain = getattr(settings, "DEFAULT_USER_EMAIL_DOMAIN", "iesmartinabescos.es")
    return f"{username}@{domain}"


class IncidenciaNotificationService:
    @staticmethod
    def get_participant_emails(incidencia: Incidencia) -> list[str]:
        """
        Recopila los emails de todos los participantes de una incidencia:
        - Creador (reportado_por)
        - Técnico asignado (si lo hay)
        - Usuarios que hayan comentado previamente
        """
        emails = set()

        # 1. Creador
        if incidencia.reportero_nombre:
            email_creador = _username_to_email(incidencia.reportero_nombre)
            if email_creador:
                emails.add(email_creador)

        # 2. Técnico asignado
        if incidencia.asignado_a and incidencia.asignado_a.user.email:
            emails.add(incidencia.asignado_a.user.email)

        # 3. Comentaristas
        for comentario in incidencia.comentarios.all():
            if comentario.autor_nombre:
                email_comentarista = _username_to_email(comentario.autor_nombre)
                if email_comentarista:
                    emails.add(email_comentarista)

        return list(emails)

    @staticmethod
    def notify_estado_changed(incidencia_id: int, old_estado: str, new_estado: str) -> None:
        """Dispara tarea asíncrona para notificar cambio de estado."""
        from django.db import transaction
        from ..tasks import send_estado_changed_notification

        transaction.on_commit(
            lambda: send_estado_changed_notification(incidencia_id, old_estado, new_estado)
        )

    @staticmethod
    def notify_new_comment(incidencia_id: int, comentario_id: int) -> None:
        """Dispara tarea asíncrona para notificar nuevo comentario."""
        from django.db import transaction
        from ..tasks import send_new_comment_notification

        transaction.on_commit(
            lambda: send_new_comment_notification(incidencia_id, comentario_id)
        )