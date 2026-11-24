"""Patrones de piano de las fichas (fases 114 y 115): leer la progresión y validar.

Un patrón de piano es un ejercicio de ficha que guarda cuatro datos y ninguna
nota: la progresión en grados, el patrón (un identificador del catálogo), la
tonalidad y el tempo. Las notas las calcula el navegador al pintar
(`static/js/src/patron_piano.js`); aquí vive lo que el servidor tiene que saber
para no guardar algo que luego no se pueda escribir en un pentagrama.

El catálogo es `musica/patrones_piano.json`, el mismo fichero que entra en el
bundle del navegador: los desplegables y la validación salen de ahí, así que un
patrón nuevo no se puede ofrecer en la página sin que el navegador lo conozca.

**A propósito estrecho:** 4/4, un acorde por compás y las tríadas de la escala
de la tonalidad. El modo lo dice la tonalidad (fase 115): en «Bm», Si menor, los
grados son los de la escala menor natural, `i ii° III iv v VI VII`.

La progresión se escribe de tres maneras y se guarda de una:

- `I V IV I`, toda en mayúsculas, o `1 5 4 1`: dice solo los grados, y el tipo
  de cada acorde lo pone el modo. En Si menor se guarda `i v iv i`.
- `I vi IV V`, con minúsculas: la caja dice el tipo de acorde y tiene que cuadrar
  con el modo. Si no cuadra se dice cuál es la buena; no se adivina, porque quien
  escribe «V» entre minúsculas en una tonalidad menor está pidiendo el V mayor,
  el de la sensible, y ese acorde todavía no está.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

RUTA_DEL_CATALOGO = Path(__file__).resolve().parent.parent / "patrones_piano.json"

MODO_DE_PARTIDA = "mayor"
# Cómo se llama la escala de cada modo en un aviso, y su grupo en un desplegable.
_ESCALA_DE = {"mayor": "mayor", "menor": "menor natural"}
_GRUPO_DE = (("mayor", "Mayores"), ("menor", "Menores"))

MAX_COMPASES = 16
TEMPO_MINIMO, TEMPO_MAXIMO, TEMPO_DE_PARTIDA = 40, 200, 80

PROGRESION_DE_PARTIDA = "I V V I"

# Lo que separa dos acordes: espacios, comas, barras de compás, guiones y
# flechas. La barra inclinada no: «V/V» es un solo acorde, y no de la escala.
_SEPARADORES = re.compile(r"[\s,;|·>→–—-]+")
# El círculo del disminuido, como lo deje el teclado.
_DISMINUIDO = re.compile(r"(°|º|o|dim)$")
_NOMBRE_DE_GRADO = ("primer", "segundo", "tercer", "cuarto", "quinto", "sexto", "séptimo")


class PatronNoValido(ValueError):
    """Lo que se ha pedido no se puede guardar. El mensaje es para quien edita."""


@lru_cache(maxsize=1)
def catalogo():
    return json.loads(RUTA_DEL_CATALOGO.read_text(encoding="utf-8"))


def patrones():
    """[(id, nombre)] en el orden del catálogo, de más fácil a más difícil."""
    return [(p["id"], p["nombre"]) for p in catalogo()["patrones"]]


def romanos(modo=MODO_DE_PARTIDA):
    """Los siete grados de un modo, con la caja que dice el tipo de cada tríada."""
    return tuple(catalogo()["modos"][modo]["grados"])


# Los de la escala mayor, que es como se llamaba esto en la fase 114.
ROMANOS = romanos()


def tonalidades(modo=None):
    """[(id, nombre)]: las mayores y después las menores, de menos a más alteraciones.

    Con `modo`, solo las suyas.
    """
    return [(t["id"], t["nombre"]) for t in catalogo()["tonalidades"] if modo in (None, t["modo"])]


def tonalidades_por_modo():
    """[("Mayores", [(id, nombre), …]), ("Menores", […])] para un desplegable con grupos."""
    return [(rotulo, tonalidades(modo)) for modo, rotulo in _GRUPO_DE]


def modo_de(tonalidad):
    """«mayor» o «menor»: lo dice la tonalidad. Si no está en el catálogo, mayor."""
    for t in catalogo()["tonalidades"]:
        if t["id"] == tonalidad:
            return t["modo"]
    return MODO_DE_PARTIDA


def nombre_del_patron(clave):
    return dict(patrones()).get(clave, "")


def nombre_de_la_tonalidad(clave):
    return dict(tonalidades()).get(clave, "")


def _tipo(romano):
    """«mayor», «menor» o «disminuido»: lo dice cómo se escribe el grado."""
    if romano.endswith("°"):
        return "disminuido"
    return "mayor" if romano.isupper() else "menor"


def _solo_grados(tokens):
    """¿Va la progresión entera en mayúsculas o en números?

    Entonces está escrita a la manera de aquí, donde «I V IV I» vale igual para
    una canción mayor que para una menor: dice los grados y nada más.
    """
    return not any(c.islower() for t in tokens for c in _DISMINUIDO.sub("", t))


def _grado(token, modo, solo_grados):
    """El grado (1-7) de un trozo de la progresión, o PatronNoValido."""
    if token.isdigit():
        if len(token) == 1 and "1" <= token <= "7":
            return int(token)
        raise PatronNoValido(f"«{token}» no es un grado: van del 1 al 7.")

    grados = romanos(modo)
    base = _DISMINUIDO.sub("", token)
    con_circulo = base != token
    for i, romano in enumerate(grados):
        limpio = romano.rstrip("°")
        if base.lower() != limpio.lower():
            continue
        # El círculo solo lo lleva el disminuido: «I°» no es un acorde de la escala.
        if con_circulo and not romano.endswith("°"):
            break
        if base == limpio or solo_grados:
            return i + 1
        # Bien escrito salvo la caja: se dice cuál es la buena, no se adivina.
        aviso = f"En una tonalidad {modo} el {_NOMBRE_DE_GRADO[i]} grado es {_tipo(romano)}: escríbelo «{romano}»."
        if modo == "menor" and base == "V":
            aviso += " El V mayor, el de la sensible, todavía no está."
        raise PatronNoValido(aviso)

    raise PatronNoValido(
        f"No entiendo «{token}». De momento valen las tríadas de la escala {_ESCALA_DE[modo]}: "
        f"{' '.join(grados)} (o los números del 1 al 7)."
    )


def leer_progresion(texto, modo=MODO_DE_PARTIDA):
    """`I V V I`, `I – vi – IV – V` o `1 5 5 1` → `[1, 5, 5, 1]`.

    Un acorde por compás. `modo` es el de la tonalidad: con él, `I V IV I` y
    `i v iv i` son los mismos grados en una menor. Lanza `PatronNoValido` con un
    mensaje que dice qué trozo no vale y por qué.
    """
    tokens = [t for t in _SEPARADORES.split((texto or "").strip()) if t]
    if not tokens:
        raise PatronNoValido("Escribe la progresión, un acorde por compás: por ejemplo, I V V I.")
    if len(tokens) > MAX_COMPASES:
        raise PatronNoValido(f"La progresión tiene {len(tokens)} compases y el máximo son {MAX_COMPASES}.")
    solo_grados = _solo_grados(tokens)
    return [_grado(t, modo, solo_grados) for t in tokens]


def escribir_progresion(grados, separador=" ", modo=MODO_DE_PARTIDA):
    """`[1, 5, 5, 1]` → `I V V I` (o `I – V – V – I` con otro separador).

    En una tonalidad menor, `[1, 5, 4, 1]` → `i v iv i`.
    """
    los_del_modo = romanos(modo)
    return separador.join(los_del_modo[g - 1] for g in grados)


def grados_de(valor):
    """Los grados de un bloque guardado, o `[]` si su progresión no se entiende."""
    valor = valor or {}
    try:
        return leer_progresion(valor.get("progresion") or "", modo_de(valor.get("tonalidad")))
    except PatronNoValido:
        return []


def _entero(valor, defecto, minimo, maximo):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return defecto
    return max(minimo, min(n, maximo))


def valor_de_patron(datos, anterior=None):
    """El valor de un bloque `patron_piano` a partir de un formulario.

    Lo que el formulario no trae se queda como estaba en `anterior`. Lanza
    `PatronNoValido` si la progresión, el patrón o la tonalidad no valen: no se
    guarda nada a medias.
    """
    anterior = anterior or {}

    patron = datos.get("patron") or anterior.get("patron") or patrones()[0][0]
    if not nombre_del_patron(patron):
        raise PatronNoValido(f"No hay ningún patrón «{patron}» en el catálogo.")

    tonalidad = datos.get("tonalidad") or anterior.get("tonalidad") or tonalidades()[0][0]
    if not nombre_de_la_tonalidad(tonalidad):
        raise PatronNoValido(f"No hay ninguna tonalidad «{tonalidad}» en el catálogo.")
    modo = modo_de(tonalidad)

    progresion = datos.get("progresion", anterior.get("progresion") or PROGRESION_DE_PARTIDA)
    # Pasar un patrón de mayor a menor sin tocar la progresión conserva los
    # grados: lo que había en la casilla lo escribió la app, con la caja del
    # modo anterior, y nadie ha pedido con ella un acorde distinto.
    intacta = (progresion or "").strip() == (anterior.get("progresion") or "").strip()
    de_antes = grados_de(anterior) if intacta and modo != modo_de(anterior.get("tonalidad")) else []
    grados = de_antes or leer_progresion(progresion, modo)

    return {
        "titulo": (datos.get("titulo", anterior.get("titulo", "")) or "").strip()[:120],
        "progresion": escribir_progresion(grados, modo=modo),
        "patron": patron,
        "tonalidad": tonalidad,
        "tempo": _entero(
            datos.get("tempo"), anterior.get("tempo") or TEMPO_DE_PARTIDA, TEMPO_MINIMO, TEMPO_MAXIMO
        ),
    }


def titulo_de(valor):
    """El nombre del ejercicio: su título, o «I – V – V – I»."""
    valor = valor or {}
    if valor.get("titulo"):
        return valor["titulo"]
    grados = grados_de(valor)
    if not grados:
        return "Patrón de piano"
    return escribir_progresion(grados, " – ", modo_de(valor.get("tonalidad")))


def progresion_legible(valor):
    """«i – v – iv – i», con la caja del modo de su tonalidad, o vacío si no se entiende."""
    valor = valor or {}
    return escribir_progresion(grados_de(valor), " – ", modo_de(valor.get("tonalidad")))


def para_el_navegador(valor):
    """Lo que `patron_piano.js` necesita de un bloque guardado."""
    valor = valor or {}
    return {
        "grados": grados_de(valor),
        "patron": valor.get("patron") or "",
        "tonalidad": valor.get("tonalidad") or "",
        "tempo": _entero(valor.get("tempo"), TEMPO_DE_PARTIDA, TEMPO_MINIMO, TEMPO_MAXIMO),
    }
