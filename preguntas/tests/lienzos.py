"""Imágenes sintéticas para los tests: un aula de 640×480 con tarjetas dibujadas."""

import cv2
import numpy as np

from preguntas import aruco

# Girar k veces 90° en sentido antihorario (`np.rot90`) equivale a levantar la
# tarjeta con esta letra arriba.
LETRA_POR_GIRO = {0: "A", 1: "B", 2: "C", 3: "D"}


def lienzo(tarjetas, ancho=640, alto=480, lado=80, margen=16):
    """`tarjetas`: [(id, giros_antihorarios), …] colocadas en rejilla sobre blanco."""
    img = np.full((alto, ancho), 255, dtype=np.uint8)
    por_fila = max(1, (ancho - margen) // (lado + margen))
    for n, (id_, giros) in enumerate(tarjetas):
        fila, col = divmod(n, por_fila)
        x = margen + col * (lado + margen)
        y = margen + fila * (lado + margen)
        img[y : y + lado, x : x + lado] = np.rot90(aruco.marcador(id_, lado), giros)
    return img


def jpeg(img, calidad=70):
    ok, datos = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, calidad])
    assert ok
    return datos.tobytes()


def girado(img, grados):
    """La imagen entera girada `grados` (antihorario) sobre su centro, fondo blanco."""
    alto, ancho = img.shape[:2]
    matriz = cv2.getRotationMatrix2D((ancho / 2, alto / 2), grados, 1.0)
    return cv2.warpAffine(img, matriz, (ancho, alto), borderValue=255)
