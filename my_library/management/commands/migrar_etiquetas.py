"""Migra el vocabulario de etiquetas a facetas `faceta:valor`.

taggit es GLOBAL en todo el sitio: la misma etiqueta la usan la biblioteca, el
blog y los documentos. Renombrar aquí cambia el nombre en todas partes, así que
el comando NO hace nada sin `--ejecutar` y todo va dentro de una transacción.

    just manage migrar_etiquetas                    # en seco, enseña qué haría
    just manage migrar_etiquetas --ejecutar         # lo hace de verdad

El mapa vive en `my_library/migracion/mapa_etiquetas.txt` y es un fichero de
texto pensado para revisarse a mano antes de ejecutar nada.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from taggit.models import Tag, TaggedItem

BORRAR = "__BORRAR__"


def slug_para(nombre, excluir_pk=None):
    """Slug único para una etiqueta renombrada.

    taggit solo genera el slug al CREAR (`if self._state.adding and not
    self.slug`), nunca al renombrar. Dejarlo vacío hacía que dos etiquetas
    renombradas chocaran contra `taggit_tag_slug_key`.

    Los dos puntos se convierten en guion antes de slugificar: si no,
    `estilo:jazz` daría `estilojazz` en vez de `estilo-jazz`.
    """
    base = slugify(nombre.replace(":", "-")) or "etiqueta"
    slug, n = base, 2
    while Tag.objects.filter(slug=slug).exclude(pk=excluir_pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug
MAPA_POR_DEFECTO = (
    Path(__file__).resolve().parent.parent.parent / "migracion" / "mapa_etiquetas.txt"
)


def leer_mapa(ruta):
    """Devuelve {origen: destino}. Ignora comentarios y líneas sueltas."""
    mapa = {}
    for numero, linea in enumerate(Path(ruta).read_text().splitlines(), start=1):
        linea = linea.split("#")[0].strip()
        if not linea:
            continue
        if "->" not in linea:
            raise CommandError(f"Línea {numero} sin '->': {linea!r}")
        origen, _, destino = linea.partition("->")
        origen, destino = origen.strip(), destino.strip()
        if not origen or not destino:
            continue
        mapa[origen] = destino
    return mapa


def nombres_de_etiqueta_vivos(mapa):
    """Los orígenes del mapa que TODAVÍA existen como etiqueta.

    Hasta C37c había dos vocabularios que consultar y esta función unía los dos.
    Con `cms.MusicTag` retirado queda uno: `taggit.Tag`, global del sitio.
    """
    return set(
        Tag.objects.filter(name__in=list(mapa)).values_list("name", flat=True)
    )


def planificar_mazos(mapa, vivos):
    """[(mazo, tags_viejos, tags_nuevos, huerfano)] de los mazos que cambian.

    Un `LibraryDeck` guarda su filtro como una lista de NOMBRES en `tags_json`,
    y el emparejamiento es comparación de cadenas. Renombrar la fila de `Tag`
    no lo toca: el mazo se queda apuntando a un nombre que ya no existe y pasa
    a contar 0 en silencio. Eso es justo lo que pasó el 2026-08-12.

    Se aplica el MAPA, no el estado de `Tag`, y por eso la reparación funciona
    sobre mazos que se quedaron atrás en una ejecución anterior. Es idempotente
    porque ningún destino del mapa es a su vez un origen.

    `vivos` es la salvaguarda: nombres que SIGUEN existiendo como etiqueta y por
    tanto NO se tocan. El defecto es que un mazo apunte a un nombre MUERTO; si
    el nombre sigue vivo no hay nada que arreglar, y reescribirlo rompería un
    mazo que funciona. Pasa de verdad: una etiqueta plana borrada por el
    renombrado puede volver a nacer después, al etiquetar material nuevo con el
    nombre viejo. Al migrar de verdad este conjunto queda vacío — los orígenes
    acaban de desaparecer — así que arrastra todo, que es lo que se quiere.

    `huerfano` marca los mazos que se quedarían SIN NINGUNA etiqueta porque
    todas las suyas van a `__BORRAR__`. A esos no se les toca: un mazo vacío no
    filtra nada y `get_matching_item_pks` devuelve la biblioteca entera. Un
    mazo que enseña 0 está visiblemente roto; uno que enseña 51 miente.
    """
    from my_library.models import LibraryDeck

    indice = {}
    for origen, destino in mapa.items():
        clave = origen.lower()
        if indice.get(clave, destino) != destino:
            raise CommandError(
                f"El mapa tiene dos orígenes que solo difieren en mayúsculas "
                f"({clave!r}) apuntando a destinos distintos."
            )
        indice[clave] = destino

    vivos_lower = {n.lower() for n in vivos}

    plan = []
    for mazo in LibraryDeck.objects.select_related("user").order_by("pk"):
        viejos = mazo.get_tags()
        nuevos = []
        for tag in viejos:
            if tag.lower() in vivos_lower:
                destino = tag  # sigue existiendo: no es un puntero muerto
            else:
                destino = indice.get(tag.lower(), tag)
            if destino == BORRAR:
                continue
            if destino not in nuevos:  # el renombrado puede fusionar dos en uno
                nuevos.append(destino)
        if nuevos == viejos:
            continue
        plan.append((mazo, viejos, nuevos, not nuevos))
    return plan


def facetas_desconocidas(mapa):
    """{faceta: [ejemplos]} de destinos cuya faceta no existe.

    Sin esta comprobación el renombrado funciona igual, pero la etiqueta queda
    muerta: `facets.parse` no la reconoce, así que no agrupa ni filtra. Falla
    en silencio, que es la peor forma de fallar.
    """
    from my_library import facets

    encontradas = {}
    for origen, destino in sorted(mapa.items()):
        if destino == BORRAR or facets.SEPARADOR not in destino:
            continue
        if facets.parse(destino)[0] is None:
            faceta = destino.split(facets.SEPARADOR)[0]
            encontradas.setdefault(faceta, []).append(f"{origen} -> {destino}")
    return encontradas


class Command(BaseCommand):
    help = "Migra las etiquetas de taggit al formato faceta:valor"

    def add_arguments(self, parser):
        parser.add_argument("--mapa", default=str(MAPA_POR_DEFECTO))
        parser.add_argument(
            "--ejecutar",
            action="store_true",
            help="Aplica los cambios. Sin esto solo enseña qué haría.",
        )
        parser.add_argument(
            "--solo-mazos",
            action="store_true",
            help=(
                "Solo arrastra los mazos, sin tocar ninguna etiqueta. Para "
                "reparar mazos que se quedaron atrás en una ejecución previa."
            ),
        )

    def handle(self, *args, **opciones):
        mapa = leer_mapa(opciones["mapa"])
        ejecutar = opciones["ejecutar"]
        solo_mazos = opciones["solo_mazos"]

        if solo_mazos:
            # Reparación sobre una base ya migrada: lo que siga existiendo con
            # el nombre viejo es una etiqueta viva, no un puntero muerto.
            plan_mazos = planificar_mazos(mapa, nombres_de_etiqueta_vivos(mapa))
            self._resumen_mazos(plan_mazos)
            if not ejecutar:
                self.stdout.write(
                    self.style.WARNING(
                        "\nEN SECO — no se ha tocado nada. "
                        "Añade --ejecutar para aplicarlo."
                    )
                )
                return
            with transaction.atomic():
                self._aplicar_mazos(plan_mazos)
            self.stdout.write(self.style.SUCCESS("\nHecho."))
            return

        desconocidas = facetas_desconocidas(mapa)
        if desconocidas:
            for faceta, ejemplos in sorted(desconocidas.items()):
                self.stdout.write(
                    self.style.ERROR(f"Faceta desconocida {faceta!r}: {ejemplos[0]}")
                )
            raise CommandError(
                "Hay destinos con facetas que no existen en facets.FACETAS. "
                "El renombrado funcionaría, pero la biblioteca las trataría como "
                "etiquetas planas: no agruparían ni filtrarían. Añade la faceta a "
                "facets.FACETAS o corrige el mapa."
            )

        renombres, fusiones, borrados, ausentes = [], [], [], []

        # Agrupar por destino ANTES de clasificar. Si no, dos orígenes que
        # apuntan al mismo destino se clasifican los dos como renombrado —
        # ninguno de los dos ve al otro, porque el destino aún no existe — y el
        # segundo revienta contra la restricción de unicidad de taggit.
        por_destino = {}
        for origen, destino in sorted(mapa.items()):
            if Tag.objects.filter(name=origen).exists():
                por_destino.setdefault(destino, []).append(origen)
            else:
                ausentes.append(origen)

        def _usos(nombre):
            return TaggedItem.objects.filter(tag__name=nombre).count()

        for destino, origenes in sorted(por_destino.items()):
            if destino == BORRAR:
                borrados.extend((o, _usos(o)) for o in origenes)
                continue

            # Si el destino ya existe tal cual, todos los orígenes se fusionan
            # en él. Si no, el primero se renombra y el resto se fusionan
            # en ese recién renombrado.
            ya_existe = Tag.objects.filter(name=destino).exclude(
                name__in=origenes
            ).exists()

            pendientes = list(origenes)
            if not ya_existe:
                primero = max(pendientes, key=_usos)  # el más usado conserva su fila
                pendientes.remove(primero)
                renombres.append((primero, destino, _usos(primero)))

            fusiones.extend((o, destino, _usos(o)) for o in pendientes)

        # Al migrar de verdad, todos los orígenes del mapa desaparecen de
        # taggit en esta misma transacción, así que no sobrevive ninguno y el
        # arrastre alcanza a todos los mazos. Antes de C37c aquí se pasaban los
        # nombres vivos en `MusicTag`, el otro vocabulario, que ya no existe.
        plan_mazos = planificar_mazos(mapa, set())

        self._resumen(renombres, fusiones, borrados, ausentes)
        self._resumen_mazos(plan_mazos)

        if not ejecutar:
            self.stdout.write(
                self.style.WARNING(
                    "\nEN SECO — no se ha tocado nada. "
                    "Añade --ejecutar para aplicarlo."
                )
            )
            return

        with transaction.atomic():
            for origen, destino, _ in renombres:
                etiqueta = Tag.objects.get(name=origen)
                etiqueta.name = destino
                etiqueta.slug = slug_para(destino, excluir_pk=etiqueta.pk)
                etiqueta.save()

            for origen, destino, _ in fusiones:
                self._fusionar(origen, destino)

            for origen, _ in borrados:
                Tag.objects.filter(name=origen).delete()

            # Dentro de la misma transacción que el renombrado: si los mazos no
            # se pueden arrastrar, tampoco se renombra nada. Quedarse a medias
            # es precisamente el estado del que venimos.
            self._aplicar_mazos(plan_mazos)

        self.stdout.write(self.style.SUCCESS("\nHecho."))

    def _aplicar_mazos(self, plan):
        for mazo, _viejos, nuevos, huerfano in plan:
            if huerfano:
                continue
            mazo.set_tags(nuevos)
            mazo.save(update_fields=["tags_json"])

    def _fusionar(self, origen, destino):
        """Mueve los usos de `origen` a `destino` y borra `origen`.

        Mismo cuidado que la fusión del admin: se comprueba que no queda ni un
        uso colgando antes de borrar, y si queda algo se aborta la transacción
        entera en vez de perder etiquetados por el camino.
        """
        viejo = Tag.objects.get(name=origen)
        nuevo = Tag.objects.get(name=destino)

        for etiquetado in list(TaggedItem.objects.filter(tag=viejo)):
            ya_esta = TaggedItem.objects.filter(
                tag=nuevo,
                content_type=etiquetado.content_type,
                object_id=etiquetado.object_id,
            ).exists()
            if ya_esta:
                etiquetado.delete()
            else:
                etiquetado.tag = nuevo
                etiquetado.save()

        restantes = TaggedItem.objects.filter(tag=viejo).count()
        if restantes:
            raise CommandError(
                f"Fusión abortada: quedan {restantes} usos en {origen!r}. "
                "No se ha aplicado ningún cambio."
            )
        viejo.delete()

    def _resumen(self, renombres, fusiones, borrados, ausentes):
        w = self.stdout.write
        if renombres:
            w(self.style.SUCCESS(f"\nRENOMBRAR ({len(renombres)})"))
            for origen, destino, usos in renombres:
                w(f"  {origen}  ->  {destino}   [{usos} usos]")
        if fusiones:
            w(self.style.WARNING(f"\nFUSIONAR ({len(fusiones)}) — el destino ya existe"))
            for origen, destino, usos in fusiones:
                w(f"  {origen}  ->  {destino}   [{usos} usos se mueven]")
        if borrados:
            w(self.style.ERROR(f"\nBORRAR ({len(borrados)})"))
            for origen, usos in borrados:
                w(f"  {origen}   [{usos} usos se pierden]")
        if ausentes:
            w(f"\nYa no existen en la base de datos ({len(ausentes)}), se ignoran.")

    def _resumen_mazos(self, plan):
        w = self.stdout.write
        arrastrados = [f for f in plan if not f[3]]
        huerfanos = [f for f in plan if f[3]]
        if not plan:
            w("\nMAZOS: ninguno cambia.")
            return
        if arrastrados:
            w(self.style.SUCCESS(f"\nMAZOS A ARRASTRAR ({len(arrastrados)})"))
            for mazo, viejos, nuevos, _ in arrastrados:
                w(f"  {mazo.user.email} / {mazo.name!r}")
                w(f"      {viejos}  ->  {nuevos}")
        if huerfanos:
            w(self.style.ERROR(f"\nMAZOS QUE QUEDARÍAN VACÍOS ({len(huerfanos)}) — NO se tocan"))
            for mazo, viejos, _, _ in huerfanos:
                w(f"  {mazo.user.email} / {mazo.name!r}  tags={viejos}")
            w(
                "  Todas sus etiquetas van a __BORRAR__. Vaciar el filtro haría "
                "que el mazo enseñara la biblioteca entera; se dejan rotos a la "
                "vista para que se decida a mano."
            )
