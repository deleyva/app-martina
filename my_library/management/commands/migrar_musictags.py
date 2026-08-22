"""Mueve las etiquetas de las páginas de `cms.MusicTag` a taggit facetado.

No es el mismo trabajo que `migrar_etiquetas`. Aquel renombraba filas DENTRO de
taggit; este mueve etiquetados de un modelo a otro: lee lo que cada página tiene
en `MusicTag` (vocabulario plano, propio, 80 nombres) y escribe el equivalente
facetado en taggit, que es el vocabulario que la sesión de estudio sabe agrupar
y filtrar.

    just command python manage.py migrar_musictags              # en seco
    just command python manage.py migrar_musictags --ejecutar   # lo hace

El mapa vive en `my_library/migracion/mapa_musictags.txt`, lo revisó el
principal el 2026-08-17 y es un fichero de texto pensado para leerse a mano.

**La mitad de escritura depende de C33.** El campo `tags` de las cuatro páginas
ya lo ocupa el `ParentalManyToManyField` a `MusicTag`, así que el manager de
taggit entra al lado con otro nombre (`faceted_tags`) y se renombra al final,
cuando ya no lea nadie el viejo. Mientras ese campo no exista, el ensayo en seco
funciona entero y `--ejecutar` aborta diciendo por qué: planificar es aritmética
sobre el mapa y no necesita esquema ninguno.

Lo que este comando NO hace, a propósito:

- No borra ni una sola `MusicTag`. Qué pasa con el modelo es C37, y mezclar el
  movimiento con el borrado deja sin red la comprobación de paridad de C35.
- No toca `MusicCategory`, que es una TERCERA taxonomía que nadie ha mirado.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Los helpers puros del comando hermano. Se importan en vez de duplicarse: el
# formato del fichero de mapa es el mismo y la validación de facetas también.
# Se importa el módulo, no se toca — es código verificado en producción.
from my_library.management.commands.migrar_etiquetas import (
    BORRAR,
    facetas_desconocidas,
    leer_mapa,
)

MAPA_POR_DEFECTO = (
    Path(__file__).resolve().parent.parent.parent / "migracion" / "mapa_musictags.txt"
)

# El manager de taggit que añade C33, al lado del `tags` de siempre. Se renombra
# a `tags` en C37, cuando `build_tag_map` ya lea solo de aquí.
CAMPO_DESTINO = "faceted_tags"


def modelos_de_pagina():
    """Los cuatro tipos de página que llevan `MusicTag`.

    Importados dentro de la función: `cms.models` arrastra medio Wagtail y a
    nivel de módulo rompe la carga del comando en algunos arranques.
    """
    from cms.models import BlogPage, DictadoPage, ScorePage, TestPage

    return [BlogPage, ScorePage, DictadoPage, TestPage]


def musictags_sin_mapear(mapa):
    """Nombres de `MusicTag` que existen en la BD y el mapa no menciona.

    El mapa dice cubrir las 80. Si aparece una nueva —alguien etiquetó algo en
    el admin después del 17/08— el comando NO debe seguir: esa etiqueta se
    quedaría fuera en silencio, que es como se pierde una migración a medias.
    """
    from cms.models import MusicTag

    conocidos = {o.lower() for o in mapa}
    return sorted(
        n
        for n in MusicTag.objects.values_list("name", flat=True)
        if n.lower() not in conocidos
    )


def destinos_que_son_origen(mapa):
    """Destinos del mapa que también aparecen como origen.

    Con una cadena `a -> b` y `b -> c`, ejecutar dos veces no da lo mismo que
    ejecutar una. La idempotencia es lo que permite volver a lanzar el comando
    después de un fallo a medias sin pensárselo.
    """
    origenes = {o.lower() for o in mapa}
    return sorted(
        {d for d in mapa.values() if d != BORRAR and d.lower() in origenes}
    )


def origenes_ambiguos(mapa):
    """Orígenes que solo difieren en mayúsculas y van a destinos distintos.

    `MusicTag.name` es único pero sensible a mayúsculas, y el emparejamiento de
    los mazos es en minúsculas. Dos orígenes que colapsan al bajar a minúsculas
    harían que el resultado dependiera del orden de lectura del fichero.
    """
    indice, malos = {}, []
    for origen, destino in sorted(mapa.items()):
        clave = origen.lower()
        if clave in indice and indice[clave] != destino:
            malos.append((clave, indice[clave], destino))
        indice[clave] = destino
    return malos


def planificar_paginas(mapa):
    """[(pagina, viejos, nuevos, se_queda_pelada)] de las páginas que cambian.

    Se aplica el MAPA, nunca el estado actual de taggit: así el plan es el mismo
    lo hayan ejecutado antes o no, y una ejecución interrumpida se retoma
    volviendo a lanzar el comando.

    `nuevos` es lo que la página debe acabar teniendo en taggit, en orden
    estable y sin repetidos — el mapa fusiona (`guitar`, `guitarra` y
    `guitar solo` van los tres a `instrumento:guitarra`), y una fusión que
    dejara duplicados reventaría contra la unicidad del through model.

    `se_queda_pelada` marca las páginas cuyas etiquetas van TODAS a
    `__BORRAR__`. A diferencia de un mazo vacío —que enseña la biblioteca
    entera y miente— una página sin etiquetas no rompe nada: solo deja de
    aportar al `build_tag_map` de los elementos que la tienen por `source_page`.
    No se frena por ellas, pero se cuentan y se enseñan, porque son pérdida real
    de información y el principal tiene que verla antes de aceptarla.
    """
    indice = {o.lower(): d for o, d in mapa.items()}

    plan = []
    for modelo in modelos_de_pagina():
        paginas = modelo.objects.prefetch_related("tags").order_by("pk")
        for pagina in paginas:
            viejos = [t.name for t in pagina.tags.all()]
            if not viejos:
                continue
            nuevos = []
            for nombre in viejos:
                destino = indice.get(nombre.lower())
                if destino is None or destino == BORRAR:
                    continue
                if destino not in nuevos:
                    nuevos.append(destino)
            plan.append((pagina, viejos, nuevos, not nuevos))
    return plan


def etiquetados_que_se_pierden(mapa):
    """({etiqueta: veces}, n_paginas) de lo que `__BORRAR__` se lleva por delante.

    El informe tiene que enseñar la pérdida, no solo la ganancia. Un resumen que
    solo cuenta lo que se gana invita a aprobar una migración sin mirar lo que
    borra, y borrar 26 etiquetas fue una decisión, no un efecto secundario.
    """
    perdidos, paginas = {}, set()
    indice = {o.lower(): d for o, d in mapa.items()}
    for modelo in modelos_de_pagina():
        for pagina in modelo.objects.prefetch_related("tags"):
            for etiqueta in pagina.tags.all():
                if indice.get(etiqueta.name.lower()) == BORRAR:
                    perdidos[etiqueta.name] = perdidos.get(etiqueta.name, 0) + 1
                    paginas.add((modelo.__name__, pagina.pk))
    return perdidos, len(paginas)


def clasificar_destinos(plan):
    """({destino: veces}, nuevos_en_taggit) — cuánto se escribe y qué se crea.

    Separar los destinos que YA existen en taggit de los que habría que crear es
    lo que deja ver de un vistazo si el mapa está fusionando con el vocabulario
    bueno o inventando ramas nuevas. Con 139 etiquetas ya facetadas, un mapa
    sano crea muy pocas.
    """
    from taggit.models import Tag

    conteo = {}
    for _pagina, _viejos, nuevos, _pelada in plan:
        for destino in nuevos:
            conteo[destino] = conteo.get(destino, 0) + 1

    existentes = set(
        Tag.objects.filter(name__in=list(conteo)).values_list("name", flat=True)
    )
    return conteo, sorted(set(conteo) - existentes)


def campo_destino_existe():
    """¿Han entrado ya los managers de taggit de C33?

    Se comprueba en los cuatro modelos: media migración —dos páginas con manager
    y dos sin él— es peor que ninguna, porque `--ejecutar` escribiría parte y
    dejaría el resto atrás creyendo que ha terminado.
    """
    return all(
        any(f.name == CAMPO_DESTINO for f in modelo._meta.get_fields())
        for modelo in modelos_de_pagina()
    )


class Command(BaseCommand):
    help = "Mueve las etiquetas de las páginas de MusicTag a taggit facetado"

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

        self._validar(mapa)

        plan = planificar_paginas(mapa)
        conteo, por_crear = clasificar_destinos(plan)
        perdidos, paginas_con_perdida = etiquetados_que_se_pierden(mapa)

        self._resumen(plan, conteo, por_crear, perdidos, paginas_con_perdida)

        if not ejecutar:
            self.stdout.write(
                self.style.WARNING(
                    "\nEN SECO — no se ha tocado nada. "
                    "Añade --ejecutar para aplicarlo."
                )
            )
            return

        if not campo_destino_existe():
            raise CommandError(
                f"Las páginas no tienen el campo {CAMPO_DESTINO!r} todavía, así "
                "que no hay dónde escribir las etiquetas. Falta la migración de "
                "esquema (C33): ClusterTaggableManager + through model en "
                "BlogPage, ScorePage, DictadoPage y TestPage. El ensayo en seco "
                "de arriba sí es válido: planificar no necesita el esquema."
            )

        with transaction.atomic():
            self._aplicar(plan)

        self.stdout.write(self.style.SUCCESS("\nHecho."))

    def _validar(self, mapa):
        """Las cuatro comprobaciones, todas antes de tocar nada.

        Cada una para un fallo que sería silencioso: una etiqueta que se queda
        fuera, una migración que no se puede repetir, un resultado que depende
        del orden de lectura, y una etiqueta que nace muerta porque su faceta no
        existe y `facets.parse` no la reconoce.
        """
        sin_mapear = musictags_sin_mapear(mapa)
        if sin_mapear:
            raise CommandError(
                f"{len(sin_mapear)} MusicTag existen en la BD y no están en el "
                f"mapa: {', '.join(repr(n) for n in sin_mapear[:10])}"
                f"{'…' if len(sin_mapear) > 10 else ''}. Se quedarían fuera sin "
                "avisar. Añádelas al mapa o bórralas del admin."
            )

        cadenas = destinos_que_son_origen(mapa)
        if cadenas:
            raise CommandError(
                f"El mapa tiene cadenas origen->destino->origen: "
                f"{', '.join(repr(d) for d in cadenas)}. Ejecutarlo dos veces no "
                "daría el mismo resultado."
            )

        ambiguos = origenes_ambiguos(mapa)
        if ambiguos:
            for clave, uno, otro in ambiguos:
                self.stdout.write(
                    self.style.ERROR(f"  {clave!r}: {uno!r} vs {otro!r}")
                )
            raise CommandError(
                "Hay orígenes que solo difieren en mayúsculas apuntando a "
                "destinos distintos. El resultado dependería del orden de "
                "lectura del fichero."
            )

        desconocidas = facetas_desconocidas(mapa)
        if desconocidas:
            for faceta, ejemplos in sorted(desconocidas.items()):
                self.stdout.write(
                    self.style.ERROR(f"Faceta desconocida {faceta!r}: {ejemplos[0]}")
                )
            raise CommandError(
                "Hay destinos con facetas que no existen en facets.FACETAS. El "
                "etiquetado funcionaría, pero la biblioteca las trataría como "
                "etiquetas planas: no agruparían ni filtrarían."
            )

    def _aplicar(self, plan):
        """La mitad de escritura (C34b). SIN VERIFICAR todavía.

        No se puede ejercitar hasta que exista `faceted_tags` (C33), así que
        este cuerpo es la intención, no código probado. Queda por resolver con
        C33 si basta `.set()` + `save()` o hace falta `save_revision()` para
        que el cambio sobreviva al sistema de revisiones de Wagtail. El guardia
        de `handle` existe justo para que esto no se ejecute a ciegas.
        """
        from taggit.models import Tag

        for destino in sorted({d for _p, _v, nuevos, _s in plan for d in nuevos}):
            Tag.objects.get_or_create(
                name=destino, defaults={"slug": _slug_para(destino)}
            )

        for pagina, _viejos, nuevos, pelada in plan:
            if pelada:
                continue
            getattr(pagina, CAMPO_DESTINO).set(nuevos)
            pagina.save()

    def _resumen(self, plan, conteo, por_crear, perdidos, paginas_con_perdida):
        w = self.stdout.write

        if not plan:
            w("\nNinguna página tiene MusicTag. No hay nada que mover.")
            return

        peladas = [f for f in plan if f[3]]
        cambian = [f for f in plan if not f[3]]
        etiquetados = sum(conteo.values())

        w(self.style.SUCCESS(f"\nPÁGINAS A RE-ETIQUETAR ({len(cambian)})"))
        por_tipo = {}
        for pagina, _v, nuevos, _s in cambian:
            clave = type(pagina).__name__
            tipo = por_tipo.setdefault(clave, [0, 0])
            tipo[0] += 1
            tipo[1] += len(nuevos)
        for nombre, (paginas, etiquetas) in sorted(por_tipo.items()):
            w(f"  {nombre}: {paginas} páginas, {etiquetas} etiquetados")

        w(self.style.SUCCESS(f"\nETIQUETAS DE DESTINO ({len(conteo)}, {etiquetados} etiquetados)"))
        for destino, veces in sorted(conteo.items(), key=lambda x: (-x[1], x[0])):
            marca = "  NUEVA" if destino in por_crear else ""
            w(f"  {destino}   [{veces} páginas]{marca}")

        if por_crear:
            w(
                self.style.WARNING(
                    f"\nSE CREARÍAN EN TAGGIT ({len(por_crear)}) — el resto fusiona "
                    "con etiquetas que ya existen"
                )
            )
            for destino in por_crear:
                w(f"  {destino}")

        if perdidos:
            w(
                self.style.ERROR(
                    f"\nSE PIERDEN ({sum(perdidos.values())} etiquetados en "
                    f"{paginas_con_perdida} páginas) — van a __BORRAR__"
                )
            )
            for nombre, veces in sorted(perdidos.items(), key=lambda x: (-x[1], x[0])):
                w(f"  {nombre}   [{veces}]")

        if peladas:
            w(
                self.style.ERROR(
                    f"\nPÁGINAS QUE SE QUEDAN SIN ETIQUETAS ({len(peladas)}) — "
                    "todas las suyas van a __BORRAR__"
                )
            )
            for pagina, viejos, _n, _s in peladas:
                w(f"  {type(pagina).__name__} {pagina.pk} {pagina.title!r}  tags={viejos}")
            w(
                "  No rompe nada —una página sin etiquetas simplemente no aporta "
                "al build_tag_map de los elementos que la tienen por source_page— "
                "pero es pérdida real de información."
            )


def _slug_para(nombre):
    """Slug único para una etiqueta nueva de taggit.

    Misma trampa que documenta `migrar_etiquetas.slug_para`: los dos puntos se
    convierten en guion antes de slugificar, o `estilo:jazz` daría `estilojazz`
    en vez de `estilo-jazz`.
    """
    from django.utils.text import slugify
    from taggit.models import Tag

    base = slugify(nombre.replace(":", "-")) or "etiqueta"
    slug, n = base, 2
    while Tag.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug
