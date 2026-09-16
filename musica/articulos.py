"""Lectura de un borrador de artículo: del Markdown a lo que traga Wagtail.

Sin Django a propósito. Lo usan dos consumidores con necesidades distintas: el
comando de gestión, que escribe directo en la base de datos, y el publicador
por API, que corre fuera del contenedor y solo tiene la biblioteca estándar.
Tener el conversor en un sitio es lo que evita que los dos caminos se
desincronicen, que es exactamente como aparecieron dos publicadores.

El conversor entiende solo lo que usa `docs/PLANTILLA_ARTICULO_CANCION.md`
—encabezados, párrafos, listas, negrita, cursiva, imágenes, enlaces de YouTube
y el bloque de escucha guiada—, porque el destino es un `RichTextField`, que no
admite `<pre>` ni `<table>`.
"""

import html
import re

CABECERA_ES = "## Versión en castellano"
CABECERA_EN = "## English version"
# Dentro de cada lengua, la entradilla es el primer apartado y va al campo
# `intro`; el cuerpo empieza en el siguiente.
APARTADO_ENTRADILLA = ("Entradilla", "Intro line")


def _frontmatter(texto):
    """`---\\nclave: valor\\n---` al principio del fichero."""
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if not m:
        raise ValueError("El borrador no empieza por un bloque `---` de datos")
    datos = {}
    for linea in m.group(1).splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            datos[clave.strip()] = valor.strip()
    return datos, texto[m.end():]


def _seccion(texto, cabecera, siguiente=None):
    """El trozo entre una cabecera `##` y la siguiente."""
    inicio = texto.find(cabecera)
    if inicio == -1:
        return ""
    inicio += len(cabecera)
    fin = texto.find(siguiente, inicio) if siguiente else -1
    return texto[inicio:fin if fin != -1 else len(texto)].strip()


def _en_linea(texto):
    """Negrita, cursiva y escapado. El orden importa: primero se escapa."""
    texto = html.escape(texto, quote=False)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"(?<![\*\w])\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", texto)
    texto = re.sub(r"`([^`\n]+?)`", r"\1", texto)
    return texto


def _bloque_escucha(lineas):
    """El bloque cercado de la Escucha guiada, a lista.

    Una línea nueva empieza entrada nueva; las sangradas continúan la anterior,
    porque en el Markdown están partidas para que quepan a 79 columnas.
    """
    entradas = []
    for linea in lineas:
        if not linea.strip():
            continue
        if linea.startswith((" ", "\t")) and entradas:
            entradas[-1] += " " + linea.strip()
        else:
            entradas.append(linea.strip())
    items = []
    for entrada in entradas:
        m = re.match(r"^(⟨\?:\?\?⟩|\d+:\d\d)\s+(.*)$", entrada)
        if m:
            items.append(f"<li><b>{_en_linea(m.group(1))}</b> {_en_linea(m.group(2))}</li>")
        else:
            items.append(f"<li>{_en_linea(entrada)}</li>")
    return "<ul>" + "".join(items) + "</ul>"


