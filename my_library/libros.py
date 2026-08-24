"""Meter un libro entero en la biblioteca de una vez.

Un libro es una `BlogIndexPage` con capítulos `BlogPage` debajo. Lo que se
practica no es el capítulo: son los medios que lleva dentro — las imágenes de
las partituras, los PDF, los audios. La convención ya existía y se ve en los
datos: los 23 elementos del libro de Jens Larsen son las imágenes de sus
capítulos, cada una con su capítulo en `source_page`.

**El problema que resuelve:** hasta ahora se añadían de uno en uno, con un botón
por medio. *Ukulele Aerobics* tiene 40 capítulos y estaba entero fuera de la
biblioteca, porque meterlo costaba cuarenta y pico clics.

**El orden importa y sale gratis.** Los elementos se crean recorriendo los
capítulos en el orden del árbol de Wagtail y, dentro de cada uno, en el orden en
que aparecen los medios. Como la cola de estudio ordena lo nuevo por pk, un
libro metido así entra en el orden del libro sin necesitar nada más. Para los
libros que ya estaban dentro eso era una casualidad; para estos, no.
"""

from django.contrib.contenttypes.models import ContentType

from my_library.models import LibraryItem


def capitulos_de(libro):
    """Los capítulos publicados del libro, en el orden del libro."""
    from cms.models import BlogPage

    return list(BlogPage.objects.child_of(libro).live().order_by("path"))


def material_de(capitulo):
    """Los medios practicables de un capítulo, en el orden en que aparecen.

    Imágenes primero porque son el caso mayoritario y las que llevan la
    partitura; después los PDF y los audios. `get_images` ya mezcla las de
    los bloques adjuntos con las incrustadas en el texto, que son las que de
    verdad usan estos libros: el capítulo 1 de Jens Larsen tiene cero bloques
    y dieciséis imágenes dentro del cuerpo.
    """
    objetos = list(capitulo.get_images() or [])

    for bloque in capitulo.get_pdf_blocks() or []:
        documento = bloque.get("pdf_file") if hasattr(bloque, "get") else None
        if documento:
            objetos.append(documento)

    for bloque in capitulo.get_audios() or []:
        documento = bloque.get("audio_file") if hasattr(bloque, "get") else None
        if documento:
            objetos.append(documento)

    return [o for o in objetos if o is not None]


def material_del_libro(libro):
    """[(capitulo, objeto)] de todo el libro, en orden de libro."""
    salida = []
    for capitulo in capitulos_de(libro):
        for objeto in material_de(capitulo):
            salida.append((capitulo, objeto))
    return salida


def meter_libro(user, libro):
    """Mete el libro entero en la biblioteca. Devuelve (creados, ya_estaban).

    Idempotente: `LibraryItem` es único por (usuario, tipo, objeto), así que
    volver a pulsar no duplica nada. Importa que no duplique de verdad y no
    solo que no reviente: un elemento repetido saldría dos veces en la cola.
    """
    creados = ya_estaban = 0
    for capitulo, objeto in material_del_libro(libro):
        _, creado = LibraryItem.objects.get_or_create(
            user=user,
            content_type=ContentType.objects.get_for_model(objeto),
            object_id=objeto.pk,
            defaults={"source_page": capitulo},
        )
        if creado:
            creados += 1
        else:
            ya_estaban += 1
    return creados, ya_estaban


def _ya_vistos(user, libro):
    """{(content_type_id, object_id)} del material del libro que ya tiene fila.

    Incluye los descartados a propósito: la lápida existe justamente para que
    el objetivo no vuelva a ofrecerlos.
    """
    from my_library.models import LibraryItem

    return set(
        LibraryItem.objects.filter(user=user, source_page__in=capitulos_de(libro))
        .values_list("content_type_id", "object_id")
    )


