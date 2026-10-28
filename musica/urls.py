"""URLs propias de `musica`.

Hasta la pantalla de recorte, esta app no tenia ninguna: sus paginas las sirve
Wagtail por el arbol. El flujo de importacion no son paginas de contenido, son
herramientas de autoria, asi que necesitan ruta propia.
"""

from django.urls import path

from musica import letras, pistas, recortador, servido

app_name = "musica"

urlpatterns = [
    # Pistas de práctica del visor ChordPro (fase 82). El audio solo sale por
    # aquí: nginx cierra /media/pistas_practica/.
    path("pistas/recurso/<int:page_id>/subir/", pistas.pista_subir, name="pista_subir"),
    path("pistas/<int:pk>/audio/", pistas.pista_audio, name="pista_audio"),
    path("pistas/<int:pk>/guardar/", pistas.pista_guardar, name="pista_guardar"),
    path("pistas/<int:pk>/borrar/", pistas.pista_borrar, name="pista_borrar"),
    # Guardar la letra con acordes desde el botón ✎ (artículo y visores).
    path(
        "letras/<int:page_id>/chordpro/",
        letras.guardar_chordpro,
        name="guardar_chordpro",
    ),
    # El PDF cortado al rango de un recorte. Es la unica via por la que sale
    # material de un documento restringido.
    path(
        "recortes/<int:pk>/pdf/",
        servido.pdf_del_recorte,
        name="pdf_del_recorte",
    ),
    # El documento entero, solo con sesion de profesor: para recortar hay que
    # ver el libro, no solo los trozos ya recortados.
    path(
        "recortar/<int:document_id>/pdf/",
        servido.pdf_para_recortar,
        name="pdf_para_recortar",
    ),

    # --- Flujo de importacion, de principio a fin y sin admin de Wagtail ---
    path("importar/", recortador.importar, name="importar"),
    path("importar/subir/", recortador.subir_pdf, name="subir_pdf"),
    path("importar/libro/", recortador.crear_libro, name="crear_libro"),

    path(
        "recortar/<int:document_id>/",
        recortador.recortador,
        name="recortador",
    ),
    path(
        "recortar/<int:document_id>/crear/",
        recortador.crear_recorte,
        name="crear_recorte",
    ),
    path(
        "recortar/<int:document_id>/lista/",
        recortador.lista_de_recortes,
        name="lista_de_recortes",
    ),
    path(
        "recortar/<int:document_id>/restriccion/",
        recortador.alternar_restriccion,
        name="alternar_restriccion",
    ),
    path(
        "recortes/<int:pk>/editar/",
        recortador.editar_recorte,
        name="editar_recorte",
    ),
    path(
        "recortes/<int:pk>/borrar/",
        recortador.borrar_recorte,
        name="borrar_recorte",
    ),
    path(
        "libros/<int:libro_id>/reordenar/",
        recortador.reordenar_libro,
        name="reordenar_libro",
    ),
]
