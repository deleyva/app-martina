import numpy as np
import pytest

from preguntas import aruco

from .lienzos import LETRA_POR_GIRO, girado, jpeg, lienzo

SEIS = [(1, 0), (7, 1), (13, 2), (42, 3), (77, 0), (99, 1)]


def test_seis_tarjetas_se_leen_con_su_id_y_su_letra():
    leidas = aruco.detectar(jpeg(lienzo(SEIS)))
    assert [(m["id"], m["letra"]) for m in leidas] == sorted(
        (id_, LETRA_POR_GIRO[g]) for id_, g in SEIS
    )


def test_una_imagen_sin_tarjetas_da_lista_vacia_y_no_error():
    assert aruco.detectar(jpeg(lienzo([]))) == []


def test_unos_bytes_que_no_son_imagen_se_rechazan():
    with pytest.raises(ValueError, match="legible"):
        aruco.detectar(b"esto no es un jpeg")


@pytest.mark.parametrize("id_", [0, 1, 50, 99])
def test_cada_id_vuelve_como_el_mismo_id(id_):
    [m] = aruco.detectar_en_imagen(lienzo([(id_, 0)]))
    assert m["id"] == id_ and m["letra"] == "A"


def test_un_id_fuera_del_diccionario_no_se_puede_dibujar():
    with pytest.raises(ValueError):
        aruco.marcador(100)


@pytest.mark.parametrize("giros", [1, 2, 3])
def test_girar_la_imagen_entera_avanza_todas_las_letras(giros):
    """Universal: girar el aula k cuartos antihorarios mueve cada letra k puestos en A→B→C→D."""
    base = lienzo(SEIS, ancho=480, alto=480)
    antes = {m["id"]: m["letra"] for m in aruco.detectar_en_imagen(base)}
    despues = {m["id"]: m["letra"] for m in aruco.detectar_en_imagen(np.rot90(base, giros))}
    assert antes.keys() == despues.keys() == {id_ for id_, _ in SEIS}
    for id_, letra in antes.items():
        assert despues[id_] == aruco.LETRAS[(aruco.LETRAS.index(letra) + giros) % 4]


@pytest.mark.parametrize("grados", [20, -20, 110, 200, -70])
def test_una_tarjeta_algo_torcida_se_lee_igual(grados):
    """Hasta 25° de inclinación la letra no cambia."""
    base = lienzo([(5, 0)], ancho=400, alto=400, lado=120, margen=140)
    [recta] = aruco.detectar_en_imagen(base)
    [torcida] = aruco.detectar_en_imagen(girado(base, grados))
    esperada = aruco.LETRAS[(aruco.LETRAS.index(recta["letra"]) + round(grados / 90)) % 4]
    assert torcida["id"] == 5 and torcida["letra"] == esperada


@pytest.mark.parametrize("grados", [45, -45, 135, 40, 50])
def test_una_tarjeta_a_45_grados_es_ambigua_y_no_se_cuenta(grados):
    base = lienzo([(5, 0)], ancho=400, alto=400, lado=120, margen=140)
    [m] = aruco.detectar_en_imagen(girado(base, grados))
    assert m["id"] == 5 and m["letra"] is None


def test_la_letra_sale_de_la_primera_esquina():
    cuadrado = np.array([[10, 10], [20, 10], [20, 20], [10, 20]], dtype=float)
    assert aruco.letra_de(cuadrado) == "A"
    assert aruco.letra_de(np.roll(cuadrado, -1, axis=0)) == "D"  # arriba-derecha primero
    assert aruco.letra_de(np.roll(cuadrado, -2, axis=0)) == "C"
    assert aruco.letra_de(np.roll(cuadrado, -3, axis=0)) == "B"


def test_un_png_transparente_se_lee_sobre_blanco_no_sobre_negro():
    """Gotcha: sin componer el alfa, lo transparente es negro y no se lee nada."""
    import cv2

    gris = lienzo([(9, 1), (21, 3)])
    bgra = cv2.cvtColor(gris, cv2.COLOR_GRAY2BGRA)
    bgra[:, :, 3] = np.where(gris < 128, 255, 0).astype(np.uint8)  # solo lo negro es opaco
    ok, png = cv2.imencode(".png", bgra)
    assert ok
    assert [(m["id"], m["letra"]) for m in aruco.detectar(png.tobytes())] == [(9, "B"), (21, "D")]


def test_un_jpeg_en_color_tambien_se_lee():
    import cv2

    color = cv2.cvtColor(lienzo([(4, 2)]), cv2.COLOR_GRAY2BGR)
    color[:, :, 0] = np.minimum(color[:, :, 0] + 40, 255)  # tinte azul como una foto de aula
    [m] = aruco.detectar(jpeg(color))
    assert (m["id"], m["letra"]) == (4, "C")
