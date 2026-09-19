"""Tonalidades: leerlas en castellano y saber si son mayores o menores.

El dato de origen viene limpio y en cifrado anglosajón: letra, alteración
opcional y el sufijo `mi` para el menor. `G`, `Ami`, `E♭`, `C#mi`.

**Dos decisiones.**

Los enarmónicos NO se agrupan. `D♭` y `C#` suenan igual, pero el chart está
escrito en una de las dos grafías y juntarlos diría algo que la partitura no
dice. Son pares pequeños (15 y 4) y separados son más honestos.

La tonalidad cuelga de la VERSIÓN, no de la canción: la misma canción está en
Re bemol en la original y en Do en la fácil. Filtrar por «en Do» significa que
hay alguna versión en Do, que es lo que le importa a quien va a tocarla.
"""

import re

CASTELLANO = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa", "G": "Sol", "A": "La", "B": "Si"}
ANGLOSAJON = {v.lower(): k for k, v in CASTELLANO.items()}

SUFIJO_MENOR = "mi"


def es_menor(tonalidad):
    return (tonalidad or "").endswith(SUFIJO_MENOR)


def partes(tonalidad):
    """`(letra, alteración, menor)` a partir de `E♭mi`. Alteración es '', '♭' o '#'."""
    t = (tonalidad or "").strip()
    menor = es_menor(t)
    if menor:
        t = t[: -len(SUFIJO_MENOR)]
    m = re.match(r"^([A-G])([♭b#♯]?)$", t)
    if not m:
        return None, "", menor
    alteracion = {"b": "♭", "♯": "#"}.get(m.group(2), m.group(2))
    return m.group(1), alteracion, menor


def nombre(tonalidad):
    """Cómo se dice en castellano: `E♭mi` → «Mi bemol menor»."""
    letra, alteracion, menor = partes(tonalidad)
    if letra is None:
        return tonalidad or ""
    texto = CASTELLANO[letra]
    if alteracion == "♭":
        texto += " bemol"
    elif alteracion == "#":
        texto += " sostenido"
    if menor:
        texto += " menor"
    return texto


def etiqueta(tonalidad):
    """«Sol · G». El nombre con el que piensas, y la letra que pone el chart."""
    n = nombre(tonalidad)
    return f"{n} · {tonalidad}" if n and n != tonalidad else (tonalidad or "")


def desde_texto(texto):
    """Encuentra «en la menor», «en sol», «en Ami» dentro de una frase.

    Devuelve `(tonalidad, trozo_reconocido)` o `(None, None)`.

    **Siempre exige la preposición «en»**, y si la nota va en castellano exige
    además que la siga un modificador o el final de la frase. Sin eso, «la» y
    «mi» son palabras corrientes y «la bamba» se leería como La mayor.
    """
    if not texto:
        return None, None

    notas_es = "|".join(ANGLOSAJON)
    patron_es = (
        rf"\ben\s+(?P<nota>{notas_es})"
        r"(?:\s+(?P<alt>sostenido|bemol))?"
        r"(?:\s+(?P<modo>mayor|menor))?"
        r"(?=\s*$|\s*[,.;])"
    )
    m = re.search(patron_es, texto, re.I)
    if m:
        letra = ANGLOSAJON[m.group("nota").lower()]
        alteracion = {"sostenido": "#", "bemol": "♭"}.get((m.group("alt") or "").lower(), "")
        menor = (m.group("modo") or "").lower() == "menor"
        return f"{letra}{alteracion}{SUFIJO_MENOR if menor else ''}", m.group(0)

    # Cifrado anglosajón tras «en»: `en C`, `en Ami`, `en E♭`, `en C#mi`.
    # El límite final es un lookahead y no `\b`: el bemol no es carácter de
    # palabra, así que `E♭\b` fallaba y el motor retrocedía a `E` a secas.
    m = re.search(r"\ben\s+(?P<t>[A-G](?:[♭b#♯])?(?:mi)?)(?=\s|$|[,.;])", texto)
    if m:
        letra, alteracion, menor = partes(m.group("t"))
        if letra:
            return f"{letra}{alteracion}{SUFIJO_MENOR if menor else ''}", m.group(0)

    return None, None


def modo_desde_texto(texto):
    """«en menor» / «en mayor» sueltos, sin nota. Devuelve 'menor', 'mayor' o None."""
    if not texto:
        return None
    if re.search(r"\ben\s+menor\b|\bmenores\b|\bmodo\s+menor\b", texto, re.I):
        return "menor"
    if re.search(r"\ben\s+mayor\b|\bmayores\b|\bmodo\s+mayor\b", texto, re.I):
        return "mayor"
    return None
