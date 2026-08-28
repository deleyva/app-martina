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
    """Los capítulos publicados del libro, en el orden del libro.

    Conviven DOS formas de libro, a propósito:

    - **Por árbol.** Un índice con páginas colgando debajo. Es como llegaron los
      libros importados (Jens Larsen, CAGED). El orden es el `path` de
      treebeard, o sea el que se ve y se arrastra en el explorador de Wagtail.
    - **Por referencia.** `LibroDeEstudioPage` apunta a páginas que viven en
      otro sitio del árbol. Es la única forma de que una canción esté en varios
      libros a la vez: en Wagtail una página tiene UN padre y su URL sale de
      ahí, así que agrupar por el árbol obliga a elegir un solo libro para
      siempre. El orden es el de los bloques.

    Se distinguen por capacidad y no por `isinstance` para no atar `my_library`
    a un tipo concreto de `cms`: cualquier página que sepa decir qué páginas
    referencia se comporta como un libro por referencia.
    """
    from cms.models import BlogPage

    referencias = getattr(libro, "paginas_referenciadas", None)
    if callable(referencias):
        return referencias()
    return list(BlogPage.objects.child_of(libro).live().order_by("path"))


def _incrustado_en_el_cuerpo(pagina):
    """Lo que va dentro del texto, en orden ESTRICTO de aparición.

    Imágenes y embeds mezclados según dónde estén escritos, que es como se lee
    la página. `get_images()` no vale para esto: devuelve primero los adjuntos
    y luego el cuerpo, así que pierde justo el orden que aquí importa.

    Los embeds (YouTube, Vimeo…) se resuelven a `wagtail.embeds.models.Embed`,
    que es un modelo con pk y por tanto puede ser el contenido de un
    `LibraryItem` — la biblioteca ya guarda embeds así desde antes.
    """
    cuerpo = getattr(pagina, "body", None)
    if not cuerpo or "<embed" not in cuerpo:
        return []

    from bs4 import BeautifulSoup
    from wagtail.embeds.embeds import get_embed
    from wagtail.embeds.exceptions import EmbedException
    from wagtail.images import get_image_model

    sopa = BeautifulSoup(cuerpo, "html.parser")
    etiquetas = sopa.find_all("embed")

    # Las imágenes se resuelven en UNA consulta, no una por etiqueta.
    Imagen = get_image_model()
    ids = [t.get("id") for t in etiquetas if t.get("embedtype") == "image" and t.get("id")]
    imagenes = {str(i.pk): i for i in Imagen.objects.filter(pk__in=ids)} if ids else {}

    salida = []
    for etiqueta in etiquetas:
        tipo = etiqueta.get("embedtype")
        if tipo == "image":
            imagen = imagenes.get(str(etiqueta.get("id")))
            if imagen is not None:
                salida.append(imagen)
        elif tipo == "media" and etiqueta.get("url"):
            try:
                # Puede pegarle a la red la primera vez; después va de la BD.
                salida.append(get_embed(etiqueta["url"]))
            except EmbedException:
                # Un embed que el proveedor ya no sirve no puede tumbar el libro.
                continue
    return salida


def _de_los_adjuntos(pagina):
    """Los adjuntos del StreamField, por tipo y en el orden en que se pusieron.

    Se piden con `getattr` porque no todas las páginas referenciables tienen
    los mismos accesores: `BlogPage` y `ScorePage` sí, `DictadoPage` no ninguno.
    """
    salida = []

    def _acceso(nombre):
        metodo = getattr(pagina, nombre, None)
        return list(metodo() or []) if callable(metodo) else []

    salida.extend(_acceso("get_images"))
    for campo, nombre in (
        ("pdf_file", "get_pdf_blocks"),
        ("audio_file", "get_audios"),
        ("video_file", "get_videos"),
    ):
        for bloque in _acceso(nombre):
            documento = bloque.get(campo) if hasattr(bloque, "get") else None
            if documento is not None:
                salida.append(documento)
    return salida


