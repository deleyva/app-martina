"""Traer a casa dieciséis blogs de Blogspot.

Todo lo que hay aquí es **puro**: entra texto, sale texto. Ni red, ni base de
datos, ni Django. El comando de gestión pone la red y la BD; esta parte se
prueba entera sin levantar nada.

Esa separación no es estética. El cuerpo de un post de Blogspot es HTML pegado
desde Google Docs —3.636 `<span>`, 1.670 `<div>`, `style=` en casi cada
etiqueta, restos de Word con espacio de nombres (`<o:p>`, `<v:shape>`)— y la
limpieza es la parte que de verdad puede salir mal. Si para probarla hiciera
falta la red, no se probaría.
"""

from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import CData, Comment, Declaration, Doctype, ProcessingInstruction

# ---------------------------------------------------------------------------
# El mapa: qué blog va a qué departamento
# ---------------------------------------------------------------------------

# Host de blogspot (sin `.blogspot.com`) -> slug de la `BlogIndexPage` destino.
# Los slugs de la derecha ya existen en el sitio; el comando aborta si alguno
# deja de existir, en vez de crear páginas colgando de la nada.
BLOG_MAP: dict[str, str] = {
    "dalemaniesmbescos": "aleman",
    "efiesmb": "educacion-fisica",
    "dplasticaiesmbescos": "educacion-plastica-y-visual",
    "dfrancesiesmbescos": "frances",
    "dgeohistoriaiesmbescos": "geografia-e-historia",
    "naturalesmbescos": "biologia-y-geologia",
    "dptingiesmartinabescos": "ingles",
    "dlenguaiesmbescos": "lengua-y-literatura",
    "dmatematicasiesmbescos": "matematicas",
    "dmusicaiesmbescos": "musica",
    "dorientacioniesmbescos": "orientacion",
    "dtecnologiaiesmbescos": "tecnologia",
    "dfyqmbescos": "fisica-y-quimica",
    "economiambescos": "economia",
    "filosofiambescos": "filosofia",
    "culturaclasicambescos": "cultura-clasica",
}

# ---------------------------------------------------------------------------
# Imágenes: de la miniatura al original
# ---------------------------------------------------------------------------

# Blogger sirve la MISMA foto a cualquier tamaño cambiando un trozo de la URL.
# Importa porque 271 de las 582 imágenes están incrustadas a `/s320/`: traerse
# lo que pone el `<img src>` sería quedarse con miniaturas de 320px para
# siempre. `s0` es el original tal y como se subió (medido: 254x320 -> 825x1040).
_SIZE_IN_PATH = re.compile(r"/(?:s\d+|w\d+-h\d+|h\d+-w\d+)(?:-[a-z-]+)?/")
_SIZE_IN_SUFFIX = re.compile(r"=(?:s\d+|w\d+-h\d+|h\d+-w\d+)(?:-[a-z-]+)?$")

# `https://www.youtube.com/embed/ID?feature=player_embedded` -> `ID`.
# Los 22 iframes del archivo son todos de YouTube, en las dos formas que ha
# usado Blogger a lo largo de los años (`/embed/` y `/v/`).
_YOUTUBE_ID = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:embed|v)/|youtu\.be/)([A-Za-z0-9_-]{6,})"
)


def id_de_youtube(url: str) -> str | None:
    """El identificador del vídeo, o `None` si la URL no es de YouTube."""
    encontrado = _YOUTUBE_ID.search(url or "")
    return encontrado.group(1) if encontrado else None


def url_de_ver_youtube(url_incrustada: str) -> str | None:
    """De la URL de incrustar a la de ver, que es la que entiende Wagtail."""
    identificador = id_de_youtube(url_incrustada)
    return f"https://www.youtube.com/watch?v={identificador}" if identificador else None


DOMINIOS_GOOGLE = (
    "blogger.googleusercontent.com",
    "bp.blogspot.com",
    "lh3.googleusercontent.com",
    "lh4.googleusercontent.com",
    "lh5.googleusercontent.com",
    "lh6.googleusercontent.com",
    "lh7-us.googleusercontent.com",
    "googleusercontent.com",
)


def es_imagen_de_google(url: str) -> bool:
    """¿Esta imagen vive en un servidor de Google del que podemos bajarla?"""
    return any(d in url for d in DOMINIOS_GOOGLE)


def url_maxima_resolucion(url: str) -> str:
    """Reescribe una URL de imagen de Blogger para pedir el original.

    Devuelve la URL tal cual si no reconoce el patrón de tamaño: es preferible
    bajar la miniatura a inventarse una URL que da 404.
    """
    nueva = _SIZE_IN_PATH.sub("/s0/", url, count=1)
    if nueva != url:
        return nueva
    return _SIZE_IN_SUFFIX.sub("=s0", url, count=1)


