"""Escaleras de peldaños: hasta dónde va cada grupo con cada elemento (fase 93).

La app sabía QUÉ había visto cada grupo (`GroupBookItem.estado`,
`ClassSessionItem.visto`/`tratado`), pero no HASTA DÓNDE lo había trabajado.
Aquí vive todo lo que decide algo sobre los peldaños; los modelos solo guardan
y las vistas solo pintan.

Tres reglas, las tres pedidas o aceptadas por Jesús el 2026-11-01:

- **El estado es un conjunto de peldaños, no un número.** Los modos rítmicos
  no se abandonan, así que el «siguiente» se deriva: el primero que falta.
- **Ningún gesto nuevo en clase.** Marcar tratado sube UN peldaño; «+2» sube
  dos, y es opcional. Desmarcar retira exactamente lo que ese toque añadió.
- **Un libro sin escalera no cambia en nada.** Todas las funciones devuelven
  None o la lista vacía cuando no hay escalera, y no escriben.
"""

from clases.models import SECCIONES_CLASE, GroupBookItem

# Las cuatro de fábrica. La rítmica y la de canción son el borrador que Jesús
# aceptó; la melódica y la de ordenamientos las dictó él. Se cargan por
# migración de datos y después mandan los datos: esto es solo la semilla.
DE_FABRICA = [
    {
        "nombre": "Lectura rítmica",
        "peldanos": [
            ("tempo", "Con tempo"),
            ("compas", "Con compás"),
            ("modos", "Otros modos rítmicos"),
            ("polirritmia_grupal", "Polirritmia grupal"),
            ("polirritmia_individual", "Polirritmia individual"),
        ],
    },
    {
        "nombre": "Lectura melódica",
        "peldanos": [
            ("ritmo", "Ritmo"),
            ("na", "Con «na»"),
            ("notas", "Nombre de notas"),
            ("notas_canto", "Notas y canto"),
        ],
    },
    {
        "nombre": "Ordenamientos (sensorialidad)",
        "peldanos": [
            ("na", "Cantar con «na»"),
            ("notas", "Nombre de notas"),
            ("notas_canto", "Notas y canto"),
        ],
    },
    {
        "nombre": "Canción",
        "peldanos": [
            ("letra", "Letra y forma"),
            ("ritmo", "Patrón rítmico (groove)"),
            ("armonia", "Progresión armónica"),
            ("melodia", "Melodía, riffs y solos"),
            ("montaje", "Montaje completo con roles"),
        ],
    },
]

CANCION = "Canción"

# Cuántos peldaños puede subir un toque. Uno es lo pedido por defecto; dos es el
# «+2» opcional. Más no: subir tres de golpe ya no es registrar, es rellenar.
SALTO_MAXIMO = 2


def crear_de_fabrica(Escalera=None):
    """Crea las que falten, por nombre. Vale desde la migración (le pasa el
    modelo histórico) y desde los tests. Devuelve cuántas ha creado."""
    if Escalera is None:
        from clases.models import Escalera as Modelo

        Escalera = Modelo
    creadas = 0
    for semilla in DE_FABRICA:
        _, creada = Escalera.objects.get_or_create(
            nombre=semilla["nombre"],
            defaults={
                "peldanos": [
                    {"clave": clave, "nombre": nombre} for clave, nombre in semilla["peldanos"]
                ]
            },
        )
        creadas += int(creada)
    return creadas


def por_defecto(seccion):
    """La escalera con la que nace un libro en esa sección, o None.

    Solo las canciones: no todo lo que va en «sensorialidad» son ordenamientos,
    y un libro de ritmo puede ser rítmico o melódico. Esas se eligen a mano en
    la pantalla de libros del grupo.
    """
    from clases.models import Escalera

    if seccion != "cancion":
        return None
    return Escalera.objects.filter(nombre=CANCION).first()


def _fila_del_grupo(session_item):
    if session_item.group_book_id is None:
        return None
    return GroupBookItem.objects.filter(
        group_book_id=session_item.group_book_id,
        content_type_id=session_item.content_type_id,
        object_id=session_item.object_id,
    ).first()


