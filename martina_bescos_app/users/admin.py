from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import User

if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    # Force the `admin` sign in process to go through the `django-allauth` workflow:
    # https://docs.allauth.org/en/latest/common/admin.html#admin
    admin.autodiscover()
    admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("name", "first_name", "last_name")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = ["email", "name", "first_name", "last_name", "is_superuser", "get_last_login_display"]
    search_fields = ["name", "first_name", "last_name", "email"]
    ordering = ["id"]
    readonly_fields = ["last_login", "date_joined"]
    
    @admin.display(description=_("Último acceso"), ordering="last_login")
    def get_last_login_display(self, obj):
        """Formatear la fecha del último login de forma legible"""
        if obj.last_login:
            from django.utils import timezone
            now = timezone.now()
            diff = now - obj.last_login
            
            # Si fue hoy
            if diff.days == 0:
                hours = diff.seconds // 3600
                if hours == 0:
                    minutes = diff.seconds // 60
                    if minutes == 0:
                        return "Hace unos segundos"
                    return f"Hace {minutes} min"
                return f"Hace {hours}h"
            # Si fue ayer
            elif diff.days == 1:
                return "Ayer"
            # Si fue esta semana
            elif diff.days < 7:
                return f"Hace {diff.days} días"
            # Si fue hace más tiempo
            else:
                return obj.last_login.strftime("%d/%m/%Y %H:%M")
        return "Nunca"
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "name", "first_name", "last_name"),
            },
        ),
    )
