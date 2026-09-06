"""Traer los blogs de departamento de Blogspot a `blogs.iesmartinabescos.es`.

    just manage import_blogspot --dry-run          # ver qué haría
    just manage import_blogspot                    # importar los 16
    just manage import_blogspot --blog dmusicaiesmbescos

Se puede relanzar tantas veces como haga falta: un artículo ya importado se
reconoce por `source_url` y se salta. Eso permite importar un departamento,
mirarlo, y seguir con el resto.

Lo que NO hace, a propósito: no toca ningún artículo existente, no borra nada,
no escribe fuera del árbol de `blogs.iesmartinabescos.es`, y no deja ninguna
imagen apuntando a los servidores de Google. Si una foto no se puede bajar, el
`<img>` se elimina y el fallo sale en el informe final; un enlace a Google que
hoy funciona es una imagen rota el día que alguien cierre la cuenta de Blogger.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO

from bs4 import BeautifulSoup
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from wagtail.images import get_image_model
from wagtail.models import Collection

from blogs.blogspot import (
    BLOG_MAP,
    derivar_intro,
    es_imagen_de_google,
    etiqueta_facetada,
    limpiar_cuerpo,
    slug_desde_url,
    url_maxima_resolucion,
)
from blogs.models import ArticuloPage, BlogIndexPage

UA = "Mozilla/5.0 (compatible; IES Martina Bescos importador de blogs)"
TIMEOUT = 45
MAX_BYTES_IMAGEN = 25 * 1024 * 1024


@dataclass
class Informe:
    """Lo que pasó de verdad, para poder contarlo entero al final."""

    creados: int = 0
    saltados: int = 0
    imagenes_ok: int = 0
    imagenes_fallidas: list[tuple[str, str]] = field(default_factory=list)
    etiquetas_descartadas: list[str] = field(default_factory=list)
    posts_sin_cuerpo: list[str] = field(default_factory=list)
    sin_entradilla: list[str] = field(default_factory=list)


def _get(url: str, binario: bool = False):
    peticion = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
        datos = respuesta.read(MAX_BYTES_IMAGEN + 1 if binario else None)
    if binario and len(datos) > MAX_BYTES_IMAGEN:
        raise ValueError(f"imagen de más de {MAX_BYTES_IMAGEN // 1024 // 1024} MB")
    return datos if binario else datos.decode("utf-8", errors="replace")


def leer_feed(host: str, tipo: str = "posts") -> list[dict]:
    """Todas las entradas de un blog, paginando.

    Blogger tope a 500 por petición aunque le pidas más, así que hay que
    encadenar por `start-index` en vez de fiarse de un solo tirón.
    """
    entradas: list[dict] = []
    inicio = 1
    while True:
        url = (
            f"https://{host}.blogspot.com/feeds/{tipo}/default"
            f"?alt=json&max-results=500&start-index={inicio}"
        )
        feed = json.loads(_get(url))["feed"]
        lote = feed.get("entry", [])
        entradas.extend(lote)
        if len(lote) < 500:
            return entradas
        inicio += len(lote)


def _enlace_original(entrada: dict) -> str:
    for enlace in entrada.get("link", []):
        if enlace.get("rel") == "alternate":
            return enlace.get("href", "")
    return ""


class Command(BaseCommand):
    help = "Importa los blogs de departamento de Blogspot a blogs.iesmartinabescos.es"

    def add_arguments(self, parser):
        parser.add_argument(
            "--blog",
            action="append",
            dest="blogs",
            help="Host de blogspot sin `.blogspot.com`. Repetible. Por defecto, los 16.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Cuenta y muestra lo que haría, sin escribir en la BD ni bajar imágenes.",
        )
        parser.add_argument(
            "--draft",
            action="store_true",
            help="Crea los artículos sin publicar. Por defecto entran publicados.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Como mucho N artículos por blog. 0 = sin límite.",
        )
        parser.add_argument(
            "--all-pages",
            action="store_true",
            help=(
                "Traer también las páginas estáticas de los blogs que SÍ tienen posts. "
                "Por defecto solo se traen las de un blog que no tenga ninguno."
            ),
        )

    # -- imágenes ---------------------------------------------------------

    def _coleccion(self, nombre: str) -> Collection:
        raiz = Collection.get_first_root_node()
        existente = raiz.get_children().filter(name=nombre).first()
        return existente or raiz.add_child(name=nombre)

    def _descargar_imagen(self, url: str, titulo: str, coleccion: Collection, informe: Informe):
        """Baja al original y crea la `Image` de Wagtail. `None` si no se puede.

        Prueba primero la URL a máxima resolución y cae a la original si esa da
        error: perder resolución es aceptable, perder la foto no.
        """
        candidatas = [url_maxima_resolucion(url)]
        if candidatas[0] != url:
            candidatas.append(url)

        ultimo_error = ""
        for candidata in candidatas:
            try:
                datos = _get(candidata, binario=True)
            except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
                ultimo_error = f"{type(exc).__name__}: {exc}"
                continue
            if not datos:
                ultimo_error = "respuesta vacía"
                continue

            nombre = urllib.parse.unquote(urllib.parse.urlparse(candidata).path.split("/")[-1])
            nombre = re.sub(r"[^A-Za-z0-9._-]", "_", nombre)[:80] or "imagen"
            if "." not in nombre:
                nombre += ".jpg"

            imagen = get_image_model()(
                title=titulo[:255] or nombre,
                collection=coleccion,
            )
            try:
                imagen.file = ImageFile(BytesIO(datos), name=nombre)
                imagen.save()
            except Exception as exc:  # imagen corrupta o formato que Willow no lee
                ultimo_error = f"no se pudo guardar: {type(exc).__name__}: {exc}"
                continue
            informe.imagenes_ok += 1
            return imagen

        informe.imagenes_fallidas.append((url, ultimo_error or "desconocido"))
        return None

    def _sustituir_imagenes(self, html: str, titulo: str, coleccion: Collection, informe: Informe):
        """Cada `<img>` pasa a ser un `<embed>` de Wagtail apuntando a una imagen nuestra.

        Devuelve `(html, primera_imagen, primera_era_la_cabecera)`. La primera
        imagen se promociona a `featured_image` porque es lo que pinta la
        portada y las fichas del listado; si además era lo primero del
        artículo, se quita del cuerpo para no verla dos veces seguidas.
        """
        soup = BeautifulSoup(html or "", "html.parser")
        primera = None
        primera_al_principio = False

        for indice, etiqueta in enumerate(soup.find_all("img")):
            src = (etiqueta.get("src") or "").strip()
            alt = (etiqueta.get("alt") or "").strip()

            if not src or src.startswith("file:"):
                # `file:///C:/Users/...` — ya estaba rota en Blogspot el día que
                # se publicó. Se va, y se dice.
                informe.imagenes_fallidas.append((src or "(sin src)", "ruta local, nunca fue pública"))
                etiqueta.decompose()
                continue

            if not es_imagen_de_google(src):
                # Enlace externo a otro sitio (catedu, wordpress...). No es
                # nuestro para bajarlo y reproducirlo; se convierte en enlace.
                enlace = soup.new_tag("a", href=src)
                enlace.string = alt or "Ver imagen original"
                parrafo = soup.new_tag("p")
                parrafo.append(enlace)
                etiqueta.replace_with(parrafo)
                informe.imagenes_fallidas.append((src, "externa: convertida en enlace"))
                continue

            imagen = self._descargar_imagen(src, alt or titulo, coleccion, informe)
            if imagen is None:
                etiqueta.decompose()  # A27.3: nunca dejar el src apuntando a Google
                continue

            embed = soup.new_tag("embed")
            embed.attrs = {
                "embedtype": "image",
                "id": str(imagen.pk),
                "format": "fullwidth",
                "alt": alt or titulo[:200],
            }

            # Blogger envuelve casi cada foto en un enlace a su propia versión
            # grande. Ese enlace ya no sirve para nada: la grande es la que
            # acabamos de guardar.
            objetivo = etiqueta
            padre = etiqueta.parent
            if padre is not None and padre.name == "a" and len(padre.find_all(True)) == 1:
                objetivo = padre
            objetivo.replace_with(embed)

            if primera is None:
                primera = imagen
                primera_al_principio = indice == 0 and self._esta_al_principio(soup, embed)

        return soup.decode(), primera, primera_al_principio

    @staticmethod
    def _esta_al_principio(soup: BeautifulSoup, embed) -> bool:
        """¿El embed es lo primero que se ve, ignorando huecos en blanco?"""
        for nodo in soup.descendants:
            if getattr(nodo, "name", None) is None:
                if str(nodo).strip():
                    return False
                continue
            if nodo is embed:
                return True
            if nodo.name in {"p", "br"} and not nodo.get_text(strip=True):
                continue
            if nodo.name in {"h2", "h3", "h4", "table", "iframe", "li"}:
                return False
        return False

    # -- artículos --------------------------------------------------------

    def _crear_articulo(self, entrada, destino, coleccion, informe, publicar, es_pagina):
        original = _enlace_original(entrada)
        if not original:
            return False

        if ArticuloPage.objects.filter(source_url=original).exists():
            informe.saltados += 1
            return False

        titulo = (entrada.get("title", {}).get("$t") or "").strip()
        crudo = entrada.get("content", {}).get("$t") or entrada.get("summary", {}).get("$t") or ""

        slug = slug_desde_url(original) or "articulo"
        if not titulo:
            titulo = slug.replace("-", " ").capitalize()

        # Wagtail exige slug único entre hermanos, y un departamento puede ya
        # tener un artículo escrito a mano con ese slug (A27.2: ese no se toca).
        base, sufijo = slug, 2
        while ArticuloPage.objects.child_of(destino).filter(slug=slug).exists():
            slug = f"{base}-{sufijo}"
            sufijo += 1

        cuerpo, portada, quitar_primera = self._sustituir_imagenes(
            crudo, titulo, coleccion, informe
        )
        cuerpo = limpiar_cuerpo(cuerpo)

        if quitar_primera and portada is not None:
            cuerpo = re.sub(
                r'<embed[^>]*\bid="%d"[^>]*>\s*' % portada.pk, "", cuerpo, count=1
            )

        # `intro` es obligatorio en el modelo a propósito: es la entradilla en
        # cursiva que la maqueta editorial pone bajo el titular. Hay posts que
        # son solo un cartel escaneado y no tienen ni una palabra de texto; ahí
        # la entradilla cae al propio título, que es lo único que ese artículo
        # dice de sí mismo. No se inventa nada (A27.5), y los que caen así se
        # listan al final para que alguien les escriba una de verdad.
        intro = derivar_intro(cuerpo)
        if not intro:
            intro = titulo[:250]
            informe.sin_entradilla.append(f"{titulo} — {original}")

        if not cuerpo.strip():
            informe.posts_sin_cuerpo.append(f"{titulo} — {original}")

        publicado = parse_datetime(entrada.get("published", {}).get("$t") or "")
        if publicado is None:
            publicado = datetime.now().astimezone()

        articulo = ArticuloPage(
            title=titulo[:255],
            slug=slug,
            date=publicado.date(),
            intro=intro,
            body=cuerpo,
            featured_image=portada,
            source_url=original[:500],
            live=publicar,
            first_published_at=publicado,
            last_published_at=publicado,
        )
        destino.add_child(instance=articulo)

        etiquetas = []
        for categoria in entrada.get("category", []):
            mapeada = etiqueta_facetada(categoria.get("term", ""))
            if mapeada:
                etiquetas.append(mapeada)
            else:
                informe.etiquetas_descartadas.append(categoria.get("term", ""))
        if etiquetas:
            articulo.faceted_tags.add(*etiquetas)

        revision = articulo.save_revision()
        if publicar:
            revision.publish()

        # `publish()` vuelve a sellar las fechas con la de hoy. Las originales
        # son parte de lo que se está trayendo (C113), así que se reponen.
        ArticuloPage.objects.filter(pk=articulo.pk).update(
            first_published_at=publicado, last_published_at=publicado
        )

        informe.creados += 1
        etiqueta_pagina = " [página]" if es_pagina else ""
        self.stdout.write(f"    + {articulo.date} {titulo[:62]}{etiqueta_pagina}")
        return True

    # -- orquestación -----------------------------------------------------

    def handle(self, *args, **opciones):
        hosts = opciones["blogs"] or list(BLOG_MAP)
        desconocidos = [h for h in hosts if h not in BLOG_MAP]
        if desconocidos:
            raise CommandError(
                f"Blog(s) sin departamento en el mapa: {', '.join(desconocidos)}. "
                f"Añádelo a BLOG_MAP en blogs/blogspot.py."
            )

        # Comprobar TODOS los destinos antes de escribir nada: si falta un
        # departamento, es mejor no haber importado la mitad.
        destinos: dict[str, BlogIndexPage] = {}
        for host in hosts:
            slug = BLOG_MAP[host]
            pagina = BlogIndexPage.objects.filter(slug=slug).first()
            if pagina is None:
                raise CommandError(
                    f"No existe el departamento «{slug}» (destino de {host}). "
                    f"Créalo en Wagtail antes de importar."
                )
            destinos[host] = pagina

        seco = opciones["dry_run"]
        publicar = not opciones["draft"]
        limite = opciones["limit"]
        informe = Informe()

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{'ENSAYO — no se escribe nada' if seco else 'IMPORTANDO'} · "
                f"{len(hosts)} blog(s) · artículos {'publicados' if publicar else 'en borrador'}\n"
            )
        )

        for host in hosts:
            destino = destinos[host]
            self.stdout.write(self.style.HTTP_INFO(f"\n{host}.blogspot.com → /{destino.slug}/"))

            entradas = [(e, False) for e in leer_feed(host, "posts")]

            # Las páginas estáticas de Blogspot son la barra lateral del blog
            # —«CONTACTO», «INFORMACIÓN DEL CURSO»—, no noticias, y traerlas
            # todas metería 40 fichas de contacto en el listado de artículos.
            # Se traen solo cuando son lo ÚNICO que tiene el blog: es el caso
            # de Francés, que no tiene ni un post y si no se queda vacío.
            if opciones["all_pages"] or not entradas:
                entradas += [(e, True) for e in leer_feed(host, "pages")]

            entradas.sort(key=lambda par: par[0].get("published", {}).get("$t") or "")
            if limite:
                entradas = entradas[:limite]

            posts = sum(1 for _, es_pagina in entradas if not es_pagina)
            paginas = len(entradas) - posts
            self.stdout.write(f"    {posts} post(s), {paginas} página(s) estática(s)")

            if seco:
                informe.creados += sum(
                    0 if ArticuloPage.objects.filter(source_url=_enlace_original(e)).exists() else 1
                    for e, _ in entradas
                )
                continue

            coleccion = self._coleccion(f"Blogspot — {destino.title}")
            for entrada, es_pagina in entradas:
                with transaction.atomic():
                    self._crear_articulo(
                        entrada, destino, coleccion, informe, publicar, es_pagina
                    )

        self._resumen(informe, seco)

    def _resumen(self, informe: Informe, seco: bool) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n\n── Resumen ──"))
        etiqueta = "se crearían" if seco else "creados"
        self.stdout.write(f"  Artículos {etiqueta}: {informe.creados}")
        self.stdout.write(f"  Ya estaban (saltados): {informe.saltados}")
        if seco:
            return

        self.stdout.write(f"  Imágenes descargadas: {informe.imagenes_ok}")

        # A27.4: los fallos se cuentan uno a uno, no se resumen en «casi todo bien».
        if informe.imagenes_fallidas:
            self.stdout.write(
                self.style.WARNING(f"\n  Imágenes NO descargadas: {len(informe.imagenes_fallidas)}")
            )
            for url, motivo in informe.imagenes_fallidas:
                self.stdout.write(f"    · {url[:95]}\n        {motivo}")

        if informe.posts_sin_cuerpo:
            self.stdout.write(
                self.style.WARNING(f"\n  Artículos que quedaron sin cuerpo: {len(informe.posts_sin_cuerpo)}")
            )
            for linea in informe.posts_sin_cuerpo:
                self.stdout.write(f"    · {linea[:110]}")

        if informe.sin_entradilla:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  Sin texto para la entradilla (se usó el título): {len(informe.sin_entradilla)}"
                )
            )
            for linea in informe.sin_entradilla:
                self.stdout.write(f"    · {linea[:110]}")

        if informe.etiquetas_descartadas:
            self.stdout.write(
                self.style.WARNING(f"\n  Etiquetas sin mapear: {informe.etiquetas_descartadas}")
            )

        self.stdout.write(self.style.SUCCESS("\n  Hecho.\n"))
