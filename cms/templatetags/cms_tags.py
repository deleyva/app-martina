from django import template

register = template.Library()

@register.filter
def get_list(dictionary, key):
    return dictionary.getlist(key)


# Un color por FACETA, no por etiqueta.
#
# `MusicTag` tenía un campo `color` que cada etiqueta llevaba suelto: 65
# etiquetas repartidas en 8 colores elegidos a mano, sin regla. `taggit.Tag` no
# tiene ese campo, así que al retirar `MusicTag` (C37b) había que decidir entre
# perder el color o darle un criterio.
#
# Se le da criterio: el color dice de qué faceta es la etiqueta. Así el color
# pasa a ser información —"esto es un instrumento", "esto es un estilo"— en vez
# de decoración, y una etiqueta nueva nace con el color correcto sin que nadie
# se lo ponga. Son 18 facetas contra 65 etiquetas y subiendo.
COLOR_POR_FACETA = {
    "instrumento": "#3B82F6",
    "concepto": "#8B5CF6",
    "estilo": "#EC4899",
    "tipo": "#F59E0B",
    "tonalidad": "#14B8A6",
    "compas": "#14B8A6",
    "progresion": "#8B5CF6",
    "voz": "#3B82F6",
    "dificultad": "#EF4444",
    "autor": "#10B981",
    "artista": "#10B981",
    "obra": "#10B981",
    "curso": "#F97316",
    "evaluacion": "#F97316",
    "tema": "#F97316",
    "lugar": "#14B8A6",
    "idioma": "#14B8A6",
    "orientacion": "#F59E0B",
}


@register.filter
def color_de_faceta(tag):
    """El color de una etiqueta según su faceta. Vacío si no lleva faceta.

    Devolver vacío es deliberado: las plantillas envuelven el estilo en
    `{% if %}`, así que una etiqueta sin faceta se pinta con el color normal
    del tema en vez de con uno inventado.
    """
    from my_library import facets

    nombre = getattr(tag, "name", tag)
    faceta, _ = facets.parse(nombre)
    return COLOR_POR_FACETA.get(faceta, "")
