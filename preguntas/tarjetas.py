"""PDF de tarjetas de respuesta (fase 76·0): dos por A4, marcador de 10×10 cm.

Cada tarjeta: el marcador en el centro, las letras A/B/C/D alrededor giradas de
modo que la letra que quede ARRIBA se lea derecha, el número grande en una
esquina y el nombre en pequeño. El blanco del papel alrededor del marcador es
la zona de silencio que ArUco necesita: no se dibuja nada a menos de 4 mm.
"""

from __future__ import annotations

import io

from PIL import Image
from reportlab.lib.colors import black, grey
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from . import aruco

ANCHO, ALTO = A4
LADO_MARCADOR = 100 * mm
SEPARACION_LETRA = 5 * mm
TAMANO_LETRA = 12 * mm
PIXELES_MARCADOR = 1200  # 300 ppp a 10 cm: los bordes salen nítidos al imprimir


def pdf_tarjetas(tarjetas: list[dict]) -> bytes:
    """`tarjetas`: [{"id": 7, "numero": 7, "nombre": "…"}, …]. Dos por página."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Tarjetas de respuesta")
    for i, tarjeta in enumerate(tarjetas):
        if i and i % 2 == 0:
            c.showPage()
        arriba = i % 2 == 0
        y0 = ALTO / 2 if arriba else 0
        _dibujar_tarjeta(c, tarjeta, 0, y0, ANCHO, ALTO / 2)
        if arriba:
            c.setDash(3, 3)
            c.setStrokeColor(grey)
            c.line(0, ALTO / 2, ANCHO, ALTO / 2)
            c.setDash()
    c.showPage()
    c.save()
    return buf.getvalue()


def _dibujar_tarjeta(c, tarjeta, x0, y0, ancho, alto):
    cx, cy = x0 + ancho / 2, y0 + alto / 2
    lado = LADO_MARCADOR
    imagen = ImageReader(Image.fromarray(aruco.marcador(tarjeta["id"], PIXELES_MARCADOR)))
    c.drawImage(imagen, cx - lado / 2, cy - lado / 2, lado, lado)

    c.setFillColor(black)
    c.setFont("Helvetica-Bold", TAMANO_LETRA)
    distancia = lado / 2 + SEPARACION_LETRA + TAMANO_LETRA * 0.35
    # Letra, posición, giro. El giro deja cada letra derecha cuando SU lado
    # queda arriba: B (derecha) se gira −90° porque la tarjeta se girará +90°.
    for letra, (lx, ly), giro in (
        ("A", (cx, cy + distancia), 0),
        ("B", (cx + distancia, cy), -90),
        ("C", (cx, cy - distancia), 180),
        ("D", (cx - distancia, cy), 90),
    ):
        c.saveState()
        c.translate(lx, ly)
        c.rotate(giro)
        c.drawCentredString(0, -TAMANO_LETRA * 0.35, letra)
        c.restoreState()

    c.setFont("Helvetica-Bold", 20 * mm)
    c.drawString(x0 + 12 * mm, y0 + alto - 30 * mm, str(tarjeta["numero"]))
    c.setFont("Helvetica", 9)
    c.setFillColor(grey)
    c.drawString(x0 + 12 * mm, y0 + alto - 36 * mm, str(tarjeta.get("nombre", ""))[:40])
    c.drawRightString(x0 + ancho - 12 * mm, y0 + 8 * mm, "Levanta la tarjeta con tu respuesta arriba")
