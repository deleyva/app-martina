"""Lectura de tarjetas de respuesta con marcadores ArUco (fase 76·0).

Cada tarjeta lleva un marcador con un id; la respuesta es la orientación con
que el alumno la levanta. La tarjeta impresa lleva A arriba, B a la derecha,
C abajo y D a la izquierda: para responder B se gira hasta que la B quede
arriba, o sea 90° en sentido antihorario; C es media vuelta; D, 90° horario.

`detectMarkers` devuelve las cuatro esquinas de cada marcador EMPEZANDO por la
que es «arriba a la izquierda» en el dibujo canónico, en sentido horario. La
respuesta se lee de dónde ha ido a parar esa primera esquina:

    arriba-izquierda → A      abajo-izquierda → B
    abajo-derecha    → C      arriba-derecha  → D

Si la tarjeta está girada cerca de 45° no se decide: `letra` sale `None`.
Mejor no contar una respuesta que contar la equivocada.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

# 4×4: los menos bits y por tanto las celdas más grandes para un tamaño dado,
# que es lo que importa a cinco metros. 100 ids bastan de sobra para un grupo.
DICCIONARIO_ID = cv2.aruco.DICT_4X4_100
LETRAS = "ABCD"
# Grados a cada lado de las diagonales (0°, ±90°, 180° desde el centro) en los
# que la orientación se considera ambigua.
MARGEN_AMBIGUO = 15.0


def diccionario():
    return cv2.aruco.getPredefinedDictionary(DICCIONARIO_ID)


def marcador(id_: int, lado_px: int = 600) -> np.ndarray:
    """La imagen (gris, uint8) del marcador `id_`, sin margen blanco alrededor."""
    if not 0 <= id_ < 100:
        raise ValueError(f"El id {id_} no cabe en el diccionario (0–99)")
    return cv2.aruco.generateImageMarker(diccionario(), int(id_), int(lado_px))


def letra_de(esquinas: np.ndarray) -> str | None:
    """La respuesta que indica la orientación del marcador, o None si es ambigua.

    `esquinas`: 4×2 en píxeles de imagen (y hacia abajo), en el orden que da
    OpenCV: la primera es la esquina canónica «arriba-izquierda».
    """
    pts = np.asarray(esquinas, dtype=float).reshape(4, 2)
    dx, dy = pts[0] - pts.mean(axis=0)
    angulo = math.degrees(math.atan2(dy, dx))
    distancia_a_diagonal = abs(((angulo + 45.0) % 90.0) - 45.0)
    if distancia_a_diagonal < MARGEN_AMBIGUO:
        return None
    if dx < 0 and dy < 0:
        return "A"
    if dx < 0 and dy > 0:
        return "B"
    if dx > 0 and dy > 0:
        return "C"
    return "D"


def detectar_en_imagen(gris: np.ndarray) -> list[dict]:
    """Todos los marcadores de una imagen en gris: id, letra y centro, por id."""
    detector = cv2.aruco.ArucoDetector(diccionario(), cv2.aruco.DetectorParameters())
    esquinas, ids, _rechazados = detector.detectMarkers(gris)
    if ids is None:
        return []
    marcadores = []
    for cs, id_ in zip(esquinas, ids.flatten()):
        pts = cs.reshape(4, 2)
        centro = pts.mean(axis=0)
        marcadores.append(
            {
                "id": int(id_),
                "letra": letra_de(pts),
                "centro": [round(float(centro[0]), 1), round(float(centro[1]), 1)],
            }
        )
    return sorted(marcadores, key=lambda m: m["id"])


def detectar(datos: bytes) -> list[dict]:
    """Decodifica un JPEG/PNG en memoria y lee sus marcadores. Nada toca el disco."""
    arr = np.frombuffer(datos, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("No es una imagen legible")
    return detectar_en_imagen(a_gris(img))


def a_gris(img: np.ndarray) -> np.ndarray:
    """Gris de 8 bits. Un PNG con transparencia se compone sobre BLANCO antes.

    Gotcha medido (2026-10-15): `IMREAD_GRAYSCALE` tira el canal alfa y lo
    transparente queda NEGRO; una página de PDF rasterizada así es un rectángulo
    negro con cuadrados blancos y no se lee ni un marcador.
    """
    if img.dtype != np.uint8:
        img = cv2.convertScaleAbs(img, alpha=255.0 / max(int(img.max()), 1))
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        alfa = img[:, :, 3:4].astype(np.float32) / 255.0
        color = img[:, :, :3].astype(np.float32) * alfa + 255.0 * (1.0 - alfa)
        img = color.astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
