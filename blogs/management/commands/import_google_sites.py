"""Traer un sitio de Google Sites a un departamento de `blogs.iesmartinabescos.es`.

    just manage import_google_sites URL --departamento tecnologia --dry-run
    just manage import_google_sites URL --departamento tecnologia
    just manage import_google_sites URL --departamento tecnologia \\
        --titulo "inicio=Profesorado del departamento" --fijar programaciones

Cada página del sitio pasa a ser un artículo del departamento. Los PDF que el
sitio enlaza en Drive se bajan al servidor, las imágenes también, y los enlaces
entre páginas del sitio pasan a apuntar a los artículos nuevos.

Se puede relanzar: una página ya importada se reconoce por `source_url` y se
salta. No toca ningún artículo existente y no borra nada.

Hereda de `import_blogspot` para usar exactamente las mismas descargas (Drive,
imágenes, colecciones) y la misma limpieza de HTML: lo que cambia entre un blog
de Blogspot y un sitio de Sites es cómo se lee, no cómo se guarda.
"""

from __future__ import annotations

import urllib.error

from bs4 import BeautifulSoup
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone
from wagtail.models import Collection

from blogs.blogspot import derivar_intro, limpiar_cuerpo
from blogs.google_sites import (
    enlaces_internos,
    extraer_pagina,
    prefijo_del_sitio,
    reescribir_enlaces_internos,
    ruta_interna,
    slug_de_ruta,
    url_canonica,
)
from blogs.management.commands.import_blogspot import Command as ImportBlogspot
from blogs.management.commands.import_blogspot import Informe, _get
from blogs.models import ArticuloPage, BlogIndexPage

MAX_PAGINAS = 200


def _pares(valores, opcion):
    """`["ruta=Título", ...]` -> `{ruta: título}`."""
    pares = {}
    for valor in valores or []:
        ruta, separador, titulo = valor.partition("=")
        if not separador or not ruta.strip() or not titulo.strip():
            raise CommandError(f"{opcion} espera RUTA=TÍTULO y recibió «{valor}».")
        pares[ruta.strip().strip("/")] = titulo.strip()
    return pares


class Command(ImportBlogspot):
    help = "Importa un sitio de Google Sites como artículos de un departamento de blogs"

    def add_arguments(self, parser):
        parser.add_argument("url", help="Dirección de cualquier página del sitio.")
        parser.add_argument(
            "--departamento", required=True,
            help="Slug del departamento de destino (p. ej. `tecnologia`).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Lee el sitio y cuenta lo que haría, sin escribir ni bajar ficheros.",
        )
        parser.add_argument(
            "--draft", action="store_true",
            help="Crea los artículos sin publicar. Por defecto entran publicados.",
        )
        parser.add_argument(
            "--titulo", action="append", metavar="RUTA=TÍTULO",
            help="Título del artículo para esa página, en vez del que trae. Repetible.",
        )
        parser.add_argument(
            "--fijar", action="append", metavar="RUTA", default=[],
            help="Deja esa página fijada en el departamento («Siempre a mano»). Repetible.",
        )
        parser.add_argument(
            "--saltar", action="append", metavar="RUTA", default=[],
            help="No importa esa página. Repetible.",
        )

    # -- leer el sitio ----------------------------------------------------

    def _leer_sitio(self, url: str, prefijo: str) -> dict[str, str]:
        """`ruta -> html` de todas las páginas alcanzables desde `url`."""
        inicial = ruta_interna(url, prefijo)
        if inicial is None:
            # Dieron la raíz del sitio: Google redirige a su portada, y el
            # menú de esa portada trae todas las demás.
            html = _get(f"https://sites.google.com{prefijo}")
            pendientes = enlaces_internos(html, prefijo)
        else:
            pendientes = [inicial]

        paginas: dict[str, str] = {}
        rotas: set[str] = set()
        while pendientes:
            ruta = pendientes.pop(0)
            if ruta in paginas or ruta in rotas:
                continue
            if len(paginas) >= MAX_PAGINAS:
                raise CommandError(f"El sitio tiene más de {MAX_PAGINAS} páginas; no sigo.")
            try:
                paginas[ruta] = _get(url_canonica(prefijo, ruta))
            except urllib.error.HTTPError as exc:
                if exc.code != 404 or ruta == inicial:
                    raise CommandError(f"No pude leer «{ruta}» (HTTP {exc.code}).") from exc
                # Un enlace del sitio a una página que ya borraron: no es
                # motivo para dejar sin importar las que sí existen.
                self.stdout.write(self.style.WARNING(f"    «{ruta}» está enlazada pero no existe (404)"))
                rotas.add(ruta)
                continue
            except (urllib.error.URLError, OSError) as exc:
                raise CommandError(
                    f"No pude leer «{ruta}» ({type(exc).__name__}). Si el sitio pide "
                    f"iniciar sesión, hay que publicarlo para cualquiera con el enlace."
                ) from exc
            pendientes += [r for r in enlaces_internos(paginas[ruta], prefijo) if r not in paginas]
        return paginas

    # -- guardar ----------------------------------------------------------

    def _coleccion_del_departamento(self, departamento: BlogIndexPage) -> Collection:
        """`Blogs > Departamento`, que es donde su profesorado tiene permisos.

        Importa dónde caen los ficheros: una programación es de un curso, y
        quien tiene que sustituirla en septiembre es el departamento, no quien
        lanzó el importador.
        """
        blogs = Collection.objects.filter(name="Blogs", depth=2).first()
        if blogs is not None:
            propia = blogs.get_children().filter(name=departamento.title).first()
            if propia is not None:
                return propia
        return self._coleccion(f"Google Sites — {departamento.title}")

    def _traer_imagenes(self, soup: BeautifulSoup, titulo: str, coleccion, informe: Informe):
        for etiqueta in soup.find_all("img"):
            src = (etiqueta.get("src") or "").strip()
            alt = (etiqueta.get("alt") or "").strip()
            imagen = self._descargar_imagen(src, alt or titulo, coleccion, informe) if src else None
            if imagen is None:
                etiqueta.decompose()  # nunca dejar el `src` apuntando a Google
                continue
            embed = soup.new_tag("embed")
            embed.attrs = {
                "embedtype": "image",
                "id": str(imagen.pk),
                # Una imagen estrecha (un logotipo, un icono) a todo el ancho
                # del artículo queda desproporcionada.
                "format": "fullwidth" if imagen.width >= 1000 and imagen.width < 3 * imagen.height else "left",
                "alt": alt or titulo[:200],
            }
            etiqueta.replace_with(embed)

    def handle(self, *args, **opciones):
        self._documentos_vistos = {}
        try:
            prefijo = prefijo_del_sitio(opciones["url"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        departamento = BlogIndexPage.objects.filter(slug=opciones["departamento"]).first()
        if departamento is None:
            raise CommandError(
                f"No existe el departamento «{opciones['departamento']}». "
                f"Créalo en Wagtail antes de importar."
            )

        titulos = _pares(opciones["titulo"], "--titulo")
        fijar = {r.strip("/") for r in opciones["fijar"]}
        saltar = {r.strip("/") for r in opciones["saltar"]}
        seco = opciones["dry_run"]
        publicar = not opciones["draft"]
        informe = Informe()

        paginas = self._leer_sitio(opciones["url"], prefijo)

        # Una ruta mal escrita en una opción no puede pasar en silencio: el
        # artículo saldría con el título de siempre y sin fijar, y nadie lo
        # notaría hasta verlo publicado.
        desconocidas = (set(titulos) | fijar | saltar) - set(paginas)
        if desconocidas:
            raise CommandError(
                f"Estas rutas no están en el sitio: {', '.join(sorted(desconocidas))}. "
                f"Las que hay: {', '.join(paginas)}."
            )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{'ENSAYO — no se escribe nada' if seco else 'IMPORTANDO'} · "
                f"{len(paginas)} página(s) de {prefijo} → /{departamento.slug}/ · "
                f"artículos {'publicados' if publicar else 'en borrador'}\n"
            )
        )

        if seco:
            for ruta, html in paginas.items():
                titulo, cuerpo = extraer_pagina(html)
                titulo = titulos.get(ruta, titulo)
                if ruta in saltar:
                    estado = "se salta"
                elif ArticuloPage.objects.filter(source_url=url_canonica(prefijo, ruta)).exists():
                    estado = "ya importada"
                    informe.saltados += 1
                else:
                    estado = "se crearía" + (" (fijada)" if ruta in fijar else "")
                    informe.creados += 1
                soup = BeautifulSoup(cuerpo, "html.parser")
                self.stdout.write(
                    f"    {ruta}: «{titulo}» — {estado} · "
                    f"{len(soup.get_text(' ', strip=True))} caracteres, "
                    f"{len(soup.find_all('img'))} imagen(es), "
                    f"{sum(1 for a in soup.find_all('a', href=True) if 'google.com' in a['href'] and ruta_interna(a['href'], prefijo) is None)} enlace(s) a Drive"
                )
            return self._resumen(informe, seco)

        # Todo el sitio en una transacción: los artículos se enlazan entre sí,
        # así que medio sitio importado es un sitio con enlaces a la nada.
        with transaction.atomic():
            coleccion = self._coleccion_del_departamento(departamento)
            hoy = timezone.localdate()
            nuevos: dict[str, ArticuloPage] = {}

            for ruta, html in paginas.items():
                if ruta in saltar:
                    continue
                original = url_canonica(prefijo, ruta)
                if ArticuloPage.objects.filter(source_url=original).exists():
                    informe.saltados += 1
                    continue

                titulo, crudo = extraer_pagina(html)
                titulo = titulos.get(ruta, titulo) or ruta

                soup = BeautifulSoup(crudo, "html.parser")
                self._sustituir_videos(soup, informe)
                self._sustituir_archivos(soup, coleccion, informe)
                self._traer_imagenes(soup, titulo, coleccion, informe)
                cuerpo = limpiar_cuerpo(soup.decode())

                intro = derivar_intro(cuerpo)
                if not intro:
                    intro = titulo[:250]
                    informe.sin_entradilla.append(f"{titulo} — {original}")
                if not cuerpo.strip():
                    informe.posts_sin_cuerpo.append(f"{titulo} — {original}")

                # Con título propio, la dirección sale de ese título: la
                # portada del sitio se llama «inicio», y un artículo titulado
                # «Profesorado» en `/inicio/` no lo encuentra nadie.
                base = slug = (
                    slug_de_ruta(titulos[ruta]) if ruta in titulos else slug_de_ruta(ruta)
                ) or "pagina"
                sufijo = 2
                while ArticuloPage.objects.child_of(departamento).filter(slug=slug).exists():
                    slug = f"{base}-{sufijo}"
                    sufijo += 1

                articulo = ArticuloPage(
                    title=titulo[:255],
                    slug=slug,
                    date=hoy,
                    intro=intro,
                    body=cuerpo,
                    is_pinned=ruta in fijar,
                    source_url=original[:500],
                    live=False,
                )
                departamento.add_child(instance=articulo)
                nuevos[ruta] = articulo

            # Segunda pasada, ya con todos creados: los enlaces entre páginas.
            # Cuentan también las importadas en una ejecución anterior.
            destinos = {ruta: articulo.pk for ruta, articulo in nuevos.items()}
            for ruta in paginas:
                if ruta not in destinos:
                    previa = ArticuloPage.objects.filter(
                        source_url=url_canonica(prefijo, ruta)
                    ).first()
                    if previa is not None:
                        destinos[ruta] = previa.pk

            for ruta, articulo in nuevos.items():
                articulo.body = reescribir_enlaces_internos(articulo.body, prefijo, destinos)
                articulo.save()
                revision = articulo.save_revision()
                if publicar:
                    revision.publish()
                informe.creados += 1
                fijada = " [fijada]" if articulo.is_pinned else ""
                self.stdout.write(f"    + {articulo.title[:62]}{fijada}")

        self._resumen(informe, seco)
