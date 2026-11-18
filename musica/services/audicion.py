"""Fichas de audición (fase 111): generar tests audiométricos y editar ejercicios.

Una ficha es una `DictadoPage` cuyos bloques son ejercicios (`audiometrico`,
`dictado_abc`, `dictado_imagen`). Aquí vive lo que no es vista: el generador de
tests y las operaciones sobre los bloques, que trabajan con el JSON crudo del
StreamField para no perder los `id` de los bloques —son la dirección con la que
el editor de la página se refiere a cada ejercicio—.

**Las distancias son fracciones de TONO.** El generador de 2022
(`generate_audiometric_tests.py`) llamaba «4º de tono» a `2^(1/(12·4))`, que es
un cuarto de SEMITONO (25 cents). Jesús lo corrigió el 2026-11-17: la serie
empieza en el cuarto de tono, 50 cents. Una fracción 1/n de tono son 200/n
cents.
"""

import random

# (clave, cents, etiqueta). El orden es el de dificultad creciente.
DISTANCIAS = [
    ("1/4", 50.0, "¼ de tono"),
    ("1/8", 25.0, "⅛ de tono"),
    ("1/16", 12.5, "1/16 de tono"),
    ("1/24", 200 / 24, "1/24 de tono"),
    ("1/50", 4.0, "1/50 de tono"),
    ("1/100", 2.0, "1/100 de tono"),
    ("1/200", 1.0, "1/200 de tono"),
]

# Rango de la frecuencia base, el mismo del script de 2022.
F_MIN, F_MAX = 240, 600

PARES_POR_TEST = 10
MAX_TESTS_DE_GOLPE = 10


class EjercicioNoEncontrado(LookupError):
    pass


def distancia(clave):
    """`(cents, etiqueta)` de una clave de `DISTANCIAS`, o ValueError."""
    for k, cents, etiqueta in DISTANCIAS:
        if k == clave:
            return cents, etiqueta
    raise ValueError(f"Distancia desconocida: {clave!r}")


def etiqueta_de_cents(cents):
    """«¼ de tono · 50 cents» para los cents de una distancia conocida."""
    for _, c, etiqueta in DISTANCIAS:
        if abs(c - cents) < 1e-6:
            return f"{etiqueta} · {_cents(c)} cents"
    return f"{_cents(cents)} cents"


def _cents(c):
    texto = f"{c:.1f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def generar_audiometrico(cents, n=PARES_POR_TEST, rng=None):
    """El valor de un bloque `audiometrico`: n pares al azar a `cents` de distancia.

    Cada par lleva la frecuencia base (entera, entre 240 y 600 Hz) y si el
    segundo sonido sube. El segundo está a `f·2^(cents/1200)` cuando sube; cuando
    baja, el navegador toca primero el agudo y luego `f`, como el script de 2022.
    """
    if not cents or cents <= 0:
        raise ValueError("Los cents tienen que ser positivos.")
    rng = rng or random.Random()
    return {
        "titulo": "",
        "cents": float(cents),
        "pares": [
            {"f": float(rng.randint(F_MIN, F_MAX)), "sube": rng.choice([True, False])}
            for _ in range(n)
        ],
    }


def segundo_sonido(f, cents):
    """La frecuencia a `cents` por encima de `f`."""
    return f * 2 ** (cents / 1200)


# --- Operaciones sobre los bloques de una ficha ------------------------------


def _datos(ficha):
    """Lista mutable de `{type, value, id}` con el contenido de la ficha."""
    return [dict(b) for b in ficha.content.raw_data]


def _indice(datos, bloque_id):
    for i, b in enumerate(datos):
        if b.get("id") == bloque_id:
            return i
    raise EjercicioNoEncontrado(bloque_id)


def anadir(ficha, tipo, valor):
    """Añade un ejercicio al final. No guarda: eso es de `guardar`."""
    datos = _datos(ficha)
    datos.append({"type": tipo, "value": valor})
    ficha.content = datos


def reemplazar(ficha, bloque_id, valor):
    datos = _datos(ficha)
    i = _indice(datos, bloque_id)
    datos[i] = {"type": datos[i]["type"], "value": valor, "id": bloque_id}
    ficha.content = datos


def borrar(ficha, bloque_id):
    datos = _datos(ficha)
    del datos[_indice(datos, bloque_id)]
    ficha.content = datos


def mover(ficha, bloque_id, delta):
    """Sube (delta=-1) o baja (+1) un ejercicio. En los extremos no hace nada."""
    datos = _datos(ficha)
    i = _indice(datos, bloque_id)
    j = i + delta
    if 0 <= j < len(datos):
        datos[i], datos[j] = datos[j], datos[i]
        ficha.content = datos


def valor_crudo(ficha, bloque_id):
    """El valor en JSON crudo de un bloque (para modificar un campo y reemplazar)."""
    datos = _datos(ficha)
    return dict(datos[_indice(datos, bloque_id)]["value"])


def regenerar(ficha, bloque_id, rng=None):
    """Pares nuevos para un test audiométrico, con su misma distancia y título."""
    valor = valor_crudo(ficha, bloque_id)
    nuevo = generar_audiometrico(valor["cents"], len(valor.get("pares") or []) or PARES_POR_TEST, rng)
    nuevo["titulo"] = valor.get("titulo", "")
    reemplazar(ficha, bloque_id, nuevo)


def guardar(ficha, user):
    """Revisión nueva; se publica si `user` puede publicar. Devuelve si se publicó.

    Igual que el botón ✎ de las letras (`musica/letras.py`): quien solo puede
    editar deja una revisión pendiente, como en el administrador.
    """
    revision = ficha.save_revision(user=user, log_action=True)
    publicada = ficha.permissions_for_user(user).can_publish()
    if publicada:
        revision.publish(user=user)
    return publicada


def ficha_para_editar(ficha):
    """La última versión de la ficha (borrador incluido), para no pisarlo."""
    return ficha.get_latest_revision_as_object() if ficha.has_unpublished_changes else ficha
