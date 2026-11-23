"""Leer un sitio de Google Sites (el «nuevo», 2016 en adelante).

Igual que `blogspot.py`, todo lo de aquí es **puro**: entra HTML, sale HTML.
La red y la base de datos las pone el comando `import_google_sites`.

Google Sites no tiene feed ni exportación. Lo que sí tiene es HTML servido ya
montado, con una forma estable: cada franja de la página es un `<section>`, el
texto va en `<p>`, `<h1>`…`<h3>` y `<ul>`, y **la negrita no es una etiqueta**
sino un `font-weight: 700` en el `style` de un `<span>`. Si se pasara ese HTML
tal cual por `limpiar_cuerpo`, que tira los `<span>` y los `style`, el artículo
saldría entero en texto plano: sin un solo subtítulo, porque en Sites casi
nadie usa los encabezados y casi todo el mundo pone una línea en negrita.

Este módulo traduce esa forma a etiquetas de verdad **antes** de la limpieza.
"""

from __future__ import annotations

import re
import urllib.parse

from bs4 import BeautifulSoup, Tag

from blogs.blogspot import slugify_simple

#: Un párrafo entero en negrita de hasta este largo es un subtítulo.
MAX_SUBTITULO = 90

_NEGRITA = re.compile(r"font-weight:\s*(bold|[6-9]00)", re.I)
_CURSIVA = re.compile(r"font-style:\s*italic", re.I)
_SITIO = re.compile(r"^(/(?:view|[a-z0-9.-]+\.[a-z]{2,})/[^/?#]+)", re.I)


def prefijo_del_sitio(url: str) -> str:
    """`https://sites.google.com/centro.es/depto/inicio?x=1` -> `/centro.es/depto`.

    Vale también para los sitios sin dominio (`/view/nombre`). Lanza
    `ValueError` si la URL no es de Google Sites: es preferible parar a ponerse
    a recorrer una web cualquiera creyendo que es un sitio.
    """
    partes = urllib.parse.urlparse(url)
    if partes.netloc != "sites.google.com":
        raise ValueError(f"No es una dirección de Google Sites: {url}")
    encontrado = _SITIO.match(urllib.parse.unquote(partes.path))
    if not encontrado:
        raise ValueError(f"No reconozco el sitio en la dirección: {url}")
    return encontrado.group(1)


def ruta_interna(href: str, prefijo: str) -> str | None:
    """La ruta de una página del sitio, relativa al prefijo, o `None`.

    `/centro.es/depto/cursos/3º-eso?authuser=0` -> `cursos/3º-eso`. Los enlaces
    a otra parte de la misma página (`#h.abc`) y a otros sitios dan `None`.
    """
    if not href:
        return None
    partes = urllib.parse.urlparse(href)
    if partes.netloc not in ("", "sites.google.com"):
        return None
    ruta = urllib.parse.unquote(partes.path)
    if not ruta.startswith(prefijo + "/"):
        return None
    return ruta[len(prefijo) + 1 :].strip("/") or None


def url_canonica(prefijo: str, ruta: str) -> str:
    """La dirección estable de una página: la identidad del artículo importado."""
    return "https://sites.google.com" + urllib.parse.quote(f"{prefijo}/{ruta}")


