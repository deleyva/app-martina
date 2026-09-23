# ruff: noqa: ERA001, E501
"""Base settings to build other settings files upon."""


from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# martina_bescos_app/
APPS_DIR = BASE_DIR / "martina_bescos_app"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "Europe/Madrid"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
# Castellano: es el idioma del centro. Manda en el admin de Wagtail para
# quien no tenga idioma elegido en su perfil, y en los correos de aviso
# de moderacion, que salian en ingles por este valor.
LANGUAGE_CODE = "es"
# El defecto NO basta, y esto se midio: `get_preferred_language()` de un
# perfil sin idioma elegido —los ocho de produccion— devuelve el idioma
# ACTIVO si es uno de los que trae el admin, y solo cae en `LANGUAGE_CODE`
# si no lo es. El idioma activo lo pone `LocaleMiddleware` a partir del
# `Accept-Language` del navegador, asi que a quien tiene el Chrome en
# ingles el admin le salia en ingles igualmente, y el aviso de moderacion
# salia en el idioma de QUIEN ENVIA, no en el de quien lo recibe.
#
# Dejando una sola lengua permitida, ningun idioma del navegador es un
# idioma de admin valido y todos caen en `LANGUAGE_CODE`. Afecta solo al
# panel: la negociacion de idioma del sitio publico no se toca.
#
# Efecto secundario: desaparece el desplegable de idioma de
# `/cms/account/` (wagtail/admin/forms/account.py lo quita cuando hay una
# sola). Para devolverlo, borrar estas lineas.
WAGTAILADMIN_PERMITTED_LANGUAGES = [("es", "Español")]
# https://docs.djangoproject.com/en/dev/ref/settings/#languages
# from django.utils.translation import gettext_lazy as _
# LANGUAGES = [
#     ('en', _('English')),
#     ('fr-fr', _('French')),
#     ('pt-br', _('Portuguese')),
# ]
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(BASE_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize", # Handy template tags
    "django.contrib.postgres",  # registra el lookup `unaccent` del buscador
    "django.contrib.admin",
    "django.forms",
]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_tailwind",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "huey.contrib.djhuey",
    "django_mailbox",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
]

LOCAL_APPS = [
    "martina_bescos_app.users",
    "clases",  # Gestión de grupos, estudiantes y sesiones de clase
    "evaluations",
    "api_keys",
    "songs_ranking",
    "explorer",
    "cms",  # Núcleo compartido: portada, página estándar, ayuda, enlaces externos
    "blogs",  # Blogs de departamento — blogs.iesmartinabescos.es
    "musica",  # Biblioteca musical — apps.iesmartinabescos.es
    "my_library",  # Biblioteca personal de usuario
    "incidencias",  # Sistema de incidencias informáticas
    "wifi",  # Altas de dispositivos en la WiFi del centro
    "analytics",
    "content_hub",  # Sistema flexible de gestión de contenido musical (grafo de conocimiento)
    "programacion",  # Programación didáctica: planes por trimestre, cobertura y recomendaciones
    "repertorio",  # Catálogo de repertorio consultable (JamZone importado + propio)
    "calificaciones",  # Calificaciones: criterios × instrumentos, cuadro, modo clase y evidencias
    # Your stuff: custom apps go here
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# JamZone (Music Will): endpoint GROQ del CMS Sanity que hay detrás de su web.
# Va como setting con valor por defecto y NO como variable de entorno a
# propósito: `just deploy-production` solo copia los `.envs` que existan en
# local, así que una variable nueva no llegaría sola al servidor.
JAMZONE_SANITY_URL = env(
    "JAMZONE_SANITY_URL",
    default="https://teha7qd2.api.sanity.io/v2025-09-25/data/query/production",
)

# Spotify API settings
# ------------------------------------------------------------------------------
SPOTIFY_CLIENT_ID = env("SPOTIFY_CLIENT_ID", default="your-spotify-client-id")
SPOTIFY_CLIENT_SECRET = env(
    "SPOTIFY_CLIENT_SECRET", default="your-spotify-client-secret"
)

# Meilisearch Configuration (for content_hub full-text search)
# ------------------------------------------------------------------------------
MEILISEARCH_URL = env("MEILISEARCH_URL", default="http://localhost:7700")
MEILISEARCH_API_KEY = env("MEILISEARCH_API_KEY", default="")

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "martina_bescos_app.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "users:redirect"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = "account_login"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.sites.middleware.CurrentSiteMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "martina_bescos_app.middleware.AppModeMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [str(APPS_DIR / "static")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = str(APPS_DIR / "media")
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        "DIRS": [str(APPS_DIR / "templates")],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "martina_bescos_app.users.context_processors.allauth_settings",
                "martina_bescos_app.users.context_processors.impersonation_info",
                "martina_bescos_app.users.context_processors.user_profile_picture",
                "martina_bescos_app.users.context_processors.user_groups",
                "martina_bescos_app.users.context_processors.profesorado",
                "martina_bescos_app.utils.context_processors.base_template_context",
                "blogs.context_processors.blog_navigation",
            ],
        },
    },
]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "tailwind"
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
#
# SAMEORIGIN y no DENY: la app se enmarca a sí misma en tres sitios —el botón de
# «ver la página completa» del modo presentación, el modal de plantillas y las
# previsualizaciones del panel de Wagtail—, y `DENY` bloquea eso aunque el marco
# y la página vengan del mismo dominio. En producción eso salía como un error
# del navegador dentro del modal, y en local no se veía porque `local.py` pone
# `ALLOWALL`: el fallo solo existía donde nadie lo probaba.
#
# La protección contra clickjacking sigue en pie. Para enmarcar la app haría
# falta servir la página contenedora desde este mismo origen, y quien pueda
# hacer eso ya tiene bastante más que un marco.
X_FRAME_OPTIONS = "SAMEORIGIN"

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_TIMEOUT = 5

