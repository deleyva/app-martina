"""La lista de lectura del profesor: lo que está viendo y lo que viene.

Cruza todos sus grupos en una pantalla para que se vaya leyendo el material
antes de darlo. **No guarda nada propio salvo los libros ocultos**: «en clase»
sale de las sesiones ya registradas y «próximo» del mismo motor que «Preparar»
(`libros_de_grupo`), así que la lista nunca se desincroniza de la clase.

Es una lista de lectura y no repetición espaciada (decisión del principal,
2026-10-04): abrir un elemento no lo mete en ninguna biblioteca ni lo da por
visto en ningún grupo.
"""

from datetime import timedelta

from django.utils import timezone
from wagtail.models import Page

from clases import libros_de_grupo
from clases.models import ClassSessionItem, Group, LibroOcultoEnLectura
from my_library.libros import material_del_libro

# El horizonte. Elegido por mí al construirla, no por Jesús: si se queda corto
# o largo, se cambia aquí.
DIAS_ATRAS = 21
PROXIMOS_POR_LIBRO = 3

EN_CLASE = "en_clase"
VISTO = "visto"
PROXIMO = "proximo"

# Un chip por grupo y elemento. Si el mismo elemento está en clase y además
# vuelve a salir como próximo en ese grupo, gana lo que está pasando ya.
_PRIORIDAD = {EN_CLASE: 0, VISTO: 0, PROXIMO: 1}


def libros_ocultos(user):
    return set(
        LibroOcultoEnLectura.objects.filter(user=user).values_list("libro_id", flat=True)
    )


def alternar_oculto(user, libro):
    """Oculta el libro si se veía y lo vuelve a mostrar si estaba oculto.

    Devuelve si queda oculto.
    """
    borrados, _ = LibroOcultoEnLectura.objects.filter(user=user, libro=libro).delete()
    if borrados:
        return False
    LibroOcultoEnLectura.objects.create(user=user, libro=libro)
    return True


def _articulo(pagina):
    """La página de donde sale el elemento, si es una página con URL.

    Un capítulo-recorte no es una `Page` y no tiene artículo que abrir.
    """
    return pagina if isinstance(pagina, Page) else None


class _Acumulador:
    """Junta los elementos por (tipo, objeto): una fila aunque esté en tres grupos."""

    def __init__(self):
        self.filas = {}

    def anadir(self, tipo, objeto, articulo, group, estado, fecha):
        clave = (tipo.pk, objeto.pk)
        fila = self.filas.get(clave)
        if fila is None:
            icono, titulo, tipo_legible = libros_de_grupo.describir(objeto)
            fila = self.filas[clave] = {
                "tipo": tipo,
                "objeto": objeto,
                "icono": icono,
                "titulo": titulo,
                "tipo_legible": tipo_legible,
                "articulo": articulo,
                "chips": {},
            }
        if fila["articulo"] is None:
            fila["articulo"] = articulo
        _poner_chip(fila["chips"], group, estado, fecha)

    def tiene(self, tipo, objeto, group):
        fila = self.filas.get((tipo.pk, objeto.pk))
        return fila is not None and group.pk in fila["chips"]


def _poner_chip(chips, group, estado, fecha):
    """El chip de `group`, quedándose con el más relevante.

    En clase gana a próximo; entre dos de clase, el más reciente; entre dos
    próximos, el más cercano, y uno con fecha a uno sin ella.
    """
    nuevo = {"group": group, "estado": estado, "fecha": fecha}
    actual = chips.get(group.pk)
    if actual is None:
        chips[group.pk] = nuevo
        return
    if _PRIORIDAD[estado] != _PRIORIDAD[actual["estado"]]:
        if _PRIORIDAD[estado] < _PRIORIDAD[actual["estado"]]:
            chips[group.pk] = nuevo
        return
    if estado == PROXIMO:
        if fecha is not None and (actual["fecha"] is None or fecha < actual["fecha"]):
            chips[group.pk] = nuevo
    elif fecha is not None and (actual["fecha"] is None or fecha > actual["fecha"]):
        chips[group.pk] = nuevo


def _material_oculto(ocultos):
    """{(content_type_id, object_id)} de todo lo que hay en los libros ocultos.

    **Ocultar un libro oculta su material, no solo lo que entró por él.** Mirar
    `item.group_book` no basta: en producción hay elementos de las lecturas
    rítmicas en clases sin libro asociado (preparadas antes de asignar libros, o
    añadidas sueltas), y se colaban en la lista con el libro oculto (encontrado
    al verificar el despliegue, 2026-10-04).
    """
    claves = set()
    for libro in Page.objects.filter(pk__in=ocultos):
        for _capitulo, objeto in material_del_libro(libro):
            tipo, pk = libros_de_grupo._clave(objeto)
            claves.add((tipo.pk, pk))
    return claves


def _de_las_sesiones(acumulador, grupos, ocultos, hoy):
    """Lo que ya está en una clase: de hace `DIAS_ATRAS` días en adelante.

    Una sesión con fecha futura es una clase ya preparada, así que lo suyo es
    «próximo», no «en clase».
    """
    material_oculto = _material_oculto(ocultos)
    items = (
        ClassSessionItem.objects.filter(
            session__group__in=grupos,
            session__date__gte=hoy - timedelta(days=DIAS_ATRAS),
        )
        .select_related("session__group", "group_book", "content_type", "source_page")
        .prefetch_related("content_object")
        .order_by("session__date", "order")
    )
    for item in items:
        if item.group_book is not None and item.group_book.libro_id in ocultos:
            continue
        if (item.content_type_id, item.object_id) in material_oculto:
            continue
        objeto = item.content_object
        if objeto is None:
            continue
        fecha = item.session.date
        if fecha > hoy:
            estado = PROXIMO
        else:
            estado = VISTO if item.visto else EN_CLASE
        acumulador.anadir(
            item.content_type, objeto, item.source_page, item.session.group, estado, fecha
        )


