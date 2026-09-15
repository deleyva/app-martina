"""Fase 32 — Plantillas de nivel. Una plantilla es un grupo sin alumnos.

Montar «lo que se da en tercero» una vez y mandarlo a los grupos que elijas, en
vez de repetir la misma faena en cada uno. La plantilla no desaparece al enviar:
se queda, y por eso un libro nuevo en marzo se configura una vez y se envía.

**Por qué una plantilla es un `Group`.** Así el motor entero funciona sin tocar
nada. El precio es que podría colarse en cualquier pantalla que liste grupos, y
ese precio se paga en el gestor por defecto, no pantalla por pantalla.
"""

import pytest

from clases.models import Group, Subject


def _asignatura():
    return Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})[0]


def _plantilla(profesor, nombre="3.º ESO"):
    plantilla = Group.todos.create(
        name=nombre,
        subject=_asignatura(),
        academic_year="2026-2027",
        es_plantilla=True,
    )
    plantilla.teachers.add(profesor)
    return plantilla


def _clase(profesor, nombre="3-C-BIL"):
    grupo = Group.objects.create(
        name=nombre, subject=_asignatura(), academic_year="2026-2027"
    )
    grupo.teachers.add(profesor)
    return grupo


@pytest.fixture
def profe(db, django_user_model):
    return django_user_model.objects.create_user(email="plantillas@x.es", password="x")


# =============================================================================
# C176 · La plantilla no se cuela por ningún lado
# =============================================================================


def test_la_relacion_inversa_no_trae_plantillas(profe):
    """**El cimiento de todo el diseño, y por eso tiene test propio.**

    Hay nueve sitios en el código que preguntan `user.teaching_groups` fuera del
    embudo de `del_profesor`: la navegación, las evaluaciones, la programación,
    las fichas de estudio. Ninguno se ha tocado. Lo que los protege es que
    Django construye el gestor inverso a partir del gestor por defecto, así que
    el filtro de `GrupoManager` llega solo hasta ahí.

    Si una versión de Django cambiara eso, este test cae y avisa antes de que
    una plantilla aparezca en el menú de alguien.
    """
    clase = _clase(profe)
    plantilla = _plantilla(profe)

    desde_la_relacion = set(profe.teaching_groups.all())

    assert desde_la_relacion == {clase}, "la plantilla se ha colado por la relación inversa"
    assert plantilla in set(Group.todos.filter(teachers=profe))


def test_el_gestor_por_defecto_no_ve_plantillas(profe):
    _clase(profe)
    plantilla = _plantilla(profe)

    assert plantilla not in Group.objects.all()
    assert plantilla in Group.todos.all()


def test_una_relacion_hacia_dentro_si_resuelve_la_plantilla(profe):
    """`base_manager_name`. Sin esto, un `GroupBook` de una plantilla no podría
    leer su propio grupo y el motor reventaría en la primera pantalla."""
    from my_library.tests import _libro_con_capitulos
    from clases.models import GroupBook

    plantilla = _plantilla(profe)
    libro, _ = _libro_con_capitulos("Teoría", "teoria-plantilla", [("Cap", ["m1"])])
    group_book = GroupBook.objects.create(
        group=plantilla, libro=libro, seccion="teoria"
    )

    de_vuelta = GroupBook.objects.get(pk=group_book.pk)

    assert de_vuelta.group == plantilla, "el motor no puede leer el grupo de la plantilla"


def test_del_profesor_no_trae_plantillas(profe):
    clase = _clase(profe)
    plantilla = _plantilla(profe)

    assert list(Group.del_profesor(profe)) == [clase]
    assert plantilla not in Group.del_profesor(profe, incluir_archivados=True)


# =============================================================================
# C176 · Por HTTP: la plantilla no sale en ninguna pantalla de clases
# =============================================================================
#
# El test va por las pantallas y no por el ORM a propósito. El agujero de
# `archivado` se coló justamente así: el filtro estaba puesto en el sitio
# evidente y faltaba en una pantalla que nadie volvió a mirar.


