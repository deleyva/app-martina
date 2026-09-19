"""Traer el catálogo de JamZone (Music Will) al repertorio local.

    just manage importar_jamzone --dry-run    # cuenta qué haría, sin escribir
    just manage importar_jamzone              # importa de verdad

**Cómo.** Detrás de JamZone hay un CMS Sanity con el dataset público. Una sola
consulta GROQ con dereferencia baja las 575 canciones con todos sus campos, así
que esto no es un scraping de 29 páginas: es una petición y se puede repetir
cuantas veces haga falta.

**Qué NO se trae.** Las imágenes de los charts, que tienen copyright y viven en
el CDN de Music Will. Aquí solo entran metadatos factuales y el slug con el que
construir el enlace al original.

**Los dos invariantes.** Se reimporta encima sin miedo:

1. Las canciones con `origen="propio"` no se tocan jamás.
2. Los campos que escribe Jesús —`notas`, `cursos`, `favorito`— no se
   sobrescriben nunca, ni siquiera en las filas que vinieron de JamZone. La
   lista está en `repertorio.models.CAMPOS_PROPIOS` y hay un test que lo vigila.
"""

import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from repertorio.models import (
    CAMPOS_PROPIOS,
    Artista,
    Cancion,
    Genero,
    Idioma,
    Sincronizacion,
    Version,
)

UA = "Mozilla/5.0 (compatible; IES Martina Bescos catalogo de repertorio)"
TIMEOUT = 120
MAX_BYTES = 40 * 1024 * 1024

# Dereferencia todo de una vez. Dos detalles que costaron encontrarlos y que no
# se pueden simplificar:
#
# - `coalesce(instrumentType->name, instrument->name)`: conviven DOS
#   generaciones del documento de chart, `instrumentChartUpload` (con
#   `instrumentType`) y `uploadChart` (con `instrument`). Si solo se pide una,
#   la mitad de los instrumentos salen a null en silencio.
# - El nivel se llama `level`, no `gradeLevel`, y **cuelga de la versión, no de
#   la canción**: la misma canción es Intermediate en tonalidad original y
#   Beginner en la transpuesta, con tonalidad y acordes propios en cada una.
CONSULTA = """
*[_type == "song"]{
  _id, title, "slug": slug.current, releaseYear, numberOfChords, tempo,
  chordProgression, gRated, spotifyId, musicVideo, songLyrics,
  "forma": songForm[].value,
  "dato": pt::text(songFact),
  "artistas": artist[]->name,
  "generos": genre[]->name,
  "idiomas": language[]->name,
  "charts": songChart[]->{
    version,
    "nivel": level->name,
    "tonalidad": coalesce(transposedKey->name, ^.originalKey->name),
    "acordes": coalesce(transposedChords[]->name, ^.chords[]->name),
    "instrumentos": uploadChart[]->{
      "nombre": coalesce(instrumentType->name, instrument->name)
    }
  }
}
"""


@dataclass
class Informe:
    """Lo que pasó de verdad, para poder contarlo entero al final."""

    recibidas: int = 0
    creadas: int = 0
    actualizadas: int = 0
    sin_cambios: int = 0
    versiones: int = 0
    propias_intactas: int = 0
    huerfanos_borrados: int = 0
    campos_respetados: int = 0
    correcciones: list[str] = field(default_factory=list)
    sin_titulo: list[str] = field(default_factory=list)
    sin_slug: list[str] = field(default_factory=list)
    ids_descartados: list[str] = field(default_factory=list)
    fallidas: list[tuple[str, str]] = field(default_factory=list)


def _get(url):
    peticion = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
        datos = respuesta.read(MAX_BYTES + 1)
    if len(datos) > MAX_BYTES:
        raise ValueError(f"respuesta de más de {MAX_BYTES // 1024 // 1024} MB")
    return json.loads(datos.decode("utf-8"))


def descargar():
    """Las canciones tal cual las devuelve Sanity."""
    base = getattr(
        settings,
        "JAMZONE_SANITY_URL",
        "https://teha7qd2.api.sanity.io/v2025-09-25/data/query/production",
    )
    url = f"{base}?{urllib.parse.urlencode({'query': CONSULTA})}"
    respuesta = _get(url)
    if "error" in respuesta:
        raise RuntimeError(f"Sanity devolvió un error: {respuesta['error']}")
    return respuesta.get("result") or []


# Los identificadores llegan sucios: 128 canciones traen la URL entera de
# Spotify o el `?si=` de seguimiento, y algunos vídeos vienen como `watch?v=…`.
# Se normalizan aquí en vez de ensanchar la columna, porque lo que hace falta
# para construir el enlace es el identificador limpio, no el pegote original.

def _spotify_id(bruto):
    if not bruto:
        return ""
    valor = bruto.strip()
    if "/track/" in valor:
        valor = valor.split("/track/", 1)[1]
    valor = valor.split("?", 1)[0].split("#", 1)[0].strip("/")
    return valor if re.fullmatch(r"[A-Za-z0-9]{22}", valor) else ""


