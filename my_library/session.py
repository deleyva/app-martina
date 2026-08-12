"""Construcción de sesiones de estudio acotadas.

El problema que resuelve: hasta ahora estudiar un mazo significaba recorrerlo
entero, así que cada elemento añadido a la biblioteca alargaba la sesión. La
cola crecía sin techo y eso genera ansiedad.

Aquí una sesión es un presupuesto fijo de elementos. La biblioteca puede crecer
todo lo que quiera: el tamaño de la sesión no depende de ella.

Tres decisiones, en este orden:

1. QUÉ ENTRA — por caducidad. Cada elemento tiene un intervalo objetivo según lo
   bien que te lo sepas; si lleva más tiempo sin tocarse, está vencido. Se cogen
   los más vencidos primero. Lo nunca practicado es prioridad máxima.

2. CUÁNTOS — un tope. Si no hay bastantes vencidos, se rellena con lo menos
   reciente; nunca se pasa del tope.

3. EN QUÉ ORDEN — agrupado por temática. Los elementos que comparten etiqueta
   salen seguidos, en bloques cortos.

Sobre el punto 3, que va contra el manual: la repetición espaciada clásica
entrelaza, y entrelazar retiene mejor que agrupar (efecto de interferencia
contextual). Se agrupa igual, y a conciencia — trabajar la posición 2 de las
pentatónicas exige tenerlas juntas, y una sesión que no se hace no retiene nada.
El compromiso son bloques CORTOS (MAX_BLOQUE): continuidad suficiente para
trabajar, no tanta como para que la sesión sea un bloque único.
"""

from collections import defaultdict

from . import facets

# Cuántos días debería aguantar cada nivel antes de volver a tocarse.
# No es un algoritmo de repetición espaciada: son plazos observables que se
# ajustarán cuando ReviewLog tenga datos reales. Deliberadamente cortos —
# la destreza motora decae más despacio que un dato, pero necesita más contacto.
INTERVALO_POR_NIVEL = {
    0: 1,   # sin valorar
    1: 1,   # apenas lo conozco
    2: 3,   # lo estoy aprendiendo
    3: 7,   # lo conozco bien
    4: 21,  # me lo sé muy bien
}

TAMANO_SESION_POR_DEFECTO = 8
TAMANO_SESION_MAXIMO = 50
MAX_BLOQUE = 4  # elementos seguidos de la misma temática

# Qué parte de la sesión se reserva para material que nunca se ha practicado.
# 0.25 de 8 = 2 huecos.
#
# Nació de un defecto real: al principio lo nunca practicado tenía prioridad
# máxima (`inf`), con la idea de que si no, nunca entraría en rotación. La idea
# era buena y la implementación demasiado bruta — TODO lo nuevo iba antes que
# TODO lo demás, así que añadir un libro de 60 ejercicios borraba el repaso
# durante un mes. Con la cuota, ese mismo libro entra a dos por sesión y el
# repaso sigue vivo.
PROPORCION_NOVEDAD = 0.25


def intervalo_objetivo(item):
    """Días que este elemento debería aguantar sin practicarse."""
    return INTERVALO_POR_NIVEL.get(item.proficiency_level, 1)


def _ratio_vencimiento(item, dias_sin_practicar):
    """Cuánto ha rebasado su plazo. >= 1 significa vencido.

    None (nunca practicado) es prioridad máxima: es el material que aún no ha
    entrado en rotación, y dejarlo fuera lo dejaría fuera para siempre.
    """
    if dias_sin_practicar is None:
        return float("inf")
    return dias_sin_practicar / intervalo_objetivo(item)


def unidades_de_practica(items):
    """Convierte elementos en unidades practicables.

    Un elemento sin secciones ES la unidad. Un elemento troceado se sustituye
    por sus secciones — el PDF entero deja de salir en la cola, que es el punto
    entero de trocear.
    """
    unidades = []
    for item in items:
        secciones = list(item.sections.all())
        if secciones:
            unidades.extend(secciones)
        else:
            unidades.append(item)
    return unidades


