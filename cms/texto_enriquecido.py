"""Enderezar el HTML que el editor de Wagtail no sabe abrir.

El editor convierte el HTML guardado a ContentState antes de pintarlo, y ese
conversor **afirma** que al cerrar un bloque no queda ningún estilo ni enlace
abierto (`html_to_contentstate.py`). Si queda, no avisa: revienta con un
`AssertionError` y el profesor ve un 500 al pulsar «editar».

La forma que lo provoca es siempre la misma, y viene de la importación de
Blogspot: una etiqueta de línea envolviendo un bloque.

    <strong><h2>Aviso</h2></strong>          ← estilo por fuera del bloque
    <a><p><a>…</a></p></a>                   ← enlace envolviendo un párrafo
    <b><p><embed/></p><p>…</p></b>           ← estilo sobre dos párrafos

Se arregla metiendo la etiqueta dentro del bloque en vez de fuera, que es
donde el editor la entiende. El texto no se toca.
"""

from bs4 import BeautifulSoup

# Etiquetas de línea que el conversor guarda como «estilo en curso».
ESTILOS = {"b", "strong", "i", "em", "u", "s", "strike", "sup", "sub", "code", "span"}

# Las de «entidad»: un enlace abierto al cerrar el bloque da el mismo 500 con
# otro mensaje («closing entity elements»).
ENTIDADES = {"a"}

# Lo que el conversor trata como bloque. Al cerrar cualquiera de estas, no
# puede quedar nada de lo de arriba abierto.
BLOQUES = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote", "div", "pre",
    "table", "thead", "tbody", "tr", "td", "th",
}

# Lo que vale por sí solo y no admite que lo envuelvan: un estilo alrededor de
# un embed deja el estilo abierto cuando el bloque atómico se cierra, o sea el
# mismo fallo por otra puerta.
ATOMICOS = {"embed", "img", "hr", "iframe", "video", "audio"}

_CULPABLES = list(ESTILOS | ENTIDADES)


def _envuelve_un_bloque(etiqueta) -> bool:
    """¿Esta etiqueta de línea tiene un bloque dentro?"""
    return etiqueta.find(list(BLOQUES)) is not None


def reparar(html: str) -> str:
    """Devuelve el mismo HTML con las etiquetas de línea dentro de sus bloques.

    Dos tratos distintos, y la diferencia importa:

    - **Un estilo se empuja hacia dentro**, para no perder la negrita ni el
      subrayado que alguien puso a propósito.
    - **Un enlace se desenvuelve**, porque empujarlo hacia dentro produciría un
      enlace dentro de otro enlace —estas páginas ya traen el de dentro— y eso
      no lo dibuja ningún navegador de forma predecible.

    Un bloque que contiene algo atómico (un embed, una imagen) se deja como
    está: envolverlo devolvería el fallo por la otra puerta.
    """
    if not html:
        return html

    sopa = BeautifulSoup(html, "html.parser")

    # Desenvolver cambia el árbol bajo los pies, así que se repite hasta que no
    # queda ningún culpable. El tope existe para que un HTML retorcido no deje
    # el comando dando vueltas.
    for _ in range(20):
        culpables = [t for t in sopa.find_all(_CULPABLES) if _envuelve_un_bloque(t)]
        if not culpables:
            break
        for etiqueta in culpables:
            if etiqueta.name in ENTIDADES:
                etiqueta.unwrap()
                continue
            _empujar_estilo(sopa, etiqueta)

    return str(sopa)


def _empujar_estilo(sopa, etiqueta):
    """Mete el estilo dentro de cada hijo de bloque, y luego se quita de en medio."""
    for hijo in list(etiqueta.children):
        if getattr(hijo, "name", None) not in BLOQUES:
            continue
        if hijo.find(list(ATOMICOS)) or hijo.find(list(BLOQUES)):
            # Ni lo atómico ni un bloque dentro de otro: ahí el estilo sobra.
            continue
        contenido = list(hijo.contents)
        hijo.clear()
        nuevo = sopa.new_tag(etiqueta.name, attrs=dict(etiqueta.attrs))
        for trozo in contenido:
            nuevo.append(trozo)
        hijo.append(nuevo)
    etiqueta.unwrap()


def el_editor_lo_abre(html: str) -> bool:
    """¿El editor de Wagtail puede abrir esto sin reventar?

    Se pregunta con el MISMO widget que usa la página de edición. Con un
    conversor propio, esta comprobación acabaría diciendo que sí mientras el
    editor sigue dando 500, que es exactamente lo que no puede pasar aquí.
    """
    from wagtail.admin.rich_text import get_rich_text_editor_widget

    try:
        get_rich_text_editor_widget().format_value(html or "")
    except Exception:
        return False
    return True


def texto_visible(html: str) -> str:
    """El texto sin etiquetas, para comprobar que la reparación no se come nada."""
    return " ".join(BeautifulSoup(html or "", "html.parser").get_text().split())
