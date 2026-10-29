"""Fotos sintéticas de folios para los tests de la fase 84: nada de fotos de alumnos.

Un dictado rítmico dibujado (cabecera impresa, figuras a bolígrafo azul,
correcciones en rojo y una marca azul en cada esquina), puesto sobre una mesa
de madera oscura, en perspectiva y con una sombra que oscurece la izquierda.
"""

import cv2
import numpy as np

# BGR
PAPEL = (222, 232, 240)  # blanco cálido, como bajo una bombilla
AZUL = (150, 60, 20)
ROJO = (40, 40, 200)
NEGRO = (30, 30, 30)
LAPIZ = (175, 178, 182)
# Dónde va el nombre a lápiz, en fracción del folio: x de 0.1 a 0.48, y en torno a 0.89.
ZONA_LAPIZ = (0.1, 0.48, 0.87, 0.91)
MESA = (45, 70, 105)

# Las cuatro marcas de esquina, en fracción del folio: Anti-B.
ESQUINAS = [(0.04, 0.03), (0.96, 0.03), (0.96, 0.97), (0.04, 0.97)]


def folio(ancho=1000, alto=1414):
    """Un A4 vertical escrito, sin mesa: lo que daría un escáner."""
    img = np.full((alto, ancho, 3), PAPEL, dtype=np.uint8)
    cv2.putText(img, "DICTADO RITMICO", (int(ancho * 0.1), int(alto * 0.08)), cv2.FONT_HERSHEY_SIMPLEX, 1.4, NEGRO, 3)
    for fila in range(6):
        y = int(alto * (0.18 + fila * 0.12))
        cv2.line(img, (int(ancho * 0.08), y), (int(ancho * 0.92), y), NEGRO, 2)
        for n in range(8):
            x = int(ancho * (0.12 + n * 0.1))
            cv2.ellipse(img, (x, y - 14), (13, 9), -20, 0, 360, AZUL, -1)
            cv2.line(img, (x + 11, y - 16), (x + 11, y - 80), AZUL, 3)
            if n % 2 == 0:
                cv2.line(img, (x + 11, y - 80), (x + 11 + int(ancho * 0.1), y - 80), AZUL, 7)
        # Una corrección en rojo por fila.
        cv2.circle(img, (int(ancho * (0.25 + 0.08 * fila)), y - 40), 34, ROJO, 4)
    cv2.putText(img, "7", (int(ancho * 0.8), int(alto * 0.93)), cv2.FONT_HERSHEY_SIMPLEX, 3, ROJO, 8)
    # El nombre, a lápiz flojo.
    puntos = [(int(ancho * (0.1 + 0.02 * n)), int(alto * (0.89 + 0.008 * ((-1) ** n)))) for n in range(20)]
    cv2.polylines(img, [np.array(puntos, np.int32)], False, LAPIZ, 2)
    lado = max(12, ancho // 50)
    for fx, fy in ESQUINAS:
        cx, cy = int(fx * ancho), int(fy * alto)
        cv2.rectangle(img, (cx - lado // 2, cy - lado // 2), (cx + lado // 2, cy + lado // 2), AZUL, -1)
    return img


def sombra(img, desde=0.62):
    """Oscurece de izquierda (×`desde`) a derecha (×1), como una luz de lado."""
    alto, ancho = img.shape[:2]
    factor = np.linspace(desde, 1.0, ancho, dtype=np.float32)[None, :, None]
    return np.clip(img.astype(np.float32) * factor, 0, 255).astype(np.uint8)


def ruido(img, sigma=4, semilla=0):
    generador = np.random.default_rng(semilla)
    return np.clip(img.astype(np.float32) + generador.normal(0, sigma, img.shape), 0, 255).astype(np.uint8)


def sobre_la_mesa(papel, ancho=3024, alto=4032, esquinas=None):
    """El folio fotografiado en vertical sobre una mesa, en perspectiva y con sombra."""
    generador = np.random.default_rng(1)
    mesa = np.full((alto, ancho, 3), MESA, dtype=np.float32)
    # Vetas de madera.
    vetas = (np.sin(np.linspace(0, 60, ancho))[None, :, None] * 12).astype(np.float32)
    mesa = np.clip(mesa + vetas + generador.normal(0, 6, (alto, ancho, 3)), 0, 255).astype(np.uint8)
    if esquinas is None:
        esquinas = [(560, 520), (2420, 640), (2560, 3520), (430, 3400)]
    h, w = papel.shape[:2]
    origen = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    matriz = cv2.getPerspectiveTransform(origen, np.array(esquinas, dtype=np.float32))
    puesto = cv2.warpPerspective(papel, matriz, (ancho, alto))
    mascara = cv2.warpPerspective(np.full((h, w), 255, np.uint8), matriz, (ancho, alto))
    foto = np.where(mascara[..., None] > 127, puesto, mesa)
    return ruido(sombra(foto))


def no_es_un_papel(ancho=2000, alto=1500):
    """Algo oscuro y de colores: un instrumento, un mural. No hay folio que buscar."""
    generador = np.random.default_rng(2)
    img = np.zeros((alto, ancho, 3), dtype=np.uint8)
    for _ in range(40):
        color = tuple(int(c) for c in generador.integers(20, 200, 3))
        centro = (int(generador.integers(0, ancho)), int(generador.integers(0, alto)))
        cv2.circle(img, centro, int(generador.integers(60, 300)), color, -1)
    return cv2.GaussianBlur(img, (31, 31), 0)


def jpeg(img, calidad=90):
    ok, datos = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, calidad])
    assert ok
    return datos.tobytes()


def descodificar(webp: bytes):
    return cv2.imdecode(np.frombuffer(webp, np.uint8), cv2.IMREAD_COLOR)


def rojos(img):
    """Píxeles donde manda el rojo: la tinta de corrección."""
    b, g, r = (img[..., i].astype(int) for i in range(3))
    return int(((r - np.maximum(g, b)) > 60).sum())


def azules(img):
    b, g, r = (img[..., i].astype(int) for i in range(3))
    return int(((b - np.maximum(g, r)) > 40).sum())