def siguiente_del_objetivo(user, libro, cuantos=1):
    """Crea y devuelve los siguientes elementos del libro, en orden de libro.

    Esta es la creación perezosa: hasta que un elemento no toca, no existe.
    Se salta lo que ya tiene fila, descartado incluido, así que la cola avanza
    por el libro y no se atasca en lo que el principal ya dijo que no.
    """
    from my_library.models import LibraryItem

    vistos = _ya_vistos(user, libro)
    nuevos = []
    for capitulo, objeto in material_del_libro(libro):
        if len(nuevos) >= cuantos:
            break
        tipo = ContentType.objects.get_for_model(objeto)
        if (tipo.pk, objeto.pk) in vistos:
            continue
        item, _ = LibraryItem.objects.get_or_create(
            user=user,
            content_type=tipo,
            object_id=objeto.pk,
            defaults={"source_page": capitulo},
        )
        vistos.add((tipo.pk, objeto.pk))
        nuevos.append(item)
    return nuevos


def progreso(user, libro):
    """(capitulos_tocados, capitulos_totales) del libro.

    Un capítulo cuenta como tocado en cuanto uno de sus elementos tiene al menos
    un repaso. Es lo que responde a "por dónde voy": «Semana 12 de 40».
    """
    from my_library.models import LibraryItem, ReviewLog

    capitulos = capitulos_de(libro)
    con_repaso = set(
        ReviewLog.objects.filter(
            item__in=LibraryItem.objects.filter(
                user=user, source_page__in=capitulos
            )
        ).values_list("item__source_page_id", flat=True)
    )
    return len(con_repaso), len(capitulos)


def rellenar_para_sesion(user, cuota):
    """Crea material nuevo desde los objetivos activos, si hace falta.

    La cuota de novedad de la sesión es una cuarta parte (fase 5) y no se toca:
    el objetivo decide QUÉ entra, no cuánto. Esto solo se asegura de que haya
    material sin practicar disponible cuando la biblioteca se ha quedado seca,
    que es exactamente el caso de un libro recién puesto como objetivo.

    Devuelve los elementos creados.
    """
    from my_library.models import LibraryGoal, LibraryItem, ReviewLog

    practicados = set(
        ReviewLog.objects.filter(user=user).values_list("item_id", flat=True)
    )
    sin_tocar = (
        LibraryItem.objects.filter(user=user, descartado=False)
        .exclude(pk__in=practicados)
        .count()
    )
    faltan = cuota - sin_tocar
    if faltan <= 0:
        return []

    creados = []
    for objetivo in LibraryGoal.objects.filter(user=user, activo=True):
        if faltan <= 0:
            break
        nuevos = siguiente_del_objetivo(user, objetivo.libro.specific, faltan)
        creados.extend(nuevos)
        faltan -= len(nuevos)
    return creados


def contexto_en_el_libro(item, palabras=60):
    """(texto, titulo_capitulo, url_capitulo) de dónde sale este elemento.

    Responde a "¿qué era esto?" sin salir de la sesión. El texto es el párrafo
    que rodea a la imagen en el cuerpo del capítulo: en estos libros las
    imágenes van incrustadas en el texto, así que lo que hay justo antes es la
    explicación del ejercicio.

    Devuelve `(None, None, None)` si el elemento no viene de una página, que es
    el caso de lo que se añadió suelto desde el índice.
    """
    from bs4 import BeautifulSoup

    if not item.source_page_id:
        return None, None, None

    capitulo = item.source_page.specific
    url = capitulo.url
    titulo = capitulo.title
    cuerpo = getattr(capitulo, "body", None)
    if not cuerpo:
        return None, titulo, url

    soup = BeautifulSoup(cuerpo, "html.parser")
    marca = soup.find("embed", embedtype="image", id=str(item.object_id))
    if marca is None:
        return None, titulo, url

    # El párrafo de antes explica el ejercicio; el de después, si lo hay, suele
    # comentarlo. Se cogen los dos y se recorta, que es lo que cabe en una
    # ventana sin taparte la partitura.
    trozos = []
    anterior = marca.find_previous(["p", "h2", "h3", "li"])
    if anterior is not None:
        trozos.append(anterior.get_text(" ", strip=True))
    siguiente = marca.find_next(["p", "h2", "h3", "li"])
    if siguiente is not None:
        trozos.append(siguiente.get_text(" ", strip=True))

    texto = " ".join(t for t in trozos if t)
    if not texto:
        return None, titulo, url

    corte = texto.split()
    if len(corte) > palabras:
        texto = " ".join(corte[:palabras]) + "…"
    return texto, titulo, url
