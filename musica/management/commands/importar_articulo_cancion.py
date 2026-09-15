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

import html
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from cms.etiquetas import aplicar_etiquetas
from musica.models import MusicLibraryIndexPage, RecursoPage, RecursoTraduccion

# Relativo a este fichero, no a `settings`: `APPS_DIR` de cookiecutter apunta al
# paquete interno, y ahí no vive `musica/`.
DIRECTORIO = Path(__file__).resolve().parents[3] / "musica" / "data" / "articulos"

CABECERA_ES = "## Versión en castellano"
CABECERA_EN = "## English version"
# Dentro de cada lengua, la entradilla es el primer apartado y va al campo
# `intro`; el cuerpo empieza en el siguiente.
APARTADO_ENTRADILLA = ("Entradilla", "Intro line")


def _frontmatter(texto):
    """`---\\nclave: valor\\n---` al principio del fichero."""
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if not m:
        raise ValueError("El borrador no empieza por un bloque `---` de datos")
    datos = {}
    for linea in m.group(1).splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            datos[clave.strip()] = valor.strip()
    return datos, texto[m.end():]


def _seccion(texto, cabecera, siguiente=None):
    """El trozo entre una cabecera `##` y la siguiente."""
    inicio = texto.find(cabecera)
    if inicio == -1:
        return ""
    inicio += len(cabecera)
    fin = texto.find(siguiente, inicio) if siguiente else -1
    return texto[inicio:fin if fin != -1 else len(texto)].strip()


def _en_linea(texto):
    """Negrita, cursiva y escapado. El orden importa: primero se escapa."""
    texto = html.escape(texto, quote=False)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"(?<![\*\w])\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", texto)
    texto = re.sub(r"`([^`\n]+?)`", r"\1", texto)
    return texto


def _bloque_escucha(lineas):
    """El bloque cercado de la Escucha guiada, a lista.

    Una línea nueva empieza entrada nueva; las sangradas continúan la anterior,
    porque en el Markdown están partidas para que quepan a 79 columnas.
    """
    entradas = []
    for linea in lineas:
        if not linea.strip():
            continue
        if linea.startswith((" ", "\t")) and entradas:
            entradas[-1] += " " + linea.strip()
        else:
            entradas.append(linea.strip())
    items = []
    for entrada in entradas:
        m = re.match(r"^(⟨\?:\?\?⟩|\d+:\d\d)\s+(.*)$", entrada)
        if m:
            items.append(f"<li><b>{_en_linea(m.group(1))}</b> {_en_linea(m.group(2))}</li>")
        else:
            items.append(f"<li>{_en_linea(entrada)}</li>")
    return "<ul>" + "".join(items) + "</ul>"


def markdown_a_richtext(texto):
    """El subconjunto que usa la plantilla. `###` pasa a `<h2>`: en el artículo
    esos apartados son los de primer nivel; el `##` es la lengua, que no se
    pinta."""
    salida = []
    parrafo = []
    lista = []
    cercado = None

    def cerrar_parrafo():
        if parrafo:
            salida.append(f"<p>{_en_linea(' '.join(parrafo).strip())}</p>")
            parrafo.clear()

    def cerrar_lista():
        if lista:
            salida.append("<ul>" + "".join(f"<li>{_en_linea(x)}</li>" for x in lista) + "</ul>")
            lista.clear()

    for linea in texto.splitlines():
        if linea.startswith("```"):
            if cercado is None:
                cerrar_parrafo()
                cerrar_lista()
                cercado = []
            else:
                salida.append(_bloque_escucha(cercado))
                cercado = None
            continue
        if cercado is not None:
            cercado.append(linea)
            continue

        if not linea.strip():
            cerrar_parrafo()
            cerrar_lista()
            continue
        if linea.startswith("### "):
            cerrar_parrafo()
            cerrar_lista()
            salida.append(f"<h2>{_en_linea(linea[4:].strip())}</h2>")
            continue
        if linea.startswith("> "):
            continue  # notas para el profesor, no van a la página
        if re.match(r"^\d+\.\s", linea):
            cerrar_parrafo()
            lista.append(re.sub(r"^\d+\.\s", "", linea).strip())
            continue
        if linea.startswith("- "):
            cerrar_parrafo()
            lista.append(linea[2:].strip())
            continue
        if linea.startswith("|") or linea.startswith("---"):
            continue  # la tabla de la ficha es para ti, no para el alumnado
        parrafo.append(linea.strip())

    cerrar_parrafo()
    cerrar_lista()
    return "".join(salida)


def partir_lengua(bloque):
    """(entradilla, cuerpo) de un bloque de una sola lengua."""
    apartados = re.split(r"(?m)^### ", bloque)
    entradilla, cuerpo = "", []
    for apartado in apartados:
        if not apartado.strip():
            continue
        titulo, _, resto = apartado.partition("\n")
        if titulo.strip() in APARTADO_ENTRADILLA:
            entradilla = " ".join(l.strip() for l in resto.strip().splitlines() if l.strip())
        else:
            cuerpo.append("### " + apartado.rstrip())
    return entradilla, markdown_a_richtext("\n".join(cuerpo))


class Command(BaseCommand):
    help = "Importa borradores de artículo como RecursoPage en borrador, con sus dos lenguas."

    def add_arguments(self, parser):
        parser.add_argument("ficheros", nargs="*", help="Nombres dentro de musica/data/articulos")
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
            intro_es, body_es = partir_lengua(bloque_es)
            intro_en, body_en = partir_lengua(bloque_en)

            self.stdout.write(f"\n{datos['titulo']}  ({datos['slug']})")
            self.stdout.write(f"  castellano: entradilla {len(intro_es)} car., cuerpo {len(body_es)} car.")
            self.stdout.write(f"  inglés:     entradilla {len(intro_en)} car., cuerpo {len(body_en)} car.")
            self.stdout.write(f"  etiquetas:  {datos.get('etiquetas', '')}")

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
