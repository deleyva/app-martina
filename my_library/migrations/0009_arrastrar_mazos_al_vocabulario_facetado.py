"""Arrastra los mazos al vocabulario facetado, a la vez que C36.

`LibraryDeck` guarda su filtro como una lista de NOMBRES en `tags_json` y
empareja por comparación de cadenas. En el momento en que `build_tag_map` deja
de leer los `MusicTag` planos de las páginas, un mazo que apuntase a uno de esos
nombres se queda apuntando a nada y **cuenta 0 en silencio**.

Ya pasó el 2026-08-12 con la migración de las 188 etiquetas: los tres mazos del
principal se quedaron atrás y dos de ellos contaban 0 sin avisar. Esta migración
existe para que no sea la tercera vez.

Va como migración de datos, y no como comando a mano, por una razón concreta:
`deploy-production` lanza `migrate` justo después de levantar el código nuevo,
así que el arrastre ocurre solo, en el mismo despliegue que el cambio de lectura.
Hacerlo a mano abriría una ventana entre las dos cosas.

Medido antes de escribirla, sobre la copia de producción: de los cuatro nombres
que usan los tres mazos, tres ya son etiquetas vivas de taggit
(`instrumento:guitarra`, `estilo:jazz`, `instrumento:piano`) y solo uno
(`caged-system`) es un `MusicTag` plano que el mapa manda a `concepto:caged`.
Aun así el código es genérico: aplica el mapa entero, porque un mazo nuevo
creado entre el ensayo y el despliegue tiene que quedar cubierto igual.
"""

import json
from pathlib import Path

from django.db import migrations

BORRAR = "__BORRAR__"
MAPA = Path(__file__).resolve().parent.parent / "migracion" / "mapa_musictags.txt"


def _leer_mapa():
    """{origen_en_minusculas: destino}. Mismo formato que el del comando.

    El parseo se repite aquí a propósito en vez de importarlo: una migración
    tiene que seguir corriendo igual dentro de cinco años, y para entonces el
    comando puede haberse borrado con C37.
    """
    mapa = {}
    for linea in MAPA.read_text().splitlines():
        linea = linea.split("#")[0].strip()
        if "->" not in linea:
            continue
        origen, _, destino = linea.partition("->")
        origen, destino = origen.strip(), destino.strip()
        if origen and destino:
            mapa[origen.lower()] = destino
    return mapa


def arrastrar(apps, schema_editor):
    LibraryDeck = apps.get_model("my_library", "LibraryDeck")
    Tag = apps.get_model("taggit", "Tag")

    mapa = _leer_mapa()
    # Un nombre que sigue existiendo en taggit NO es un puntero muerto: el mazo
    # que lo use funciona y reescribirlo lo rompería. La salvaguarda mira solo
    # taggit, que a partir de ahora es el único vocabulario que empareja.
    vivos = {n.lower() for n in Tag.objects.values_list("name", flat=True)}

    for mazo in LibraryDeck.objects.all():
        try:
            viejos = json.loads(mazo.tags_json)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(viejos, list):
            continue

        nuevos = []
        for nombre in viejos:
            destino = nombre if nombre.lower() in vivos else mapa.get(nombre.lower(), nombre)
            if destino == BORRAR:
                continue
            if destino not in nuevos:  # el mapa fusiona: dos nombres, un destino
                nuevos.append(destino)

        if nuevos == viejos:
            continue
        # Un mazo sin etiquetas no filtra nada: `get_matching_item_pks` devuelve
        # la biblioteca entera. Uno que enseña 0 está visiblemente roto; uno que
        # enseña 51 miente. Se deja como está para que se decida a mano.
        if not nuevos:
            continue

        mazo.tags_json = json.dumps(nuevos)
        mazo.save(update_fields=["tags_json"])


def sin_vuelta_atras(apps, schema_editor):
    """Deshacerlo devolvería los mazos a nombres que ya no emparejan nada.

    La vuelta atrás de verdad es restaurar la copia del día, que es lo que se
    hace con cualquier migración de datos de esta fase.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("my_library", "0008_itemsection_reviewlog_section_and_more"),
        ("taggit", "0006_rename_taggeditem_content_type_object_id_taggit_tagg_content_8fc721_idx"),
    ]

    operations = [migrations.RunPython(arrastrar, sin_vuelta_atras)]
