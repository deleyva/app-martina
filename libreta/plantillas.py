"""Las hojas A4 para imprimir, dibujadas en código.

Las plantillas del CMS son para proyectar: A5, con cabecera y número de página
dentro del propio PDF y pocos elementos por hoja. Para fotocopiar hace falta
otra cosa: A4 denso, limpio, sin ningún número dentro (el único número es el
del pie que pone la libreta). Como son geometría —líneas, rejillas, teclas—,
se dibujan con ReportLab y salen vectoriales. La excepción son las claves del
pentagrama de piano, que van como imagen recortada del material del año
pasado (`static/libreta/claves-piano.png`).

Cada hoja es una función `dibujar(lienzo)` registrada en `HOJAS` por clave;
la clave es lo que guarda `Elemento.plantilla`. Añadir una hoja nueva es
añadir una función y una fila.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

ANCHO, ALTO = A4
MARGEN = 15 * mm
BANDA_PIE = 12 * mm  # la misma que reserva `pdf.py` para el rótulo
X0, X1 = MARGEN, ANCHO - MARGEN
Y0, Y1 = BANDA_PIE + MARGEN, ALTO - MARGEN
ANCHO_UTIL, ALTO_UTIL = X1 - X0, Y1 - Y0
GRIS = 0.6

CLAVES_PIANO = Path(__file__).parent / "static" / "libreta" / "claves-piano.png"
# En la imagen de las claves, la primera línea de la clave de sol está en la
# fila 40 y la última de la de fa en la 286 (medido sobre el PNG original).
CLAVES_LINEA_ALTA, CLAVES_LINEA_BAJA, CLAVES_ALTO, CLAVES_ANCHO = 40, 286, 320, 96


def _filas(n, alto_elemento, y_arriba=Y1, y_abajo=Y0):
    """Las `n` coordenadas `y` (borde superior) para repartir elementos de
    `alto_elemento` en vertical con el mismo hueco entre ellos."""
    hueco = (y_arriba - y_abajo - n * alto_elemento) / (n - 1) if n > 1 else 0
    return [y_arriba - i * (alto_elemento + hueco) for i in range(n)]


def _columnas(n, ancho_elemento):
    hueco = (ANCHO_UTIL - n * ancho_elemento) / (n - 1) if n > 1 else 0
    return [X0 + i * (ancho_elemento + hueco) for i in range(n)]


def _lineas(lienzo, x0, x1, y_arriba, n, paso, grosor=0.6):  # noqa: PLR0913
    lienzo.setLineWidth(grosor)
    for i in range(n):
        y = y_arriba - i * paso
        lienzo.line(x0, y, x1, y)


# --- Pentagramas y tablaturas ------------------------------------------------


def pentagrama(lienzo):
    """12 pentagramas, espacio de 2 mm entre líneas (8 mm de alto)."""
    paso = 2 * mm
    for y in _filas(12, 4 * paso):
        _lineas(lienzo, X0, X1, y, 5, paso)


def _tablatura(lienzo, cuerdas, n):
    paso = 2.6 * mm
    alto = (cuerdas - 1) * paso
    for y in _filas(n, alto):
        _lineas(lienzo, X0, X1, y, cuerdas, paso, grosor=0.5)
        lienzo.setFont("Helvetica", 7.5)
        centro = y - alto / 2
        for i, letra in enumerate("TAB"):
            lienzo.drawCentredString(
                X0 + 2.2 * mm,
                centro + (1 - i) * 2.6 * mm - 0.9 * mm,
                letra,
            )


def tablatura_guitarra(lienzo):
    _tablatura(lienzo, 6, 10)


def tablatura_bajo(lienzo):
    _tablatura(lienzo, 4, 12)


def tablatura_ukelele(lienzo):
    _tablatura(lienzo, 4, 12)


def pentagrama_piano(lienzo):
    """6 pentagramas de piano. Las líneas son vectoriales; la llave y las dos
    claves son la imagen, colocada para que sus líneas caigan sobre estas."""
    claves = ImageReader(str(CLAVES_PIANO))
    paso = 2 * mm
    # De la primera línea de sol a la última de fa, en puntos, con el hueco
    # entre pentagramas igual al que trae la imagen (fila 108 → 218).
    alto_sistema = (CLAVES_LINEA_BAJA - CLAVES_LINEA_ALTA) / 17 * paso
    escala = alto_sistema / (CLAVES_LINEA_BAJA - CLAVES_LINEA_ALTA)
    ancho_img, alto_img = CLAVES_ANCHO * escala, CLAVES_ALTO * escala
    for y in _filas(6, alto_sistema):
        y_img_arriba = y + CLAVES_LINEA_ALTA * escala
        lienzo.drawImage(
            claves,
            X0,
            y_img_arriba - alto_img,
            ancho_img,
            alto_img,
            mask="auto",
        )
        x_lineas = X0 + ancho_img - 1
        _lineas(lienzo, x_lineas, X1, y, 5, paso)
        _lineas(lienzo, x_lineas, X1, y - alto_sistema + 4 * paso, 5, paso)
        lienzo.setLineWidth(0.6)
        lienzo.line(X1, y, X1, y - alto_sistema)


# --- Teclados -----------------------------------------------------------------


def _teclado(lienzo, x, y_arriba, ancho, alto):
    """Dos octavas (14 teclas blancas), como el diagrama del año pasado."""
    blancas = 14
    ancho_tecla = ancho / blancas
    lienzo.setLineWidth(0.5)
    lienzo.setStrokeGray(0)
    lienzo.rect(x, y_arriba - alto, ancho, alto)
    for i in range(1, blancas):
        lienzo.line(x + i * ancho_tecla, y_arriba - alto, x + i * ancho_tecla, y_arriba)
    # Negras tras las blancas 0,1 · 3,4,5 · 7,8 · 10,11,12
    # (do re · fa sol la · do re · fa sol la).
    lienzo.setFillGray(GRIS)
    ancho_negra, alto_negra = ancho_tecla * 0.6, alto * 0.62
    for i in (0, 1, 3, 4, 5, 7, 8, 10, 11, 12):
        cx = x + (i + 1) * ancho_tecla
        lienzo.rect(
            cx - ancho_negra / 2,
            y_arriba - alto_negra,
            ancho_negra,
            alto_negra,
            stroke=0,
            fill=1,
        )
    lienzo.setFillGray(0)


def teclados(lienzo):
    """24 teclados de dos octavas, en 3 columnas."""
    columnas, filas = 3, 8
    ancho = 54 * mm
    alto = ancho * 214 / 608  # la proporción del diagrama original
    for y in _filas(filas, alto):
        for x in _columnas(columnas, ancho):
            _teclado(lienzo, x, y, ancho, alto)


# --- Rejillas de acordes ---------------------------------------------------------


def _rejilla_vertical(lienzo, x, y_arriba, cuerdas, trastes, ancho, alto):  # noqa: PLR0913
    """Cejilla arriba (barra gruesa), cuerdas en vertical."""
    lienzo.setLineWidth(0.5)
    paso_x, paso_y = ancho / (cuerdas - 1), alto / trastes
    for i in range(cuerdas):
        lienzo.line(x + i * paso_x, y_arriba - alto, x + i * paso_x, y_arriba)
    for j in range(trastes + 1):
        lienzo.line(x, y_arriba - j * paso_y, x + ancho, y_arriba - j * paso_y)
    lienzo.setLineWidth(2.2)
    lienzo.line(x, y_arriba, x + ancho, y_arriba)


def _rejilla_horizontal(lienzo, x, y_arriba, cuerdas, trastes, ancho, alto):  # noqa: PLR0913
    """Cejilla a la izquierda, cuerdas en horizontal."""
    lienzo.setLineWidth(0.5)
    paso_x, paso_y = ancho / trastes, alto / (cuerdas - 1)
    for i in range(cuerdas):
        lienzo.line(x, y_arriba - i * paso_y, x + ancho, y_arriba - i * paso_y)
    for j in range(trastes + 1):
        lienzo.line(x + j * paso_x, y_arriba - alto, x + j * paso_x, y_arriba)
    lienzo.setLineWidth(2.2)
    lienzo.line(x, y_arriba - alto, x, y_arriba)


def _hoja_de_rejillas(lienzo, columnas, filas, forma):
    """`forma` = (cuerdas, trastes, ancho, alto, horizontal)."""
    cuerdas, trastes, ancho, alto, horizontal = forma
    dibujo = _rejilla_horizontal if horizontal else _rejilla_vertical
    for y in _filas(filas, alto):
        for x in _columnas(columnas, ancho):
            dibujo(lienzo, x, y, cuerdas, trastes, ancho, alto)


def acordes_guitarra_v(lienzo):
    """30 rejillas de 6 cuerdas por 5 trastes."""
    _hoja_de_rejillas(lienzo, 5, 6, (6, 5, 24 * mm, 30 * mm, False))


def acordes_guitarra_h(lienzo):
    """24 rejillas apaisadas de 6 cuerdas por 5 trastes."""
    _hoja_de_rejillas(lienzo, 3, 8, (6, 5, 42 * mm, 22 * mm, True))


def acordes_ukelele_v(lienzo):
    """42 rejillas de 4 cuerdas por 5 trastes."""
    _hoja_de_rejillas(lienzo, 7, 6, (4, 5, 15 * mm, 30 * mm, False))


def acordes_ukelele_h(lienzo):
    """36 rejillas apaisadas de 4 cuerdas por 5 trastes."""
    _hoja_de_rejillas(lienzo, 4, 9, (4, 5, 34 * mm, 14 * mm, True))


# --- Registro -------------------------------------------------------------------

HOJAS = {
    "pentagrama": ("Pentagrama", pentagrama),
    "pentagrama_piano": ("Pentagrama de piano", pentagrama_piano),
    "teclados": ("Teclados", teclados),
    "tablatura_guitarra": ("Tablatura de guitarra", tablatura_guitarra),
    "tablatura_bajo": ("Tablatura de bajo", tablatura_bajo),
    "tablatura_ukelele": ("Tablatura de ukelele", tablatura_ukelele),
    "acordes_guitarra_v": ("Acordes de guitarra", acordes_guitarra_v),
    "acordes_guitarra_h": ("Acordes de guitarra (horizontal)", acordes_guitarra_h),
    "acordes_ukelele_v": ("Acordes de ukelele", acordes_ukelele_v),
    "acordes_ukelele_h": ("Acordes de ukelele (horizontal)", acordes_ukelele_h),
}


def titulo(clave: str) -> str:
    return HOJAS[clave][0]


def dibujar(clave: str, lienzo) -> None:
    HOJAS[clave][1](lienzo)


def disponibles() -> list[dict]:
    return [
        {"tipo": "plantilla", "clave": clave, "titulo": nombre}
        for clave, (nombre, _) in HOJAS.items()
    ]