def estado_de(session_item, trabajados=None):
    """Dónde va el grupo con el elemento de ESTA clase; None sin escalera.

    `trabajados` se puede pasar ya leído (la presentación lo trae en una sola
    consulta para toda la sesión); si no, se lee la fila del grupo.
    """
    group_book = session_item.group_book if session_item.group_book_id else None
    escalera = group_book.escalera if group_book else None
    if escalera is None or escalera.total == 0:
        return None
    if trabajados is None:
        fila = _fila_del_grupo(session_item)
        trabajados = list(fila.peldanos) if fila else []
    siguiente = escalera.siguiente(trabajados)
    # Lo previsto es lo que se copió al preparar; si ya está hecho (se subió a
    # mano entretanto), lo que se anuncia es lo que de verdad falta.
    previsto = session_item.peldano if session_item.peldano not in (trabajados or []) else None
    previsto = previsto or siguiente
    return {
        "escalera": escalera,
        "trabajados": list(trabajados),
        "hechos": escalera.hechos(trabajados),
        "total": escalera.total,
        "siguiente": siguiente,
        "previsto": previsto,
        "previsto_n": escalera.indice(previsto),
        "previsto_nombre": escalera.nombre_de(previsto),
        "completa": escalera.completa(trabajados),
        "puede_dos": len(escalera.siguientes(trabajados, 2)) == 2,
        "dibujo": escalera.dibujo(trabajados, previsto),
        # Lo que el toque de tratado de esta clase subió: el visor lo necesita
        # para reflejar un cambio de marca sin volver a pedir la sesión.
        "anadidos": list(session_item.peldanos_anadidos or []),
    }


def para_json(estado):
    """Lo mismo, sin el modelo dentro, para la presentación."""
    if estado is None:
        return None
    return {
        "nombre": estado["escalera"].nombre,
        "trabajados": estado["trabajados"],
        "hechos": estado["hechos"],
        "total": estado["total"],
        "previsto": estado["previsto"],
        "previsto_n": estado["previsto_n"],
        "previsto_nombre": estado["previsto_nombre"],
        "puede_dos": estado["puede_dos"],
        "anadidos": estado["anadidos"],
        "peldanos": [
            {"n": p["n"], "clave": p["clave"], "nombre": p["nombre"], "hecho": p["hecho"]}
            for p in estado["dibujo"]
        ],
    }


def trabajados_de_la_sesion(items):
    """{pk del ClassSessionItem: peldaños trabajados} en UNA consulta."""
    con_libro = [i for i in items if i.group_book_id]
    if not con_libro:
        return {}
    filas = GroupBookItem.objects.filter(
        group_book_id__in={i.group_book_id for i in con_libro}
    ).values_list("group_book_id", "content_type_id", "object_id", "peldanos")
    por_clave = {(gb, ct, oid): peldanos for gb, ct, oid, peldanos in filas}
    return {
        i.pk: list(por_clave.get((i.group_book_id, i.content_type_id, i.object_id), []))
        for i in con_libro
    }


def _guardar_peldanos(item, peldanos, session=None):
    """Escribe la lista y deriva el visto: completa ⇒ visto; incompleta y
    estaba visto por la escalera ⇒ vuelve a pendiente."""
    escalera = item.group_book.escalera
    item.peldanos = list(peldanos)
    cambios = ["peldanos"]
    if escalera.completa(item.peldanos):
        if item.estado != GroupBookItem.VISTO:
            item.estado = GroupBookItem.VISTO
            item.visto_en = session
            cambios += ["estado", "visto_en"]
    elif item.estado == GroupBookItem.VISTO:
        item.estado = GroupBookItem.PENDIENTE
        item.visto_en = None
        cambios += ["estado", "visto_en"]
    item.save(update_fields=cambios + ["updated_at"])
    return item


def avanzar(session_item, saltos=1):
    """El toque de «tratado»: sube `saltos` peldaños (1, o 2 con «+2»).

    Sube los primeros que FALTAN, no «el previsto y el siguiente» a ciegas: si
    el grupo subió a mano entretanto, lo previsto ya está hecho y repetirlo no
    registraría nada. Devuelve las claves añadidas, y las deja apuntadas en el
    elemento de la sesión para poder deshacerlas.
    """
    from clases import libros_de_grupo

    group_book = session_item.group_book if session_item.group_book_id else None
    escalera = group_book.escalera if group_book else None
    if escalera is None or session_item.content_object is None:
        return []
    saltos = max(1, min(int(saltos or 1), SALTO_MAXIMO))

    item, _ = libros_de_grupo.excepcion(
        group_book, session_item.content_object, capitulo=session_item.source_page
    )
    nuevos = escalera.siguientes(item.peldanos, saltos)
    if not nuevos:
        return []
    _guardar_peldanos(item, list(item.peldanos) + nuevos, session=session_item.session)
    session_item.peldanos_anadidos = nuevos
    session_item.save(update_fields=["peldanos_anadidos"])

    # Si completar la escalera lo dio por visto y estaba marcado para casa,
    # baja ya, igual que al dar por visto con el botón.
    if item.estado == GroupBookItem.VISTO and item.a_casa:
        libros_de_grupo.bajar_a_las_bibliotecas(session_item, item)
    return nuevos


def retroceder(session_item):
    """Deshace lo que el toque de «tratado» de esta clase añadió, y nada más."""
    quitar = list(session_item.peldanos_anadidos or [])
    if not quitar:
        return []
    fila = _fila_del_grupo(session_item)
    if fila is not None and fila.group_book.escalera is not None:
        _guardar_peldanos(fila, [c for c in fila.peldanos if c not in quitar])
    session_item.peldanos_anadidos = []
    session_item.save(update_fields=["peldanos_anadidos"])
    return quitar


