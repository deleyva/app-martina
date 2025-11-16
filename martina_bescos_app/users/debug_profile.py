"""Vista temporal de debug para verificar la foto de perfil de Google."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from allauth.socialaccount.models import SocialAccount


@login_required
def debug_profile_picture(request):
    """Vista de debug para verificar la información de la cuenta social."""
    data = {
        "user_email": request.user.email,
        "user_name": request.user.name,
        "has_social_accounts": False,
        "picture_url": None,
        "extra_data": None,
    }

    social_accounts = SocialAccount.objects.filter(user=request.user)

    if social_accounts.exists():
        data["has_social_accounts"] = True
        data["social_accounts_count"] = social_accounts.count()

        google_account = social_accounts.filter(provider="google").first()
        if google_account:
            data["has_google_account"] = True
            data["picture_url"] = google_account.extra_data.get("picture")
            data["extra_data"] = google_account.extra_data
        else:
            data["has_google_account"] = False

    return JsonResponse(data, json_dumps_params={"indent": 2})
