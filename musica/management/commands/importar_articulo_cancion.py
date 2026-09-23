"""Convierte un borrador de artículo en una `RecursoPage` con sus dos lenguas.

El borrador es un Markdown que sigue `docs/PLANTILLA_ARTICULO_CANCION.md`: una
cabecera con los datos de la ficha, `## Versión en castellano` y
`## English version`. De ahí salen la entradilla, el cuerpo y la traducción, en
una sola pasada, que es justo lo que la fase 33 quería hacer sostenible.

**Nace como borrador, nunca publicado.** Estos textos llevan el minutaje de la
Escucha guiada sin comprobar, y publicar `⟨?:??⟩` en una página pública sería
peor que no tenerla. Publicar es un gesto humano, después de escuchar.

**Es idempotente por `slug`**: volver a pasarlo reescribe la misma página en vez
de crear una segunda. Así se puede corregir el Markdown y reimportar.

El conversor de Markdown es de andar por casa a propósito: solo entiende lo que
esta plantilla usa (encabezados, párrafos, listas, negrita, cursiva y el bloque
de escucha guiada), y el destino es un `RichTextField`, que no admite `<pre>`
ni `<table>`. Traer una dependencia para seis construcciones sería pagar de más.
"""

import os
from pathlib import Path

from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.images import get_image_model

from cms.etiquetas import aplicar_etiquetas
from musica.articulos import (
    CABECERA_EN,
    CABECERA_ES,
    _frontmatter,
    _seccion,
    partir_lengua,
)
from musica.models import MusicLibraryIndexPage, RecursoPage, RecursoTraduccion

# Los borradores viven fuera del repo (el remoto es público). Mismo sitio que
# usa scripts/publicar_cancion.py; se cambia con IES_ARTICULOS_DIR.
DIRECTORIO = Path(
    os.environ.get("IES_ARTICULOS_DIR", "~/Documents/articulos-ies")
).expanduser()

def imagen_de_portada(datos):
    """Crea (o encuentra) la imagen de portada del artículo.

    La imagen vive en el repo, ya convertida a WebP y a 1600 px de ancho: así
    la importación no depende de que Wikimedia conteste, y lo que se publica es
    exactamente lo que se revisó.

    **El crédito va en el título de la imagen y también en el texto del
    artículo.** Las licencias Creative Commons piden atribución visible para
    quien lee, y el título de una imagen de Wagtail no lo ve nadie.

    Idempotente por título: reimportar no llena la biblioteca de copias.
    """
    nombre = datos.get("imagen")
    if not nombre:
        return None
    Imagen = get_image_model()
    titulo = datos.get("imagen_titulo") or nombre
    existente = Imagen.objects.filter(title=titulo).first()
    if existente:
        return existente
    ruta = DIRECTORIO / "imagenes" / nombre
    if not ruta.exists():
        raise FileNotFoundError(f"No está la imagen {ruta}")
    with ruta.open("rb") as fichero:
        imagen = Imagen(title=titulo, file=ImageFile(fichero, name=nombre))
        imagen.save()
    return imagen


def resolver_imagen_desde_disco(url, alt, fuente):
    """Las imágenes del borrador, subidas desde `imagenes/` del propio repo.

    En el borrador se escriben con la ruta del fichero, no con una URL remota:
    importar no puede depender de que un servidor de fotos conteste, y lo que
    se publica tiene que ser exactamente lo que se revisó.
    """
    Imagen = get_image_model()
    titulo = fuente or alt or url
    existente = Imagen.objects.filter(title=titulo).first()
    if existente:
        return existente.id
    ruta = DIRECTORIO / "imagenes" / url
    if not ruta.exists():
        raise FileNotFoundError(f"No está la imagen {ruta}")
    with ruta.open("rb") as fichero:
        imagen = Imagen(title=titulo, file=ImageFile(fichero, name=url))
        imagen.save()
    return imagen.id


