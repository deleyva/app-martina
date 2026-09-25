"""Monta el PDF de la libreta y la hoja de pedido. Solo pypdf + ReportLab.

**Todas las páginas de salida son A4 vertical.** Cuatro de las nueve plantillas
del CMS son A5 y una es apaisada (medido 2026-09-25): se escalan al A4 y las
apaisadas se giran 90°, así la fotocopiadora recibe hojas iguales. El pie de
cada hoja lleva el rótulo «<título> · hoja i de n» y el número de página; para
que no pise el contenido, el contenido se encaja en la hoja menos una banda
inferior reservada al pie.

No se rasteriza nada: los PDF del CMS entran como vectores y salen igual.
"""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from pypdf import PageObject
from pypdf import PdfReader
from pypdf import PdfWriter
from pypdf import Transformation
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame
from reportlab.platypus import Paragraph
from reportlab.platypus import Table
from reportlab.platypus import TableStyle

ANCHO, ALTO = A4
BANDA_PIE = 12 * mm  # reservada al rótulo y al número
MARGEN = 15 * mm
CENTRO = "IES Martina Bescós"
FUENTE = "Helvetica"
FUENTE_NEGRITA = "Helvetica-Bold"


# --- Geometría ---------------------------------------------------------------


def _a4(origen: PageObject) -> PageObject:
    """Una página cualquiera, encajada en un A4 vertical sobre la banda del pie.

    Las apaisadas se giran en el sentido de las agujas del reloj: así un
    diagrama de acordes horizontal queda con la cejilla arriba y se lee como
    uno vertical, sin girar la hoja.
    """
    origen.transfer_rotation_to_content()
    caja = origen.mediabox
    ancho, alto = float(caja.width), float(caja.height)
    hueco_ancho, hueco_alto = ANCHO, ALTO - BANDA_PIE
    hoja = PageObject.create_blank_page(width=ANCHO, height=ALTO)
    mover_al_origen = Transformation().translate(-float(caja.left), -float(caja.bottom))
    if ancho > alto:
        escala = min(hueco_ancho / alto, hueco_alto / ancho)
        # rotate(-90): (x, y) -> (y, -x); la hoja queda en y ∈ [-ancho, 0] y se sube.
        t = (
            mover_al_origen.rotate(-90)
            .translate(0, ancho)
            .scale(escala, escala)
            .translate(
                (hueco_ancho - alto * escala) / 2,
                BANDA_PIE + (hueco_alto - ancho * escala) / 2,
            )
        )
    else:
        escala = min(hueco_ancho / ancho, hueco_alto / alto)
        t = mover_al_origen.scale(escala, escala).translate(
            (hueco_ancho - ancho * escala) / 2,
            BANDA_PIE + (hueco_alto - alto * escala) / 2,
        )
    hoja.merge_transformed_page(origen, t)
    return hoja


def _pagina_de(dibujar) -> PageObject:
    """Una página A4 dibujada con ReportLab, como `PageObject` de pypdf."""
    buffer = BytesIO()
    lienzo = canvas.Canvas(buffer, pagesize=A4)
    dibujar(lienzo)
    lienzo.showPage()
    lienzo.save()
    return PdfReader(BytesIO(buffer.getvalue())).pages[0]


def _en_blanco() -> PageObject:
    return PageObject.create_blank_page(width=ANCHO, height=ALTO)


def _titulo_de_seccion(lienzo, titulo):
    lienzo.setFont(FUENTE_NEGRITA, 13)
    lienzo.drawString(MARGEN, ALTO - MARGEN, titulo)


def _pagina_imagen(titulo: str, ruta: str) -> PageObject:
    def dibujar(lienzo):
        _titulo_de_seccion(lienzo, titulo)
        imagen = ImageReader(ruta)
        ancho, alto = imagen.getSize()
        hueco_ancho = ANCHO - 2 * MARGEN
        hueco_alto = ALTO - 2 * MARGEN - BANDA_PIE - 8 * mm
        escala = min(hueco_ancho / ancho, hueco_alto / alto)
        w, h = ancho * escala, alto * escala
        x = (ANCHO - w) / 2
        y = (
            ALTO - MARGEN - 8 * mm - h
        )  # pegada al título, no centrada: se escribe debajo
        lienzo.drawImage(imagen, x, y, w, h, mask="auto")

    return _pagina_de(dibujar)


def _pagina_texto(titulo: str, texto: str) -> PageObject:
    def dibujar(lienzo):
        _titulo_de_seccion(lienzo, titulo)
        estilo = ParagraphStyle(
            "cuerpo",
            parent=getSampleStyleSheet()["Normal"],
            fontName=FUENTE,
            fontSize=11,
            leading=15,
        )
        parrafos = [
            Paragraph(escape(p).replace("\n", "<br/>"), estilo)
            for p in texto.split("\n\n")
            if p.strip()
        ]
        marco = Frame(
            MARGEN,
            BANDA_PIE + MARGEN,
            ANCHO - 2 * MARGEN,
            ALTO - 2 * MARGEN - BANDA_PIE - 8 * mm,
            showBoundary=0,
        )
        marco.addFromList(parrafos, lienzo)

    return _pagina_de(dibujar)


