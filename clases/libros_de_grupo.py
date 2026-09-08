"""El motor de libros de `my_library`, aplicado a los grupos.

Un grupo tiene libros asignados (`GroupBook`), cada uno con su sitio en el orden
fijo de la clase. Preparar una sesión es recorrer las secciones en ese orden y
pedirle a cada libro activo su siguiente elemento pendiente.

**Nada de esto copia material.** El material se enumera al vuelo desde la página
del libro con `my_library.libros`, y lo único que se guarda es lo que el
profesor decide que se salga del defecto: excluir, recolocar, dar por visto o
marcar que baja a las bibliotecas del alumnado. Un libro recién asignado son
cero filas en `GroupBookItem`.

Los dos tipos de libro valen, y sale gratis: `capitulos_de` distingue por
capacidad y no por tipo, así que un `LibroPage` con páginas hijas se recorre por
el árbol y un `LibroDeEstudioPage` por sus referencias.
"""

from django.contrib.contenttypes.models import ContentType

from clases.models import (
    ClassSessionItem,
    GroupBook,
    GroupBookItem,
    SECCIONES_CLASE,
)
from my_library.libros import material_del_libro


def _clave(objeto):
    """(content_type, object_id) de un medio, que es como se referencia todo."""
    return ContentType.objects.get_for_model(objeto), objeto.pk


def _excepciones(group_book):
    """{(content_type_id, object_id): GroupBookItem} de lo que este grupo tocó.

    Una consulta para todo el libro. Recorrer el material preguntando fila a
    fila daría una consulta por medio, y los libros grandes pasan de 200.
    """
    return {
        (item.content_type_id, item.object_id): item
        for item in group_book.items.select_related("content_type")
    }