DEFAULT_USER_EMAIL_DOMAIN = env("DJANGO_DEFAULT_USER_EMAIL_DOMAIN", default="iesmartinabescos.es")
INCIDENCIAS_SITE_URL = env("DJANGO_INCIDENCIAS_SITE_URL", default="https://apps.iesmartinabescos.es/incidencias")

# WiFi — altas de dispositivos
# ------------------------------------------------------------------------------
# La clave NO tiene valor por defecto a propósito: este repositorio es público y
# escribirla aquí la publicaría para siempre y con historial. Sin ella, la app
# funciona pero no manda el correo, y lo deja escrito en el log.
WIFI_SSID = env("DJANGO_WIFI_SSID", default="MARTINABESCOS")
WIFI_PASSWORD = env("DJANGO_WIFI_PASSWORD", default="")
WIFI_SITE_URL = env("DJANGO_WIFI_SITE_URL", default="https://apps.iesmartinabescos.es/wifi")
# Separa personal de alumnado por la convención de cuentas del centro: el
# alumnado lleva prefijo numérico de promoción (`0125eromero`), el personal no.
# Es una heurística; el grupo «WiFi personal autorizado» cubre las excepciones.
WIFI_PATRON_PERSONAL = env("DJANGO_WIFI_PATRON_PERSONAL", default=r"^[a-z]")
WIFI_DOMINIOS_EXTRA = env.list("DJANGO_WIFI_DOMINIOS_EXTRA", default=[])

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [("""Jesús López de Leyva""", "jesuslopezdeleyva@gmail.com")]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS
# https://cookiecutter-django.readthedocs.io/en/latest/settings.html#other-environment-settings
# Force the `admin` sign in process to go through the `django-allauth` workflow
DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
REDIS_SSL = REDIS_URL.startswith("rediss://")

# django-allauth
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
# Correos que SÍ pueden entrar con email y contraseña. El adaptador
# (`users/adapters.py`) obliga a Google a todo el mundo salvo staff, cuentas con
# social vinculada e impersonación; esto abre una puerta estrecha y NOMINAL para
# cuentas de pruebas o de servicio, sin tener que darles `is_staff` —que es
# acceso al admin— ni abrir el login por contraseña a todo el alumnado.
# Vacío por defecto: sin configurar la variable, no cambia nada para nadie.
# Dominios que entran con Google. Todo lo demás solo entra si el administrador
# lo da de alta a mano (casilla «Puede entrar con contraseña» en la ficha del
# usuario). Es una variable, y no una constante, para poder ampliarla el día que
# el centro estrene otro dominio sin tener que desplegar.
SOCIAL_LOGIN_DOMAINS = env.list(
    "DJANGO_SOCIAL_LOGIN_DOMAINS", default=["iesmartinabescos.es"]
)
PASSWORD_LOGIN_EMAILS = env.list("DJANGO_PASSWORD_LOGIN_EMAILS", default=[])
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_AUTHENTICATION_METHOD = "email"
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_EMAIL_REQUIRED = True
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_USERNAME_REQUIRED = False
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_ADAPTER = "martina_bescos_app.users.adapters.AccountAdapter"
# https://docs.allauth.org/en/latest/account/forms.html
ACCOUNT_FORMS = {"signup": "martina_bescos_app.users.forms.UserSignupForm"}
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
SOCIALACCOUNT_ADAPTER = "martina_bescos_app.users.adapters.SocialAccountAdapter"
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
SOCIALACCOUNT_FORMS = {"signup": "martina_bescos_app.users.forms.UserSocialSignupForm"}

# Bypass the intermediate "Sign In" page when clicking on a social login button
# https://django-allauth.readthedocs.io/en/latest/configuration.html
SOCIALACCOUNT_LOGIN_ON_GET = True

# Your stuff...
# ------------------------------------------------------------------------------


# Your stuff...
# ------------------------------------------------------------------------------

# Configuración de proveedores de socialaccount
# ------------------------------------------------------------------------------
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        # Permitir callback dinámico para desarrollo
        "OAUTH_PKCE_ENABLED": True,
    }
}


