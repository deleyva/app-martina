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
from django.core.files.base import ContentFile
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from wagtail.images import get_image_model
from wagtail.models import Collection

from wagtail.documents import get_document_model
from wagtail.embeds.embeds import get_embed
from wagtail.embeds.exceptions import EmbedException

from blogs.blogspot import (
    BLOG_MAP,
    descarga_de_google,
    es_enlace_a_google_drive,
    derivar_intro,
    es_imagen_de_google,
    etiqueta_facetada,
    limpiar_cuerpo,
    slug_desde_url,
    url_de_ver_youtube,
    url_maxima_resolucion,
)
from blogs.models import ArticuloPage, BlogIndexPage

UA = "Mozilla/5.0 (compatible; IES Martina Bescos importador de blogs)"
TIMEOUT = 45
MAX_BYTES_IMAGEN = 25 * 1024 * 1024
MAX_BYTES_ARCHIVO = 150 * 1024 * 1024


@dataclass
class Informe:
    """Lo que pasó de verdad, para poder contarlo entero al final."""

    creados: int = 0
    saltados: int = 0
    imagenes_ok: int = 0
    imagenes_fallidas: list[tuple[str, str]] = field(default_factory=list)
    archivos_ok: int = 0
    archivos_borrados: list[str] = field(default_factory=list)
    archivos_restringidos: list[str] = field(default_factory=list)
    archivos_no_traibles: list[str] = field(default_factory=list)
    videos_ok: int = 0
    videos_en_blogger: list[str] = field(default_factory=list)
    videos_fallidos: list[tuple[str, str]] = field(default_factory=list)
    etiquetas_descartadas: list[str] = field(default_factory=list)
    posts_sin_cuerpo: list[str] = field(default_factory=list)
    sin_entradilla: list[str] = field(default_factory=list)
    fallidos: list[tuple[str, str]] = field(default_factory=list)


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
            "--reintentar-archivos",
            action="store_true",
            dest="reintentar_archivos",
            help=(
                "No importa nada nuevo: recorre los artículos YA importados y vuelve a "
                "intentar bajar los archivos de Drive que siguen enlazados. Para usarlo "
                "después de abrir permisos en Drive."
            ),
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

    #: Documentos ya bajados en esta ejecución, por identificador de Drive.
    _documentos_vistos: dict

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

    def _sustituir_archivos(self, soup: BeautifulSoup, coleccion, informe: Informe) -> None:
        """Los PDF que el profesorado dejó en Drive se traen al servidor.

        El profesorado no subía los documentos al blog: los subía a Drive y
        enlazaba. Un artículo importado que siga apuntando ahí no está
        realmente traído — depende de una carpeta que alguien puede mover,
        cerrar o vaciar mañana. Se baja el fichero, se guarda como documento de
        Wagtail y el enlace del texto pasa a apuntar a nuestra copia, con el
        mismo texto que escribió quien lo puso.

        Tres cosas se quedan como enlace a propósito: las carpetas de Drive (no
        son un fichero), los formularios (son formularios vivos) y todo lo que
        no se pueda bajar sin credenciales. Para eso último NO se usa la cuenta
        de Google de nadie: si un fichero está restringido al dominio del
        centro, se dice y se deja el enlace.
        """
        for enlace in soup.find_all("a"):
            destino = (enlace.get("href") or "").strip()
            if not es_enlace_a_google_drive(destino):
                continue

            objetivo = descarga_de_google(destino)
            if objetivo is None:
                # Carpeta o formulario: el enlace es la forma correcta.
                informe.archivos_no_traibles.append(destino)
                continue

            url_descarga, identificador, extension = objetivo

            # El mismo PDF se enlaza desde varios articulos —las «Orientaciones
            # para el alumnado» salen en nueve semanas seguidas—. Sin esta
            # cache se bajaria y se guardaria una copia por enlace.
            documento = self._documentos_vistos.get(identificador)
            if documento is None:
                documento = self._descargar_documento(
                    url_descarga, identificador, extension,
                    enlace.get_text(" ", strip=True), coleccion, informe, destino,
                )
                if documento is not None:
                    self._documentos_vistos[identificador] = documento
            if documento is None:
                continue  # ya anotado; el enlace original se queda como estaba

            # `linktype="document"` es la forma nativa de Wagtail: sobrevive a
            # que el fichero se renombre y respeta los permisos de la colección.
            enlace.attrs = {"linktype": "document", "id": str(documento.pk)}
            informe.archivos_ok += 1

    def _descargar_documento(
        self, url, identificador, extension, texto, coleccion, informe, original
    ):
        """Baja un fichero de Drive. `None` si no se puede, siempre anotando por qué."""
        try:
            peticion = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
                tipo = respuesta.headers.get("Content-Type", "")
                disposicion = respuesta.headers.get("Content-Disposition", "")
                datos = respuesta.read(MAX_BYTES_ARCHIVO + 1)
        except urllib.error.HTTPError as exc:
            # 404/410: el fichero ya no existe en Drive. Hoy, en el blog de
            # Blogspot, ese enlace ya está roto: no se pierde nada al importar,
            # pero conviene saber cuántos son.
            (informe.archivos_borrados if exc.code in (404, 410) else informe.archivos_restringidos).append(
                f"{original} (HTTP {exc.code})"
            )
            return None
        except (urllib.error.URLError, OSError) as exc:
            informe.archivos_restringidos.append(f"{original} ({type(exc).__name__})")
            return None

        if len(datos) > MAX_BYTES_ARCHIVO:
            informe.archivos_restringidos.append(f"{original} (más de 150 MB)")
            return None

        if "text/html" in tipo:
            # Drive contesta HTML en dos casos: pide iniciar sesión (fichero
            # restringido al dominio del centro) o avisa de que no puede pasar
            # el antivirus por tamaño. El segundo se puede confirmar.
            texto_html = datos.decode("utf-8", errors="replace")
            if "confirm=" in texto_html:
                try:
                    peticion = urllib.request.Request(
                        url + "&confirm=t", headers={"User-Agent": UA}
                    )
                    with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
                        disposicion = respuesta.headers.get("Content-Disposition", "")
                        datos = respuesta.read(MAX_BYTES_ARCHIVO + 1)
                except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
                    informe.archivos_restringidos.append(f"{original} ({type(exc).__name__})")
                    return None
            else:
                informe.archivos_restringidos.append(f"{original} (pide iniciar sesión)")
                return None

        nombre = self._nombre_de_fichero(disposicion) or f"{identificador}.{extension or 'pdf'}"
        documento = get_document_model()(
            title=(texto or nombre)[:255],
            collection=coleccion,
        )
        try:
            documento.file.save(nombre, ContentFile(datos), save=False)
            documento.save()
        except Exception as exc:
            informe.archivos_restringidos.append(f"{original} (no se pudo guardar: {type(exc).__name__})")
            return None
        return documento

    @staticmethod
    def _nombre_de_fichero(disposicion: str) -> str:
        """El nombre real que da Drive, con los acentos puestos.

        Drive manda el nombre en UTF-8 dentro de una cabecera que Python
        interpreta como latin-1: sin deshacer eso, «1º ESO» se guarda como
        «1Â° ESO».
        """
        encontrado = re.search(r"filename\*?=(?:UTF-8\'\')?\"?([^\";]+)", disposicion or "")
        if not encontrado:
            return ""
        nombre = urllib.parse.unquote(encontrado.group(1).strip())
        try:
            nombre = nombre.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        nombre = re.sub(r"[/\\\x00-\x1f]", "_", nombre).strip()
        return nombre[:90]

    def _sustituir_videos(self, soup: BeautifulSoup, informe: Informe) -> None:
        """El `<iframe>` de Blogspot pasa a ser un embed nativo de Wagtail.

        Esto no es cosmética. `articulo.html` hace responsive los vídeos con
        `.blog-embed-wrapper > div:first-child iframe`, un selector escrito para
        la forma que produce Wagtail: `<div class="responsive-object"><iframe>`.
        Un iframe pegado tal cual de Blogspot cuelga de un `<p>`, no casa con el
        selector, se queda sin dimensiones y **el vídeo sale como un hueco en
        blanco** — verificado en el navegador antes de arreglarlo. Pasando por
        el embed nativo, un vídeo importado se comporta igual que uno que meta
        un profesor desde el editor.

        Se pide el embed aquí, en la importación, y no en cada visita: así queda
        cacheado en la BD y, de paso, un vídeo borrado de YouTube se detecta hoy
        y no dentro de un año.
        """
        for marco in soup.find_all("iframe"):
            fuente = marco.get("src") or ""
            url_ver = url_de_ver_youtube(fuente)
            if not url_ver:
                # 11 vídeos del archivo están SUBIDOS a Blogger, no enlazados de
                # YouTube: `blogger.com/video.g?token=…`. Son grabaciones de
                # clase y trabajos del alumnado, y no existen en ningún otro
                # sitio. Su página de reproducción arranca el reproductor de
                # YouTube desde JavaScript ofuscado, así que el fichero no se
                # puede bajar sin adivinar cómo funciona por dentro un servicio
                # de Google. Se deja el iframe, que sigue funcionando, y se
                # anota: es lo ÚNICO que esta migración no trae al servidor del
                # centro, y sigue dependiendo de la cuenta de Blogger.
                if "blogger.com/video" in fuente:
                    informe.videos_en_blogger.append(fuente.split("?")[0])
                continue
            try:
                get_embed(url_ver)
            except (EmbedException, OSError) as exc:
                # El vídeo ya no existe o YouTube no contesta: se deja un enlace
                # en vez de un hueco, y se dice cuál (A27.4).
                informe.videos_fallidos.append((url_ver, f"{type(exc).__name__}: {exc}"))
                enlace = soup.new_tag("a", href=url_ver)
                enlace.string = "Ver el vídeo en YouTube"
                parrafo = soup.new_tag("p")
                parrafo.append(enlace)
                marco.replace_with(parrafo)
                continue

            embed = soup.new_tag("embed")
            embed.attrs = {"embedtype": "media", "url": url_ver}
            marco.replace_with(embed)
            informe.videos_ok += 1

    def _sustituir_imagenes(self, html: str, titulo: str, coleccion: Collection, informe: Informe):
        """Cada `<img>` pasa a ser un `<embed>` de Wagtail apuntando a una imagen nuestra.

        Devuelve `(html, primera_imagen, primera_era_la_cabecera)`. La primera
        imagen se promociona a `featured_image` porque es lo que pinta la
        portada y las fichas del listado; si además era lo primero del
        artículo, se quita del cuerpo para no verla dos veces seguidas.
        """
        soup = BeautifulSoup(html or "", "html.parser")
        self._sustituir_videos(soup, informe)
        self._sustituir_archivos(soup, coleccion, informe)
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
        self._documentos_vistos = {}
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

        if opciones["reintentar_archivos"]:
            return self._reintentar_archivos(hosts, destinos)

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
                # Un post con HTML que rompa la limpieza no puede llevarse por
                # delante los otros 227. Se anota, se sigue, y sale en el
                # informe (A27.4). Como cada artículo va en su transacción, el
                # que falla no deja nada a medias, y al relanzar se reintenta.
                try:
                    with transaction.atomic():
                        self._crear_articulo(
                            entrada, destino, coleccion, informe, publicar, es_pagina
                        )
                except Exception as exc:
                    titulo = (entrada.get("title", {}).get("$t") or "(sin título)").strip()
                    informe.fallidos.append(
                        (f"{titulo} — {_enlace_original(entrada)}", f"{type(exc).__name__}: {exc}")
                    )
                    self.stderr.write(self.style.ERROR(f"    ! {titulo[:60]} — {type(exc).__name__}"))

        self._resumen(informe, seco)

    def _reintentar_archivos(self, hosts, destinos) -> None:
        """Segunda pasada solo para los archivos que la primera no pudo bajar.

        Existe porque la razón más común de no poder bajar uno es que esté
        restringido al dominio del centro, y eso se arregla en Drive con dos
        clics. Sin esta pasada, la única forma de recoger el arreglo sería
        borrar y reimportar el artículo, perdiendo lo que alguien haya editado.
        """
        informe = Informe()
        self.stdout.write(
            self.style.MIGRATE_HEADING("\nREINTENTANDO ARCHIVOS de artículos ya importados\n")
        )
        for host in hosts:
            destino = destinos[host]
            coleccion = self._coleccion(f"Blogspot — {destino.title}")
            articulos = [
                a
                for a in ArticuloPage.objects.child_of(destino).specific()
                if a.source_url and es_enlace_a_google_drive(a.body or "")
            ]
            if not articulos:
                continue
            self.stdout.write(self.style.HTTP_INFO(f"\n{host} → /{destino.slug}/ ({len(articulos)})"))
            for articulo in articulos:
                antes = informe.archivos_ok
                soup = BeautifulSoup(articulo.body, "html.parser")
                self._sustituir_archivos(soup, coleccion, informe)
                if informe.archivos_ok == antes:
                    continue
                with transaction.atomic():
                    articulo.body = limpiar_cuerpo(soup.decode())
                    articulo.save()
                    revision = articulo.save_revision()
                    if articulo.live:
                        revision.publish()
                self.stdout.write(f"    + {informe.archivos_ok - antes} archivo(s) · {articulo.title[:55]}")
        self._resumen(informe, seco=False)

    def _resumen(self, informe: Informe, seco: bool) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n\n── Resumen ──"))
        etiqueta = "se crearían" if seco else "creados"
        self.stdout.write(f"  Artículos {etiqueta}: {informe.creados}")
        self.stdout.write(f"  Ya estaban (saltados): {informe.saltados}")
        if seco:
            return

        self.stdout.write(f"  Imágenes descargadas: {informe.imagenes_ok}")
        self.stdout.write(f"  Vídeos de YouTube incrustados: {informe.videos_ok}")
        self.stdout.write(f"  Archivos traídos de Drive: {informe.archivos_ok}")

        if informe.archivos_borrados:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  Archivos que YA NO EXISTEN en Drive: {len(informe.archivos_borrados)}"
                )
            )
            self.stdout.write(
                "    Estos enlaces ya están rotos hoy en el blog de Blogspot. No se pierde\n"
                "    nada al importar: se perdieron cuando alguien borró el fichero."
            )
            for linea in informe.archivos_borrados:
                self.stdout.write(f"    · {linea[:110]}")

        if informe.archivos_restringidos:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  Archivos que piden iniciar sesión: {len(informe.archivos_restringidos)}"
                )
            )
            self.stdout.write(
                "    Están restringidos al dominio del centro. NO se ha usado la cuenta de\n"
                "    Google de nadie para bajarlos. Si los abres a «cualquiera con el enlace»\n"
                "    en Drive, `--reintentar-archivos` los trae sin tocar nada más."
            )
            for linea in informe.archivos_restringidos:
                self.stdout.write(f"    · {linea[:110]}")

        if informe.archivos_no_traibles:
            self.stdout.write(
                f"\n  Carpetas y formularios que se quedan como enlace (correcto):"
                f" {len(informe.archivos_no_traibles)}"
            )

        if informe.videos_en_blogger:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  Vídeos que siguen alojados en Blogger, NO en el servidor del centro:"
                    f" {len(informe.videos_en_blogger)}"
                )
            )
            self.stdout.write(
                "    Son grabaciones subidas a Blogger, no enlaces de YouTube. Se ven bien,\n"
                "    pero dependen de que la cuenta de Blogger siga existiendo."
            )

        if informe.videos_fallidos:
            self.stdout.write(
                self.style.WARNING(f"\n  Vídeos que no se pudieron incrustar: {len(informe.videos_fallidos)}")
            )
            for url, motivo in informe.videos_fallidos:
                self.stdout.write(f"    · {url}\n        {motivo[:140]}")

        if informe.fallidos:
            self.stdout.write(
                self.style.ERROR(f"\n  Artículos que NO se pudieron importar: {len(informe.fallidos)}")
            )
            for linea, motivo in informe.fallidos:
                self.stdout.write(f"    · {linea[:100]}\n        {motivo[:160]}")

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
