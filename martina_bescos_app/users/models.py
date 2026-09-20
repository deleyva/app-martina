from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    """
    Default custom user model for Martina Bescós App.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = CharField(_("First Name"), blank=True, max_length=150)
    last_name = CharField(_("Last Name"), blank=True, max_length=150)
    email = EmailField(_("email address"), unique=True)
    acceso_con_contrasena = BooleanField(
        _("Puede entrar con contraseña"),
        default=False,
        help_text=_(
            "Para las cuentas de fuera del centro, que da de alta el "
            "administrador a mano. Quien tiene correo del centro entra con "
            "Google y no necesita esto."
        ),
    )
    username = None  # type: ignore[assignment]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.id})

    @property
    def es_tecnico(self) -> bool:
        """Check if user has an active technician profile."""
        return hasattr(self, "perfil_tecnico") and self.perfil_tecnico.activo