class Command(BaseCommand):
    help = "Importa borradores de artículo como RecursoPage en borrador, con sus dos lenguas."

    def add_arguments(self, parser):
        parser.add_argument("ficheros", nargs="*", help="Nombres dentro de IES_ARTICULOS_DIR (~/Documents/articulos-ies)")
        parser.add_argument("--aplicar", action="store_true", help="Escribe las páginas")
        parser.add_argument(
            "--publicar",
            action="store_true",
            help="Publica en vez de dejar en borrador. Solo con el minutaje comprobado",
        )

    def handle(self, *args, **options):
        nombres = options["ficheros"] or sorted(p.name for p in DIRECTORIO.glob("*.md"))
        padre = MusicLibraryIndexPage.objects.live().first()
        if padre is None:
            self.stdout.write(self.style.ERROR("No hay índice de recursos musicales."))
            return

        for nombre in nombres:
            ruta = DIRECTORIO / nombre
            if not ruta.exists():
                self.stdout.write(self.style.ERROR(f"No existe {ruta}"))
                continue
            datos, cuerpo = _frontmatter(ruta.read_text(encoding="utf-8"))
            bloque_es = _seccion(cuerpo, CABECERA_ES, CABECERA_EN)
            bloque_en = _seccion(cuerpo, CABECERA_EN)
            intro_es, body_es = partir_lengua(bloque_es, resolver_imagen_desde_disco)
            intro_en, body_en = partir_lengua(bloque_en, resolver_imagen_desde_disco)

            self.stdout.write(f"\n{datos['titulo']}  ({datos['slug']})")
            self.stdout.write(f"  castellano: entradilla {len(intro_es)} car., cuerpo {len(body_es)} car.")
            self.stdout.write(f"  inglés:     entradilla {len(intro_en)} car., cuerpo {len(body_en)} car.")
            self.stdout.write(f"  etiquetas:  {datos.get('etiquetas', '')}")
            self.stdout.write(f"  portada:    {datos.get('imagen', '(ninguna)')}")

            if not (intro_es and body_es and intro_en and body_en):
                self.stdout.write(self.style.ERROR("  Falta alguna de las dos lenguas. No se importa."))
                continue
            if not options["aplicar"]:
                continue

            with transaction.atomic():
                page = RecursoPage.objects.filter(slug=datos["slug"]).first()
                nueva = page is None
                if nueva:
                    page = RecursoPage(slug=datos["slug"])
                page.title = datos["titulo"]
                page.date = datos["fecha"]
                page.intro = intro_es[:250]
                page.body = body_es
                page.idioma = datos.get("idioma", "es")
                page.artist = datos.get("artista", "")
                for campo in ("key_fifths", "tempo_bpm", "duracion_segundos"):
                    valor = datos.get(campo)
                    destino = "duration_seconds" if campo == "duracion_segundos" else campo
                    if valor:
                        setattr(page, destino, int(valor))
                page.key_mode = datos.get("key_mode", "")
                portada = imagen_de_portada(datos)
                if portada:
                    page.featured_image = portada
                page.traducciones = [
                    RecursoTraduccion(idioma="en", intro=intro_en[:250], body=body_en)
                ]
                if nueva:
                    padre.add_child(instance=page)
                    page.live = False
                    page.save()
                else:
                    page.save()
                etiquetas = [e.strip() for e in datos.get("etiquetas", "").split(",") if e.strip()]
                if etiquetas:
                    aplicar_etiquetas(page, etiquetas)
                revision = page.save_revision()
                if options["publicar"]:
                    revision.publish()

            estado = "publicada" if options["publicar"] else "en borrador"
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {'Creada' if nueva else 'Actualizada'} {estado} — id {page.id}, /cms/pages/{page.id}/edit/"
                )
            )

        if not options["aplicar"]:
            self.stdout.write(self.style.WARNING("\nNo se ha escrito nada. Repite con --aplicar."))
