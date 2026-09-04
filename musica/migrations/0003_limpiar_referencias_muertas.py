"""Borra las referencias genéricas que apuntaban a páginas que ya no existen.

Aparecieron al comprobar la fase 25: después de repartir los content types,
quedaban 7 filas en `evaluations_grouplibraryitem` con el tipo `cms.blogpage` y
`object_id` 310, 312 y 317 — tres páginas que no están en `wagtailcore_page`.

No las rompió la partición. Una `GenericForeignKey` no tiene clave ajena, así
que borrar una página deja atrás sus filas y nadie se entera; el código ya lo
sortea comprobando `content_object is not None`. Estaban muertas desde antes.

Se limpian aquí porque son justo las filas que quedarían apuntando a un content
type que esta misma migración deja sin modelo detrás, y porque «huérfanas: 7» en
un informe de verificación es ruido que la próxima persona tendría que volver a
investigar para llegar a esta misma conclusión.

Solo se borra lo que apunta a una página inexistente. Si algo apuntara a una
página viva, la migración se planta.
"""

from django.db import migrations


def limpiar(apps, schema_editor):
    c = schema_editor.connection.cursor()
    c.execute("""SELECT c1.table_name, c2.data_type
                 FROM information_schema.columns c1 JOIN information_schema.columns c2
                   ON c1.table_name = c2.table_name AND c2.column_name = 'object_id'
                 WHERE c1.table_schema = 'public' AND c1.column_name = 'content_type_id'""")
    tablas = c.fetchall()

    c.execute("""SELECT id FROM django_content_type WHERE app_label = 'cms'
                 AND model IN ('blogpage','blogindexpage','scorepage','dictadopage',
                               'musiclibraryindexpage','setlistpage','testpage',
                               'slidesconaudiopage','librodeestudiopage')""")
    viejos = [str(r[0]) for r in c.fetchall()]
    if not viejos:
        return
    lista = ", ".join(viejos)

    borradas = 0
    for tabla, tipo in tablas:
        objeto = "object_id" if tipo == "integer" else "object_id::text"
        pagina = "p.id" if tipo == "integer" else "p.id::text"

        # Si algo sobreviviente apunta a una página VIVA, es que la fase 25 se
        # dejó un caso: mejor plantarse que borrar datos buenos.
        c.execute(f"""SELECT count(*) FROM {tabla} t
                      WHERE t.content_type_id IN ({lista})
                        AND EXISTS (SELECT 1 FROM wagtailcore_page p
                                    WHERE {pagina} = t.{objeto})""")
        vivas = c.fetchone()[0]
        if vivas:
            raise RuntimeError(
                f"{tabla}: {vivas} filas apuntan a páginas VIVAS con un content "
                "type de cms. No se borra nada; revisa el reparto de la 0002."
            )

        c.execute(f"""DELETE FROM {tabla} WHERE content_type_id IN ({lista})""")
        if c.rowcount:
            print(f"   {c.rowcount:6d}  filas muertas borradas de {tabla}")
            borradas += c.rowcount

    print(f"=== Fase 25 · referencias muertas limpiadas: {borradas} ===")


class Migration(migrations.Migration):
    dependencies = [("musica", "0002_traer_datos_desde_cms")]
    operations = [migrations.RunPython(limpiar, migrations.RunPython.noop)]