def enlaces_internos(html: str, prefijo: str) -> list[str]:
    """Las páginas del sitio enlazadas desde esta, sin repetir y en orden.

    Incluye el menú: es justo ahí donde están todas las páginas.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    vistas: list[str] = []
    for enlace in soup.find_all("a", href=True):
        ruta = ruta_interna(enlace["href"], prefijo)
        if ruta and ruta not in vistas:
            vistas.append(ruta)
    return vistas


def slug_de_ruta(ruta: str) -> str:
    """`cursos/3º-eso` -> `cursos-3o-eso`.

    Entra la ruta entera y no solo el último tramo: dos subpáginas de padres
    distintos pueden llamarse igual («contacto» bajo dos secciones).
    """
    return slugify_simple(ruta.replace("/", "-").replace("º", "o").replace("ª", "a"))[:225]


def _texto(etiqueta: Tag) -> str:
    # Sin separador: Sites parte una palabra en varios `<span>` («202», «6»,
    # «/2», «7») y un espacio entre ellos escribiría «202 6 /2 7».
    return re.sub(r"\s+", " ", etiqueta.get_text("")).strip()


def _toda_en_negrita(parrafo: Tag) -> bool:
    """¿Todo el texto del párrafo está dentro de un `<strong>`?"""
    hay_texto = False
    for trozo in parrafo.find_all(string=True):
        if not trozo.strip():
            continue
        hay_texto = True
        if trozo.find_parent("strong") is None:
            return False
    return hay_texto


def _estilos_a_etiquetas(soup: BeautifulSoup) -> None:
    for span in soup.find_all("span"):
        estilo = span.get("style") or ""
        if not span.get_text(strip=True):
            continue
        if _CURSIVA.search(estilo):
            span.wrap(soup.new_tag("em"))
        # Dentro de un enlace la negrita es el estilo del enlace en el tema
        # del sitio, no un énfasis de quien escribió.
        if _NEGRITA.search(estilo) and span.find_parent("a") is None:
            span.wrap(soup.new_tag("strong"))

    # «sa» + «randa» + «@centro.es», cada trozo con su negrita: una sola.
    for fuerte in soup.find_all("strong"):
        siguiente = fuerte.next_sibling
        while isinstance(siguiente, Tag) and siguiente.name == "strong":
            fuerte.extend(list(siguiente.contents))
            siguiente.decompose()
            siguiente = fuerte.next_sibling


def _botones_a_enlaces(soup: BeautifulSoup) -> None:
    """Un botón de Sites es `<a><div><p>Texto</p></div></a>`: un bloque dentro
    de un enlace. Se deja como un párrafo con el enlace dentro."""
    for enlace in soup.find_all("a", href=True):
        if enlace.find(["p", "div"]) is None:
            continue
        texto = _texto(enlace)
        if not texto:
            enlace.decompose()
            continue
        limpio = soup.new_tag("a", href=enlace["href"])
        limpio.string = texto
        parrafo = soup.new_tag("p")
        parrafo.append(limpio)
        enlace.replace_with(parrafo)


def extraer_pagina(html: str) -> tuple[str, str]:
    """`(título, cuerpo)` de una página de Google Sites.

    El cuerpo sale con etiquetas de verdad pero todavía sin limpiar: conserva
    los `<img>` y los enlaces a Drive, que el comando sustituye por copias
    propias antes de pasar el resultado por `limpiar_cuerpo`.

    Tres traducciones, las tres por estructura y ninguna por contenido:

    - el primer `<h1>` es el título de la página y sale del cuerpo;
    - una franja que solo tiene una línea corta es el rótulo de lo que viene
      debajo: pasa a `<h2>`;
    - un párrafo corto entero en negrita es un subtítulo: pasa a `<h3>`.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for sobra in soup.find_all(["script", "style", "nav", "header", "footer", "noscript"]):
        sobra.decompose()

    secciones = soup.find_all("section")
    titulo = ""
    primero = soup.find("h1")
    if primero is not None:
        titulo = _texto(primero)
        primero.decompose()

    # El ancla que Sites cuelga de cada encabezado («copiar enlace a esta
    # sección») es un enlace vacío que acabaría como basura delante del texto.
    for encabezado in soup.find_all(["h1", "h2", "h3", "h4"]):
        for enlace in encabezado.find_all("a"):
            if not enlace.get_text(strip=True):
                enlace.decompose()

    _botones_a_enlaces(soup)
    _estilos_a_etiquetas(soup)

    # Sites mete un `<p>` dentro de cada `<li>`; en texto enriquecido eso es
    # una viñeta con un salto de más.
    for elemento in soup.find_all("li"):
        for parrafo in elemento.find_all("p"):
            parrafo.unwrap()

    trozos: list[str] = []
    for seccion in secciones:
        bloques = [
            b for b in seccion.find_all(["p", "h1", "h2", "h3", "h4", "ul", "ol", "img"])
            if b.find_parent(["ul", "ol", "p"]) is None
        ]
        con_contenido = [b for b in bloques if b.name == "img" or _texto(b)]
        if not con_contenido:
            continue

        es_rotulo = (
            len(con_contenido) == 1
            and con_contenido[0].name == "p"
            and len(_texto(con_contenido[0])) <= MAX_SUBTITULO
            and con_contenido[0].find("a") is None
        )
        for bloque in con_contenido:
            if bloque.name == "p":
                largo = len(_texto(bloque))
                if es_rotulo:
                    trozos.append(f"<h2>{_texto(bloque)}</h2>")
                    continue
                # Una frase que acaba en punto o en exclamación es un énfasis
                # («¡Estaremos encantados de orientarte!»), no un subtítulo.
                es_frase = _texto(bloque).endswith((".", "!"))
                if (
                    largo <= MAX_SUBTITULO
                    and not es_frase
                    and _toda_en_negrita(bloque)
                    and bloque.find("a") is None
                ):
                    trozos.append(f"<h3>{_texto(bloque)}</h3>")
                    continue
            elif bloque.name in ("h1", "h2", "h3", "h4"):
                # El `h1` ya salió como título; los demás bajan un escalón como
                # mucho hasta `h2`, que es el primer nivel dentro del artículo.
                nivel = "h2" if bloque.name in ("h1", "h2") else "h3"
                trozos.append(f"<{nivel}>{_texto(bloque)}</{nivel}>")
                continue
            trozos.append(str(bloque))

    return titulo, "\n".join(trozos)


def reescribir_enlaces_internos(html: str, prefijo: str, destinos: dict[str, int]) -> str:
    """Los enlaces entre páginas del sitio pasan a apuntar a nuestros artículos.

    `destinos` es `ruta -> pk` de la página de Wagtail. Un enlace a una página
    que no se ha importado se queda apuntando al sitio original, con la
    dirección completa: una ruta relativa de Google no significa nada aquí.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for enlace in soup.find_all("a", href=True):
        ruta = ruta_interna(enlace["href"], prefijo)
        if ruta is None:
            continue
        if ruta in destinos:
            enlace.attrs = {"linktype": "page", "id": str(destinos[ruta])}
        else:
            enlace["href"] = url_canonica(prefijo, ruta)
    return soup.decode()
