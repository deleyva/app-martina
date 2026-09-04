"""Mueve los datos de `cms` a `blogs` y `musica` (fase 25).

Ni un `page.id` cambia. Wagtail guarda cada página en dos filas —la base en
`wagtailcore_page` y los campos propios en la tabla del modelo concreto, con la
misma clave— así que mover un modelo de app es copiar la fila hija a la tabla
nueva con el MISMO `page_ptr_id` y reapuntar `content_type_id`. El árbol, los
slugs, las URLs, las revisiones y todo lo que apunta a `wagtailcore.Page` se
quedan como están.

Lo único que se decide aquí, y no es mecánico, es en cuál de las dos apps cae
cada `BlogPage` y cada `BlogIndexPage`: si cuelga de la biblioteca musical es
música (238 recursos, 12 libros), si no es un departamento (17 artículos, 19
índices). Se resuelve por `path`, que es como Wagtail guarda el árbol.

Dos cosas se tiran a propósito, y están contadas en el informe que imprime:
  - `moderator` y `subject` de los libros (2 filas): un libro no tiene
    departamento que lo apruebe.
  - `cms_blogpage_categories` de los artículos (1 fila): era una categoría
    MUSICAL —«COFOTAP»— colgada de un artículo de departamento, justo el
    síntoma que motivó partir la app.
"""

from django.db import migrations


def _ct(apps, app_label, model):
    ContentType = apps.get_model("contenttypes", "ContentType")
    return ContentType.objects.get_or_create(app_label=app_label, model=model)[0].id


