
class AppModeMiddleware:
    """
    Decide el modo de aplicación (principal vs incidencias) a partir de la URL,
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

    Solo se persiste 'incidencias'. Los dos únicos consumidores del valor
    (`utils/context_processors.py` y `users/adapters.py`) comparan contra esa
    cadena y nada más, de modo que la ausencia de la clave ya significa "main".
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
        return self.DEFAULT_MODE

    def _remember(self, session, mode):
        """Escribe en la sesión únicamente si el estado guardado cambia."""
        current = session.get(self.SESSION_KEY)
        if mode == self.DEFAULT_MODE:
            # El defecto no se guarda. Solo hay que limpiar si veníamos de
            # incidencias, y esa sí es una transición real.
            if current is not None:
                del session[self.SESSION_KEY]
        elif current != mode:
            session[self.SESSION_KEY] = mode
