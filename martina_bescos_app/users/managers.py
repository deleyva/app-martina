from typing import TYPE_CHECKING

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import UserManager as DjangoUserManager

if TYPE_CHECKING:
    from .models import User  # noqa: F401


class UserManager(DjangoUserManager["User"]):
    """Custom manager for the User model."""

    def precrear_del_centro(self, email: str, nombre: str = "", apellidos: str = ""):
        """Un usuario que entrará con Google y todavía no ha entrado.

        Devuelve `(usuario, creado)`. Si ya existe se devuelve tal cual, sin
        tocarle el nombre: el nombre lo pisa Google en cada entrada
        (`SocialAccountAdapter._nombre_de_google`) y lo que escribió la gestión
        del centro no tiene por qué ganar a lo que ya había.

        Sin contraseña utilizable, y con la `EmailAddress` verificada, que es lo
        que allauth mira para enlazar la cuenta de Google al usuario existente
        sin pedir nada.
        """
        from allauth.account.models import EmailAddress

        email = self.normalize_email(email.strip())
        existente = self.filter(email__iexact=email).first()
        if existente is not None:
            return existente, False

        usuario = self.model(
            email=email,
            first_name=nombre.strip(),
            last_name=apellidos.strip(),
            name=f"{nombre.strip()} {apellidos.strip()}".strip(),
        )
        usuario.set_unusable_password()
        usuario.save(using=self._db)
        EmailAddress.objects.create(
            user=usuario, email=email, verified=True, primary=True
        )
        return usuario, True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            msg = "The given email must be set"
            raise ValueError(msg)
        email = self.normalize_email(email)
        
        # Split name into first_name and last_name if name is provided
        if 'name' in extra_fields and extra_fields['name']:
            name_parts = extra_fields['name'].split(' ', 1)
            if len(name_parts) > 0 and not extra_fields.get('first_name'):
                extra_fields['first_name'] = name_parts[0]
            if len(name_parts) > 1 and not extra_fields.get('last_name'):
                extra_fields['last_name'] = name_parts[1]
                
        user = self.model(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):  # type: ignore[override]
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):  # type: ignore[override]
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            msg = "Superuser must have is_staff=True."
            raise ValueError(msg)
        if extra_fields.get("is_superuser") is not True:
            msg = "Superuser must have is_superuser=True."
            raise ValueError(msg)

        return self._create_user(email, password, **extra_fields)
