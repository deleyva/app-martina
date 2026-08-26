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
    # Sin esto son ~3 consultas por elemento subiendo a la página de origen:
    # 51 elementos pasaban de 74 a 222 ms, y crece en línea recta.
    from my_library.models import LibraryDeck

    items = list(items)
    LibraryDeck.precargar_etiquetas_de_pagina(items)

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


def _libro_de(unidad):
    """Clave del libro al que pertenece la unidad, o None si va suelta.

    Se saca del `path` de treebeard en vez de `get_parent()` para no hacer una
    consulta por unidad: el padre de una página es su propio path menos el
    último paso, y `steplen` es un atributo documentado de Wagtail.
    """
    from wagtail.models import Page

    item = getattr(unidad, "item", None) or unidad
    pagina = getattr(item, "source_page", None)
    if pagina is None:
        return None
    return pagina.path[: -Page.steplen] or None


def _paths_con_objetivo(unidades):
    """Paths de los libros que este usuario ha declarado como objetivo.

    Una sola consulta para toda la sesión: el usuario sale de la primera unidad
    porque `construir_sesion` recibe elementos de un único usuario.
    """
    from my_library.models import LibraryGoal

    if not unidades:
        return set()
    primera = unidades[0]
    item = getattr(primera, "item", None) or primera
    return set(
        LibraryGoal.objects.filter(user=item.user, activo=True).values_list(
            "libro__path", flat=True
        )
    )


def _repartir_por_libro(nuevos):
    """Intercala lo nuevo por libro, en vez de servirlo por orden de alta.

    La otra mitad de "alternar la cuota" (decisión del principal, 2026-08-25).
    Medido en producción: con tres objetivos, `nuevos` salía ordenado por pk y
    los trece elementos pendientes del libro más viejo ocupaban los dos huecos
    de novedad de TODAS las sesiones. No era mala suerte, era determinista: los
    pk más bajos ganan siempre. Los otros dos libros no aparecían nunca.

    Se conserva el orden DENTRO de cada libro, que es el orden del libro y es
    justo lo que compró la fase 11. Los libros salen en el orden en que
    aparecía su primer elemento, así que esto es estable entre llamadas.

    **Y el material suelto va el último.** Ordenar los grupos solo por primera
    aparición es ordenarlos por pk, y eso deja al libro recién empezado
    SIEMPRE en la cola: lo que acaba de crear `rellenar_para_sesion` tiene por
    fuerza el pk más alto. Medido en producción el 2026-08-26 —tres grupos sin
    tocar (un suelto, Larsen y el elemento de CAGED recién creado) y cuota 2—:
    la creación perezosa hacía su trabajo, la faceta `caged` pasaba de 11 a 12,
    y la sesión salía sin él. No era mala suerte otra vez: era el mismo
    determinismo que arregló C54, que se probó con DOS grupos y en producción
    hay tres.

    La regla ya estaba escrita en `libros.rellenar_para_sesion`, del lado de la
    creación: un elemento suelto de hace meses no satisface la intención "quiero
    estudiarme CAGED". El lado de la selección nunca la recibió.

    **Y los objetivos van por delante de los demás libros.** Distinguir solo
    "libro" de "suelto" no bastó, y lo dijo producción el mismo día: con el
    suelto ya fuera de la competición quedaban TRES grupos de libro por delante
    de CAGED y la cuota seguía siendo 2, así que el objetivo recién empezado
    seguía sin entrar. Un capítulo que está en la biblioteca porque se metió a
    mano hace meses no es lo mismo que un libro que el usuario ha declarado que
    quiere estudiarse; ordenarlos igual es perder justo la información que la
    fase 11 añadió al modelo.

    Cuesta UNA consulta por sesión, no una por unidad, que es la línea que este
    camino no puede cruzar.
    """
    grupos = {}
    for unidad in nuevos:
        grupos.setdefault(_libro_de(unidad), []).append(unidad)

    con_objetivo = _paths_con_objetivo(nuevos)
    orden = [c for c in grupos if c is not None and c in con_objetivo]
    orden += [c for c in grupos if c is not None and c not in con_objetivo]
    if None in grupos:
        orden.append(None)

    repartido = []
    while orden:
        for clave in list(orden):
            repartido.append(grupos[clave].pop(0))
            if not grupos[clave]:
                orden.remove(clave)
    return repartido


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

    # Y luego se intercalan por libro, para que un libro con material acumulado
    # no se quede con todos los huecos de novedad. Ver `_repartir_por_libro`.
    nuevos = _repartir_por_libro(nuevos)

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