# HUEY Configuration
# ------------------------------------------------------------------------------
HUEY = {
    "huey_class": "huey.RedisHuey",
    "name": env("DJANGO_HUEY_NAME", default="default-huey-queue"),
    "results": True,  # Store task results
    "store_none": False,  # Do not store None results
    "immediate": env.bool("DJANGO_HUEY_IMMEDIATE", default=False),
    "utc": True,  # Use UTC for scheduled tasks
    "connection": {
        "host": env("REDIS_HOST", default="redis"),
        "port": env.int("REDIS_PORT", default=6379),
        "db": env.int("DJANGO_HUEY_REDIS_DB", default=0),
        "password": env("REDIS_PASSWORD", default=None),
    },
    "consumer": {
        "workers": env.int("DJANGO_HUEY_WORKERS", default=2),
        "worker_type": "thread",  # Options: 'thread', 'process', 'greenlet'
        "initial_delay": 0.1,  # In seconds
        "backoff": 1.15,  # Exponential backoff factor
        "max_delay": 10.0,  # Maximum delay in seconds
        "scheduler_interval": 1,  # In seconds
        "periodic": True,  # Enable periodic tasks
        "check_worker_health": True,
        "health_check_interval": 10,  # In seconds
    },
}

# django-sql-explorer
EXPLORER_DEFAULT_CONNECTION = "default"
EXPLORER_CONNECTIONS = {"readonly": "default"}
EXPLORER_PERMISSION_VIEW = lambda r: r.user.is_staff  # Solo staff puede ver queries
EXPLORER_PERMISSION_CHANGE = lambda r: r.user.is_staff  # Solo staff puede editar
EXPLORER_PUBLIC_QUERY_MODE = True  # Permitir compartir queries públicamente

# Wagtail
WAGTAIL_SITE_NAME = "IES Blog"
# Los avisos de moderación van al jefe del departamento, no a todos los
# superusuarios. Con el valor por defecto (True), cada artículo enviado a
# revisión en cualquiera de los 17 departamentos mandaba dos correos a cada
# superusuario. Decisión de Jesús, 2026-09-16.
WAGTAILADMIN_NOTIFICATION_INCLUDE_SUPERUSERS = False

# Los documentos pasan POR LA VISTA de Wagtail, para que el gancho decida.
#
# El defecto es `redirect`: la URL del documento manda un 302 al fichero de
# media y a partir de ahí lo sirve el servidor web sin pasar por Django. Con
# eso, `before_serve_document` no llega a aplicarse nunca y cualquiera con el
# enlace se baja un método comercial entero.
#
# **Pero servirlo TODO por Django tampoco vale.** La vista de Wagtail no atiende
# peticiones por rango —medido: `bytes=0-99` devuelve un 200 con el fichero
# entero—, y los 43 audios del centro (101 MB, el mayor de 23) se reproducen con
# `<audio>` nativo, que necesita rangos para mover la barra.
#
# La salida es el gancho `musica.servido.servido_selectivo`: bloquea lo
# restringido y **redirige todo lo demás al fichero**, como antes. Django decide;
# el servidor web sigue sirviendo.
WAGTAILDOCS_SERVE_METHOD = "serve_view"

WAGTAILDOCS_EXTENSIONS = [
    "csv",
    "docx",
    "key",
    "odt",
    "pdf",
    "pptx",
    "rtf",
    "txt",
    "xlsx",
    "zip",
    # Audio formats for Music Pills
    "mp3",
    "wav",
    "ogg",
    "m4a",
    "aac",
    "flac",
    "wma",
    # MIDI formats for Music Pills
    "mid",
    "midi",
    # Video formats for Blog
    "mp4",
    "webm",
    "mov",
    # Guitar Pro — se renderizan con alphaTab en la ficha y en el visor
    "gp",
    "gp3",
    "gp4",
    "gp5",
    "gpx",
]

# Wagtail Embeds Custom Finders
WAGTAILEMBEDS_FINDERS = [
    {
        'class': 'cms.embed_finders.HooktheoryEmbedFinder',
    },
    {
        'class': 'wagtail.embeds.finders.oembed',
    }
]

# Google Gemini API
# ------------------------------------------------------------------------------
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")

# Gemini Rate Limiting (project-wide)
# ------------------------------------------------------------------------------
GEMINI_RATE_LIMIT_HOURLY = env.int("GEMINI_RATE_LIMIT_HOURLY", default=2)
GEMINI_ALERT_EMAIL = env("GEMINI_ALERT_EMAIL", default="")

# django-mailbox (Email → Incidencia)
# ------------------------------------------------------------------------------
MAILBOX_IMAP_HOST = env("MAILBOX_IMAP_HOST", default="imap.gmail.com")
MAILBOX_IMAP_PORT = env.int("MAILBOX_IMAP_PORT", default=993)
MAILBOX_IMAP_USER = env("MAILBOX_IMAP_USER", default="")
MAILBOX_IMAP_PASSWORD = env("MAILBOX_IMAP_PASSWORD", default="")
