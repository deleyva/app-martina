"""Pone el árbol de colecciones a la forma de las dos apps (fase 25).

El problema, medido antes de tocar nada: había 19 colecciones colgando de Root,
todas al mismo nivel, y una de ellas —«Música»— no era un departamento. Era el
vertedero de la biblioteca musical: 1.221 imágenes y 38 documentos, de los que
el índice de referencias atribuye 1.287 usos a páginas de `musica` y 8 a un
artículo de blog. Es decir, en el desplegable de «¿dónde subo esta imagen?»
convivían diecisiete departamentos y una aplicación entera, y había que elegir
entre «Música» y «Filosofía» como si fueran lo mismo.

Después:

    Root
    ├── Biblioteca musical      (la app: las 1.221 imágenes se quedan quietas)
    └── Blogs
        ├── Actividades Extraescolares
        ├── ...
        ├── Música              (nueva y vacía: el DEPARTAMENTO de música)
        └── Tecnología

Ni una imagen cambia de colección: «Música» se renombra a «Biblioteca musical»,
que es lo que siempre fue, y el departamento estrena una colección vacía.

Lo que sí hay que mover con cuidado son los permisos. «Jefe del departamento de
Música» y «Profesores de Música» apuntaban a la colección que ahora es la
biblioteca entera; si no se repuntan, el renombrado les regala permiso sobre las
1.221 imágenes de la app. Este comando los repunta a la colección nueva.

Idempotente: se puede volver a ejecutar.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.models import Collection, GroupCollectionPermission

BIBLIOTECA = "Biblioteca musical"
BLOGS = "Blogs"
DEPARTAMENTO_MUSICA = "Música"


class Command(BaseCommand):
    help = "Reordena las colecciones en Biblioteca musical + Blogs/<departamento>."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Enseña lo que haría y no toca nada.",
        )

    def handle(self, *args, **options):
        seco = options["dry_run"]
        root = Collection.objects.get(depth=1)

        with transaction.atomic():
            # El orden de los pasos importa. `Collection` es un árbol ORDENADO
            # (`node_order_by = ["name"]`), y treebeard NO reordena al renombrar:
            # si renombras primero, «Biblioteca musical» se queda en el hueco de
            # «Música» y el árbol deja de estar ordenado. La siguiente inserción
            # calcula entonces un `path` ya ocupado y todo revienta con un
            # IntegrityError sobre `path` que no menciona el orden por ningún
            # lado. Así que: mover primero, renombrar al final, con Root ya casi
            # vacío.
            root = Collection.objects.get(depth=1)

            # 1. El contenedor de los blogs.
            blogs = Collection.objects.filter(name=BLOGS, depth=2).first()
            if blogs is None:
                self.stdout.write(f"  crear «{BLOGS}»")
                if seco:
                    self.stdout.write(self.style.WARNING("  (dry-run: no se sigue)"))
                    return
                blogs = root.add_child(name=BLOGS)

            if seco:
                self.stdout.write(self.style.WARNING("  (dry-run: no se sigue)"))
                return

            # 2. Los departamentos, menos «Música», debajo de «Blogs».
            pks = list(
                Collection.objects.filter(depth=2)
                .exclude(pk=blogs.pk)
                .exclude(name=DEPARTAMENTO_MUSICA)
                .exclude(name=BIBLIOTECA)
                .order_by("name")
                .values_list("pk", flat=True)
            )
            for pk in pks:
                col = Collection.objects.get(pk=pk)
                self.stdout.write(f"  mover «{col.name}» bajo «{BLOGS}»")
                col.move(Collection.objects.get(pk=blogs.pk), pos="sorted-child")

            # 3. Ahora «Música» es casi el único hijo de Root: renombrarla a lo
            #    que de verdad es y recolocarla en su sitio del orden.
            biblioteca = Collection.objects.filter(name=BIBLIOTECA).first()
            if biblioteca is None:
                vieja = Collection.objects.filter(
                    name=DEPARTAMENTO_MUSICA, depth=2
                ).first()
                if vieja is not None:
                    self.stdout.write(
                        f"  renombrar «{DEPARTAMENTO_MUSICA}» -> «{BIBLIOTECA}» "
                        "(es la app, no el departamento)"
                    )
                    vieja.name = BIBLIOTECA
                    vieja.save()
                    Collection.objects.get(pk=vieja.pk).move(
                        Collection.objects.get(pk=root.pk), pos="sorted-child"
                    )
                    biblioteca = Collection.objects.get(pk=vieja.pk)
                else:
                    self.stdout.write(f"  crear «{BIBLIOTECA}»")
                    biblioteca = Collection.objects.get(pk=root.pk).add_child(
                        name=BIBLIOTECA
                    )

            # 4. El departamento de música estrena colección propia y vacía.
            blogs = Collection.objects.get(pk=blogs.pk)
            depto = Collection.objects.filter(
                name=DEPARTAMENTO_MUSICA, path__startswith=blogs.path
            ).exclude(pk=blogs.pk).first()
            if depto is None:
                self.stdout.write(f"  crear «{DEPARTAMENTO_MUSICA}» bajo «{BLOGS}»")
                depto = blogs.add_child(name=DEPARTAMENTO_MUSICA)

            # 5. Repuntar los permisos del departamento de música.
            #    Sin esto, el renombrado del paso 3 les regala la biblioteca
            #    entera: 1.221 imágenes que no son suyas.
            biblioteca = Collection.objects.get(pk=biblioteca.pk)
            movidos = GroupCollectionPermission.objects.filter(
                collection=biblioteca,
                group__name__in=[
                    f"Jefe del departamento de {DEPARTAMENTO_MUSICA}",
                    f"Profesores de {DEPARTAMENTO_MUSICA}",
                ],
            )
            n = movidos.count()
            movidos.update(collection=depto)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {n} permisos del departamento de música repuntados de "
                    f"«{BIBLIOTECA}» a «{BLOGS} > {DEPARTAMENTO_MUSICA}»"
                )
            )

        self.stdout.write("\n=== árbol resultante ===")
        for c in Collection.objects.all():
            self.stdout.write("   " + c.get_indented_name())