def _pie(rotulo: str | None, numero: int) -> PageObject:
    def dibujar(lienzo):
        lienzo.setFont(FUENTE, 8)
        lienzo.setFillColor(colors.HexColor("#444444"))
        if rotulo:
            lienzo.drawString(MARGEN, 6 * mm, rotulo)
        lienzo.drawCentredString(ANCHO / 2, 6 * mm, str(numero))

    return _pagina_de(dibujar)


def _portada(libreta) -> PageObject:
    def dibujar(lienzo):
        y = ALTO * 0.68
        lienzo.setFont(FUENTE_NEGRITA, 30)
        lienzo.drawCentredString(ANCHO / 2, y, libreta.titulo)
        lienzo.setLineWidth(0.8)
        lienzo.line(ANCHO * 0.2, y - 12 * mm, ANCHO * 0.8, y - 12 * mm)
        lienzo.setFont(FUENTE, 18)
        if libreta.subtitulo:
            lienzo.drawCentredString(ANCHO / 2, y - 26 * mm, libreta.subtitulo)
        lienzo.setFont(FUENTE, 13)
        lienzo.drawCentredString(ANCHO / 2, y - 38 * mm, CENTRO)
        lienzo.setFont(FUENTE, 12)
        for i, etiqueta in enumerate(("Nombre:", "Clase:", "Curso:")):
            fila = ALTO * 0.36 - i * 16 * mm
            lienzo.drawString(MARGEN + 10 * mm, fila, etiqueta)
            lienzo.line(
                MARGEN + 32 * mm,
                fila - 1.5 * mm,
                ANCHO - MARGEN - 10 * mm,
                fila - 1.5 * mm,
            )

    return _pagina_de(dibujar)


def _indice(secciones) -> PageObject:
    """`secciones`: [(título, primera, última)] con la numeración real."""

    def dibujar(lienzo):
        lienzo.setFont(FUENTE_NEGRITA, 20)
        lienzo.drawCentredString(ANCHO / 2, ALTO - MARGEN - 10 * mm, "Índice")
        lienzo.setLineWidth(0.6)
        lienzo.line(
            MARGEN,
            ALTO - MARGEN - 15 * mm,
            ANCHO - MARGEN,
            ALTO - MARGEN - 15 * mm,
        )
        y = ALTO - MARGEN - 28 * mm
        for titulo, primera, ultima in secciones:
            rango = str(primera) if primera == ultima else f"{primera} – {ultima}"  # noqa: RUF001
            lienzo.setFont(FUENTE, 11)
            lienzo.drawString(MARGEN, y, titulo)
            lienzo.drawRightString(ANCHO - MARGEN, y, rango)
            x0 = MARGEN + lienzo.stringWidth(titulo, FUENTE, 11) + 3 * mm
            x1 = ANCHO - MARGEN - lienzo.stringWidth(rango, FUENTE, 11) - 3 * mm
            if x1 > x0:
                lienzo.setDash(1, 2)
                lienzo.line(x0, y - 1 * mm, x1, y - 1 * mm)
                lienzo.setDash()
            y -= 9 * mm
            if y < MARGEN + BANDA_PIE:
                break  # más de ~70 elementos no caben; la libreta real tiene una docena

    return _pagina_de(dibujar)


# --- Montaje -----------------------------------------------------------------


def _paginas_por_copia(elemento) -> list[PageObject]:
    if elemento.tipo == elemento.PDF:
        with elemento.documento.file.open("rb") as fichero:
            lector = PdfReader(BytesIO(fichero.read()))
            return [_a4(pagina) for pagina in lector.pages]
    if elemento.tipo == elemento.IMAGEN:
        return [_pagina_imagen(elemento.titulo, _ruta_de_la_imagen(elemento.imagen))]
    if elemento.tipo == elemento.PLANTILLA:
        from . import plantillas

        return [
            _pagina_de(lambda lienzo: plantillas.dibujar(elemento.plantilla, lienzo)),
        ]
    return [_pagina_texto(elemento.titulo, elemento.texto)]


def _ruta_de_la_imagen(imagen) -> str:
    """Una versión a tamaño de impresión; el original si la rendition falla."""
    try:
        return imagen.get_rendition("max-2400x2400").file.path
    except Exception:  # noqa: BLE001 — el original siempre vale
        return imagen.file.path


