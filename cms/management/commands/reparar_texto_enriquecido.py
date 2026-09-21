"""Busca las páginas que el editor de Wagtail no puede abrir, y las endereza.

El síntoma es un 500 al pulsar «editar», y el correo de error dice «End of
block reached without closing inline style elements» (o `entity`). La causa y
la reparación están explicadas en `cms/texto_enriquecido.py`.

    python manage.py reparar_texto_enriquecido            # solo mira
    python manage.py reparar_texto_enriquecido --escribir # repara

**Mira en dos sitios, y hacen falta los dos.** La página de edición carga la
ÚLTIMA REVISIÓN, no el campo publicado (`get_latest_revision_as_object`), así
que arreglar solo el campo deja el 500 intacto. Y arreglar solo la revisión
deja el HTML torcido esperando a la próxima publicación.
"""

from django.core.management.base import BaseCommand
from wagtail.fields import RichTextField
from wagtail.models import Page

from cms.texto_enriquecido import el_editor_lo_abre, reparar, texto_visible


class Command(BaseCommand):
    help = "Repara el texto enriquecido que hace reventar la página de edición"

    def add_arguments(self, parser):
        parser.add_argument(
            "--escribir",
            action="store_true",
            help="Guarda los arreglos. Sin esto solo informa.",
        )
        parser.add_argument(
            "--pk",
            type=int,
            default=None,
            help="Mirar una sola página, por su id.",
        )

    def handle(self, *args, **opciones):
        escribir = opciones["escribir"]
        solo = opciones["pk"]

        if not escribir:
            self.stdout.write(self.style.WARNING("EN SECO: no se guarda nada.\n"))

        paginas = Page.objects.all()
        if solo:
            paginas = paginas.filter(pk=solo)

        revisados = arregladas = fallidas = 0

        for pagina in paginas.iterator():
            try:
                especifica = pagina.specific
            except Exception:  # noqa: BLE001 — una página huérfana no debe parar el barrido
                continue

            campos = [
                f.name
                for f in especifica._meta.get_fields()
                if isinstance(f, RichTextField)
            ]
            if not campos:
                continue
            revisados += len(campos)

            revision = especifica.get_latest_revision()
            arreglos_campo = {}
            arreglos_revision = {}

            for campo in campos:
                # 1) el campo publicado
                valor = getattr(especifica, campo, None)
                if valor and not el_editor_lo_abre(valor):
                    nuevo = self._reparar_y_comprobar(pagina, campo, valor, "campo")
                    if nuevo is None:
                        fallidas += 1
                    else:
                        arreglos_campo[campo] = nuevo

                # 2) la última revisión, que es lo que abre el editor
                if revision is None:
                    continue
                guardado = (revision.content or {}).get(campo)
                if guardado and not el_editor_lo_abre(guardado):
                    nuevo = self._reparar_y_comprobar(pagina, campo, guardado, "revisión")
                    if nuevo is None:
                        fallidas += 1
                    else:
                        arreglos_revision[campo] = nuevo

            if not arreglos_campo and not arreglos_revision:
                continue

            arregladas += 1
            self.stdout.write(
                f"  pk={pagina.pk} «{pagina.title}» "
                f"campo:{sorted(arreglos_campo)} revisión:{sorted(arreglos_revision)}"
            )

            if not escribir:
                continue

            if arreglos_campo:
                for campo, nuevo in arreglos_campo.items():
                    setattr(especifica, campo, nuevo)
                especifica.save(update_fields=list(arreglos_campo))
            if arreglos_revision:
                for campo, nuevo in arreglos_revision.items():
                    revision.content[campo] = nuevo
                revision.save(update_fields=["content"])

        self.stdout.write("")
        self.stdout.write(f"Campos revisados: {revisados}")
        self.stdout.write(f"Páginas con algo que arreglar: {arregladas}")
        if fallidas:
            self.stdout.write(
                self.style.ERROR(
                    f"Sin arreglar (la reparación no bastó): {fallidas}. "
                    "Esas se quedan como estaban."
                )
            )
        if arregladas and not escribir:
            self.stdout.write(
                self.style.WARNING("Nada guardado. Repite con --escribir.")
            )

    def _reparar_y_comprobar(self, pagina, campo, valor, donde):
        """Repara, y **solo devuelve el arreglo si de verdad lo arregla**.

        Dos comprobaciones antes de dar nada por bueno: que el editor lo abra y
        que el texto visible sea el mismo. Escribir un arreglo sin comprobarlo
        sería cambiar un 500 por una página mutilada, que es peor porque no
        avisa.
        """
        nuevo = reparar(valor)
        if not el_editor_lo_abre(nuevo):
            self.stdout.write(
                self.style.ERROR(
                    f"  pk={pagina.pk} {campo} ({donde}): sigue sin abrirse tras reparar"
                )
            )
            return None
        if texto_visible(nuevo) != texto_visible(valor):
            self.stdout.write(
                self.style.ERROR(
                    f"  pk={pagina.pk} {campo} ({donde}): la reparación cambia el texto"
                )
            )
            return None
        return nuevo