def traer(apps, schema_editor):
    c = schema_editor.connection.cursor()
    informe = []

    # Las rutas de las bibliotecas musicales: todo lo que cuelgue de ahí es música.
    c.execute("""SELECT p.path FROM wagtailcore_page p
                 JOIN cms_musiclibraryindexpage m ON m.page_ptr_id = p.id""")
    rutas = [r[0] for r in c.fetchall()]
    if rutas:
        es_musica = " OR ".join(f"p.path LIKE '{r}%%'" for r in rutas)
    else:
        es_musica = "FALSE"

    def ejecuta(sql, etiqueta):
        c.execute(sql)
        informe.append(f"{c.rowcount:6d}  {etiqueta}")

    # --- 1. snippets, con los mismos ids porque hay FKs apuntándolos ---------
    ejecuta("INSERT INTO musica_musiccomposer SELECT * FROM cms_musiccomposer",
            "MusicComposer")
    ejecuta("INSERT INTO musica_musiccategory SELECT * FROM cms_musiccategory",
            "MusicCategory")

    # --- 2. páginas que se mueven enteras -----------------------------------
    for tabla, cols in [
        ("musiclibraryindexpage", "page_ptr_id, intro"),
        ("scorepage", "page_ptr_id, content, composer_id"),
        ("dictadopage", "page_ptr_id, date, intro, content"),
        ("setlistpage", "page_ptr_id, description, setlist_items"),
        ("slidesconaudiopage", "page_ptr_id, date, intro, slides"),
        ("testpage", "page_ptr_id, date, intro, questions, featured_image_id"),
        ("librodeestudiopage",
         "page_ptr_id, intro, capitulos, is_protected, is_private, cover_image_id"),
    ]:
        ejecuta(f"INSERT INTO musica_{tabla} ({cols}) SELECT {cols} FROM cms_{tabla}",
                f"{tabla} -> musica")

    # --- 3. BlogIndexPage: libro o departamento -----------------------------
    ejecuta(f"""INSERT INTO musica_libropage
                  (page_ptr_id, intro, is_protected, is_private, cover_image_id)
                SELECT b.page_ptr_id, b.intro, b.is_protected, b.is_private, b.cover_image_id
                FROM cms_blogindexpage b JOIN wagtailcore_page p ON p.id = b.page_ptr_id
                WHERE {es_musica}""", "BlogIndexPage -> musica.LibroPage")
    c.execute(f"""SELECT count(*) FROM cms_blogindexpage b
                  JOIN wagtailcore_page p ON p.id = b.page_ptr_id
                  WHERE ({es_musica}) AND (b.moderator_id IS NOT NULL OR b.subject_id IS NOT NULL)""")
    informe.append(f"{c.fetchone()[0]:6d}  libros con moderator/subject DESCARTADOS a propósito")

    ejecuta(f"""INSERT INTO blogs_blogindexpage
                  (page_ptr_id, intro, is_protected, is_private, cover_image_id,
                   moderator_id, subject_id)
                SELECT b.page_ptr_id, b.intro, b.is_protected, b.is_private,
                       b.cover_image_id, b.moderator_id, b.subject_id
                FROM cms_blogindexpage b JOIN wagtailcore_page p ON p.id = b.page_ptr_id
                WHERE NOT ({es_musica})""", "BlogIndexPage -> blogs.BlogIndexPage")

    # --- 4. BlogPage: recurso musical o artículo de departamento ------------
    musicales = ("page_ptr_id, date, intro, body, is_featured, is_protected, is_private, "
                 "attachments, artist, key_fifths, key_mode, time_signature_beats, "
                 "time_signature_beat_type, tempo_bpm, duration_seconds, reference, "
                 "songsterr_url, chordpro, featured_image_id")
    ejecuta(f"""INSERT INTO musica_recursopage ({musicales})
                SELECT {', '.join('b.' + x.strip() for x in musicales.split(','))}
                FROM cms_blogpage b JOIN wagtailcore_page p ON p.id = b.page_ptr_id
                WHERE {es_musica}""", "BlogPage -> musica.RecursoPage")

    llanos = ("page_ptr_id, date, intro, body, is_featured, is_protected, is_private, "
              "attachments, featured_image_id")
    ejecuta(f"""INSERT INTO blogs_articulopage ({llanos})
                SELECT {', '.join('b.' + x.strip() for x in llanos.split(','))}
                FROM cms_blogpage b JOIN wagtailcore_page p ON p.id = b.page_ptr_id
                WHERE NOT ({es_musica})""", "BlogPage -> blogs.ArticuloPage")

    # --- 5. etiquetas -------------------------------------------------------
    ejecuta("""INSERT INTO musica_recursopagetag (content_object_id, tag_id)
               SELECT t.content_object_id, t.tag_id FROM cms_blogpagetag t
               WHERE t.content_object_id IN (SELECT page_ptr_id FROM musica_recursopage)""",
            "etiquetas -> RecursoPage")
    ejecuta("""INSERT INTO blogs_articulopagetag (content_object_id, tag_id)
               SELECT t.content_object_id, t.tag_id FROM cms_blogpagetag t
               WHERE t.content_object_id IN (SELECT page_ptr_id FROM blogs_articulopage)""",
            "etiquetas -> ArticuloPage")
    for tabla in ("scorepagetag", "dictadopagetag", "testpagetag"):
        ejecuta(f"""INSERT INTO musica_{tabla} (content_object_id, tag_id)
                    SELECT content_object_id, tag_id FROM cms_{tabla}""",
                f"etiquetas -> {tabla}")

    # --- 6. categorías ------------------------------------------------------
    ejecuta("""INSERT INTO musica_recursopage_categories (recursopage_id, musiccategory_id)
               SELECT blogpage_id, musiccategory_id FROM cms_blogpage_categories
               WHERE blogpage_id IN (SELECT page_ptr_id FROM musica_recursopage)""",
            "categorías -> RecursoPage")
    c.execute("""SELECT count(*) FROM cms_blogpage_categories
                 WHERE blogpage_id IN (SELECT page_ptr_id FROM blogs_articulopage)""")
    informe.append(f"{c.fetchone()[0]:6d}  categorías musicales en artículos DESCARTADAS a propósito")

    ejecuta("""INSERT INTO musica_dictadopage_categories (dictadopage_id, musiccategory_id)
               SELECT dictadopage_id, musiccategory_id FROM cms_dictadopage_categories""",
            "categorías -> DictadoPage")
    ejecuta("""INSERT INTO musica_testpage_categories (testpage_id, musiccategory_id)
               SELECT testpage_id, musiccategory_id FROM cms_testpage_categories""",
            "categorías -> TestPage")
    ejecuta("""INSERT INTO musica_scorepagecategory (sort_order, category_id, score_page_id)
               SELECT sort_order, category_id, score_page_id FROM cms_scorepagecategory""",
            "categorías -> ScorePage")

    # --- 7. content_type: la tabla nueva es ahora la autoridad --------------
    # Cada fila insertada arriba dice, por sí sola, qué tipo es ahora esa página.
    destinos = [
        ("musica", "musiclibraryindexpage"), ("musica", "scorepage"),
        ("musica", "dictadopage"), ("musica", "setlistpage"),
        ("musica", "slidesconaudiopage"), ("musica", "testpage"),
        ("musica", "librodeestudiopage"), ("musica", "libropage"),
        ("musica", "recursopage"), ("blogs", "blogindexpage"),
        ("blogs", "articulopage"),
    ]
    origen_ct = {}
    for app, modelo in [("cms", m) for m in (
            "musiclibraryindexpage", "scorepage", "dictadopage", "setlistpage",
            "slidesconaudiopage", "testpage", "librodeestudiopage",
            "blogindexpage", "blogpage")]:
        origen_ct[modelo] = _ct(apps, app, modelo)
    viejos = ", ".join(str(v) for v in origen_ct.values())

    # Todas las tablas del esquema que llevan (content_type_id, object_id).
    c.execute("""SELECT c1.table_name, c2.data_type
                 FROM information_schema.columns c1 JOIN information_schema.columns c2
                   ON c1.table_name = c2.table_name AND c2.column_name = 'object_id'
                 WHERE c1.table_schema = 'public' AND c1.column_name = 'content_type_id'""")
    genericas = c.fetchall()

    for app, modelo in destinos:
        nuevo = _ct(apps, app, modelo)
        tabla = f"{app}_{modelo}"
        ejecuta(f"""UPDATE wagtailcore_page SET content_type_id = {nuevo}
                    WHERE id IN (SELECT page_ptr_id FROM {tabla})
                      AND content_type_id IN ({viejos})""",
                f"wagtailcore_page -> {app}.{modelo}")
        for gt, tipo in genericas:
            objeto = "object_id" if tipo == "integer" else "object_id::text"
            sub = (f"(SELECT page_ptr_id FROM {tabla})" if tipo == "integer"
                   else f"(SELECT page_ptr_id::text FROM {tabla})")
            c.execute(f"""UPDATE {gt} SET content_type_id = {nuevo}
                          WHERE content_type_id IN ({viejos}) AND {objeto} IN {sub}""")
            if c.rowcount:
                informe.append(f"{c.rowcount:6d}  {gt} -> {app}.{modelo}")

    print("\n=== Fase 25 · datos movidos de cms a blogs/musica ===")
    for linea in informe:
        print("   " + linea)
    c.execute(f"""SELECT count(*) FROM wagtailcore_page WHERE content_type_id IN ({viejos})""")
    huerfanas = c.fetchone()[0]
    print(f"   páginas que siguen apuntando a un content type de cms: {huerfanas}")
    if huerfanas:
        raise RuntimeError(
            f"{huerfanas} páginas se quedaron con content type de cms; se aborta.")


def volver(apps, schema_editor):
    raise RuntimeError(
        "Sin marcha atrás automática: restaura de la copia previa a la migración."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("musica", "0001_initial"),
        ("blogs", "0001_initial"),
        ("cms", "0037_blogpage_chordpro_blogpage_songsterr_url"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]
    operations = [migrations.RunPython(traer, volver)]
