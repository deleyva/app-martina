"""Catálogo de repertorio consultable: JamZone importado + canciones propias.

**Por qué existe.** JamZone (Music Will) publica 575 canciones con metadatos muy
buenos —número de acordes, tonalidad, década, idioma, qué instrumentos tienen
chart— pero su buscador no deja cruzar criterios. «Una de los 70, con tres
acordes y chart de ukelele» es la consulta que hace falta al programar, y allí
no se puede formular. Aquí sí.

**Qué se guarda y qué no.** Solo metadatos factuales y el enlace al original.
Los charts son imágenes con copyright alojadas en el CDN de Music Will: no se
descargan, no se incrustan y no se republican. Cada ficha enlaza a su página en
JamZone, que es donde se ve el chart.

El patrón del módulo es el de la casa: modelos gordos, vistas delgadas. Toda la
lógica de consulta y de facetas vive aquí.
"""

from django.db import models
from django.utils.text import slugify

from musica.models import q_texto

# Los tres campos que escribe Jesús y que la importación no puede pisar nunca.
# Vive aquí, en una constante, para que el importador no tenga que acordarse y
# para que el test que protege el invariante tenga algo concreto que comprobar.
CAMPOS_PROPIOS = ("notas", "cursos", "favorito")

# Los campos que escribe la importación. Cualquiera de ellos se puede corregir a
# mano, y al hacerlo queda anotado en `Cancion.bloqueados` para que la siguiente
# importación no lo pise. Es la lista que comparten el importador y el admin:
# si se añade un campo importable, va aquí y las dos partes se enteran.
CAMPOS_IMPORTADOS = (
    "slug_externo",
    "titulo",
    "anio",
    "num_acordes",
    "tempo",
    "progresion_romana",
    "g_rated",
    "spotify_id",
    "youtube_id",
    "lyrics_url",
    "forma",
    "dato",
)

NIVELES = [
    ("Beginner", "Principiante"),
    ("Intermediate", "Intermedio"),
    ("Advanced", "Avanzado"),
]

VERSIONES = [
    ("original", "Tonalidad original"),
    ("transposed", "Tonalidad fácil"),
]

# Los nombres son los de Sanity: se guardan tal cual para que la importación sea
# una copia y no una traducción que haya que mantener sincronizada. La etiqueta
# en castellano es cosa de la plantilla.
INSTRUMENTOS = [
    ("Modern Band", "Banda al completo"),
    ("Guitar", "Guitarra"),
    ("Keyboard", "Teclado"),
    ("Drums", "Batería"),
    ("Bass", "Bajo"),
    ("Ukulele", "Ukelele"),
]

CURSOS = [("1eso", "1º ESO"), ("3eso", "3º ESO"), ("4eso", "4º ESO")]


class Vocabulario(models.Model):
    """Base de las tablitas de apoyo: artista, género, idioma.

    Son listas cerradas que llegan de Sanity; el slug existe para que viajen por
    la URL sin sorpresas de acentos ni de mayúsculas.
    """

    nombre = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True)

    class Meta:
        abstract = True
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @classmethod
    def desde_nombre(cls, nombre):
        """El registro para ese nombre, creándolo si hace falta."""
        nombre = (nombre or "").strip()
        if not nombre:
            return None
        objeto, _ = cls.objects.get_or_create(
            nombre=nombre, defaults={"slug": slugify(nombre)[:220] or "sin-nombre"}
        )
        return objeto


class Artista(Vocabulario):
    pass


class Genero(Vocabulario):
    pass


class Idioma(Vocabulario):
    pass