def _dias_sin_practicar(unidades):
    """{clave: días} en dos consultas, en vez de una por unidad.

    La clave lleva el tipo delante (`("item", 5)` / `("seccion", 5)`) porque
    los pk de las dos tablas se pisan.
    """
    from django.db.models import Max
    from django.utils import timezone

    from .models import ItemSection, ReviewLog

    items = [u for u in unidades if not isinstance(u, ItemSection)]
    secciones = [u for u in unidades if isinstance(u, ItemSection)]
    ahora = timezone.now()
    dias = {}

    if items:
        # section__isnull: un repaso de una sección no cuenta como repaso del
        # elemento entero, aunque lleve su item_id.
        ultimos = (
            ReviewLog.objects.filter(
                item__in=items, source=ReviewLog.SOURCE_STUDY, section__isnull=True
            )
            .values("item")
            .annotate(ultimo=Max("reviewed_at"))
        )
        por_pk = {f["item"]: (ahora - f["ultimo"]).days for f in ultimos}
        dias.update({("item", i.pk): por_pk.get(i.pk) for i in items})

    if secciones:
        ultimos = (
            ReviewLog.objects.filter(
                section__in=secciones, source=ReviewLog.SOURCE_STUDY
            )
            .values("section")
            .annotate(ultimo=Max("reviewed_at"))
        )
        por_pk = {f["section"]: (ahora - f["ultimo"]).days for f in ultimos}
        dias.update({("seccion", s.pk): por_pk.get(s.pk) for s in secciones})

    return dias


def _etiquetas(unidad):
    try:
        return {t.name.lower() for t in unidad.get_content_tags()}
    except Exception:
        return set()


def _clave(unidad):
    return unidad.clave_de_practica


def agrupar_por_tematica(items, max_bloque=MAX_BLOQUE):
    """Reordena para que lo que comparte temática salga seguido, en bloques cortos.

    Solo agrupa por etiquetas CON faceta. Sin esa condición el vocabulario plano
    metía ruido: tres elementos que comparten `4-eso` o `10points` acababan
    seguidos, y eso no significa nada para practicar.

    Preserva todos los elementos: es una permutación, nunca un filtro.
    """
    if len(items) <= 2:
        return list(items)

    por_etiqueta = defaultdict(list)
    for item in items:
        for etiqueta in _etiquetas(item):
            if facets.tiene_faceta(etiqueta):
                por_etiqueta[etiqueta].append(item)

    # Etiquetas que de verdad agrupan (2+ elementos), por especificidad primero.
    # El orden de FACETAS_DE_AGRUPACION manda sobre el número de elementos:
    # si no, `instrumento:guitarra` con 8 elementos se comería a
    # `concepto:pentatonica` con 3, y agrupar por instrumento no aporta nada
    # cuando media biblioteca es de guitarra.
    prioridad = {f: n for n, f in enumerate(facets.FACETAS_DE_AGRUPACION)}
    ultima = len(prioridad)

    def _orden(par):
        etiqueta, items_del_grupo = par
        faceta, _ = facets.parse(etiqueta)
        return (prioridad.get(faceta, ultima), -len(items_del_grupo), etiqueta)

    candidatas = sorted(
        ((e, ii) for e, ii in por_etiqueta.items() if len(ii) >= 2),
        key=_orden,
    )

    ordenados = []
    colocados = set()
    for _etiqueta, del_grupo in candidatas:
        bloque = [u for u in del_grupo if _clave(u) not in colocados][:max_bloque]
        if len(bloque) < 2:
            continue
        for unidad in bloque:
            colocados.add(_clave(unidad))
        ordenados.extend(bloque)

    # Lo que no agrupó con nada mantiene su prioridad original, al final.
    ordenados.extend(u for u in items if _clave(u) not in colocados)
    return ordenados