# ---------------------------------------------------------------------------
# Etiquetas: al vocabulario que ya existe, no al lado
# ---------------------------------------------------------------------------

# Las 10 etiquetas que de verdad hay en los 16 blogs (medido 2026-09-06; solo
# 17 de 223 posts llevan alguna). Van a facetas que el sitio ya usa —`curso:` y
# `tema:`— porque meterlas sueltas rompería el vocabulario facetado: es la
# deriva que documenta LIFEOS/RULES/Tagging.md.
_CURSO = re.compile(r"^(\d)\s*[ºo°]?\s*(?:ESO|eso)\b")


def _sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def slugify_simple(texto: str) -> str:
    """Minúsculas, sin acentos, con guiones. Sin depender de Django."""
    limpio = _sin_acentos(texto).lower()
    limpio = re.sub(r"[^a-z0-9]+", "-", limpio)
    return limpio.strip("-")


def etiqueta_facetada(etiqueta_blogger: str) -> str | None:
    """`1ºESO` -> `curso:1-eso`; `información` -> `tema:informacion`.

    Devuelve `None` para una etiqueta que quede vacía al normalizar, para que
    el comando la reporte en vez de escribir un `tema:` huérfano.
    """
    bruta = etiqueta_blogger.strip()
    m = _CURSO.match(bruta)
    if m:
        return f"curso:{m.group(1)}-eso"
    valor = slugify_simple(bruta)
    if not valor:
        return None
    return f"tema:{valor}"


# ---------------------------------------------------------------------------
# El cuerpo: de HTML de Google Docs a texto enriquecido de Wagtail
# ---------------------------------------------------------------------------

# Lo que sobrevive. Todo lo demás se desenvuelve (se queda su contenido, se va
# la etiqueta). No se borra contenido nunca: se borra maquetación.
PERMITIDAS = {
    "p", "br", "hr",
    "h2", "h3", "h4", "h5", "h6",
    "b", "strong", "i", "em", "u", "s", "strike", "del", "sub", "sup",
    "ul", "ol", "li",
    "a", "blockquote", "pre", "code",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption",
    "iframe", "embed", "img",
}