AUDIO = (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac")


def describir(objeto):
    """(icono, titulo, tipo) de un medio, para pintarlo en una lista.

    Vive aquí y no en la plantilla porque distinguir un PDF de un audio exige
    mirar la extensión del fichero: los dos son `Document` de Wagtail, y un
    `{% if %}` en la plantilla no puede hacer esa pregunta.
    """
    nombre = objeto.__class__.__name__.lower()
    titulo = getattr(objeto, "title", None) or str(objeto)

    if nombre == "document" and getattr(objeto, "file", None):
        fichero = objeto.file.name.lower()
        if fichero.endswith(AUDIO):
            return "🎵", titulo, "Audio"
        if fichero.endswith(".pdf"):
            return "📄", titulo, "PDF"
        return "📎", titulo, "Documento"

    iconos = {
        "image": ("🖼️", "Imagen"),
        "embed": ("▶️", "Vídeo"),
    }
    icono, tipo = iconos.get(nombre, ("📁", nombre.title()))
    if nombre == "embed":
        titulo = getattr(objeto, "title", None) or getattr(objeto, "url", "") or titulo
    return icono, titulo, tipo


def enumerar(group_book):
    """El libro entero tal y como lo ve ESTE grupo, en su orden efectivo.

    Devuelve `[{capitulo, objeto, tipo, orden_libro, orden, item}]`, donde
    `item` es la fila de excepción si existe y `None` si el elemento sigue en su
    defecto. Es lo que pinta la pantalla de selección, que necesita ver también
    lo excluido y lo ya visto para poder deshacerlo.

    **El orden efectivo es `orden` si el grupo lo fijó, y si no el del libro.**
    Así, recolocar unos pocos elementos no obliga a escribir una fila por cada
    uno de los que nadie ha tocado.
    """
    excepciones = _excepciones(group_book)
    filas = []
    for orden_libro, (capitulo, objeto) in enumerate(material_del_libro(group_book.libro)):
        tipo, pk = _clave(objeto)
        item = excepciones.get((tipo.pk, pk))
        icono, titulo, tipo_legible = describir(objeto)
        filas.append(
            {
                "capitulo": capitulo,
                "objeto": objeto,
                "tipo": tipo,
                "orden_libro": orden_libro,
                "orden": orden_libro if item is None or item.orden is None else item.orden,
                "item": item,
                "icono": icono,
                "titulo": titulo,
                "tipo_legible": tipo_legible,
            }
        )
    filas.sort(key=lambda f: (f["orden"], f["orden_libro"]))
    return filas


def siguientes(group_book, cuantos=1):
    """Lo siguiente que este grupo tiene pendiente de este libro.

    Se salta lo excluido y lo dado por visto. Un libro en modo `en_curso` no se
    comporta distinto aquí: la diferencia entre los dos modos no está en qué
    elemento toca, sino en cuándo el libro deja de proponer —el secuencial se
    agota al llegar al final, y el que está en curso lo cierra el profesor
    marcándolo inactivo.
    """
    salida = []
    for fila in enumerar(group_book):
        if len(salida) >= cuantos:
            break
        item = fila["item"]
        if item is not None and not item.propuesto:
            continue
        salida.append(fila)
    return salida


def excepcion(group_book, objeto, capitulo=None, **campos):
    """La fila de excepción de un elemento, creándola solo si hace falta.

    Es el único sitio por el que nacen filas en `GroupBookItem`, y por eso el
    invariante "un libro sin tocar son cero filas" se sostiene mirando aquí.
    """
    tipo, pk = _clave(objeto)
    item, creado = GroupBookItem.objects.get_or_create(
        group_book=group_book,
        content_type=tipo,
        object_id=pk,
        defaults={"source_page": capitulo},
    )
    if campos:
        for nombre, valor in campos.items():
            setattr(item, nombre, valor)
        item.save(update_fields=list(campos) + ["updated_at"])
    return item, creado


def recolocar(group_book, claves_ordenadas):
    """Fija el orden de este libro PARA ESTE GRUPO.

    `claves_ordenadas` son `(content_type_id, object_id)` en el orden deseado.

    Es la única operación que escribe muchas filas de golpe, y es a propósito:
    un orden es una lista, y guardar solo los que se movieron dejaría el resto
    dependiendo del orden del libro, que puede cambiar debajo. Está acotado por
    el tamaño del libro y solo ocurre cuando alguien recoloca a mano.
    """
    por_clave = {(f["tipo"].pk, f["objeto"].pk): f for f in enumerar(group_book)}
    for posicion, clave in enumerate(claves_ordenadas):
        fila = por_clave.get(clave)
        if fila is None:
            continue
        excepcion(group_book, fila["objeto"], capitulo=fila["capitulo"], orden=posicion)


def libros_activos(group):
    """Los libros vivos del grupo, en el orden de la clase.

    El orden se calcula sobre `SECCIONES_CLASE` y no con un `order_by` sobre el
    texto de la sección: ordenar por el valor guardado daría alfabético
    —cancion, dictado, instrumento…— que no es el orden de ninguna clase.
    """
    claves = [clave for clave, _ in SECCIONES_CLASE]
    activos = group.books.filter(activo=True).select_related("libro")
    return sorted(
        activos,
        key=lambda gb: (
            claves.index(gb.seccion) if gb.seccion in claves else len(claves),
            gb.created_at,
        ),
    )


def _ya_en_la_sesion(session):
    """{(content_type_id, object_id)} de lo que la sesión ya tiene."""
    if session is None:
        return set()
    return {(i.content_type_id, i.object_id) for i in session.items.all()}


def previsualizar_sesion(group, secciones=None, por_libro=1, session=None):
    """Lo que `preparar_sesion` metería, sin meterlo.

    Lo comparten la vista previa y la preparación de verdad, que es la única
    forma de que la vista previa no mienta: con dos recorridos distintos
    acabarían discrepando en cuanto uno de los dos cambiara.

    `session` descuenta lo que ya está en la clase. Sin esto, la vista previa
    seguía ofreciendo los tres elementos recién añadidos —estar en una sesión no
    los da por vistos— y prometía un trabajo que el botón no iba a hacer.
    """
    puestos = _ya_en_la_sesion(session)
    propuesta = []
    for group_book in libros_activos(group):
        if secciones is not None and group_book.seccion not in secciones:
            continue
        # Se piden de más y se filtra, para que un elemento ya puesto no deje a
        # su libro sin propuesta: sin esto, el libro cuyo siguiente ya está en la
        # clase desaparecería de la vista previa en vez de ofrecer el de después.
        candidatas = [
            f for f in siguientes(group_book, por_libro + len(puestos))
            if (f["tipo"].pk, f["objeto"].pk) not in puestos
        ]
        for fila in candidatas[:por_libro]:
            propuesta.append({"group_book": group_book, **fila})
    return propuesta


def preparar_sesion(session, secciones=None, por_libro=1):
    """Monta la sesión con el siguiente pendiente de cada sección activa.

    Devuelve los `ClassSessionItem` creados. Es idempotente en lo que importa:
    un elemento que ya está en la sesión no se mete dos veces, así que volver a
    pulsar el botón no duplica la clase.

    Los extras que el profesor haya añadido a mano no se tocan: llevan
    `group_book = None` y conservan su orden.
    """
    orden = session.get_next_order()
    creados = []
    # La vista previa ya descuenta lo que la sesión tiene; esto cubre el choque
    # DENTRO de la misma tanda, que pasa cuando dos libros referencian la misma
    # página —una canción puede estar en varios libros a la vez, que es
    # justamente para lo que existen los libros por referencia.
    puestos = set()
    for propuesta in previsualizar_sesion(session.group, secciones, por_libro, session):
        tipo, pk = propuesta["tipo"], propuesta["objeto"].pk
        if (tipo.pk, pk) in puestos:
            continue
        puestos.add((tipo.pk, pk))
        creados.append(
            ClassSessionItem.objects.create(
                session=session,
                content_type=tipo,
                object_id=pk,
                source_page=propuesta["capitulo"],
                group_book=propuesta["group_book"],
                seccion=propuesta["group_book"].seccion,
                order=orden,
            )
        )
        orden += 1
    return creados


def marcar_visto(session_item, visto=True):
    """Da por visto un elemento de la clase, y avanza el libro si venía de uno.

    Dos escrituras que responden a dos preguntas distintas: la sesión guarda
    "hoy llegamos a verlo" y el libro guarda "no hace falta volver a
    proponérselo a este grupo". Un extra suelto (`group_book = None`) solo tiene
    la primera, que es exactamente lo que se pidió: los extras no ensucian los
    libros.

    Reversible: desmarcar devuelve el elemento a la cola. En clase se dan toques
    por error, y sin vuelta atrás el profesor deja de marcar por miedo.
    """
    session_item.visto = visto
    session_item.save(update_fields=["visto"])

    if session_item.group_book_id is None or session_item.content_object is None:
        return None

    item, _ = excepcion(
        session_item.group_book,
        session_item.content_object,
        capitulo=session_item.source_page,
        estado=GroupBookItem.VISTO if visto else GroupBookItem.PENDIENTE,
        visto_en=session_item.session if visto else None,
    )
    return item


def progreso(group_book):
    """(vistos, total) de este libro para este grupo, para la barra de avance."""
    filas = enumerar(group_book)
    vistos = sum(
        1
        for f in filas
        if f["item"] is not None and f["item"].estado == GroupBookItem.VISTO
    )
    return vistos, len(filas)


def libros_disponibles():
    """Las páginas que pueden asignarse como libro a un grupo.

    Los dos tipos, y por eso se piden por separado y se juntan: `LibroPage`
    agrupa por árbol y `LibroDeEstudioPage` por referencia. El segundo es el que
    permite que una canción esté en varios libros a la vez.
    """
    from musica.models import LibroDeEstudioPage, LibroPage

    por_arbol = list(LibroPage.objects.live().order_by("title"))
    por_referencia = list(LibroDeEstudioPage.objects.live().order_by("title"))
    return por_arbol + por_referencia