def _de_los_libros(acumulador, grupos, ocultos):
    """Los siguientes pendientes de cada libro activo, como en «Preparar».

    **El material se recorre una vez por libro**, igual que en el panel de
    progreso: un libro suele estar en varios grupos del mismo nivel y
    enumerarlo obliga a parsear el cuerpo de cada capítulo.
    """
    memoria = {}
    for group in grupos:
        for group_book in libros_de_grupo.libros_activos(group):
            if group_book.libro_id in ocultos:
                continue
            if group_book.libro_id not in memoria:
                memoria[group_book.libro_id] = material_del_libro(group_book.libro)
            puestos = 0
            for fila in libros_de_grupo._enumerar_con(group_book, memoria[group_book.libro_id]):
                if puestos >= PROXIMOS_POR_LIBRO:
                    break
                if fila["item"] is not None and not fila["item"].propuesto:
                    continue
                # Lo que ya está en una clase de este grupo no se repite como
                # próximo: ocuparía un hueco que es para lo que viene después.
                if acumulador.tiene(fila["tipo"], fila["objeto"], group):
                    continue
                acumulador.anadir(
                    fila["tipo"],
                    fila["objeto"],
                    _articulo(fila["capitulo"]),
                    group,
                    PROXIMO,
                    None,
                )
                puestos += 1


def _orden(fila):
    """En clase primero, lo más reciente arriba; luego lo próximo, lo más cercano arriba."""
    chips = fila["chips"]
    en_clase = [c["fecha"] for c in chips if c["estado"] != PROXIMO]
    if en_clase:
        return (0, -max(en_clase).toordinal())
    con_fecha = [c["fecha"] for c in chips if c["fecha"] is not None]
    return (1, min(con_fecha).toordinal()) if con_fecha else (2, 0)


def _encaja(fila, cuando):
    if cuando is None:
        return True
    if cuando == PROXIMO:
        return any(c["estado"] == PROXIMO for c in fila["chips"])
    return any(c["estado"] != PROXIMO for c in fila["chips"])


def _articulos(elementos):
    """Una fila por página de origen, con los chips de todos sus elementos."""
    articulos = {}
    for fila in elementos:
        pagina = fila["articulo"]
        if pagina is None:
            continue
        articulo = articulos.setdefault(
            pagina.pk, {"pagina": pagina, "elementos": 0, "chips": {}}
        )
        articulo["elementos"] += 1
        for chip in fila["chips"]:
            _poner_chip(articulo["chips"], chip["group"], chip["estado"], chip["fecha"])
    for articulo in articulos.values():
        articulo["chips"] = _chips_ordenados(articulo["chips"])
    return list(articulos.values())


def _chips_ordenados(chips):
    return sorted(chips.values(), key=lambda c: c["group"].name)


def _libros_para_ocultar(grupos, ocultos):
    """Cada libro activo de tus grupos una vez, con dónde se da y si está oculto."""
    libros = {}
    for group in grupos:
        for group_book in libros_de_grupo.libros_activos(group):
            libro = libros.setdefault(
                group_book.libro_id,
                {
                    "libro": group_book.libro,
                    "seccion": group_book.get_seccion_display(),
                    "grupos": [],
                    "oculto": group_book.libro_id in ocultos,
                },
            )
            libro["grupos"].append(group.name)
    return sorted(libros.values(), key=lambda l: (l["oculto"], l["libro"].title))


def lista_de_lectura(user, grupos_elegidos=(), cuando=None, hoy=None):
    """Todo lo que pinta la pantalla.

    `grupos_elegidos` son pks: vacío es todos. Un pk que no es de tus grupos se
    ignora, igual que en «empezar». `cuando` es `EN_CLASE`, `PROXIMO` o `None`.
    """
    hoy = hoy or timezone.localdate()
    todos = list(Group.del_profesor(user).select_related("subject").order_by("name"))
    elegidos = {int(g) for g in grupos_elegidos} & {g.pk for g in todos}
    grupos = [g for g in todos if g.pk in elegidos] if elegidos else todos
    ocultos = libros_ocultos(user)

    acumulador = _Acumulador()
    _de_las_sesiones(acumulador, grupos, ocultos, hoy)
    _de_los_libros(acumulador, grupos, ocultos)

    filas = []
    for fila in acumulador.filas.values():
        fila["chips"] = _chips_ordenados(fila["chips"])
        filas.append(fila)
    filas.sort(key=_orden)

    cuantos_por_grupo = {g.pk: 0 for g in todos}
    for fila in filas:
        for chip in fila["chips"]:
            cuantos_por_grupo[chip["group"].pk] += 1

    elementos = [f for f in filas if _encaja(f, cuando)]
    return {
        "elementos": elementos,
        "articulos": _articulos(elementos),
        "grupos": [
            {
                "group": g,
                "seleccionado": g.pk in elegidos,
                "cuantos": cuantos_por_grupo[g.pk] if g in grupos else None,
            }
            for g in todos
        ],
        "libros": _libros_para_ocultar(todos, ocultos),
        "dias_atras": DIAS_ATRAS,
        "proximos_por_libro": PROXIMOS_POR_LIBRO,
    }