@pytest.mark.parametrize(
    "ruta",
    [
        "clases:class_session_list",
        "clases:class_session_create",
        "clases:progreso",
    ],
)
def test_la_plantilla_no_sale_en_las_pantallas_de_clase(client, profe, ruta):
    from django.urls import reverse

    _clase(profe, "3-C-BIL")
    _plantilla(profe, "3.º ESO")
    client.force_login(profe)

    respuesta = client.get(reverse(ruta))
    cuerpo = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert "3-C-BIL" in cuerpo, "la clase de verdad tiene que salir"
    assert "3.º ESO" not in cuerpo, f"la plantilla se ha colado en {ruta}"


def test_la_plantilla_sale_en_su_propia_pantalla(client, profe):
    from django.urls import reverse

    _clase(profe, "3-C-BIL")
    _plantilla(profe, "3.º ESO")
    client.force_login(profe)

    cuerpo = client.get(reverse("clases:niveles")).content.decode()

    assert "3.º ESO" in cuerpo
    assert "3-C-BIL" not in cuerpo, "las clases no son plantillas"


# =============================================================================
# C177 · Ni alumnado ni sesiones dentro de una plantilla
# =============================================================================


def test_no_se_invita_alumnado_a_una_plantilla(client, profe):
    from django.urls import reverse

    plantilla = _plantilla(profe)
    client.force_login(profe)

    respuesta = client.get(
        reverse("clases:group_invitations", args=[plantilla.pk])
    )

    assert respuesta.status_code == 404


def test_no_se_crea_una_sesion_en_una_plantilla(client, profe):
    """Por POST, no mirando el desplegable: el desplegable se puede saltar
    escribiendo el `group` a mano, y eso es lo que hay que cerrar."""
    from datetime import date
    from django.urls import reverse

    from clases.models import ClassSession

    plantilla = _plantilla(profe)
    client.force_login(profe)

    client.post(
        reverse("clases:class_session_create"),
        {"group": plantilla.pk, "date": date.today().isoformat(), "title": "Colada"},
    )

    assert not ClassSession.objects.filter(group=plantilla).exists()


# =============================================================================
# C183 · Una plantilla es de quien la hizo
# =============================================================================


@pytest.mark.parametrize(
    "ruta", ["clases:group_books_index", "clases:group_book_add"]
)
def test_otro_profesor_no_llega_a_tu_plantilla(client, profe, django_user_model, ruta):
    from django.urls import reverse

    plantilla = _plantilla(profe)
    intruso = django_user_model.objects.create_user(email="otro@x.es", password="x")
    _clase(intruso, "1-G-BIL")
    client.force_login(intruso)

    url = reverse(ruta, args=[plantilla.pk])
    respuesta = client.post(url) if "add" in ruta else client.get(url)

    assert respuesta.status_code == 404


def test_las_plantillas_de_otro_no_salen_en_tu_lista(client, profe, django_user_model):
    """El nombre es raro a propósito: con «3.º ESO» este test pasaba por accidente
    al principio y fallaba por otro motivo —el formulario lo trae de ejemplo en
    su `placeholder`—. Un nombre que solo puede venir de la base de datos es lo
    que hace que el test mida lo que dice medir."""
    from django.urls import reverse

    _plantilla(profe, "Nivel de otro profesor")
    otro = django_user_model.objects.create_user(email="otro2@x.es", password="x")
    _clase(otro, "1-G-BIL")
    client.force_login(otro)

    cuerpo = client.get(reverse("clases:niveles")).content.decode()

    assert "Nivel de otro profesor" not in cuerpo


# =============================================================================
# C178, C179, C180 · Enviar
# =============================================================================


@pytest.fixture
def montaje(db, django_user_model):
    """Una plantilla con un libro elegido, y una clase con ese mismo libro."""
    from my_library.tests import _libro_con_capitulos
    from clases import libros_de_grupo
    from clases.models import GroupBook

    profe = django_user_model.objects.create_user(email="envia@x.es", password="x")
    plantilla = _plantilla(profe, "3.º ESO enviar")
    clase = _clase(profe, "3-C-BIL enviar")

    libro, _ = _libro_con_capitulos(
        "Lecturas", "lecturas-enviar", [("Cap", ["m1", "m2", "m3", "m4"])]
    )
    de_plantilla = GroupBook.objects.create(
        group=plantilla, libro=libro, seccion="teoria", modo=GroupBook.SECUENCIAL
    )
    return {
        "profe": profe,
        "plantilla": plantilla,
        "clase": clase,
        "libro": libro,
        "de_plantilla": de_plantilla,
        "filas": libros_de_grupo.enumerar(de_plantilla),
    }