# Los atributos que se quedan, por etiqueta. El resto —`style`, `class`, `id`,
# `dir`, `role`, `aria-*`, `data-*`, `width`, `height`— se va entero: es lo que
# hace que un artículo importado pelee con la maqueta editorial del sitio.
ATRIBUTOS = {
    "a": {"href", "target", "rel"},
    "img": {"src", "alt", "title"},
    "iframe": {"src", "allowfullscreen", "allow", "title"},
    "embed": {"embedtype", "id", "format", "alt", "url"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}

# Contenedores puros de maquetación: se desenvuelven siempre.
DESENVOLVER = {
    "span", "div", "font", "center", "section", "article", "header", "footer",
    "main", "aside", "nav", "figure", "figcaption", "small", "big", "tt",
    "ins", "abbr", "acronym", "label", "form", "col", "colgroup",
}

# Etiquetas inline: si aparecen sueltas en la raíz, se agrupan en un `<p>`.
INLINE = {
    "a", "b", "strong", "i", "em", "u", "s", "strike", "del", "sub", "sup",
    "code", "br", "img", "embed",
}


def _vivo(etiqueta) -> bool:
    """¿Sigue esta etiqueta en el árbol?

    `find_all` devuelve una lista congelada. Si al recorrerla se destruye una
    etiqueta que contenía a otra, la interior sigue en la lista pero ya está
    muerta: BeautifulSoup le pone `attrs` a `None` y cualquier `.get()` revienta
    con `AttributeError: 'NoneType' object has no attribute 'get'`. Pasó de
    verdad, en el artículo 68 de 228 del ensayo, con dos `<a>` anidados que
    Blogger deja al enlazar una foto dentro de otro enlace.

    Todos los bucles de este módulo que destruyen etiquetas pasan por aquí.
    """
    return not getattr(etiqueta, "decomposed", False) and etiqueta.attrs is not None


# Nodos que no son ni etiquetas ni texto: comentarios, CDATA, doctypes.
_NO_ES_CONTENIDO = (Comment, CData, ProcessingInstruction, Declaration, Doctype)


def _quitar_basura(soup: BeautifulSoup) -> None:
    """Scripts, estilos, comentarios y los restos de Word con espacio de nombres."""
    # Los comentarios primero, y este es el orden que importa. Word pega su
    # maquetación VML dentro de un comentario condicional:
    #
    #     <!--[if gte vml 1]><v:shape ... alt="https://lh4.googleusercontent…">
    #     <v:stroke joinstyle="miter"/> ... <![endif]-->
    #
    # BeautifulSoup lo ve como UN comentario, no como etiquetas: `find_all` no
    # entra ahí, así que ni el desenvolvedor de `<v:…>` ni el limpiador de
    # atributos lo tocaban y salía tal cual en el artículo publicado. Es como
    # sobrevivían `style=` y una URL de Google en los tres artículos del
    # concurso de fotografía matemática — invisible hasta que se cuenta sobre
    # los 228 cuerpos, porque en pantalla un comentario no se ve.
    for nodo in soup.find_all(string=lambda t: isinstance(t, _NO_ES_CONTENIDO)):
        nodo.extract()

    for etiqueta in soup.find_all(["script", "style", "noscript", "meta", "link"]):
        if _vivo(etiqueta):
            etiqueta.decompose()
    # `<o:p>`, `<v:shape>`, `<w:sdt>`: Word los deja al pegar. BeautifulSoup los
    # ve como etiquetas con dos puntos en el nombre.
    for etiqueta in soup.find_all(lambda t: isinstance(t, Tag) and ":" in t.name):
        if _vivo(etiqueta):
            etiqueta.unwrap()


def _normalizar_estructura(soup: BeautifulSoup) -> None:
    """`h1` pasa a `h2` (el `h1` de la página es el título) y fuera contenedores."""
    for etiqueta in soup.find_all("h1"):
        if _vivo(etiqueta):
            etiqueta.name = "h2"
    for nombre in DESENVOLVER:
        for etiqueta in soup.find_all(nombre):
            if _vivo(etiqueta):
                etiqueta.unwrap()
    # Lo que quede fuera de la lista y no sea de tabla, se desenvuelve también.
    for etiqueta in soup.find_all(True):
        if _vivo(etiqueta) and etiqueta.name not in PERMITIDAS:
            etiqueta.unwrap()


def _limpiar_atributos(soup: BeautifulSoup) -> None:
    for etiqueta in soup.find_all(True):
        if not _vivo(etiqueta):
            continue
        permitidos = ATRIBUTOS.get(etiqueta.name, set())
        for attr in list(etiqueta.attrs):
            if attr not in permitidos:
                del etiqueta[attr]


def _envolver_sueltos(soup: BeautifulSoup) -> None:
    """Texto e inline colgando de la raíz -> dentro de un `<p>`.

    Al desenvolver los `<div>` queda texto suelto en el nivel superior. Sin
    esto, el navegador lo pinta pegado al bloque anterior y se pierde la
    separación entre párrafos que sí tenía el original.
    """
    hijos = list(soup.children)
    grupo: list = []

    def cerrar() -> None:
        if not grupo:
            return
        if all(isinstance(n, NavigableString) and not n.strip() for n in grupo):
            grupo.clear()
            return
        parrafo = soup.new_tag("p")
        grupo[0].insert_before(parrafo)
        for nodo in grupo:
            parrafo.append(nodo.extract())
        grupo.clear()

    for nodo in hijos:
        es_inline = (
            isinstance(nodo, NavigableString)
            or (isinstance(nodo, Tag) and nodo.name in INLINE)
        )
        if es_inline:
            grupo.append(nodo)
        else:
            cerrar()
    cerrar()


def _desenvolver_tablas_de_maquetacion(soup: BeautifulSoup) -> None:
    """Las tablas de una sola columna de Blogspot no son tablas.

    El editor clásico de Blogger centra una foto con su pie metiéndola en una
    `<table>` de una celda por fila (`tr-caption-container`). Medido en el
    archivo del centro: las 7 tablas de Alemán son TODAS de este tipo. Dejarlas
    convierte cada foto en una tabla para un lector de pantalla, y en la maqueta
    editorial se ven como una caja con borde alrededor de la imagen.

    Las tablas de verdad —las 33 de Inglés, las 16 de Matemáticas— tienen varias
    columnas y no las toca esto.
    """
    for tabla in soup.find_all("table"):
        if not _vivo(tabla):
            continue
        filas = tabla.find_all("tr")
        if not filas or any(len(f.find_all(["td", "th"], recursive=False)) > 1 for f in filas):
            continue
        for fila in filas:
            for celda in fila.find_all(["td", "th"], recursive=False):
                contenedor = soup.new_tag("p")
                for nodo in list(celda.contents):
                    contenedor.append(nodo.extract())
                tabla.insert_before(contenedor)
        tabla.decompose()


def _quitar_rastro_de_google(soup: BeautifulSoup) -> None:
    """Ni un enlace ni una imagen apuntando a los servidores de Google.

    Dos cosas distintas, el mismo motivo. Cada foto de Blogspot viene envuelta
    en un enlace a su propia versión ampliada en `googleusercontent.com`; una
    vez que la foto es nuestra, ese enlace solo sirve para mandar al lector de
    vuelta a Google. Y si un `<img>` de Google llega hasta aquí, es que la
    sustitución por `<embed>` no lo cogió: se va igual.

    Ese segundo caso es un cinturón sobre los tirantes a propósito. C108 —«las
    imágenes viven en el servidor del IES»— no debería depender de que dos
    pasos se llamen en el orden correcto: un `<img>` a Google se ve bien hoy y
    es un hueco gris el día que alguien cierre la cuenta de Blogger (A27.3).
    """
    for enlace in soup.find_all("a"):
        if not _vivo(enlace):
            continue
        destino = enlace.get("href") or ""
        if not any(dominio in destino for dominio in DOMINIOS_GOOGLE):
            continue
        if enlace.get_text(strip=True) or enlace.find(["embed", "img", "iframe"]):
            enlace.unwrap()   # tenía contenido: se queda el contenido, se va el enlace
        else:
            enlace.decompose()  # era solo el envoltorio de una foto ya traída

    for imagen in soup.find_all("img"):
        if _vivo(imagen) and any(d in (imagen.get("src") or "") for d in DOMINIOS_GOOGLE):
            imagen.decompose()


def _podar_vacios(soup: BeautifulSoup) -> None:
    """Párrafos vacíos, enlaces sin destino y cadenas de `<br>`.

    Blogspot separa con `<p><br /></p>` en lugar de con márgenes; sin podar,
    un artículo importado aparece con agujeros de tres líneas en blanco.
    """
    for enlace in soup.find_all("a"):
        if not _vivo(enlace):
            continue
        if not enlace.get("href"):
            enlace.unwrap()
        elif not enlace.get_text(strip=True) and not enlace.find(["embed", "img", "iframe"]):
            # Enlace con destino pero sin nada visible: no se puede pulsar.
            enlace.decompose()

    for etiqueta in soup.find_all(["p", "li", "h2", "h3", "h4", "h5", "h6"]):
        if not _vivo(etiqueta):
            continue
        tiene_contenido = etiqueta.find(["img", "embed", "iframe", "table"]) is not None
        if not tiene_contenido and not etiqueta.get_text(strip=True):
            etiqueta.decompose()

    # `<br><br><br>` -> un solo salto.
    for salto in soup.find_all("br"):
        if not _vivo(salto):
            continue
        siguiente = salto.next_sibling
        while siguiente is not None:
            if isinstance(siguiente, NavigableString) and not siguiente.strip():
                siguiente = siguiente.next_sibling
                continue
            if isinstance(siguiente, Tag) and siguiente.name == "br":
                a_borrar, siguiente = siguiente, siguiente.next_sibling
                a_borrar.decompose()
                continue
            break


def limpiar_cuerpo(html: str) -> str:
    """El pipeline entero, en el orden en que importa.

    Las imágenes NO se tocan aquí: eso lo hace `extraer_imagenes` antes, porque
    necesita la red para bajarlas y este módulo no la tiene.
    """
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    _quitar_basura(soup)
    _normalizar_estructura(soup)
    _limpiar_atributos(soup)
    _quitar_rastro_de_google(soup)
    _desenvolver_tablas_de_maquetacion(soup)
    _envolver_sueltos(soup)
    _podar_vacios(soup)
    salida = soup.decode()
    # Los `&nbsp;` de Google Docs se acumulan y desmaquetan el texto.
    salida = salida.replace("\xa0", " ")
    return re.sub(r"[ \t]{2,}", " ", salida).strip()


# ---------------------------------------------------------------------------
# Piezas del artículo
# ---------------------------------------------------------------------------

def slug_desde_url(url_blogspot: str) -> str:
    """`https://x.blogspot.com/2023/12/criterios-2023.html` -> `criterios-2023`.

    El permalink de Blogger es la identidad estable del post: es lo que hace
    que relanzar el comando no duplique nada.
    """
    ruta = url_blogspot.split("?")[0].split("#")[0].rstrip("/")
    ultimo = ruta.split("/")[-1]
    if ultimo.endswith(".html"):
        ultimo = ultimo[: -len(".html")]
    return slugify_simple(ultimo)[:225]


def derivar_intro(html_limpio: str, maximo: int = 250) -> str:
    """Las primeras palabras del artículo, cortadas por espacio.

    No resume, no interpreta, no llama a ningún modelo: `intro` es literalmente
    el principio del texto. Un import que "mejora" el contenido del profesorado
    es un import que miente sobre lo que trae (A27.5).
    """
    texto = BeautifulSoup(html_limpio or "", "html.parser").get_text(" ", strip=True)
    texto = re.sub(r"\s+", " ", texto).strip()
    if not texto:
        return ""
    if len(texto) <= maximo:
        return texto
    recorte = texto[: maximo - 1]
    if " " in recorte:
        recorte = recorte[: recorte.rindex(" ")]
    return recorte.rstrip(" ,;:.") + "…"
