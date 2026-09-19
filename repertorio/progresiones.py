"""Progresiones armónicas: normalizarlas para poder filtrar por ellas.

**El problema con el dato de origen.** El campo `chordProgression` de JamZone
mezcla dos cosas distintas:

1. Progresiones de verdad: `I-V-vi-IV`, `I-IV-V`.
2. **Inventarios de acordes diatónicos**, que no son progresiones. `Beat It`
   tiene tres acordes y trae `I-ii-iii-IV-V-vi`; eso es la tablita de grados del
   chart, no lo que suena. Son 128 canciones de 529. Ofrecerlas como filtro
   sería mentir, así que se descartan.

**Y la agrupación por giros.** `I-V-vi-IV`, `vi-IV-I-V` y `IV-I-V-vi` son la
misma progresión empezada en distinto sitio. Sin plegarlas, la más usada del pop
aparece partida en tres entradas de 26, 17 y 8. Plegadas son 51 canciones y un
solo clic, que es lo que sirve para dar clase.
"""

import re

ESCALA = ["i", "ii", "iii", "iv", "v", "vi", "vii"]

# Cuántos grados hacen falta para sospechar que es un inventario y no música.
MINIMO_PARA_INVENTARIO = 5

# Nombres de las que merecen uno. Solo se muestran si la familia existe en los
# datos, así que sobra con tenerlos aquí aunque alguna no aparezca nunca.
NOMBRES = {
    "I-V-vi-IV": "la de los cuatro acordes",
    "I-vi-IV-V": "doo-wop de los 50",
    "I-IV-V": "cadencia de rock y blues",
    "I-IV": "vaivén de dos acordes",
    "i-VII-VI-V": "descenso andaluz",
    "i-V": "menor y dominante",
    "12 Bar Blues": "blues de 12 compases",
}


def tokens(progresion):
    """Los grados, con los dos destrozos del origen deshechos.

    En Sanity el `vii°` viaja como `vv` y el `ii°` como `ii*`: se perdió el
    símbolo de disminuido por el camino.
    """
    crudos = [t.strip() for t in (progresion or "").split("-") if t.strip()]
    return [("vii°" if t == "vv" else t.replace("*", "°")) for t in crudos]


def grado(token):
    """El índice del grado (0 = I), o None si el token no es un grado."""
    base = re.sub(r"[b#♭♯°*]", "", token).lower()
    return ESCALA.index(base) if base in ESCALA else None


def es_inventario(toks):
    """¿Es la lista de acordes de la tonalidad en vez de una progresión?

    La firma es inconfundible: cinco grados o más, todos distintos, en orden
    ascendente y empezando por el I. Ninguna canción recorre la escala entera
    hacia arriba sin repetir.
    """
    grados = [grado(t) for t in toks]
    if None in grados or len(grados) < MINIMO_PARA_INVENTARIO:
        return False
    return grados[0] == 0 and grados == sorted(grados) and len(set(grados)) == len(grados)


def familia(progresion):
    """La forma canónica: el giro que empieza por el I, o el primero alfabético.

    Devuelve cadena vacía si es un inventario o no hay nada que normalizar; esos
    casos no entran en el filtro.
    """
    toks = tokens(progresion)
    if not toks:
        return ""
    if any(grado(t) is None for t in toks):
        # Etiquetas como «12 Bar Blues» o grados raros (`V/V`, `V6`): se
        # respetan tal cual, que son igual de buscables.
        return (progresion or "").strip()
    if es_inventario(toks):
        return ""
    giros = ["-".join(toks[i:] + toks[:i]) for i in range(len(toks))]
    empiezan_en_I = [g for g in giros if grado(g.split("-")[0]) == 0]
    return sorted(empiezan_en_I)[0] if empiezan_en_I else sorted(giros)[0]


def nombre(fam):
    """El apodo de la progresión, si lo tiene. Cadena vacía si no."""
    return NOMBRES.get(fam, "")


def etiqueta(fam):
    """Familia y apodo en una línea. Para los chips, que son de una sola línea."""
    apodo = nombre(fam)
    return f"{fam} · {apodo}" if apodo else fam


def desde_texto(texto):
    """Busca una progresión escrita a mano dentro de una frase.

    Devuelve `(familia, trozo_reconocido)` o `(None, None)`. Acepta guiones
    normales y largos, y da igual cómo se escriban las mayúsculas de los grados
    salvo en lo que distingue mayor de menor, que sí se respeta.
    """
    if not texto:
        return None, None

    if re.search(r"\b(12\s*bar\s*blues|blues\s+de\s+(12|doce)\s+compases)\b", texto, re.I):
        return "12 Bar Blues", "blues de 12 compases"

    # Las alternativas van de más larga a más corta a propósito: con `I` antes
    # que `IV`, «I-V-vi-IV» se leía como «I-V-vi-I», porque el motor se queda
    # con la primera que encaja y no vuelve atrás si el resto ya casó.
    grados = "VII|III|IV|VI|II|V|I|vii|iii|iv|vi|ii|v|i"
    uno = rf"(?:[b#♭]?(?:{grados})[°*]?)"
    patron = rf"\b({uno}(?:\s*[-–—]\s*{uno}){{1,6}})"
    m = re.search(patron, texto)
    if not m:
        return None, None
    trozo = m.group(1)
    normalizado = re.sub(r"\s*[-–—]\s*", "-", trozo.strip())
    fam = familia(normalizado)
    return (fam, trozo) if fam else (None, None)