def test_enviar_lleva_los_elementos_elegidos_y_el_momento(montaje):
    """C178."""
    from clases import libros_de_grupo
    from clases.models import GroupBook

    de_plantilla = montaje["de_plantilla"]
    de_plantilla.seccion = "cancion"
    de_plantilla.modo = GroupBook.EN_CURSO
    de_plantilla.save()
    fuera = montaje["filas"][1]["objeto"]
    libros_de_grupo.excepcion(de_plantilla, fuera, incluido=False)

    libros_de_grupo.enviar(de_plantilla, [montaje["clase"]])

    destino = GroupBook.objects.get(group=montaje["clase"], libro=montaje["libro"])
    assert (destino.seccion, destino.modo) == ("cancion", GroupBook.EN_CURSO)
    excluidos = [f for f in libros_de_grupo.enumerar(destino) if f["item"] and not f["item"].incluido]
    assert len(excluidos) == 1
    assert excluidos[0]["objeto"].pk == fuera.pk


def test_enviar_no_toca_el_avance(montaje):
    """C179. El falsador que hace que esto se pueda usar en enero sin miedo: si
    enviar reseteara lo visto, un libro nuevo en marzo borraría el trimestre.

    **La plantilla tiene fila sobre los MISMOS elementos que el grupo ya trabajó,
    y sin eso este test no vale.** La primera versión dejaba la plantilla sin
    ninguna fila, así que el envío entraba por la rama de «lo que la plantilla no
    menciona» y la rama que de verdad escribe encima no se ejecutaba nunca. Se
    descubrió saboteando el motor para que copiara `estado`: el test pasaba
    igual. Un test que no puede fallar no está probando nada.
    """
    from clases import libros_de_grupo
    from clases.models import GroupBook, GroupBookItem

    clase, libro = montaje["clase"], montaje["libro"]
    de_plantilla = montaje["de_plantilla"]
    de_la_plantilla = montaje["filas"]

    # La plantilla opina sobre los dos elementos que el grupo ya ha trabajado.
    libros_de_grupo.excepcion(de_plantilla, de_la_plantilla[0]["objeto"], orden=3)
    libros_de_grupo.excepcion(de_plantilla, de_la_plantilla[2]["objeto"], incluido=False)

    en_clase = GroupBook.objects.create(group=clase, libro=libro, seccion="teoria")
    filas = libros_de_grupo.enumerar(en_clase)
    libros_de_grupo.excepcion(en_clase, filas[0]["objeto"], estado=GroupBookItem.VISTO)
    libros_de_grupo.excepcion(en_clase, filas[2]["objeto"], a_casa=True)

    libros_de_grupo.enviar(de_plantilla, [clase])

    de_vuelta = {
        (f["tipo"].pk, f["objeto"].pk): f["item"]
        for f in libros_de_grupo.enumerar(en_clase)
    }
    visto = de_vuelta[(filas[0]["tipo"].pk, filas[0]["objeto"].pk)]
    en_casa = de_vuelta[(filas[2]["tipo"].pk, filas[2]["objeto"].pk)]

    assert visto.estado == GroupBookItem.VISTO, "se ha borrado lo visto"
    assert visto.orden == 3, "no ha llegado el orden de la plantilla"
    assert en_casa.a_casa is True, "se ha borrado lo enviado a casa"
    assert en_casa.incluido is False, "no ha llegado la exclusión de la plantilla"


def test_enviar_un_libro_no_toca_los_demas(montaje):
    """C180."""
    from my_library.tests import _libro_con_capitulos
    from clases import libros_de_grupo
    from clases.models import GroupBook

    otro, _ = _libro_con_capitulos("Otro", "otro-enviar", [("Cap", ["x1", "x2"])])
    intacto = GroupBook.objects.create(
        group=montaje["clase"], libro=otro, seccion="ritmo_melodia", modo=GroupBook.EN_CURSO
    )
    fuera = libros_de_grupo.enumerar(intacto)[0]["objeto"]
    libros_de_grupo.excepcion(intacto, fuera, incluido=False)

    libros_de_grupo.enviar(montaje["de_plantilla"], [montaje["clase"]])

    intacto.refresh_from_db()
    assert (intacto.seccion, intacto.modo) == ("ritmo_melodia", GroupBook.EN_CURSO)
    fuera_ahora = [f for f in libros_de_grupo.enumerar(intacto) if f["item"] and not f["item"].incluido]
    assert len(fuera_ahora) == 1, "el envío de un libro ha tocado otro libro"


