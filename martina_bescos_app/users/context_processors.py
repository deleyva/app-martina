from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


def allauth_settings(request):  # El argumento es necesario aunque no se use directamente
    """Expose some settings from django-allauth in templates.
    
    Args:
        request: La solicitud HTTP actual (requerido para context processors).
    """
    return {
        "ACCOUNT_ALLOW_REGISTRATION": settings.ACCOUNT_ALLOW_REGISTRATION,
    }


def impersonation_info(request):
    """Expose impersonation information to templates."""
    context = {
        "is_impersonating": False,
        "impersonator": None
    }
    
    if request.user.is_authenticated and 'impersonator_id' in request.session:
        impersonator_id = request.session['impersonator_id']
        try:
            impersonator = User.objects.get(id=impersonator_id)
            context.update({
                "is_impersonating": True,
                "impersonator": impersonator
            })
        except User.DoesNotExist:
            # Si el usuario no existe, limpiamos la sesión
            if 'impersonator_id' in request.session:
                del request.session['impersonator_id']
    
    return context