def _plan(libreta):
    """Qué páginas van, en qué orden y con qué rótulo, antes de escribir nada.

    Devuelve `(paginas, secciones)`: `paginas` es [(PageObject, rótulo | None)]
    con el frente incluido y los rellenos en blanco (rótulo `None`), y
    `secciones` [(título, primera, última)] sobre la numeración real, que es lo
    que el índice necesita ANTES de dibujarse.
    """
    rellenar = libreta.hoja_nueva_por_seccion
    cuerpo, secciones = [], []
    numero = libreta.primera_pagina
    frente = int(libreta.portada) + int(libreta.indice)
    if rellenar and frente % 2:
        frente += 1
    numero += frente

    for elemento in libreta.elementos_ordenados():
        base = _paginas_por_copia(elemento)
        total = len(base) * elemento.copias
        primera = numero
        i = 0
        for _ in range(elemento.copias):
            for pagina in base:
                i += 1
                cuerpo.append((pagina, f"{elemento.titulo} · hoja {i} de {total}"))
        secciones.append((elemento.titulo, primera, primera + total - 1))
        numero += total
        if rellenar and total % 2:
            cuerpo.append((_en_blanco(), None))
            numero += 1

    paginas = []
    if libreta.portada:
        paginas.append((_portada(libreta), None))
    if libreta.indice:
        paginas.append((_indice(secciones), None))
    if rellenar and len(paginas) % 2:
        paginas.append((_en_blanco(), None))
    return paginas + cuerpo, secciones


def construir(libreta) -> bytes:
    paginas, _ = _plan(libreta)
    escritor = PdfWriter()
    numero = libreta.primera_pagina
    for pagina, rotulo in paginas:
        nueva = escritor.add_page(pagina)
        if rotulo:
            nueva.merge_page(_pie(rotulo, numero))
        numero += 1
    escritor.add_metadata(
        {"/Title": f"{libreta.titulo} {libreta.subtitulo}".strip(), "/Creator": CENTRO},
    )
    buffer = BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


def pedido(libreta) -> bytes:
    """La hoja que se entrega en la fotocopiadora junto al PDF. Va aparte a
    propósito: dentro del PDF se imprimiría cien veces."""
    paginas, secciones = _plan(libreta)
    elementos = list(libreta.elementos_ordenados())
    total = libreta.total_hojas()
    # Lo que sale por la impresora, con portada, índice y rellenos: es lo que
    # la fotocopiadora cobra, y no coincide con la suma de los elementos.
    paginas_del_pdf = len(paginas)
    hojas_fisicas = -(-paginas_del_pdf // 2)

    def dibujar(lienzo):
        lienzo.setFont(FUENTE_NEGRITA, 18)
        lienzo.drawString(MARGEN, ALTO - MARGEN - 6 * mm, "Pedido de fotocopias")
        lienzo.setFont(FUENTE, 12)
        lienzo.drawString(
            MARGEN,
            ALTO - MARGEN - 14 * mm,
            f"{libreta.titulo} {libreta.subtitulo}".strip() + f" · {CENTRO}",
        )
        lienzo.setFont(FUENTE, 10)
        lienzo.drawString(
            MARGEN,
            ALTO - MARGEN - 21 * mm,
            timezone.localdate().strftime("%d/%m/%Y"),
        )

        filas = [["Elemento", "Copias", "Páginas", "Páginas del PDF"]]
        for elemento, (_, primera, ultima) in zip(elementos, secciones, strict=True):
            rango = str(primera) if primera == ultima else f"{primera} – {ultima}"  # noqa: RUF001
            filas.append(
                [elemento.titulo, str(elemento.copias), str(elemento.paginas()), rango],
            )
        filas.append(["Total", "", str(total), ""])
        tabla = Table(
            filas,
            colWidths=[ANCHO - 2 * MARGEN - 85 * mm, 22 * mm, 25 * mm, 38 * mm],
        )
        tabla.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), FUENTE_NEGRITA, 10),
                    ("FONT", (0, 1), (-1, -1), FUENTE, 10),
                    ("FONT", (0, -1), (-1, -1), FUENTE_NEGRITA, 10),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
                    ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ],
            ),
        )
        ancho_tabla, alto_tabla = tabla.wrapOn(lienzo, ANCHO - 2 * MARGEN, ALTO)
        tabla.drawOn(lienzo, MARGEN, ALTO - MARGEN - 30 * mm - alto_tabla)

        y = ALTO - MARGEN - 42 * mm - alto_tabla
        lienzo.setFont(FUENTE_NEGRITA, 11)
        lienzo.drawString(MARGEN, y, "Instrucciones de impresión")
        lienzo.setFont(FUENTE, 11)
        lineas = [
            f"Fichero: {libreta.nombre_de_fichero()}",
            "Papel: A4, en vertical.",
            "A doble cara, volteando por el lado largo.",
            f"El PDF tiene {paginas_del_pdf} páginas: "
            f"{hojas_fisicas} hojas por libreta.",
            "Ejemplares: ________",
        ]
        for i, linea in enumerate(lineas, start=1):
            lienzo.drawString(MARGEN, y - i * 7 * mm, linea)

    escritor = PdfWriter()
    escritor.add_page(_pagina_de(dibujar))
    buffer = BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()
