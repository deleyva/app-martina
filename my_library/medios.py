"""Qué clase de medio es un objeto. Un solo sitio, para los cuatro que preguntan.

**Por qué existe.** Esta pregunta —«¿esto es un PDF, un audio, un vídeo, un
recorte, una tablatura o un enlace?»— estaba contestada cuatro veces:
`LibraryItem.get_documents`, `render_item_content`, `class_session_item_viewer`
y el visor de la biblioteca de grupo. Divergieron, y de la peor manera posible:
en silencio, porque el síntoma no es una excepción sino una pantalla que dice
«No se encontró contenido para visualizar».

Dos agujeros medidos el 2026-09-22, los dos del mismo tipo:

- Un `.gp` no encajaba en ninguna rama de las vistas de `clases`, así que la
  tablatura de una canción no se veía en clase. `study_item_content.html` ya
  tenía escrita la rama que la pinta, esperando una clave `gp_files` que esas
  vistas no crean nunca: código muerto desde el día que se escribió.
- Un `EnlaceExterno` no encajaba en la de `my_library`, que a su vez pinta una
  clave `enlaces` que `get_documents` tampoco produce jamás.

**El dict sale SIEMPRE completo.** En una plantilla de Django, una clave que
falta y una clave vacía se comportan igual, y esa es exactamente la razón por la
que los dos fallos pudieron vivir meses sin que nadie los viera. Con todas las
claves presentes, un tipo sin clasificar es una lista vacía que se puede
inspeccionar, no una ausencia indistinguible.

**Las páginas de Wagtail no se clasifican aquí.** `ScorePage` y `RecursoPage` no
son un medio: son un contenedor del que hay que sacar bloques del StreamField, a
veces filtrando uno concreto por pk. Eso vive en la vista que lo necesita y solo
existe una vez, así que no tiene el problema que este módulo viene a resolver.
"""

AUDIO = (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")

# Los cinco que Wagtail tiene permitidos en `WAGTAILDOCS_EXTENSIONS`. Se
# renderizan con alphaTab, no con el visor de PDF.
GUITAR_PRO = (".gp", ".gp3", ".gp4", ".gp5", ".gpx")

CLAVES = (
    "pdfs",
    "images",
    "audios",
    "embeds",
    "recortes",
    "gp_files",
    "enlaces",
    "external_links",
)

# `enlaceexterno` y `externalresource` son dos modelos distintos con dos visores
# distintos, y por eso son dos claves. El primero es material con licencia que
# vive fuera (Blink Learning); el segundo, un enlace con icono y descripción.
POR_MODELO = {
    "image": "images",
    "embed": "embeds",
    "recorte": "recortes",
    "enlaceexterno": "enlaces",
    "externalresource": "external_links",
}


def vacio():
    """El dict con todas las claves y nada dentro."""
    return {clave: [] for clave in CLAVES}


def clave_de(objeto, modelo):
    """En qué cajón va este objeto, o `None` si no es un medio que sepamos pintar."""
    if modelo == "document":
        fichero = getattr(objeto, "file", None)
        nombre = (getattr(fichero, "name", "") or "").lower()
        if nombre.endswith(AUDIO):
            return "audios"
        if nombre.endswith(GUITAR_PRO):
            return "gp_files"
        # El defecto es PDF y no «nada», que es lo que hacían las vistas de
        # `clases`. Un documento con extensión rara se abre con el visor de PDF,
        # que como mucho enseña un error legible; descartarlo deja la pantalla
        # en blanco sin decir por qué.
        return "pdfs"

    return POR_MODELO.get(modelo)


def clasificar(objeto, modelo=None):
    """`{clave: [...]}` con TODAS las claves y el objeto en la que le toca.

    `modelo` es el nombre en minúsculas del modelo, que es lo que trae
    `item.content_type.model` y lo que ya tiene cargado casi todo el que llama.
    Si no se pasa, se deduce de la clase.
    """
    documentos = vacio()
    if objeto is None:
        return documentos

    if modelo is None:
        modelo = objeto.__class__.__name__.lower()

    clave = clave_de(objeto, modelo)
    if clave:
        documentos[clave].append(objeto)
    return documentos
