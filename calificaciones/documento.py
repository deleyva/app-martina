"""La foto de un folio, convertida en fotocopia en color (fase 84).

Tres pasos, en este orden, todos de array a array para que los tests midan la
imagen sin Huey ni base de datos:

1. **Enderezar el folio.** Se busca el cuadrilátero del papel y se lleva a un
   rectángulo: fuera la mesa y fuera la perspectiva. La hoja queda entera, con
   sus márgenes (decisión de Jesús, 2026-10-29: «solo el folio»). Si no hay un
   folio claro —un escaneo que ya es la hoja, una foto que no es un papel— no
   se recorta nada. Mejor una foto con mesa que una foto sin la mitad del
   dictado.
2. **Fotocopia en color.** Se estima el fondo (el papel con su sombra) y se
   divide por él: el papel queda blanco aunque la luz cayera de lado, y la
   tinta conserva su color, porque cada canal se divide por su propio fondo.
   Solo si la imagen es un papel; lo demás no se toca.
3. **Reducir.** Lado largo a 1600 px y WebP: se lee bien en el móvil y pesa
   unas decenas de kilobytes en vez de tres megas.
"""

from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps

LADO_MAXIMO = 1600
CALIDAD_WEBP = 60
# Se trabaja a esta resolución y no a la de la cámara (4032 px): sobra para
# enderezar con detalle y cuesta la tercera parte.
LADO_DE_TRABAJO = 2400
# Para buscar el folio basta una miniatura.
LADO_DE_BUSQUEDA = 640
# Fracción del área que tiene que ocupar el folio para creérselo. Por debajo
# es más fácil que sea un libro o una ventana; por encima, la foto ya es la
# hoja y no hay nada que quitar.
AREA_MINIMA, AREA_MAXIMA = 0.08, 0.97
# Lo que se recorta hacia dentro tras enderezar, para que el borde del
# contorno no deje una raya de mesa. Un folio escrito a mano deja más de un
# centímetro de margen (un 5 % del ancho de un A4), así que no muerde nada.
RECORTE_INTERIOR = 0.012


def abrir(datos: bytes) -> np.ndarray:
    """La imagen en BGR, girada según su EXIF y a lo sumo de `LADO_DE_TRABAJO`.

    Lanza si no es una imagen o si es una animación. Lo transparente se pinta
    de blanco y los 16 bits se bajan a 8: con `convert("RGB")` a secas, un PNG
    de fondo transparente salía negro entero y uno de 16 bits blanco entero, y
    la tarea habría borrado el original de una fotocopia vacía.
    """
    imagen = Image.open(BytesIO(datos))
    if getattr(imagen, "n_frames", 1) > 1:
        raise ValueError("Es una animación: se deja como está")
    # Un JPEG muy grande se descodifica ya reducido: menos memoria en el consumidor.
    imagen.draft("RGB", (LADO_DE_TRABAJO, LADO_DE_TRABAJO))
    imagen = ImageOps.exif_transpose(imagen)
    if imagen.mode in ("I", "I;16", "I;16B", "I;16L", "I;16N", "F"):
        valores = np.asarray(imagen).astype(np.float32)
        if valores.max() > 255:
            valores = valores / 257
        imagen = Image.fromarray(np.clip(valores, 0, 255).astype(np.uint8), "L")
    if "A" in imagen.getbands() or "transparency" in imagen.info:
        rgba = imagen.convert("RGBA")
        imagen = Image.alpha_composite(Image.new("RGBA", rgba.size, "white"), rgba)
    imagen = imagen.convert("RGB")
    imagen.thumbnail((LADO_DE_TRABAJO, LADO_DE_TRABAJO), Image.Resampling.LANCZOS)
    return cv2.cvtColor(np.asarray(imagen), cv2.COLOR_RGB2BGR)


def guardar_webp(img: np.ndarray, calidad: int = CALIDAD_WEBP) -> bytes:
    salida = BytesIO()
    Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).save(salida, "WEBP", quality=calidad, method=6)
    return salida.getvalue()


def reducir(img: np.ndarray, lado: int) -> np.ndarray:
    alto, ancho = img.shape[:2]
    escala = lado / max(alto, ancho)
    if escala >= 1:
        return img
    # Nunca a cero: una tira de 1×5000 haría reventar a `resize`.
    nuevo = (max(1, round(ancho * escala)), max(1, round(alto * escala)))
    return cv2.resize(img, nuevo, interpolation=cv2.INTER_AREA)