def test_el_aviso_cuenta_los_retoques_que_va_a_pisar(montaje):
    """El aviso de la pantalla. Si contara de más, el profesor deja de fiarse y
    lo ignora; si contara de menos, pierde trabajo sin avisar."""
    from clases import libros_de_grupo
    from clases.models import GroupBook, GroupBookItem

    clase, libro = montaje["clase"], montaje["libro"]
    en_clase = GroupBook.objects.create(group=clase, libro=libro, seccion="teoria")
    filas = libros_de_grupo.enumerar(en_clase)

    assert libros_de_grupo.retoques_que_pisa(montaje["de_plantilla"], en_clase) == 0

    # Un elemento excluido a mano en el grupo, que la plantilla no excluye.
    libros_de_grupo.excepcion(en_clase, filas[0]["objeto"], incluido=False)
    # Y uno dado por visto, que NO es un retoque: el avance no se pisa.
    libros_de_grupo.excepcion(en_clase, filas[1]["objeto"], estado=GroupBookItem.VISTO)

    assert libros_de_grupo.retoques_que_pisa(montaje["de_plantilla"], en_clase) == 1


def test_no_se_envia_desde_una_clase(client, montaje):
    """Enviar es un gesto de plantilla. Desde una clase no existe, y probarlo por
    HTTP es lo único que lo cierra: la plantilla no enseña el botón, pero la URL
    se puede escribir."""
    from django.urls import reverse
    from clases.models import GroupBook

    en_clase = GroupBook.objects.create(
        group=montaje["clase"], libro=montaje["libro"], seccion="teoria"
    )
    client.force_login(montaje["profe"])

    respuesta = client.get(reverse("clases:nivel_enviar", args=[en_clase.pk]))

    assert respuesta.status_code == 404


def test_no_se_envia_a_los_grupos_de_otro(client, montaje, django_user_model):
    from django.urls import reverse
    from clases.models import GroupBook

    ajeno = django_user_model.objects.create_user(email="ajeno@x.es", password="x")
    suyo = _clase(ajeno, "1-G-ajeno")
    client.force_login(montaje["profe"])

    client.post(
        reverse("clases:nivel_enviar", args=[montaje["de_plantilla"].pk]),
        {"grupos": [str(suyo.pk)]},
    )

    assert not GroupBook.objects.filter(group=suyo).exists()


def test_el_avance_no_cuenta_como_retoque(montaje):
    """Salió en pantalla, no en un test: un grupo que solo tenía cosas vistas y
    mandadas a casa —sin un solo retoque de inclusión ni de orden— avisaba de
    «pisa 2 retoques». Ninguna de esas dos cosas viaja ni se pisa.

    Un aviso que exagera se acaba ignorando, y entonces ya no avisa del caso real.
    """
    from clases import libros_de_grupo
    from clases.models import GroupBook, GroupBookItem

    de_plantilla = montaje["de_plantilla"]
    de_la_plantilla = montaje["filas"]
    libros_de_grupo.excepcion(de_plantilla, de_la_plantilla[0]["objeto"], incluido=False)
    libros_de_grupo.excepcion(de_plantilla, de_la_plantilla[1]["objeto"], orden=7)

    en_clase = GroupBook.objects.create(
        group=montaje["clase"], libro=montaje["libro"], seccion="teoria"
    )
    filas = libros_de_grupo.enumerar(en_clase)
    libros_de_grupo.excepcion(en_clase, filas[0]["objeto"], estado=GroupBookItem.VISTO)
    libros_de_grupo.excepcion(en_clase, filas[1]["objeto"], a_casa=True)

    assert libros_de_grupo.retoques_que_pisa(de_plantilla, en_clase) == 0

    # Y ahora sí: una decisión de inclusión que la plantilla contradice.
    libros_de_grupo.excepcion(en_clase, filas[2]["objeto"], incluido=False)

    assert libros_de_grupo.retoques_que_pisa(de_plantilla, en_clase) == 1