def facetas_disponibles(items):
    """Qué se puede elegir para arrancar una sesión, con cuántos elementos.

    `{"instrumento": [("guitarra", 12), ("piano", 3)], "concepto": [...]}`,
    cada faceta ordenada de más a menos elementos. Solo devuelve las facetas
    de FACETAS_DE_FILTRO: filtrar por `evaluacion` o `tema` no tiene sentido
    para practicar.
    """
    cuentas = {}
    for item in items:
        for etiqueta in _etiquetas(item):
            faceta, valor = facets.parse(etiqueta)
            if faceta in facets.FACETAS_DE_FILTRO:
                cuentas.setdefault(faceta, {})
                cuentas[faceta][valor] = cuentas[faceta].get(valor, 0) + 1

    return {
        faceta: sorted(valores.items(), key=lambda par: (-par[1], par[0]))
        for faceta, valores in sorted(
            cuentas.items(), key=lambda par: facets.FACETAS_DE_FILTRO.index(par[0])
        )
    }


def filtrar_por_facetas(items, seleccion):
    """Elementos que casan con la selección.

    Y entre facetas, O dentro de cada faceta: "guitarra Y (pentatónica O
    arpegio)". Es lo que se espera al elegir con el ratón — añadir un valor
    más dentro de una faceta amplía la búsqueda, añadir otra faceta la
    estrecha.

    Una selección vacía no filtra nada: devuelve todo.
    """
    seleccion = {f: set(v) for f, v in (seleccion or {}).items() if v}
    if not seleccion:
        return list(items)

    resultado = []
    for item in items:
        del_item = facets.por_faceta(_etiquetas(item))
        if all(del_item.get(f, set()) & valores for f, valores in seleccion.items()):
            resultado.append(item)
    return resultado


def construir_sesion(items, tamano=TAMANO_SESION_POR_DEFECTO):
    """Devuelve los elementos de una sesión, acotados y ordenados.

    `items` es cualquier iterable de LibraryItem (el mazo, la biblioteca entera,
    un filtro de etiquetas). El resultado nunca excede `tamano`.
    """
    unidades = unidades_de_practica(items)
    if not unidades:
        return []

    tamano = max(1, min(int(tamano), TAMANO_SESION_MAXIMO))
    dias = _dias_sin_practicar(unidades)

    nuevos = [u for u in unidades if dias[_clave(u)] is None]
    conocidos = [u for u in unidades if dias[_clave(u)] is not None]

    # Lo nuevo, por orden de alta. Para secciones, `orden` las mantiene en el
    # orden en que se trocearon — que sí es el orden de la pieza. Para
    # elementos sueltos es el pk, lo más parecido al orden del libro que hay
    # hoy en el modelo: no existe ningún ordinal de capítulo/ejercicio.
    nuevos.sort(key=lambda u: (getattr(u, "orden", 0), u.pk))

    # Lo conocido, más vencido primero. El desempate por clave mantiene el
    # orden estable entre llamadas: sin él, dos unidades igual de vencidas
    # bailarían en cada recarga.
    conocidos.sort(key=lambda u: (-_ratio_vencimiento(u, dias[_clave(u)]), _clave(u)))

    cuota = min(len(nuevos), max(1, round(tamano * PROPORCION_NOVEDAD))) if nuevos else 0

    elegidos = nuevos[:cuota]
    elegidos += conocidos[: tamano - len(elegidos)]

    # Si no hay bastante repaso para llenar la sesión, entra más material nuevo.
    # Lo contrario —dejar la sesión a medias habiendo cosas sin tocar— sería
    # absurdo.
    if len(elegidos) < tamano:
        ya = {_clave(u) for u in elegidos}
        elegidos += [u for u in nuevos if _clave(u) not in ya][
            : tamano - len(elegidos)
        ]

    return agrupar_por_tematica(elegidos)
