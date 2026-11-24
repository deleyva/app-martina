"""Patrones de piano de las fichas (fase 114): leer la progresión y validar.

Un patrón de piano es un ejercicio de ficha que guarda cuatro datos y ninguna
nota: la progresión en grados, el patrón (un identificador del catálogo), la
tonalidad y el tempo. Las notas las calcula el navegador al pintar
(`static/js/src/patron_piano.js`); aquí vive lo que el servidor tiene que saber
para no guardar algo que luego no se pueda escribir en un pentagrama.

El catálogo es `musica/patrones_piano.json`, el mismo fichero que entra en el
bundle del navegador: los desplegables y la validación salen de ahí, así que un
patrón nuevo no se puede ofrecer en la página sin que el navegador lo conozca.

**Primer corte, a propósito estrecho:** 4/4, un acorde por compás y tríadas de
la escala mayor. La progresión se escribe `I V V I`, `I – vi – IV – V` o
`1 5 5 1`, y se guarda siempre de la primera forma.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

RUTA_DEL_CATALOGO = Path(__file__).resolve().parent.parent / "patrones_piano.json"

# Los siete grados de la escala mayor, con la caja que dice su modo.
ROMANOS = ("I", "ii", "iii", "IV", "V", "vi", "vii°")

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


def tonalidades():
    """[(id, nombre)] de menos a más alteraciones."""
    return [(t["id"], t["nombre"]) for t in catalogo()["tonalidades"]]


def nombre_del_patron(clave):
    return dict(patrones()).get(clave, "")


def nombre_de_la_tonalidad(clave):
    return dict(tonalidades()).get(clave, "")


def _grado(token):
    """El grado (1-7) de un trozo de la progresión, o PatronNoValido."""
    if token.isdigit():
        if len(token) == 1 and "1" <= token <= "7":
            return int(token)
        raise PatronNoValido(f"«{token}» no es un grado: van del 1 al 7.")

    base = _DISMINUIDO.sub("", token)
    # El círculo solo lo lleva el séptimo: «I°» no es un acorde de la escala.
    cabe = lambda romano: base == token or romano.endswith("°")  # noqa: E731
    for i, romano in enumerate(ROMANOS):
        if base == romano.rstrip("°") and cabe(romano):
            return i + 1

    # Bien escrito salvo la caja: se dice cuál es la buena, no se adivina. En
    # modo menor «i» será otro acorde, y callarlo ahora sería mentir después.
    for i, romano in enumerate(ROMANOS):
        limpio = romano.rstrip("°")
        if base.lower() == limpio.lower() and cabe(romano):
            modo = "disminuido" if romano.endswith("°") else ("mayor" if limpio.isupper() else "menor")
            raise PatronNoValido(
                f"En una tonalidad mayor el {_NOMBRE_DE_GRADO[i]} grado es {modo}: escríbelo «{romano}»."
            )

    raise PatronNoValido(
        f"No entiendo «{token}». De momento valen las tríadas de la escala mayor: "
        f"{' '.join(ROMANOS)} (o los números del 1 al 7)."
    )


def leer_progresion(texto):
    """`I V V I`, `I – vi – IV – V` o `1 5 5 1` → `[1, 5, 5, 1]`.

    Un acorde por compás. Lanza `PatronNoValido` con un mensaje que dice qué
    trozo no vale y por qué.
    """
    tokens = [t for t in _SEPARADORES.split((texto or "").strip()) if t]
    if not tokens:
        raise PatronNoValido("Escribe la progresión, un acorde por compás: por ejemplo, I V V I.")
    if len(tokens) > MAX_COMPASES:
        raise PatronNoValido(f"La progresión tiene {len(tokens)} compases y el máximo son {MAX_COMPASES}.")
    return [_grado(t) for t in tokens]


def escribir_progresion(grados, separador=" "):
    """`[1, 5, 5, 1]` → `I V V I` (o `I – V – V – I` con otro separador)."""
    return separador.join(ROMANOS[g - 1] for g in grados)


def grados_de(valor):
    """Los grados de un bloque guardado, o `[]` si su progresión no se entiende."""
    try:
        return leer_progresion((valor or {}).get("progresion") or "")
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
    progresion = datos.get("progresion", anterior.get("progresion") or PROGRESION_DE_PARTIDA)
    grados = leer_progresion(progresion)

    patron = datos.get("patron") or anterior.get("patron") or patrones()[0][0]
    if not nombre_del_patron(patron):
        raise PatronNoValido(f"No hay ningún patrón «{patron}» en el catálogo.")

    tonalidad = datos.get("tonalidad") or anterior.get("tonalidad") or tonalidades()[0][0]
    if not nombre_de_la_tonalidad(tonalidad):
        raise PatronNoValido(f"No hay ninguna tonalidad «{tonalidad}» en el catálogo.")

    return {
        "titulo": (datos.get("titulo", anterior.get("titulo", "")) or "").strip()[:120],
        "progresion": escribir_progresion(grados),
        "patron": patron,
        "tonalidad": tonalidad,
        "tempo": _entero(
            datos.get("tempo"), anterior.get("tempo") or TEMPO_DE_PARTIDA, TEMPO_MINIMO, TEMPO_MAXIMO
        ),
    }


def titulo_de(valor):
    """El nombre del ejercicio: su título, o «I – V – V – I»."""
    titulo = (valor or {}).get("titulo")
    if titulo:
        return titulo
    grados = grados_de(valor)
    return escribir_progresion(grados, " – ") if grados else "Patrón de piano"


def para_el_navegador(valor):
    """Lo que `patron_piano.js` necesita de un bloque guardado."""
    valor = valor or {}
    return {
        "grados": grados_de(valor),
        "patron": valor.get("patron") or "",
        "tonalidad": valor.get("tonalidad") or "",
        "tempo": _entero(valor.get("tempo"), TEMPO_DE_PARTIDA, TEMPO_MINIMO, TEMPO_MAXIMO),
    }
