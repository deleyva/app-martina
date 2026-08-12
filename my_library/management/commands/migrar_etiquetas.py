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


class Command(BaseCommand):
    help = "Migra las etiquetas de taggit al formato faceta:valor"

    def add_arguments(self, parser):
        parser.add_argument("--mapa", default=str(MAPA_POR_DEFECTO))
        parser.add_argument(
            "--ejecutar",
            action="store_true",
            help="Aplica los cambios. Sin esto solo enseña qué haría.",
        )

    def handle(self, *args, **opciones):
        mapa = leer_mapa(opciones["mapa"])
        ejecutar = opciones["ejecutar"]

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

        self._resumen(renombres, fusiones, borrados, ausentes)

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

        self.stdout.write(self.style.SUCCESS("\nHecho."))

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