def material_de(capitulo):
    """Los medios practicables de un capítulo, en orden de aparición.

    **Primero el cuerpo, luego los adjuntos** (decisión del principal,
    2026-08-27). Dentro del cuerpo el orden es estricto: imágenes y embeds
    salen según dónde estén escritos, porque ahí es donde está el hilo con el
    que se explica la pieza.

    Los dos grupos NO se pueden entrelazar, y conviene que quede dicho: el
    cuerpo y los adjuntos son campos distintos del modelo, sin ningún orden
    común entre ellos. Cuál va primero es una regla elegida, no un dato que se
    pueda leer de la página.

    Se deduplica porque `get_images()` devuelve adjuntos Y cuerpo mezclados: sin
    esto, una imagen incrustada saldría dos veces, y la segunda con el orden
    equivocado.
    """
    objetos, vistos = [], set()
    for objeto in list(_incrustado_en_el_cuerpo(capitulo)) + list(_de_los_adjuntos(capitulo)):
        if objeto is None:
            continue
        clave = (objeto.__class__.__name__, objeto.pk)
        if clave in vistos:
            continue
        vistos.add(clave)
        objetos.append(objeto)
    return objetos


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

    **El `orden` es una foto del momento de crear.** Reordenar el libro después
    cambia el orden de lo que quede por crear, no el de lo ya creado. Para el
    uso normal —montar el libro y luego estudiarlo— es lo correcto y es barato;
    recalcularlo en cada sesión obligaría a recorrer todo el material del libro,
    parseando el StreamField y el RichText de cada capítulo, en cada carga.
    """
    from my_library.models import LibraryItem

    nuevos = []
    for capitulo, objeto, tipo, orden in candidatos_del_objetivo(user, libro, cuantos):
        item, _ = LibraryItem.objects.get_or_create(
            user=user,
            content_type=tipo,
            object_id=objeto.pk,
            defaults={
                "source_page": capitulo,
                "orden": orden,
                "libro": libro if _por_referencia(libro) else None,
            },
        )
        nuevos.append(item)
    return nuevos


def _por_referencia(libro):
    """`libro` solo se guarda en los libros por REFERENCIA: en los de árbol se
    deduce del path del padre, y guardarlo en unos sí y en otros no partiría en
    dos el grupo de un mismo libro. Ver `session._libro_de`."""
    return callable(getattr(libro, "paginas_referenciadas", None))


def candidatos_del_objetivo(user, libro, cuantos):
    """`[(capitulo, objeto, content_type, orden)]` de lo siguiente del libro.

    El recorrido, sin crear nada. Lo comparten la creación y la vista previa,
    que es la única forma de que la vista previa no mienta: si cada una hiciera
    su propio recorrido, acabarían discrepando.
    """
    vistos = _ya_vistos(user, libro)
    salida = []
    # El índice de la enumeración COMPLETA es el ordinal: cuenta también lo que
    # se salta, que es lo que hace que el hueco de un elemento ya creado o
    # descartado no desplace a los que vienen detrás.
    for n, (capitulo, objeto) in enumerate(material_del_libro(libro)):
        if len(salida) >= cuantos:
            break
        tipo = ContentType.objects.get_for_model(objeto)
        if (tipo.pk, objeto.pk) in vistos:
            continue
        vistos.add((tipo.pk, objeto.pk))
        salida.append((capitulo, objeto, tipo, n))
    return salida


def previsualizar_relleno(user, cuota, seleccion=None, solo_libros=None):
    """Los elementos que `rellenar_para_sesion` crearía, SIN crearlos.

    Devuelve `LibraryItem` **sin guardar**, para que la vista previa monte la
    sesión exactamente igual que la montará el lanzamiento: se le pasan a
    `construir_sesion` junto a los reales y todo lo demás funciona igual.

    El pk negativo no es un truco sucio, es el requisito: `construir_sesion`
    usa el pk como clave para agrupar y ordenar, y `None` chocaría entre sí en
    cuanto hubiera dos. Negativo y decreciente los mantiene únicos, distintos
    de cualquier real, y en el orden en que se crearían. Nada del camino de
    lectura llama a `save()`.

    Se marcan con `es_nuevo` para que la plantilla pueda decir cuáles van a
    aparecer al empezar.
    """
    from my_library.models import LibraryItem

    items, siguiente_pk = [], -1
    for libro, cuantos in reparto_del_relleno(user, cuota, seleccion, solo_libros):
        for capitulo, objeto, tipo, orden in candidatos_del_objetivo(
            user, libro, cuantos
        ):
            item = LibraryItem(
                pk=siguiente_pk,
                user=user,
                content_type=tipo,
                object_id=objeto.pk,
                source_page=capitulo,
                orden=orden,
                libro=libro if _por_referencia(libro) else None,
            )
            item.es_nuevo = True
            items.append(item)
            siguiente_pk -= 1
    return items


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


def _sin_tocar_del_libro(user, libro, practicados):
    """Cuántos elementos DE ESTE LIBRO tiene el usuario sin practicar todavía."""
    from my_library.models import LibraryItem

    return (
        LibraryItem.objects.filter(
            user=user, descartado=False, source_page__in=capitulos_de(libro)
        )
        .exclude(pk__in=practicados)
        .count()
    )


def facetas_del_libro(libro):
    """Las etiquetas facetadas que describen este libro.

    Son las de sus capítulos, que es donde viven de verdad: desde C37c las
    páginas etiquetan en `faceted_tags`, y un libro de piano lo es porque sus
    capítulos llevan `instrumento:piano`. Se suman también las del propio
    índice del libro si las tuviera, que hoy no es el caso de ningún tipo de
    página pero cuesta una línea y evita una sorpresa.
    """
    etiquetas = set()
    propias = getattr(libro, "faceted_tags", None)
    if propias is not None:
        etiquetas |= {t.name.lower() for t in propias.all()}
    for capitulo in capitulos_de(libro):
        etiquetas |= {t.name.lower() for t in capitulo.faceted_tags.all()}
    return etiquetas


def casa_con_la_seleccion(libro, seleccion):
    """¿Este libro es de lo que se ha elegido estudiar hoy?

    Misma regla que `session.filtrar_por_facetas`, y a propósito: Y entre
    facetas, O dentro de cada faceta. Una selección vacía no filtra nada.
    """
    from my_library import facets

    seleccion = {f: set(v) for f, v in (seleccion or {}).items() if v}
    if not seleccion:
        return True
    del_libro = facets.por_faceta(facetas_del_libro(libro))
    return all(del_libro.get(f, set()) & valores for f, valores in seleccion.items())


def rellenar_para_sesion(user, cuota, seleccion=None, solo_libros=None):
    """Crea material nuevo desde los objetivos activos, si hace falta.

    La cuota de novedad de la sesión es una cuarta parte (fase 5) y no se toca:
    el objetivo decide QUÉ entra, no cuánto. Esto solo se asegura de que haya
    material sin practicar disponible cuando la biblioteca se ha quedado seca.

    **Se mide por objetivo, no sobre la biblioteca entera.** Medirlo global era
    un defecto real, no una simplificación: el 2026-08-25, con dos objetivos
    puestos, el usuario tenía 28 elementos sin tocar —13 de un libro sin
    objetivo y 12 sueltos del índice— así que `cuota - sin_tocar` salía en
    negativo y esto devolvía `[]` **en cada sesión**. La creación perezosa
    estaba de hecho apagada, y ningún objetivo podía aportar nada. Un elemento
    suelto de hace meses no satisface la intención "quiero estudiarme CAGED".

    **Con varios objetivos, cada uno mantiene su propia reserva** de
    `techo(cuota / nº objetivos)` elementos sin tocar. Así ningún libro con
    material acumulado tapa a los demás: es la mitad de "alternar la cuota".
    La otra mitad está en `session.construir_sesion`, que reparte la novedad
    entre libros al ELEGIR — sin las dos, un libro con trece pendientes se
    queda con todos los huecos de novedad de todas las sesiones.

    **Y respeta el filtro de facetas de la sesión** (decisión del principal,
    2026-08-26: *"el filtro debería frenar también la creación. No quiero
    material acumulado"*). Antes esto corría antes del filtro y sin saber nada
    de él: elegir piano dejaba la sesión de piano, sí, pero ese mismo día se
    creaba material de los libros de guitarra, que se caía del filtro y se
    quedaba en la biblioteca sin tocar. Un mes estudiando solo piano dejaba las
    guitarras con material nuevo que nadie había pedido, compitiendo luego en
    las sesiones sin filtrar. Es la misma clase de defecto que la fase 12.

    Con el filtro puesto, la reserva se reparte entre los objetivos QUE CASAN:
    eligiendo piano con un solo libro de piano, sus tres huecos son suyos.

    Devuelve los elementos creados.
    """
    return [
        item
        for libro, cuantos in reparto_del_relleno(user, cuota, seleccion, solo_libros)
        for item in siguiente_del_objetivo(user, libro, cuantos)
    ]


def reparto_del_relleno(user, cuota, seleccion=None, solo_libros=None):
    """`[(libro, cuantos)]` — qué objetivo aporta cuánto. SIN efectos.

    Se extrajo de `rellenar_para_sesion` para que la vista previa use la MISMA
    aritmética que la creación en vez de una copia parecida. Una vista previa
    que calcula distinto que lo que va a pasar no es una vista previa: es otra
    respuesta a la misma pregunta, y tarde o temprano se contradicen.
    """
    from my_library.models import LibraryGoal, ReviewLog

    if cuota <= 0:
        return []

    objetivos = list(
        LibraryGoal.objects.filter(user=user, activo=True).order_by("created_at", "pk")
    )
    # Elegir un libro concreto es un filtro más fuerte que las facetas: dice
    # exactamente qué objetivo puede aportar hoy, sin aproximar por etiquetas.
    if solo_libros:
        objetivos = [o for o in objetivos if o.libro_id in set(solo_libros)]
    objetivos = [
        o for o in objetivos if casa_con_la_seleccion(o.libro.specific, seleccion)
    ]
    if not objetivos:
        return []

    practicados = set(
        ReviewLog.objects.filter(user=user).values_list("item_id", flat=True)
    )
    libros = {o.pk: o.libro.specific for o in objetivos}
    disponible = {
        o.pk: _sin_tocar_del_libro(user, libros[o.pk], practicados) for o in objetivos
    }

    # Reserva POR OBJETIVO, no un déficit global. Medido en producción el
    # 2026-08-25 con tres objetivos: la suma de material sin tocar de objetivo
    # era 15 y la cuota 2, así que un déficit global daba -13 y no se creaba
    # nada — con CAGED a cero. Un objetivo con trece elementos pendientes
    # tapaba a los otros dos. Cada objetivo mantiene ahora su propia reserva.
    reserva = -(-cuota // len(objetivos))  # techo de la división
    reparto = []
    for objetivo in objetivos:
        faltan = reserva - disponible[objetivo.pk]
        if faltan > 0:
            # Si el libro se ha acabado dará menos de lo pedido, y ya está: la
            # reserva es un techo por objetivo, no una cuota que llenar.
            reparto.append((libros[objetivo.pk], faltan))
    return reparto


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
