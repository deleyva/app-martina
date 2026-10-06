
class AppModeMiddleware:
    """
    Decide el modo de aplicación (principal, incidencias o wifi) a partir de la URL,
    para servir la plantilla base correcta en vistas compartidas como auth y
    perfiles de usuario.

    El modo se guarda en la sesión SOLO cuando cambia, y solo cuando no es el
    valor por defecto. Escribir en cada petición marcaba la sesión como
    modificada siempre (`SessionBase.__setitem__` pone `modified = True` aunque
    el valor sea idéntico), con dos consecuencias:

    1. Una fila de sesión por visitante anónimo, incluidos bots.
    2. Un read-modify-write de la sesión entera en cada petición. El backend de
       sesión en BD serializa todo el diccionario, así que dos peticiones
       concurrentes sobre la misma sesión son un "gana el último que guarda":
       la que carga antes y guarda después borra lo que escribió la otra. Eso
       llegaba a borrar el `socialaccount_states` de un login de Google en
       vuelo, y el callback moría con `Codigo: unknown` sin excepción.

    Solo se persisten los modos distintos del defecto ('incidencias', 'wifi').
    Los dos únicos consumidores del valor (`utils/context_processors.py` y
    `users/adapters.py`) comparan contra esas cadenas y nada más, de modo que
    la ausencia de la clave ya significa "main".
    """

    #: Rutas que no representan navegación del usuario y por tanto nunca deben
    #: decidir el modo. `/analytics/` está aquí no solo por la carrera de
    #: sesión: navegando por `/incidencias/`, su POST de telemetría caía en la
    #: rama por defecto y devolvía el modo a "main".
    NON_NAVIGATIONAL_PREFIXES = ("/analytics/", "/static/", "/media/")

    #: Vistas compartidas entre ambos modos: conservan el modo que ya hubiera.
    MODE_PRESERVING_PREFIXES = ("/accounts/", "/users/", "/admin/")

    #: Modo por defecto. No se persiste: su ausencia en la sesión lo implica.
    DEFAULT_MODE = "main"

    SESSION_KEY = "app_mode"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        mode = self.mode_for_path(request.path)
        if mode is not None:
            self._remember(request.session, mode)
        return self.get_response(request)

    def mode_for_path(self, path):
        """Modo que implica esta ruta, o None si la ruta no debe decidirlo."""
        if path.startswith(self.NON_NAVIGATIONAL_PREFIXES):
            return None
        if path.startswith(self.MODE_PRESERVING_PREFIXES):
            return None
        if path.startswith("/incidencias/"):
            return "incidencias"
        if path.startswith("/wifi/"):
            return "wifi"
        return self.DEFAULT_MODE

    def _remember(self, session, mode):
        """Escribe en la sesión únicamente si el estado guardado cambia."""
        current = session.get(self.SESSION_KEY)
        if mode == self.DEFAULT_MODE:
            # El defecto no se guarda. Solo hay que limpiar si veníamos de
            # otro modo, y esa sí es una transición real.
            if current is not None:
                del session[self.SESSION_KEY]
        elif current != mode:
            session[self.SESSION_KEY] = mode


class AppsAccessMiddleware:
    """La app de música de `apps.` es solo para quien `puede_usar_apps`.

    Un mismo proyecto Django sirve dos dominios y, dentro de `apps.`, tres
    públicos: la app de música (su departamento y su alumnado), y `/incidencias/`
    y `/wifi/` (todo el centro). Iniciar sesión para poner una incidencia dejaba
    a cualquier profesor dentro de la app de música. Este middleware es el
    candado: a quien tiene sesión y no `puede_usar_apps`, le da una página que
    le manda a lo que sí es suyo.

    **No toca a nadie anónimo.** Lo público de la app (el índice de recursos y
    sus páginas) sigue público igual que antes; el candado es sobre sesiones.

    **No toca el dominio de blogs.** Allí `/cms/` es el editor de los
    departamentos, que tiene sus propios permisos de Wagtail.
    """

    #: Lo que está abierto a cualquier cuenta del centro aunque no sea de
    #: música. Cada entrada tiene su porqué:
    #: - `/accounts/`, `/users/`: entrar, salir y el propio perfil.
    #: - `/incidencias/`, `/wifi/`: son de todo el centro.
    #: - `/clases/groups/join/`: canjear una invitación es justo cómo se
    #:   consigue el acceso; cerrarla sería un candado sin llave.
    #: - `/api/`: autentica con clave, no con sesión, y la usa incidencias.
    #: - `/admin/`, `/cms/`, `/documents/`, `/images/`: comprueban sus propios
    #:   permisos (staff, Wagtail).
    #: - `/analytics/`, `/static/`, `/media/`: no son navegación.
    OPEN_PREFIXES = (
        "/accounts/",
        "/users/",
        "/incidencias/",
        "/wifi/",
        "/clases/groups/join/",
        "/api/",
        "/admin/",
        "/cms/",
        "/documents/",
        "/images/",
        "/analytics/",
        "/static/",
        "/media/",
        "/robots.txt",
        "/i18n/",
        "/__debug__/",
    )

    TEMPLATE = "pages/solo_musica.html"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self.cierra(request):
            from django.shortcuts import render

            return render(request, self.TEMPLATE, status=403)
        return self.get_response(request)

    def cierra(self, request):
        from django.conf import settings

        if not getattr(settings, "APPS_CANDADO", True):
            return False
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return False
        if request.path.startswith(self.OPEN_PREFIXES):
            return False
        if not es_host_de_apps(request):
            return False
        from martina_bescos_app.users.permisos import puede_usar_apps

        return not puede_usar_apps(user)


def es_host_de_apps(request):
    """Si la petición va a la app (`apps.`), no al sitio de blogs.

    Se decide por el sitio de **Wagtail** y no por el dominio escrito: el de
    blogs es el que tiene una `BlogIndexPage` de raíz. Así vale igual en
    producción (`blogs.iesmartinabescos.es`) que en local (`127.0.0.1:8000`).
    El `Site` de Django no sirve: en local `SITE_ID` apunta al de blogs.
    Un dominio que no casa con ningún sitio cae en el sitio por defecto, que
    es el de la app.
    """
    from wagtail.models import Site

    sitio = Site.find_for_request(request)
    if sitio is None:
        return True
    return sitio.root_page.content_type.model != "blogindexpage"