def _youtube_id(bruto):
    """El identificador de 11 caracteres, o cadena vacía.

    Se descarta lo que no tenga la forma de un ID de YouTube en vez de
    guardarlo a medias: un botón «Vídeo» que lleva a un 404 es peor que no
    tener botón. Lo descartado se cuenta en el informe.
    """
    if not bruto:
        return ""
    valor = bruto.strip()
    m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", valor)
    if m:
        return m.group(1)
    valor = valor.split("?", 1)[0].split("&", 1)[0].strip("/")
    return valor if re.fullmatch(r"[A-Za-z0-9_-]{11}", valor) else ""


def _texto(valor):
    """Texto limpio: los datos de origen traen entidades HTML en crudo.

    En Sanity hay literalmente «Kool &amp; The Gang» e «Iseo &amp; DodoSound».
    Sin deshacerlas, el ampersand se ve escapado en pantalla.
    """
    return html.unescape(valor).strip() if isinstance(valor, str) else valor


def _nombres(valores):
    return [_texto(v) for v in (valores or []) if v]


class Command(BaseCommand):
    help = "Importa el catálogo de canciones de JamZone (Music Will)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Cuenta qué haría y no escribe nada.",
        )
        parser.add_argument(
            "--automatica",
            action="store_true",
            help="Marca la sincronización como lanzada por la tarea programada.",
        )

    def handle(self, *args, **opciones):
        seco = opciones["dry_run"]
        informe = Informe()

        self.stdout.write("Descargando el catálogo de JamZone…")
        try:
            canciones = descargar()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"No se pudo descargar: {e}"))
            # Queda registrado aunque no haya llegado ni un dato. Si no, una
            # sincronización mensual rota es invisible: la pantalla seguiría
            # enseñando la fecha de la última que sí funcionó.
            if not seco:
                Sincronizacion.objects.create(
                    automatica=opciones.get("automatica", False),
                    recibidas=0,
                    fallos=1,
                    detalle=f"No se pudo descargar: {e}",
                )
            return

        informe.recibidas = len(canciones)
        informe.propias_intactas = Cancion.objects.filter(origen=Cancion.PROPIO).count()
        self.stdout.write(f"Recibidas {informe.recibidas} canciones.")

        if seco:
            for doc in canciones:
                if not (doc.get("title") or "").strip():
                    informe.sin_titulo.append(doc.get("_id", "?"))
                if not (doc.get("slug") or "").strip():
                    informe.sin_slug.append(doc.get("title") or doc.get("_id", "?"))
            existentes = set(
                Cancion.objects.filter(origen=Cancion.JAMZONE).values_list(
                    "fuente_id", flat=True
                )
            )
            llegan = {d.get("_id") for d in canciones}
            informe.creadas = len(llegan - existentes)
            informe.actualizadas = len(llegan & existentes)
            self._contar(informe, seco=True)
            return

        for doc in canciones:
            try:
                with transaction.atomic():
                    self._guardar(doc, informe)
            except Exception as e:
                informe.fallidas.append((doc.get("title") or doc.get("_id", "?"), str(e)))

        informe.huerfanos_borrados = self._limpiar_vocabulario()
        Sincronizacion.objects.create(
            automatica=opciones.get("automatica", False),
            recibidas=informe.recibidas,
            creadas=informe.creadas,
            actualizadas=informe.actualizadas,
            sin_cambios=informe.sin_cambios,
            campos_respetados=informe.campos_respetados,
            huerfanos_borrados=informe.huerfanos_borrados,
            fallos=len(informe.fallidas),
            detalle="\n".join(f"{t}: {e}" for t, e in informe.fallidas[:20]),
        )
        self._contar(informe, seco=False)

    def _limpiar_vocabulario(self):
        """Borra artistas, géneros e idiomas que ya no cuelgan de ninguna canción.

        Hace falta porque el vocabulario se crea al vuelo: si en origen corrigen
        el nombre de un artista, la fila vieja se queda suelta para siempre y
        seguiría apareciendo en las facetas. Pasó de verdad con los nombres que
        traían «&amp;» sin deshacer.
        """
        borrados = 0
        for modelo in (Artista, Genero, Idioma):
            cantidad, _ = modelo.objects.filter(canciones__isnull=True).delete()
            borrados += cantidad
        return borrados

    def _guardar(self, doc, informe):
        fuente_id = doc.get("_id")
        titulo = _texto(doc.get("title") or "")
        if not fuente_id or not titulo:
            informe.sin_titulo.append(fuente_id or "?")
            return

        slug_externo = (doc.get("slug") or "").strip()
        if not slug_externo:
            informe.sin_slug.append(titulo)

        if doc.get("musicVideo") and not _youtube_id(doc.get("musicVideo")):
            informe.ids_descartados.append(f"{titulo} (vídeo)")
        if doc.get("spotifyId") and not _spotify_id(doc.get("spotifyId")):
            informe.ids_descartados.append(f"{titulo} (spotify)")

        # `defaults` NO incluye ninguno de CAMPOS_PROPIOS: es lo que hace que
        # reimportar no borre las notas de Jesús. El assert lo deja escrito.
        valores = {
            "origen": Cancion.JAMZONE,
            "slug_externo": slug_externo,
            "titulo": titulo,
            "anio": doc.get("releaseYear") or None,
            "num_acordes": doc.get("numberOfChords") or None,
            "tempo": doc.get("tempo") or None,
            "progresion_romana": doc.get("chordProgression") or "",
            "g_rated": bool(doc.get("gRated")),
            "spotify_id": _spotify_id(doc.get("spotifyId")),
            "youtube_id": _youtube_id(doc.get("musicVideo")),
            "lyrics_url": (doc.get("songLyrics") or "")[:500],
            "forma": _nombres(doc.get("forma")),
            "dato": _texto(doc.get("dato") or ""),
        }
        assert not set(valores) & set(CAMPOS_PROPIOS), (
            "La importación nunca escribe los campos propios de Jesús."
        )

        cancion = Cancion.objects.filter(
            fuente_id=fuente_id, origen=Cancion.JAMZONE
        ).first()

        if cancion is None:
            cancion = Cancion(fuente_id=fuente_id, **valores)
            cancion.save()
            informe.creadas += 1
        else:
            # Lo corregido a mano manda sobre lo que traiga JamZone.
            aplicables, respetados = cancion.valores_importables(valores)
            if respetados:
                informe.campos_respetados += len(respetados)
                informe.correcciones.append(f"{titulo}: {', '.join(respetados)}")
            if any(getattr(cancion, k) != v for k, v in aplicables.items()):
                for k, v in aplicables.items():
                    setattr(cancion, k, v)
                cancion.save()
                informe.actualizadas += 1
            else:
                informe.sin_cambios += 1

        cancion.artistas.set(
            [a for a in (Artista.desde_nombre(n) for n in _nombres(doc.get("artistas"))) if a]
        )
        cancion.generos.set(
            [g for g in (Genero.desde_nombre(n) for n in _nombres(doc.get("generos"))) if g]
        )
        cancion.idiomas.set(
            [i for i in (Idioma.desde_nombre(n) for n in _nombres(doc.get("idiomas"))) if i]
        )

        # Las versiones no guardan nada del usuario, así que se rehacen enteras.
        # Es más simple que casarlas una a una y no puede perder datos propios.
        vistas = set()
        for chart in doc.get("charts") or []:
            if not chart:
                continue
            version = chart.get("version") or "original"
            if version in vistas:
                continue
            vistas.add(version)
            instrumentos = [
                i.get("nombre")
                for i in (chart.get("instrumentos") or [])
                if i and i.get("nombre")
            ]
            Version.objects.update_or_create(
                cancion=cancion,
                version=version,
                defaults={
                    "nivel": chart.get("nivel") or "",
                    "tonalidad": chart.get("tonalidad") or "",
                    "acordes": _nombres(chart.get("acordes")),
                    "instrumentos": list(dict.fromkeys(instrumentos)),
                },
            )
            informe.versiones += 1
        cancion.versiones.exclude(version__in=vistas).delete()

    def _contar(self, informe, seco):
        cabecera = "SIMULACRO (no se ha escrito nada)" if seco else "IMPORTACIÓN COMPLETA"
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(cabecera))
        self.stdout.write(f"  Recibidas de JamZone .... {informe.recibidas}")
        self.stdout.write(f"  Creadas ................. {informe.creadas}")
        self.stdout.write(f"  Actualizadas ............ {informe.actualizadas}")
        if not seco:
            self.stdout.write(f"  Sin cambios ............. {informe.sin_cambios}")
            self.stdout.write(f"  Versiones de chart ...... {informe.versiones}")
        self.stdout.write(f"  Propias sin tocar ....... {informe.propias_intactas}")
        if not seco:
            self.stdout.write(f"  Vocabulario huérfano .... {informe.huerfanos_borrados} borrados")
            if informe.campos_respetados:
                campos = informe.campos_respetados
                cuantas = len(informe.correcciones)
                self.stdout.write(
                    f"  Correcciones respetadas . {campos} campo{'s' if campos != 1 else ''} "
                    f"en {cuantas} canci{'ones' if cuantas != 1 else 'ón'}"
                )
        if informe.sin_slug:
            self.stdout.write(
                self.style.WARNING(
                    f"  Sin slug (no enlazan a JamZone): {len(informe.sin_slug)}"
                )
            )
        if informe.ids_descartados:
            self.stdout.write(
                self.style.WARNING(
                    f"  Identificadores ilegibles descartados: {len(informe.ids_descartados)}"
                )
            )
        if informe.sin_titulo:
            self.stdout.write(
                self.style.WARNING(f"  Descartadas sin título: {len(informe.sin_titulo)}")
            )
        for titulo, error in informe.fallidas:
            self.stdout.write(self.style.ERROR(f"  FALLÓ {titulo}: {error}"))
        if not informe.fallidas:
            self.stdout.write(self.style.SUCCESS("  Sin fallos."))