def fijar(group_book, objeto, capitulo, claves, session=None):
    """Deja los peldaños trabajados exactamente en `claves` (los de la escalera).

    Es el camino de «fijar el punto de partida» desde la pantalla del libro y
    el de «elegir otro peldaño alcanzado» en el visor. Devuelve la fila, o None
    si el libro no tiene escalera.
    """
    from clases import libros_de_grupo

    escalera = group_book.escalera
    if escalera is None:
        return None
    validas = set(escalera.claves)
    item, _ = libros_de_grupo.excepcion(group_book, objeto, capitulo=capitulo)
    return _guardar_peldanos(item, [c for c in claves if c in validas], session=session)


def hasta(group_book, objeto, capitulo, clave, session=None):
    """Marca trabajados todos los peldaños hasta `clave` incluida (cumulativo).

    Es lo que hace un toque en la escalera del visor: «hemos llegado hasta
    aquí». Con `clave` vacía, ninguno.
    """
    escalera = group_book.escalera
    if escalera is None:
        return None
    claves = escalera.claves
    hasta_donde = claves.index(clave) + 1 if clave in claves else 0
    return fijar(group_book, objeto, capitulo, claves[:hasta_donde], session=session)


def anotar_filas(group_book, filas):
    """Le pone a cada fila de `enumerar` su escalera: `peldanos` (trabajados),
    `peldano` (el siguiente, como {clave, nombre, n, total}) o None."""
    escalera = group_book.escalera
    for fila in filas:
        if escalera is None or escalera.total == 0:
            fila["escalera"] = None
            fila["peldanos"] = []
            fila["peldano"] = None
            fila["dibujo"] = []
            continue
        trabajados = list(fila["item"].peldanos) if fila["item"] is not None else []
        siguiente = escalera.siguiente(trabajados)
        fila["escalera"] = escalera
        fila["peldanos"] = trabajados
        fila["peldano"] = (
            {
                "clave": siguiente,
                "nombre": escalera.nombre_de(siguiente),
                "n": escalera.indice(siguiente),
                "total": escalera.total,
            }
            if siguiente
            else None
        )
        fila["dibujo"] = escalera.dibujo(trabajados, siguiente)
    return filas


def guion(session):
    """Lo que enseña el modal «Guión» de la ficha de la sesión.

    Devuelve `{"secciones": [...], "en_curso": [...]}`. Las secciones van en el
    orden de la clase, con los extras sueltos al final; cada elemento lleva su
    estado en la escalera (o None) y el recuento de la fase 68. «En curso» son
    los elementos del grupo con algún peldaño trabajado y la escalera sin
    completar que NO están en la clase de hoy: es la foto que Jesús llevaba en
    la cabeza.
    """
    from clases import libros_de_grupo

    items = [i for i in session.get_items_ordered() if i.content_object]
    trabajados = trabajados_de_la_sesion(items)
    recuento = libros_de_grupo.recuento_en_clase(session.group)

    por_seccion = {clave: [] for clave, _ in SECCIONES_CLASE}
    extras = []
    for item in items:
        entrada = {
            "item": item,
            "titulo": item.get_content_title(),
            "icono": item.get_icon(),
            "escalera": estado_de(item, trabajados.get(item.pk)),
            "en_clase": recuento.get((item.content_type_id, item.object_id), {}),
        }
        (por_seccion.get(item.seccion) if item.seccion in por_seccion else extras).append(entrada)
    secciones = [
        {"clave": clave, "nombre": nombre, "items": por_seccion[clave]}
        for clave, nombre in SECCIONES_CLASE
        if por_seccion[clave]
    ]
    if extras:
        secciones.append({"clave": "", "nombre": "Extras", "items": extras})

    hoy = {(i.content_type_id, i.object_id) for i in items}
    en_curso = []
    for group_book in libros_de_grupo.libros_activos(session.group):
        if group_book.escalera is None or group_book.escalera.total == 0:
            continue
        escalera = group_book.escalera
        filas = (
            group_book.items.exclude(estado=GroupBookItem.VISTO)
            .select_related("content_type")
            .order_by("orden", "pk")
        )
        for fila in filas:
            if not fila.peldanos or (fila.content_type_id, fila.object_id) in hoy:
                continue
            objeto = fila.content_object
            if objeto is None:
                continue
            icono, titulo, _ = libros_de_grupo.describir(objeto)
            siguiente = escalera.siguiente(fila.peldanos)
            en_curso.append(
                {
                    "group_book": group_book,
                    "titulo": titulo,
                    "icono": icono,
                    "hechos": escalera.hechos(fila.peldanos),
                    "total": escalera.total,
                    "siguiente_nombre": escalera.nombre_de(siguiente),
                    "dibujo": escalera.dibujo(fila.peldanos, siguiente),
                }
            )
    return {"secciones": secciones, "en_curso": en_curso}