# Un enlace de YouTube en un recurso no se queda en enlace: se convierte en el
# reproductor. Es lo que pide la plantilla —videoclip primero, después un
# tutorial por instrumento— y lo que hacían los artículos buenos que ya había.
YOUTUBE = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?[^\s`)\]]*v=[\w-]+|youtu\.be/[\w-]+)")
# ![alt](url "Fuente: quién y con qué licencia")
IMAGEN_MD = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)')


def _embed_video(url):
    return f'<embed embedtype="media" url="{html.escape(url, quote=True)}"/>'


def _embed_imagen(id_imagen, alt):
    return (
        f'<embed embedtype="image" id="{id_imagen}" '
        f'alt="{html.escape(alt, quote=True)}" format="fullwidth"/>'
    )


def markdown_a_richtext(texto, resolver_imagen=None):
    """El subconjunto que usa la plantilla. `###` pasa a `<h2>`: en el artículo
    esos apartados son los de primer nivel; el `##` es la lengua, que no se
    pinta.

    `resolver_imagen(url, alt, fuente) -> id` decide qué hacer con una imagen
    del borrador. Cada consumidor la sube a su manera —desde disco o por el
    API—, y esta función solo sabe dónde va el hueco. Sin resolver, una imagen
    en el borrador es un error y no un silencio: publicar el artículo sin ella
    es justo el fallo que se quiere evitar.
    """
    salida = []
    parrafo = []
    lista = []
    cercado = None

    def cerrar_parrafo():
        if parrafo:
            salida.append(f"<p>{_en_linea(' '.join(parrafo).strip())}</p>")
            parrafo.clear()

    def cerrar_lista():
        if lista:
            salida.append("<ul>" + "".join(f"<li>{_en_linea(x)}</li>" for x in lista) + "</ul>")
            lista.clear()

    for linea in texto.splitlines():
        if linea.startswith("```"):
            if cercado is None:
                cerrar_parrafo()
                cerrar_lista()
                cercado = []
            else:
                salida.append(_bloque_escucha(cercado))
                cercado = None
            continue
        if cercado is not None:
            cercado.append(linea)
            continue

        if not linea.strip():
            cerrar_parrafo()
            cerrar_lista()
            continue
        if linea.startswith("### "):
            cerrar_parrafo()
            cerrar_lista()
            salida.append(f"<h2>{_en_linea(linea[4:].strip())}</h2>")
            continue
        imagen = IMAGEN_MD.search(linea)
        if imagen:
            cerrar_parrafo()
            cerrar_lista()
            if resolver_imagen is None:
                raise ValueError(
                    f"El borrador trae una imagen y nadie sabe subirla: {imagen.group(2)}"
                )
            alt, url, fuente = imagen.group(1), imagen.group(2), imagen.group(3) or ""
            salida.append(_embed_imagen(resolver_imagen(url, alt, fuente), alt))
            if fuente:
                salida.append(f"<p><i>{_en_linea(fuente)}</i></p>")
            continue
        video = YOUTUBE.search(linea)
        if video:
            cerrar_parrafo()
            cerrar_lista()
            # Lo que va antes de la URL es la etiqueta del recurso («Videoclip
            # oficial», «Tutorial de guitarra»), y se conserva como título.
            etiqueta = linea[: video.start()].strip()
            etiqueta = re.sub(r"^\d+\.\s*|^-\s*", "", etiqueta).strip(" —-–:`")
            if etiqueta:
                salida.append(f"<p>{_en_linea(etiqueta)}</p>")
            salida.append(_embed_video(video.group(0)))
            continue
        if linea.startswith("> "):
            continue  # notas para el profesor, no van a la página
        if re.match(r"^\d+\.\s", linea):
            cerrar_parrafo()
            lista.append(re.sub(r"^\d+\.\s", "", linea).strip())
            continue
        if linea.startswith("- "):
            cerrar_parrafo()
            lista.append(linea[2:].strip())
            continue

        if linea.startswith("|") or linea.startswith("---"):
            continue  # la tabla de la ficha es para ti, no para el alumnado
        parrafo.append(linea.strip())

    cerrar_parrafo()
    cerrar_lista()
    return "".join(salida)


def partir_lengua(bloque, resolver_imagen=None):
    """(entradilla, cuerpo) de un bloque de una sola lengua."""
    apartados = re.split(r"(?m)^### ", bloque)
    entradilla, cuerpo = "", []
    for apartado in apartados:
        if not apartado.strip():
            continue
        titulo, _, resto = apartado.partition("\n")
        if titulo.strip() in APARTADO_ENTRADILLA:
            entradilla = " ".join(l.strip() for l in resto.strip().splitlines() if l.strip())
        else:
            cuerpo.append("### " + apartado.rstrip())
    return entradilla, markdown_a_richtext("\n".join(cuerpo), resolver_imagen)