class Cancion(models.Model):
    """Una canción del catálogo, venga de JamZone o la hayas metido tú."""

    JAMZONE = "jamzone"
    PROPIO = "propio"
    ORIGENES = [(JAMZONE, "JamZone"), (PROPIO, "Propia")]

    origen = models.CharField(max_length=10, choices=ORIGENES, default=JAMZONE, db_index=True)
    # El `_id` de Sanity. Es la clave de idempotencia de la importación: lo que
    # permite reimportar mil veces sin duplicar nada. Nulo en las propias.
    fuente_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    slug_externo = models.CharField(max_length=220, blank=True)

    titulo = models.CharField(max_length=300)
    anio = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    # Derivada de `anio` en `save()`. Existe como columna propia porque «de los
    # 70» es la consulta más frecuente y no merece un cálculo por fila.
    decada = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    num_acordes = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    tempo = models.PositiveSmallIntegerField(null=True, blank=True)
    progresion_romana = models.CharField(max_length=120, blank=True)
    g_rated = models.BooleanField(default=False)

    spotify_id = models.CharField(max_length=64, blank=True)
    youtube_id = models.CharField(max_length=32, blank=True)
    lyrics_url = models.URLField(max_length=500, blank=True)

    forma = models.JSONField(default=list, blank=True)
    dato = models.TextField(blank=True)

    artistas = models.ManyToManyField(Artista, blank=True, related_name="canciones")
    generos = models.ManyToManyField(Genero, blank=True, related_name="canciones")
    idiomas = models.ManyToManyField(Idioma, blank=True, related_name="canciones")

    # --- Campos propios: la importación no los toca. Ver CAMPOS_PROPIOS. ---
    notas = models.TextField(blank=True, help_text="Tus notas: cómo fue, con qué grupo, qué cambiarías.")
    cursos = models.JSONField(default=list, blank=True, help_text="Cursos donde la has usado o la quieres usar.")
    favorito = models.BooleanField(default=False)

    # Campos de CAMPOS_IMPORTADOS corregidos a mano. La importación los salta.
    # Se rellena solo al editar en el admin: no hay que acordarse de marcarlo.
    bloqueados = models.JSONField(
        default=list,
        blank=True,
        help_text="Campos corregidos a mano que la importación no debe tocar.",
    )

    importado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["titulo"]
        indexes = [models.Index(fields=["decada", "num_acordes"])]

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        self.decada = (self.anio // 10) * 10 if self.anio else None
        super().save(*args, **kwargs)

    # -- Correcciones a mano ------------------------------------------------

    def bloquear(self, campos):
        """Anota que esos campos se han corregido a mano. Devuelve los nuevos."""
        actuales = list(self.bloqueados or [])
        nuevos = [c for c in campos if c in CAMPOS_IMPORTADOS and c not in actuales]
        if nuevos:
            self.bloqueados = actuales + nuevos
        return nuevos

    def valores_importables(self, valores):
        """De lo que trae JamZone, lo que esta canción acepta que se escriba.

        Aparte de los campos propios, que nunca entran, se descarta lo que
        figure en `bloqueados`: son correcciones manuales y mandan sobre el
        origen. Devuelve `(aplicables, respetados)`.
        """
        bloqueados = set(self.bloqueados or [])
        aplicables = {k: v for k, v in valores.items() if k not in bloqueados}
        respetados = sorted(set(valores) & bloqueados)
        return aplicables, respetados

    # -- Enlaces al original ------------------------------------------------

    @property
    def url_jamzone(self):
        if self.origen != self.JAMZONE or not self.slug_externo:
            return ""
        return f"https://jamzone.musicwill.org/songs/{self.slug_externo}"

    @property
    def url_spotify(self):
        return f"https://open.spotify.com/track/{self.spotify_id}" if self.spotify_id else ""

    @property
    def url_youtube(self):
        return f"https://www.youtube.com/watch?v={self.youtube_id}" if self.youtube_id else ""

    # -- Consulta -----------------------------------------------------------

    @classmethod
    def buscar(cls, **filtros):
        """El queryset que corresponde a esos filtros.

        Acepta claves sueltas o listas. Las que van contra `Version`
        —instrumento, nivel, versión— se aplican en un **único** `filter()` a
        propósito: así «ukelele Y principiante» significa «la misma versión es
        de ukelele y es de nivel principiante», que es lo que quiere decir de
        verdad. Encadenar dos `filter()` lo convertiría en «alguna versión tiene
        ukelele y alguna versión es fácil», que no es lo mismo.
        """
        qs = cls.objects.all()

        texto = (filtros.get("texto") or "").strip()
        if texto:
            qs = qs.filter(
                q_texto("titulo", texto)
                | q_texto("artistas__nombre", texto)
                | q_texto("notas", texto)
            )

        if filtros.get("decada"):
            qs = qs.filter(decada__in=_lista(filtros["decada"]))
        if filtros.get("num_acordes"):
            qs = qs.filter(num_acordes__in=_lista(filtros["num_acordes"]))
        if filtros.get("num_acordes_max"):
            qs = qs.filter(num_acordes__lte=filtros["num_acordes_max"])
        if filtros.get("num_acordes_min"):
            qs = qs.filter(num_acordes__gte=filtros["num_acordes_min"])
        if filtros.get("genero"):
            qs = qs.filter(generos__slug__in=_lista(filtros["genero"]))
        if filtros.get("idioma"):
            qs = qs.filter(idiomas__slug__in=_lista(filtros["idioma"]))
        if filtros.get("curso"):
            # `contains` de JSONB es `@>`: pedir varios significa «los tiene
            # todos», que es la lectura correcta de marcar dos cursos.
            qs = qs.filter(cursos__contains=_lista(filtros["curso"]))
        if filtros.get("favorito"):
            qs = qs.filter(favorito=True)
        if filtros.get("origen"):
            qs = qs.filter(origen__in=_lista(filtros["origen"]))

        condiciones_de_version = {}
        if filtros.get("instrumento"):
            # Igual que arriba: marcar ukelele y batería pide una versión que
            # tenga chart de las dos, no de cualquiera de las dos.
            condiciones_de_version["versiones__instrumentos__contains"] = _lista(
                filtros["instrumento"]
            )
        if filtros.get("nivel"):
            condiciones_de_version["versiones__nivel__in"] = _lista(filtros["nivel"])
        if condiciones_de_version:
            qs = qs.filter(**condiciones_de_version)

        return qs.distinct()

    @classmethod
    def facetas(cls, filtros):
        """Las píldoras de filtro, cada una con cuántas canciones daría.

        Cada dimensión se cuenta con **todos los demás filtros aplicados menos
        el suyo**. Es lo que hace que una faceta sin seleccionar siga diciendo
        cuántas habría si la marcases, en vez de desaparecer. Mismo idiom que
        `MusicLibraryIndexPage.get_context()`.

        Son cinco consultas de agregación sobre 575 filas: sale más barato que
        la complejidad de hacerlo en una sola.
        """
        def sin(dimension):
            return {k: v for k, v in filtros.items() if k != dimension and v}

        seleccion = {k: [str(x) for x in _lista(v)] for k, v in filtros.items() if v}

        def marcada(dimension, valor):
            return str(valor) in seleccion.get(dimension, [])

        decadas = [
            {
                "valor": fila["decada"],
                "etiqueta": f"{fila['decada']}s",
                "total": fila["total"],
                "marcada": marcada("decada", fila["decada"]),
            }
            for fila in cls.buscar(**sin("decada"))
            .exclude(decada=None)
            .values("decada")
            .annotate(total=models.Count("id"))
            .order_by("decada")
        ]

        acordes = [
            {
                "valor": fila["num_acordes"],
                "etiqueta": f"{fila['num_acordes']}",
                "total": fila["total"],
                "marcada": marcada("num_acordes", fila["num_acordes"]),
            }
            for fila in cls.buscar(**sin("num_acordes"))
            .exclude(num_acordes=None)
            .values("num_acordes")
            .annotate(total=models.Count("id"))
            .order_by("num_acordes")
        ]

        base_instrumento = cls.buscar(**sin("instrumento"))
        instrumentos = [
            {
                "valor": nombre,
                "etiqueta": etiqueta,
                "total": base_instrumento.filter(
                    versiones__instrumentos__contains=[nombre]
                )
                .distinct()
                .count(),
                "marcada": marcada("instrumento", nombre),
            }
            for nombre, etiqueta in INSTRUMENTOS
        ]

        base_nivel = cls.buscar(**sin("nivel"))
        niveles = [
            {
                "valor": codigo,
                "etiqueta": etiqueta,
                "total": base_nivel.filter(versiones__nivel=codigo).distinct().count(),
                "marcada": marcada("nivel", codigo),
            }
            for codigo, etiqueta in NIVELES
        ]

        idiomas = [
            {
                "valor": fila["idiomas__slug"],
                "etiqueta": fila["idiomas__nombre"],
                "total": fila["total"],
                "marcada": marcada("idioma", fila["idiomas__slug"]),
            }
            for fila in cls.buscar(**sin("idioma"))
            .exclude(idiomas=None)
            .values("idiomas__slug", "idiomas__nombre")
            .annotate(total=models.Count("id"))
            .order_by("-total")[:8]
        ]

        return {
            "decadas": decadas,
            "acordes": acordes,
            "instrumentos": [f for f in instrumentos if f["total"] or f["marcada"]],
            "niveles": [f for f in niveles if f["total"] or f["marcada"]],
            "idiomas": idiomas,
        }


class Version(models.Model):
    """Una de las dos versiones del chart de una canción: original o fácil.

    Vive aparte de `Cancion` porque **el nivel, la tonalidad y los acordes son
    de la versión, no de la canción**. Comprobado contra el CMS de origen:
    «16 CARRIAGES» es *Intermediate* en Re bemol y *Beginner* en Do, con dos
    acordes distintos en cada una.

    Y es lo que hace consultable el detalle que más despista de JamZone: el
    ukelele suele existir **solo en la versión transpuesta**.
    """

    cancion = models.ForeignKey(Cancion, on_delete=models.CASCADE, related_name="versiones")
    version = models.CharField(max_length=20, choices=VERSIONES)
    nivel = models.CharField(max_length=20, choices=NIVELES, blank=True, db_index=True)
    tonalidad = models.CharField(max_length=20, blank=True)
    acordes = models.JSONField(default=list, blank=True)
    instrumentos = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = [("cancion", "version")]
        ordering = ["version"]

    def __str__(self):
        return f"{self.cancion.titulo} ({self.get_version_display()})"


class Sincronizacion(models.Model):
    """El registro de cada importación.

    Existe porque una tarea mensual que se rompe en silencio es peor que no
    tener tarea: los logs siguen escribiéndose y todo parece sano. Con esto, la
    propia pantalla dice cuándo se sincronizó por última vez y cómo fue.
    """

    momento = models.DateTimeField(auto_now_add=True, db_index=True)
    automatica = models.BooleanField(default=False)
    recibidas = models.PositiveIntegerField(default=0)
    creadas = models.PositiveIntegerField(default=0)
    actualizadas = models.PositiveIntegerField(default=0)
    sin_cambios = models.PositiveIntegerField(default=0)
    campos_respetados = models.PositiveIntegerField(default=0)
    huerfanos_borrados = models.PositiveIntegerField(default=0)
    fallos = models.PositiveIntegerField(default=0)
    detalle = models.TextField(blank=True)

    class Meta:
        ordering = ["-momento"]
        verbose_name_plural = "Sincronizaciones"

    def __str__(self):
        return f"{self.momento:%Y-%m-%d %H:%M} · {self.recibidas} recibidas"

    @property
    def ok(self):
        return self.fallos == 0 and self.recibidas > 0

    @property
    def reciente(self):
        """Menos de un minuto. `timesince` diría «0 minutos», que parece un fallo."""
        from django.utils import timezone

        return (timezone.now() - self.momento).total_seconds() < 60

    @classmethod
    def ultima(cls):
        return cls.objects.first()


def _lista(valor):
    """Un valor suelto o una lista, siempre como lista sin vacíos ni repetidos."""
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set)):
        crudos = list(valor)
    else:
        crudos = [valor]
    limpios = [v for v in crudos if v not in (None, "")]
    return list(dict.fromkeys(limpios))
