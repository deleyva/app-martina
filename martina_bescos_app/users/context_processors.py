from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


def allauth_settings(
    request,
):  # El argumento es necesario aunque no se use directamente
    """Expose some settings from django-allauth in templates.

    Args:
        request: La solicitud HTTP actual (requerido para context processors).
    """
    return {
        "ACCOUNT_ALLOW_REGISTRATION": settings.ACCOUNT_ALLOW_REGISTRATION,
    }


def impersonation_info(request):
    """Expose impersonation information to templates."""
    context = {"is_impersonating": False, "impersonator": None}

    if request.user.is_authenticated and "impersonator_id" in request.session:
        impersonator_id = request.session["impersonator_id"]
        try:
            impersonator = User.objects.get(id=impersonator_id)
            context.update({"is_impersonating": True, "impersonator": impersonator})
        except User.DoesNotExist:
            # Si el usuario no existe, limpiamos la sesión
            if "impersonator_id" in request.session:
                del request.session["impersonator_id"]

    return context


def user_profile_picture(request):
    """Obtener la foto de perfil del usuario desde Google Social Account."""
    picture_url = None

    if request.user.is_authenticated:
        # Intentar obtener la foto de perfil de Google
        try:
            from allauth.socialaccount.models import SocialAccount

            social_account = SocialAccount.objects.filter(
                user=request.user, provider="google"
            ).first()

            if social_account and social_account.extra_data:
                # Google puede devolver 'picture' en extra_data
                picture_url = social_account.extra_data.get("picture")

                # Debug: Descomentar para ver la URL en logs
                # import logging
                # logger = logging.getLogger(__name__)
                # logger.info(f"Profile picture URL: {picture_url}")
        except Exception as e:
            # Si hay algún error, simplemente no mostrar imagen
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Error getting profile picture: {e}")
            pass

    return {"user_profile_picture": picture_url}


def user_groups(request):
    """Obtener los grupos del usuario (como alumno o profesor) para el menú de navegación."""
    groups = []

    if request.user.is_authenticated:
        try:
            from clases.models import Group

            if request.user.is_staff:
                # Profesores: obtener grupos donde es profesor
                groups = list(request.user.teaching_groups.all().order_by("name"))
            else:
                # Alumnos: obtener grupos a través de enrollments
                from clases.models import Student

                student = Student.objects.filter(user=request.user).first()
                if student and student.group:
                    groups = [student.group]
        except Exception:
            pass

    return {"user_groups": groups}