# ----- 1. el folio ------------------------------------------------------------------


def ordenar_esquinas(puntos: np.ndarray) -> np.ndarray:
    """Arriba-izquierda, arriba-derecha, abajo-derecha, abajo-izquierda."""
    puntos = puntos.reshape(4, 2).astype(np.float32)
    suma = puntos.sum(axis=1)
    resta = np.diff(puntos, axis=1).ravel()  # y - x
    return np.array(
        [puntos[suma.argmin()], puntos[resta.argmin()], puntos[suma.argmax()], puntos[resta.argmax()]],
        dtype=np.float32,
    )


def _claro(img: np.ndarray) -> np.ndarray:
    """Lo que parece papel: claro y poco saturado. Una mesa de madera es oscura o saturada."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return (hsv[..., 2] > 120) & (hsv[..., 1] < 80)


def _es_un_folio(cuadrilatero: np.ndarray, claro: np.ndarray) -> bool:
    if not cv2.isContourConvex(cuadrilatero.reshape(4, 1, 2).astype(np.int32)):
        return False
    area = cv2.contourArea(cuadrilatero)
    if not AREA_MINIMA * claro.size <= area <= AREA_MAXIMA * claro.size:
        return False
    # Ángulos de folio fotografiado, no de rombo.
    for i in range(4):
        a, b, c = cuadrilatero[i - 1], cuadrilatero[i], cuadrilatero[(i + 1) % 4]
        u, v = a - b, c - b
        coseno = float(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9))
        if abs(coseno) > 0.5:  # fuera de 60°-120°
            return False
    # Papel dentro y no papel fuera. Sin la segunda condición, el hueco entre
    # dos renglones de un escaneo pasa por folio y se recorta media hoja; sin
    # la primera, cualquier rectángulo de una foto que no es un papel.
    dentro = np.zeros(claro.shape, np.uint8)
    cv2.fillConvexPoly(dentro, cuadrilatero.astype(np.int32), 1)
    dentro = dentro.astype(bool)
    return claro[dentro].mean() > 0.6 and claro[~dentro].mean() < 0.4


def _cuadrilateros(mascara: np.ndarray):
    """Los contornos grandes de la máscara que se dejan aproximar por cuatro lados."""
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contorno in sorted(contornos, key=cv2.contourArea, reverse=True)[:5]:
        perimetro = cv2.arcLength(contorno, True)
        envolvente = cv2.convexHull(contorno)
        # Una esquina doblada o un dedo encima suman vértices: se va subiendo
        # la tolerancia hasta que quedan cuatro.
        for tolerancia in (0.02, 0.03, 0.04, 0.05):
            aproximado = cv2.approxPolyDP(envolvente, tolerancia * perimetro, True)
            if len(aproximado) == 4:
                # Si para quedarse en cuatro lados hay que cortar una cuña del
                # contorno, no es el folio entero (una esquina se sale del
                # encuadre) y recortar por ahí se lleva la cabecera, que es
                # donde va el nombre. Un folio entero da 0,99; con la esquina
                # fuera, 0,94 o menos (medido en la revisión del 2026-10-29).
                if cv2.contourArea(aproximado) >= 0.97 * cv2.contourArea(envolvente):
                    yield ordenar_esquinas(aproximado)
                break


def buscar_folio(img: np.ndarray) -> np.ndarray | None:
    """Las cuatro esquinas del folio en coordenadas de `img`, o `None` si no hay uno claro.

    Dos máscaras, por orden: el papel como lo más claro de la foto (Otsu),
    que sigue el borde de verdad, y los bordes (Canny), que sirven cuando la
    mesa no es mucho más oscura pero salen un poco por fuera al dilatarlos.
    Gana el folio más grande de la primera máscara que dé alguno.
    """
    miniatura = reducir(img, LADO_DE_BUSQUEDA)
    escala = img.shape[1] / miniatura.shape[1]
    claro_hsv = _claro(miniatura)
    gris = cv2.GaussianBlur(cv2.cvtColor(miniatura, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    nucleo = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))

    _, claro = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Cerrar rellena lo escrito, que si no deja agujeros en el papel.
    claro = cv2.morphologyEx(claro, cv2.MORPH_CLOSE, nucleo, iterations=2)

    mediana = float(np.median(gris))
    bordes = cv2.Canny(gris, int(max(0, 0.66 * mediana)), int(min(255, 1.33 * mediana)))
    bordes = cv2.dilate(bordes, nucleo)

    for mascara in (claro, bordes):
        candidatos = [c for c in _cuadrilateros(mascara) if _es_un_folio(c, claro_hsv)]
        if candidatos:
            return max(candidatos, key=cv2.contourArea) * escala
    return None


def enderezar(img: np.ndarray, esquinas: np.ndarray) -> np.ndarray:
    ai, ad, bd, bi = esquinas
    # La media de los lados opuestos y no el mayor: en perspectiva el borde
    # cercano sale más largo y el lejano más corto, y la media se acerca más
    # a la proporción del papel.
    ancho = round((np.linalg.norm(ad - ai) + np.linalg.norm(bd - bi)) / 2)
    alto = round((np.linalg.norm(bi - ai) + np.linalg.norm(bd - ad)) / 2)
    destino = np.array([[0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]], dtype=np.float32)
    matriz = cv2.getPerspectiveTransform(esquinas.astype(np.float32), destino)
    recto = cv2.warpPerspective(img, matriz, (ancho, alto), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    dx, dy = round(ancho * RECORTE_INTERIOR), round(alto * RECORTE_INTERIOR)
    return recto[dy : alto - dy, dx : ancho - dx]


# ----- 2. la fotocopia --------------------------------------------------------------


def es_papel(img: np.ndarray) -> bool:
    """Si la mayor parte es clara y poco saturada: un folio, aunque esté lleno de tinta."""
    return float(_claro(reducir(img, LADO_DE_BUSQUEDA)).mean()) > 0.5


def fotocopia(img: np.ndarray) -> np.ndarray:
    """Papel blanco y uniforme, tinta oscura y con su color."""
    alto, ancho = img.shape[:2]
    # El fondo se estima a un cuarto de tamaño: un trazo de bolígrafo o una
    # cabeza de nota desaparecen al dilatar y la sombra, que es suave, no.
    pequeno = cv2.resize(img, (max(1, ancho // 4), max(1, alto // 4)), interpolation=cv2.INTER_AREA)
    fondo = cv2.dilate(pequeno, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    fondo = cv2.medianBlur(fondo, 9)
    fondo = cv2.resize(fondo, (ancho, alto), interpolation=cv2.INTER_LINEAR)
    plano = cv2.divide(img, fondo, scale=255)
    # Niveles: lo casi blanco pasa a blanco y la tinta se oscurece un poco.
    # Sin pasarse: los dictados se escriben a lápiz, y un blanco más bajo o
    # una curva más fuerte borran el trazo flojo.
    negro, blanco = 50, 235
    tabla = np.clip((np.arange(256) - negro) / (blanco - negro), 0, 1) ** 1.25 * 255
    return cv2.LUT(plano, tabla.astype(np.uint8))


# ----- todo junto -------------------------------------------------------------------


def procesar(datos: bytes) -> tuple[bytes, dict]:
    """El WebP de la fotocopia y lo que se hizo, para el registro.

    Lanza si el resultado sale liso cuando la foto no lo era: la tarea
    conserva entonces el original, que es lo único que se puede perder.
    """
    img = abrir(datos)
    detalle = float(cv2.cvtColor(reducir(img, LADO_DE_BUSQUEDA), cv2.COLOR_BGR2GRAY).std())
    esquinas = buscar_folio(img)
    if esquinas is not None:
        img = enderezar(img, esquinas)
    papel = esquinas is not None or es_papel(img)
    img = reducir(img, LADO_MAXIMO)
    if papel:
        img = fotocopia(img)
    if detalle > 8 and float(cv2.cvtColor(reducir(img, LADO_DE_BUSQUEDA), cv2.COLOR_BGR2GRAY).std()) < 2:
        raise ValueError("La fotocopia ha salido lisa: se conserva el original")
    webp = guardar_webp(img)
    return webp, {"folio": esquinas is not None, "papel": papel, "ancho": img.shape[1], "alto": img.shape[0]}
