"""Facetas de etiquetas: `faceta:valor`.

Antes de esto el vocabulario era plano y se fragmentaba solo: `guitar` convivía
con `instrument/guitar`, `ukelele` con `ukulele`, `aragón` con `aragon`, y
`partitura` con `sheet-music`, `musicscore` y `score`. Filtrar por instrumento
era imposible porque nada decía qué etiqueta ERA un instrumento.

EL SEPARADOR ES `:`, NO `/`. Esto no es estética: en la biblioteca hay etiquetas
de compás — `3/4`, `6/8`, `2/4`, `3/8`, `4/4`. Con `/` como separador, `3/4`
se parsea como la faceta `3` con valor `4`. De hecho ya pasaba: al contar los
namespaces existentes aparecían `3`, `4` y `6` como si fueran categorías.

Las etiquetas sin faceta siguen siendo válidas: el sistema no las rompe, pero
la sesión de estudio no agrupa ni filtra por ellas.
"""

SEPARADOR = ":"

# Facetas musicales — las que usa la sesión de estudio.
INSTRUMENTO = "instrumento"
CONCEPTO = "concepto"
ESTILO = "estilo"
TIPO = "tipo"
TONALIDAD = "tonalidad"
COMPAS = "compas"
PROGRESION = "progresion"
VOZ = "voz"
DIFICULTAD = "dificultad"
AUTOR = "autor"      # quien firma el método o el material didáctico
ARTISTA = "artista"  # quien interpreta la música
OBRA = "obra"

# Facetas no musicales — ordenan el resto del sitio (blog, documentos, IT).
CURSO = "curso"
EVALUACION = "evaluacion"
TEMA = "tema"
LUGAR = "lugar"
IDIOMA = "idioma"

FACETAS = (
    INSTRUMENTO, CONCEPTO, ESTILO, TIPO, TONALIDAD, COMPAS, PROGRESION,
    VOZ, DIFICULTAD, AUTOR, ARTISTA, OBRA,
    CURSO, EVALUACION, TEMA, LUGAR, IDIOMA,
)

# Por cuáles tiene sentido agrupar una sesión de práctica. El orden importa:
# trabajar la posición 2 de las pentatónicas es más específico que "guitarra",
# así que `concepto` manda sobre `instrumento`.
FACETAS_DE_AGRUPACION = (CONCEPTO, PROGRESION, OBRA, TIPO, ESTILO, INSTRUMENTO)

# Por cuáles se puede arrancar una sesión filtrando.
FACETAS_DE_FILTRO = (INSTRUMENTO, CONCEPTO, ESTILO, TIPO, TONALIDAD, DIFICULTAD)


def parse(nombre):
    """`"instrumento:guitarra"` → `("instrumento", "guitarra")`.

    Devuelve `(None, nombre)` si no lleva faceta conocida. Un `3/4` o un
    `vitalinux` pasan intactos, que es justo lo que se quiere.
    """
    if not nombre or SEPARADOR not in nombre:
        return None, nombre

    faceta, _, valor = nombre.partition(SEPARADOR)
    faceta = faceta.strip().lower()
    valor = valor.strip()

    if faceta not in FACETAS or not valor:
        return None, nombre
    return faceta, valor


def tiene_faceta(nombre):
    return parse(nombre)[0] is not None


def valor_de(nombre, faceta):
    """El valor si la etiqueta es de esa faceta, si no None."""
    f, valor = parse(nombre)
    return valor if f == faceta else None


def por_faceta(nombres):
    """`["instrumento:guitarra", "concepto:blues", "vitalinux"]` →
    `{"instrumento": {"guitarra"}, "concepto": {"blues"}}`.

    Lo que no lleva faceta se descarta a propósito: es lo que impide que
    `4-eso` o `10points` agrupen una sesión de práctica.
    """
    agrupado = {}
    for nombre in nombres:
        faceta, valor = parse(nombre)
        if faceta is None:
            continue
        agrupado.setdefault(faceta, set()).add(valor)
    return agrupado


def clave_de_agrupacion(nombres):
    """La etiqueta más específica por la que agrupar este elemento, o None.

    Recorre FACETAS_DE_AGRUPACION en orden y devuelve la primera que exista,
    para que dos elementos de `concepto:pentatonica` salgan juntos aunque
    compartan también `instrumento:guitarra` con media biblioteca.
    """
    agrupado = por_faceta(nombres)
    for faceta in FACETAS_DE_AGRUPACION:
        valores = agrupado.get(faceta)
        if valores:
            return f"{faceta}{SEPARADOR}{sorted(valores)[0]}"
    return None
