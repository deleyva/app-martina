"""Pone `idioma` a los grupos de la bilingüe, con la lista delante.

El nombre del grupo **no** es el esquema: `Group.idioma` existe justo para que
renombrar un grupo no le borre la lengua. Pero para el trabajo de una vez al
curso —marcar los cuatro o cinco grupos que vienen en inglés— el nombre es la
mejor pista que hay, y verla escrita antes de escribir nada cuesta cero.

Sin `--aplicar` solo enseña la lista. Con `--grupos` se pasan los nombres
exactos y el nombre deja de opinar.
"""

from django.core.management.base import BaseCommand

from clases.models import Group


class Command(BaseCommand):
    help = "Marca en inglés los grupos de la bilingüe. Sin --aplicar, solo lista."

    def add_arguments(self, parser):
        parser.add_argument(
            "--grupos",
            default="",
            help="Nombres exactos separados por comas. Si falta, busca «bil» en el nombre",
        )
        parser.add_argument(
            "--curso",
            default="",
            help="Curso académico, ej: 2026-2027. Si falta, todos",
        )
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Escribe idioma=en en los grupos listados",
        )

    def handle(self, *args, **options):
        qs = Group.todos.all()
        if options["curso"]:
            qs = qs.filter(academic_year=options["curso"])

        nombres = [n.strip() for n in options["grupos"].split(",") if n.strip()]
        if nombres:
            qs = qs.filter(name__in=nombres)
            no_encontrados = set(nombres) - set(qs.values_list("name", flat=True))
            if no_encontrados:
                self.stdout.write(
                    self.style.ERROR(
                        f"No existe ningún grupo con estos nombres: "
                        f"{', '.join(sorted(no_encontrados))}"
                    )
                )
                return
        else:
            qs = qs.filter(name__icontains="bil")

        grupos = sorted(qs, key=lambda g: (g.academic_year, g.name))
        if not grupos:
            self.stdout.write(self.style.WARNING("Ningún grupo encaja."))
            return

        self.stdout.write(f"Grupos que se marcarían en inglés: {len(grupos)}")
        for g in grupos:
            alumnos = g.enrollments.filter(is_active=True).count()
            marca = "ya está" if g.idioma == "en" else "es → en"
            self.stdout.write(
                f"  {g.academic_year} · {g.name} · {alumnos} alumnos · {marca}"
            )

        if not options["aplicar"]:
            self.stdout.write(
                self.style.WARNING(
                    "\nNo se ha escrito nada. Repite con --aplicar si la lista es esa."
                )
            )
            return

        escritos = 0
        for g in grupos:
            if g.idioma != "en":
                g.idioma = "en"
                g.save(update_fields=["idioma"])
                escritos += 1
        self.stdout.write(self.style.SUCCESS(f"\nMarcados {escritos} grupos."))
