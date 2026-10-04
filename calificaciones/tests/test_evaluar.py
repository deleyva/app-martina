"""Fase 62 — Evaluar en clase. Los falsadores de C368 a C377 y los anti-claims.

Las afirmaciones universales se prueban como universales: la conversión de la
rúbrica contra TODAS las combinaciones de 1 a 5 apartados, y el azar con
cientos de tiradas, no con un ejemplo.
"""

import itertools
import json
import random
from unittest import mock
from decimal import Decimal
from fractions import Fraction

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from calificaciones import evaluar
from calificaciones.models import CambioNota, Evidencia, Instrumento, Nota, Plan, Prueba
from calificaciones.plantillas import ESCALA
from clases.models import ClassSession, ClassSessionItem, Enrollment
from martina_bescos_app.users.tests.factories import UserFactory
from my_library.tests import _libro_con_capitulos


# =============================================================================
# Montaje
# =============================================================================


@pytest.fixture
def lectura(plan):
    """Lectura rítmica con la escala del curso y una rúbrica de tres apartados."""
    instrumento = plan.instrumentos.get(nombre="Lectura rítmica")
    instrumento.escala = Instrumento.ESCALA_OPCIONES
    instrumento.opciones = [dict(o) for o in ESCALA]
    instrumento.rubrica = ["Pulso", "Precisión", "Fluidez"]
    instrumento.save()
    return instrumento


@pytest.fixture
def imagen(db):
    _libro, capitulos = _libro_con_capitulos("Libro", "libro-evaluar", [("Cap", ["ejercicio-12"])])
    return capitulos[0][1][0]


@pytest.fixture
def elemento(group, profesor, imagen, lectura):
    sesion = ClassSession.objects.create(
        teacher=profesor, group=group, date=timezone.localdate(), title="Clase"
    )
    return ClassSessionItem.objects.create(
        session=sesion,
        content_type=ContentType.objects.get_for_model(imagen),
        object_id=imagen.pk,
        order=0,
        instrumento=lectura,
    )


def _referencia(puntos):
    """La regla acordada, escrita de otra forma: con fracciones exactas."""
    media = Fraction(sum(puntos), len(puntos))
    if media == 3:
        return "SB"
    if media >= Fraction(5, 2):
        return "NT"
    if media >= 2:
        return "BI"
    if media >= Fraction(3, 2):
        return "SU"
    return "IN"


# =============================================================================
# C372 · la rúbrica da la letra
# =============================================================================


def test_la_rubrica_da_la_letra_en_todas_las_combinaciones():
    """C372. Todas las combinaciones de 1 a 5 apartados (363 casos)."""
    casos = 0
    for n in range(1, 6):
        for puntos in itertools.product((1, 2, 3), repeat=n):
            assert evaluar.letra_de_rubrica(puntos) == _referencia(puntos), puntos
            casos += 1
    assert casos == 3 + 9 + 27 + 81 + 243


def test_la_tabla_acordada_con_tres_apartados():
    """C372. La tabla que vio Jesús al elegir los cortes."""
    tabla = {
        (3, 3, 3): "SB", (3, 3, 2): "NT", (3, 2, 2): "BI", (2, 2, 2): "BI",
        (3, 2, 1): "BI", (2, 2, 1): "SU", (2, 1, 1): "IN", (1, 1, 1): "IN",
    }
    for puntos, letra in tabla.items():
        assert evaluar.letra_de_rubrica(puntos) == letra


@pytest.mark.parametrize("malos", [[], [0], [4], [1, 2, 5], ["3"]])
def test_puntos_fuera_de_1_a_3_no_valen(malos):
    with pytest.raises(ValueError):
        evaluar.letra_de_rubrica(malos)


# =============================================================================
# El valor de la letra en la escala del instrumento
# =============================================================================


def test_la_letra_vale_lo_de_su_escala(lectura, plan):
    for opcion in ESCALA:
        assert evaluar.valor_de_letra(lectura, opcion["etiqueta"]) == Decimal(str(opcion["valor"]))
    numerico = plan.instrumentos.get(nombre="Dictado")
    assert evaluar.valor_de_letra(numerico, "NT") == Decimal("8")


def test_una_escala_de_opciones_sin_esa_letra_se_rechaza(plan):
    viejo = plan.instrumentos.get(nombre="Dictado")
    viejo.escala = Instrumento.ESCALA_OPCIONES
    viejo.opciones = [{"etiqueta": "A", "valor": 10}, {"etiqueta": "B", "valor": 8}]
    viejo.save()
    with pytest.raises(ValueError, match="califica con A, B"):
        evaluar.valor_de_letra(viejo, "SB")


# =============================================================================
# C373 · C374 · Anti-A · guardar la nota
# =============================================================================


def test_evaluar_escribe_en_la_columna_del_instrumento(group, profesor, alumnos, lectura, elemento):
    """C373 y Anti-A: una nota, en esa columna, y nada más se toca."""
    prueba = lectura.prueba_para_evaluar()
    Nota.poner(prueba, alumnos[1], Decimal("8"), profesor)
    pruebas_antes = Prueba.objects.count()
    otras_antes = list(Nota.objects.exclude(alumno=alumnos[0]).values_list("pk", "valor"))

    nota = evaluar.evaluar(
        group=group, instrumento=lectura, alumno=alumnos[0], user=profesor,
        puntos=[3, 2, 2], comentario=" Pulso firme ", elemento=elemento,
    )

    assert nota.prueba == prueba
    assert nota.valor == Decimal("6.5")
    assert nota.comentario == "Pulso firme"
    guardada = Nota.objects.get(pk=nota.pk)
    assert guardada.rubrica["puntos"] == [3, 2, 2]
    assert guardada.rubrica["apartados"] == ["Pulso", "Precisión", "Fluidez"]
    assert guardada.rubrica["propuesta"] == "BI" and guardada.rubrica["letra"] == "BI"
    assert guardada.rubrica["sesion"] == elemento.session_id
    assert CambioNota.objects.filter(nota=nota, despues="6.5").exists()
    assert Prueba.objects.count() == pruebas_antes
    assert list(Nota.objects.exclude(alumno=alumnos[0]).values_list("pk", "valor")) == otras_antes


def test_evaluar_otra_vez_sustituye(group, profesor, alumnos, lectura):
    """C373. Una nota por alumno e instrumento; la anterior queda en el historial."""
    evaluar.evaluar(group=group, instrumento=lectura, alumno=alumnos[0], user=profesor, puntos=[1, 1, 1])
    evaluar.evaluar(group=group, instrumento=lectura, alumno=alumnos[0], user=profesor, puntos=[3, 3, 3])

    assert Nota.objects.filter(alumno=alumnos[0], prueba__instrumento=lectura).count() == 1
    assert Nota.objects.get(alumno=alumnos[0], prueba__instrumento=lectura).valor == Decimal("9.5")
    assert list(CambioNota.objects.filter(nota__alumno=alumnos[0]).order_by("ts", "pk").values_list("antes", "despues")) == [
        ("", "4"), ("4", "9.5"),
    ]


def test_con_varias_columnas_va_a_la_mas_reciente(group, profesor, alumnos, lectura):
    """C373."""
    from datetime import timedelta

    nueva = Prueba.objects.create(instrumento=lectura, nombre="2ª lectura", fecha=timezone.localdate() + timedelta(days=3))
    Prueba.objects.create(instrumento=lectura, nombre="Oculta", fecha=timezone.localdate() + timedelta(days=9), activa=False)

    nota = evaluar.evaluar(group=group, instrumento=lectura, alumno=alumnos[0], user=profesor, letra="NT")

    assert nota.prueba == nueva


def test_la_letra_a_mano_manda(group, profesor, alumnos, lectura, plan):
    """C374. Cambiar la propuesta, y evaluar sin rúbrica."""
    nota = evaluar.evaluar(
        group=group, instrumento=lectura, alumno=alumnos[0], user=profesor, puntos=[2, 2, 2], letra="nt"
    )
    assert nota.valor == Decimal("8")
    assert nota.rubrica["propuesta"] == "BI" and nota.rubrica["letra"] == "NT"

    sin_rubrica = plan.instrumentos.get(nombre="Dictado")
    assert evaluar.evaluar(group=group, instrumento=sin_rubrica, alumno=alumnos[1], user=profesor, letra="SU").valor == Decimal("5.5")
    with pytest.raises(ValueError, match="Falta la calificación"):
        evaluar.evaluar(group=group, instrumento=sin_rubrica, alumno=alumnos[2], user=profesor)


def test_rubrica_incompleta_o_alumno_ajeno_se_rechazan(group, profesor, alumnos, lectura):
    with pytest.raises(ValueError, match="Falta puntuar"):
        evaluar.evaluar(group=group, instrumento=lectura, alumno=alumnos[0], user=profesor, puntos=[3, 3])
    de_fuera = UserFactory()
    with pytest.raises(ValueError, match="no es de este grupo"):
        evaluar.evaluar(group=group, instrumento=lectura, alumno=de_fuera, user=profesor, letra="SB")
    assert not Nota.objects.filter(alumno=de_fuera).exists()


# =============================================================================
# C371 · al azar, entre quienes no tienen nota
# =============================================================================


def test_el_azar_nunca_devuelve_a_quien_ya_tiene_nota(group, profesor, lectura):
    """C371, universal: 400 tiradas con varios estados del grupo."""
    alumnos = [UserFactory(name=f"A{n}") for n in range(8)]
    for a in alumnos:
        Enrollment.objects.create(user=a, group=group)
    prueba = lectura.prueba_para_evaluar()
    azar = random.Random(62)
    for evaluados in range(0, 8):
        if evaluados:
            Nota.poner(prueba, alumnos[evaluados - 1], Decimal("8"), profesor)
        con_nota = {a.pk for a in alumnos[:evaluados]}
        for _ in range(50):
            elegido = evaluar.al_azar(group, lectura, azar=azar)
            assert elegido is not None and elegido.pk not in con_nota
    Nota.poner(prueba, alumnos[7], Decimal("8"), profesor)
    assert evaluar.al_azar(group, lectura) is None


def test_el_azar_salta_a_los_ausentes(group, alumnos, lectura):
    """C371. «Otro»: excluir al que ha salido."""
    for _ in range(100):
        assert evaluar.al_azar(group, lectura, excluir=[alumnos[0].pk, alumnos[1].pk]) == alumnos[2]
    assert evaluar.al_azar(group, lectura, excluir=[a.pk for a in alumnos]) is None


def test_una_nota_vacia_no_cuenta_como_nota(group, profesor, alumnos, lectura):
    """C371. `valor` nulo es «sin nota»: sigue entrando en el sorteo."""
    Nota.poner(lectura.prueba_para_evaluar(), alumnos[0], None, profesor, comentario="sin nota aún")
    assert alumnos[0] in evaluar.sin_nota(group, lectura)


# =============================================================================
# C368 · la rúbrica del instrumento
# =============================================================================


def test_la_rubrica_se_limpia():
    assert Instrumento.limpiar_rubrica("  Pulso \n\nPrecisión\npulso\n Fluidez ") == ["Pulso", "Precisión", "Fluidez"]
    assert Instrumento.limpiar_rubrica("") == []


def test_la_rubrica_se_guarda_desde_el_plan(client, profesor, plan):
    """C368."""
    instrumento = plan.instrumentos.get(nombre="Teoría")
    client.force_login(profesor)
    r = client.post(
        reverse("calificaciones:instrumento_editar", args=[instrumento.pk]),
        {"nombre": "Teoría", "abreviatura": "Teo", "rubrica": "Vocabulario\nRazonamiento\n"},
    )
    assert r.status_code == 302
    instrumento.refresh_from_db()
    assert instrumento.rubrica == ["Vocabulario", "Razonamiento"]

    html = client.get(reverse("calificaciones:plan", args=[plan.pk])).content.decode()
    assert 'name="rubrica"' in html and "Vocabulario\nRazonamiento" in html
    assert "{#" not in html


# =============================================================================
# C376 · reordenar instrumentos
# =============================================================================


def _orden(plan):
    return list(plan.instrumentos.order_by("orden", "pk").values_list("nombre", flat=True))


def test_mover_un_instrumento(plan):
    """C376. Y con empates en `orden`, que el formulario del plan permite."""
    assert _orden(plan) == ["Teoría", "Lectura rítmica", "Dictado", "Cuaderno"]
    plan.instrumentos.update(orden=0)
    dictado = plan.instrumentos.get(nombre="Dictado")
    assert dictado.mover(-1) is True
    assert _orden(plan) == ["Teoría", "Dictado", "Lectura rítmica", "Cuaderno"]
    assert list(plan.instrumentos.order_by("orden").values_list("orden", flat=True)) == [0, 1, 2, 3]

    primero = plan.instrumentos.get(nombre="Teoría")
    assert primero.mover(-1) is False
    ultimo = plan.instrumentos.get(nombre="Cuaderno")
    assert ultimo.mover(1) is False
    assert _orden(plan) == ["Teoría", "Dictado", "Lectura rítmica", "Cuaderno"]


def test_mover_por_la_vista_y_se_ve_en_el_registro(client, profesor, otro_profesor, otro_group, group, plan):
    """C376 y C377: el orden nuevo sale en las columnas del registro."""
    cuaderno = plan.instrumentos.get(nombre="Cuaderno")
    url = reverse("calificaciones:instrumento_mover", args=[cuaderno.pk])

    client.force_login(otro_profesor)
    assert client.post(url, {"paso": -1}).status_code == 404

    client.force_login(profesor)
    assert client.post(url, {"paso": 3}).status_code == 400
    r = client.post(url, {"paso": -1}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
    assert r.json() == {"ok": True, "movido": True}

    estado = client.get(reverse("calificaciones:estado", args=[group.pk])).json()
    columnas = [c["nombre"] for c in estado["trimestres"]["1"]["columnas"]]
    assert columnas == ["Teoría", "Lectura rítmica", "Cuaderno", "Dictado"]


# =============================================================================
# C369 · C377 · marcar evaluable
# =============================================================================


def test_marcar_y_desmarcar_evaluable(client, profesor, group, plan, elemento):
    """C369."""
    client.force_login(profesor)
    url = reverse("clases:item_evaluable", args=[elemento.pk])
    dictado = plan.instrumentos.get(nombre="Dictado")

    r = client.post(url, {"instrumento": dictado.pk})
    html = r.content.decode()
    elemento.refresh_from_db()
    assert r.status_code == 200 and elemento.instrumento == dictado
    assert "✓ evaluable · Dict" in html and "1ª evaluación" in html
    assert "{#" not in html

    client.post(url, {"instrumento": ""})
    elemento.refresh_from_db()
    assert elemento.instrumento is None


def test_evaluable_solo_con_instrumentos_del_grupo(client, profesor, otro_profesor, marco, otro_group, elemento):
    """C377: instrumento de otro plan, y profesor de otro grupo."""
    ajeno = Plan.objects.create(marco=marco, trimestre=1, nombre="Ajeno")
    ajeno.groups.add(otro_group)
    suyo = Instrumento.objects.create(plan=ajeno, nombre="Ajeno", abreviatura="Aj")
    url = reverse("clases:item_evaluable", args=[elemento.pk])

    client.force_login(profesor)
    assert client.post(url, {"instrumento": suyo.pk}).status_code == 404
    client.force_login(otro_profesor)
    assert client.post(url, {"instrumento": ""}).status_code == 404
    elemento.refresh_from_db()
    assert elemento.instrumento is not None


def test_la_fila_de_la_sesion_lleva_el_boton(client, profesor, elemento):
    """C369: el botón sale en la pantalla de editar la sesión."""
    client.force_login(profesor)
    html = client.get(reverse("clases:class_session_edit", args=[elemento.session_id])).content.decode()
    assert reverse("clases:item_evaluable", args=[elemento.pk]) in html
    assert "✓ evaluable · L.rít" in html
    assert "{#" not in html


# =============================================================================
# C370 · C371 · C375 · C377 · evaluar en clase
# =============================================================================


def test_el_boton_evaluar_solo_en_lo_evaluable(client, profesor, group, alumnos, imagen, elemento):
    """C370: el dato solo va en el elemento evaluable, y solo para el profesor."""
    ClassSessionItem.objects.create(
        session=elemento.session, content_type=elemento.content_type, object_id=imagen.pk, order=1
    )
    client.force_login(profesor)
    r = client.get(reverse("clases:class_session_present", args=[elemento.session_id]))
    playlist = json.loads(r.context["playlist_json"])
    assert [p["instrumento"] for p in playlist] == [{"id": elemento.instrumento_id, "nombre": "Lectura rítmica"}, None]
    html = r.content.decode()
    assert 'id="fab-evaluar"' in html and 'id="panel-evaluar"' in html
    assert "{#" not in html

    client.force_login(alumnos[0])
    r = client.get(reverse("clases:class_session_present", args=[elemento.session_id]))
    assert all(p["instrumento"] is None for p in json.loads(r.context["playlist_json"]))
    assert 'id="fab-evaluar"' not in r.content.decode()


def test_el_panel_evalua_de_punta_a_punta(client, profesor, group, alumnos, lectura, elemento):
    """C371, C373 y C375 por HTTP, con las mismas llamadas que hace el panel."""
    client.force_login(profesor)
    estado = client.get(reverse("clases:evaluar_estado", args=[elemento.pk])).json()
    assert estado["instrumento"]["rubrica"] == ["Pulso", "Precisión", "Fluidez"]
    assert estado["prueba"] == lectura.prueba_para_evaluar().pk
    assert [a["letra"] for a in estado["alumnos"]] == ["", "", ""]

    excluir = f"{alumnos[0].pk},{alumnos[1].pk}"
    azar = client.get(reverse("clases:evaluar_azar", args=[elemento.pk]) + f"?excluir={excluir}").json()
    assert azar["alumno"]["id"] == alumnos[2].pk and azar["quedan"] == 1

    r = client.post(
        reverse("clases:evaluar_guardar", args=[elemento.pk]),
        data=json.dumps({"alumno": alumnos[2].pk, "puntos": [3, 3, 2], "comentario": "Bien"}),
        content_type="application/json",
    )
    assert r.json()["letra"] == "NT"
    estado = client.get(reverse("clases:evaluar_estado", args=[elemento.pk])).json()
    assert [a["letra"] for a in estado["alumnos"]][2] == "NT"
    assert estado["alumnos"][2]["puntos"] == [3, 3, 2]

    # C375: la grabación entra por la misma puerta que el clip del registro.
    audio = SimpleUploadedFile("clase-1.webm", b"\x1aE\xdf\xa3audio", content_type="audio/webm")
    r = client.post(
        reverse("calificaciones:evidencia_subir", args=[estado["grupo"]]),
        {"prueba": estado["prueba"], "alumno": alumnos[2].pk, "tipo": "audio", "archivo": audio},
    )
    assert r.status_code == 200
    assert Evidencia.objects.filter(prueba_id=estado["prueba"], alumno=alumnos[2], tipo="audio").count() == 1


def test_evaluar_rechaza_lo_ajeno(client, profesor, otro_profesor, otro_group, alumnos, elemento):
    """C377."""
    client.force_login(otro_profesor)
    assert client.get(reverse("clases:evaluar_estado", args=[elemento.pk])).status_code == 404

    client.force_login(profesor)
    de_fuera = UserFactory()
    r = client.post(
        reverse("clases:evaluar_guardar", args=[elemento.pk]),
        data=json.dumps({"alumno": de_fuera.pk, "letra": "SB"}),
        content_type="application/json",
    )
    assert r.status_code == 400 and not Nota.objects.filter(alumno=de_fuera).exists()

    elemento.instrumento = None
    elemento.save()
    assert client.get(reverse("clases:evaluar_estado", args=[elemento.pk])).status_code == 404


def test_el_trimestre_de_la_sesion_va_arriba(client, profesor, group, marco, plan, elemento):
    """C369. Encontrado en el navegador: en octubre se ofrecía arriba la 2ª evaluación."""
    from datetime import date

    assert [evaluar.trimestre_de(date(2026, m, 15)) for m in (9, 12, 1, 3, 4, 6)] == [1, 1, 2, 2, 3, 3]

    segundo = Plan.objects.create(marco=marco, trimestre=2, nombre="Plan 2ª")
    segundo.groups.add(group)
    Instrumento.objects.create(plan=segundo, nombre="Solo de la segunda", abreviatura="S2")

    elemento.session.date = date(2026, 10, 6)
    elemento.session.save()
    planes = evaluar.instrumentos_del_grupo(group, elemento.session.date)
    assert [(p["trimestre"], p["actual"]) for p in planes] == [(1, True), (2, False)]

    client.force_login(profesor)
    html = client.post(reverse("clases:item_evaluable", args=[elemento.pk]), {"instrumento": plan.instrumentos.first().pk}).content.decode()
    assert html.index("1ª evaluación") < html.index("Otros trimestres") < html.index("Solo de la segunda")

    # Sin plan del trimestre de la fecha, todo abierto y sin pliegue.
    elemento.session.date = date(2027, 5, 10)
    elemento.session.save()
    html = client.post(reverse("clases:item_evaluable", args=[elemento.pk]), {"instrumento": ""}).content.decode()
    assert "Otros trimestres" not in html and "Solo de la segunda" in html


# =============================================================================
# Lo que encontró la revisión independiente (2026-10-04)
# =============================================================================


def test_los_puntos_viejos_no_se_ofrecen_si_el_registro_cambio_la_nota(client, profesor, group, alumnos, lectura, elemento):
    """Revisión 3: un NT de rúbrica cambiado a SB en el registro no vuelve a proponer NT."""
    evaluar.evaluar(group=group, instrumento=lectura, alumno=alumnos[0], user=profesor, puntos=[3, 2, 3])
    client.force_login(profesor)
    estado = client.get(reverse("clases:evaluar_estado", args=[elemento.pk])).json()
    assert estado["alumnos"][0]["puntos"] == [3, 2, 3]

    Nota.poner(lectura.prueba_para_evaluar(), alumnos[0], Decimal("9.5"), profesor)
    estado = client.get(reverse("clases:evaluar_estado", args=[elemento.pk])).json()
    assert estado["alumnos"][0]["letra"] == "SB"
    assert estado["alumnos"][0]["puntos"] == []


def test_un_nombre_con_script_no_rompe_la_presentacion(client, profesor, lectura, elemento):
    """Revisión 4: el nombre del instrumento va dentro de un <script>."""
    lectura.nombre = "</script><img src=x onerror=alert(1)>"
    lectura.save()
    client.force_login(profesor)
    r = client.get(reverse("clases:class_session_present", args=[elemento.session_id]))
    html = r.content.decode()
    assert "</script><img src=x" not in html
    assert json.loads(r.context["playlist_json"])[0]["instrumento"]["nombre"] == lectura.nombre


@pytest.mark.parametrize(
    "cuerpo",
    [
        "[]",
        '{"alumno": "abc", "letra": "SB"}',
        '{"alumno": %(a)s, "letra": 5}',
        '{"alumno": %(a)s, "puntos": [null, 2, 3]}',
        '{"alumno": %(a)s, "puntos": 3}',
        '{"alumno": %(a)s, "letra": "SB", "comentario": 5}',
    ],
)
def test_una_peticion_mal_formada_da_400_y_no_500(client, profesor, alumnos, elemento, cuerpo):
    """Revisión 5."""
    client.force_login(profesor)
    r = client.post(
        reverse("clases:evaluar_guardar", args=[elemento.pk]),
        data=cuerpo % {"a": alumnos[0].pk} if "%(a)s" in cuerpo else cuerpo,
        content_type="application/json",
    )
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        # Lo único que puede valer de estos: un comentario numérico se guarda como texto.
        assert Nota.objects.get(alumno=alumnos[0]).comentario == "5"


# =============================================================================
# Fase 62·1 · evaluar en grupo de hasta tres, una sola grabación
# =============================================================================


def _audio(nombre="clase-grupo.webm"):
    return SimpleUploadedFile(nombre, b"\x1aE\xdf\xa3audio-de-tres", content_type="audio/webm")


def _ficheros_en_disco(settings):
    import os

    raiz = os.path.join(settings.MEDIA_ROOT, "calificaciones")
    return sorted(
        os.path.join(d, f) for d, _, fs in os.walk(raiz) for f in fs
    ) if os.path.isdir(raiz) else []


def test_una_grabacion_para_tres_es_un_solo_fichero(settings, group, profesor, alumnos, lectura):
    """C383: un fichero en disco, tres evidencias que lo comparten (fase 62·2)."""
    creadas = evaluar.guardar_grabacion(
        group=group, instrumento=lectura, alumnos=alumnos, fichero=_audio(), tipo="audio", user=profesor
    )
    prueba = lectura.prueba_para_evaluar()
    assert [e.alumno_id for e in creadas] == [a.pk for a in alumnos]
    assert all(e.prueba_id == prueba.pk and e.tipo == "audio" for e in creadas)
    assert len({e.archivo.name for e in creadas}) == 1
    assert len({e.grabacion for e in creadas}) == 1 and creadas[0].grabacion is not None
    assert len(_ficheros_en_disco(settings)) == 1
    for e in Evidencia.objects.all():
        with e.archivo.open("rb") as f:
            assert f.read() == b"\x1aE\xdf\xa3audio-de-tres"


def test_borrar_la_de_uno_no_deja_a_los_otros_sin_grabacion(settings, group, profesor, alumnos, lectura):
    """C384: el fichero compartido se borra con la ÚLTIMA evidencia, no antes."""
    creadas = evaluar.guardar_grabacion(
        group=group, instrumento=lectura, alumnos=alumnos, fichero=_audio(), tipo="audio", user=profesor
    )
    nombre = creadas[0].archivo.name
    creadas[0].delete()
    creadas[1].delete()
    assert creadas[2].archivo.storage.exists(nombre)
    creadas[2].delete()
    assert _ficheros_en_disco(settings) == []


def test_una_evidencia_suelta_sigue_borrando_su_fichero(settings, group, profesor, alumnos, lectura):
    """Anti-F: sin grabación de grupo, borrar es como siempre."""
    from django.core.files.base import ContentFile

    suelta = Evidencia(prueba=lectura.prueba_para_evaluar(), alumno=alumnos[0], tipo="audio", created_by=profesor)
    suelta.archivo.save("suelta.webm", ContentFile(b"x"), save=True)
    suelta.delete()
    assert _ficheros_en_disco(settings) == []


def _ffmpeg_que_funciona(comando, **_):
    from types import SimpleNamespace

    with open(comando[-1], "wb") as f:
        f.write(b"mp4-comprimido")
    return SimpleNamespace(returncode=0, stderr="")


def test_un_video_de_grupo_se_comprime_una_vez(settings, group, profesor, alumnos, lectura):
    """C385: una pasada de ffmpeg, las tres en el mismo MP4, el original borrado."""
    from calificaciones.tasks import comprimir_video

    video = SimpleUploadedFile("clase.webm", b"video-de-tres", content_type="video/webm")
    with mock.patch("calificaciones.tasks.comprimir_video"):
        creadas = evaluar.guardar_grabacion(
            group=group, instrumento=lectura, alumnos=alumnos, fichero=video, tipo="video", user=profesor
        )
    assert all(e.estado == Evidencia.PENDIENTE for e in creadas)
    original = creadas[0].archivo.name

    with mock.patch("calificaciones.tasks.subprocess.run", side_effect=_ffmpeg_que_funciona) as ffmpeg:
        comprimir_video.call_local(creadas[0].pk)

    assert ffmpeg.call_count == 1
    finales = list(Evidencia.objects.order_by("pk"))
    assert {e.archivo_comprimido.name for e in finales} != {""}
    assert len({e.archivo_comprimido.name for e in finales}) == 1
    assert all(not e.archivo and e.estado == Evidencia.LISTO and e.tipo_mime == "video/mp4" for e in finales)
    assert not finales[0].archivo_comprimido.storage.exists(original)
    assert len(_ficheros_en_disco(settings)) == 1
    with finales[2].fichero.open("rb") as f:
        assert f.read() == b"mp4-comprimido"

    finales[0].delete()
    finales[1].delete()
    assert finales[2].fichero.storage.exists(finales[2].fichero.name)


def test_si_ffmpeg_falla_fallan_todas(group, profesor, alumnos, lectura):
    """C385: el fallo se ve en las tres, no solo en la primera."""
    from types import SimpleNamespace

    from calificaciones.tasks import comprimir_video

    video = SimpleUploadedFile("clase.webm", b"video-de-tres", content_type="video/webm")
    with mock.patch("calificaciones.tasks.comprimir_video"):
        creadas = evaluar.guardar_grabacion(
            group=group, instrumento=lectura, alumnos=alumnos, fichero=video, tipo="video", user=profesor
        )
    with mock.patch("calificaciones.tasks.subprocess.run", return_value=SimpleNamespace(returncode=1, stderr="roto")):
        comprimir_video.call_local(creadas[0].pk)
    assert set(Evidencia.objects.values_list("estado", flat=True)) == {Evidencia.FALLIDO}


def test_la_grabacion_de_grupo_tiene_limites(group, profesor, alumnos, lectura, otro_group):
    """C378 y C382: de 1 a 3, sin repetidos, del grupo, y solo audio o vídeo."""
    cuarto = UserFactory()
    Enrollment.objects.create(user=cuarto, group=group)
    casos = [
        ([], "audio", "entre 1 y 3"),
        (alumnos + [cuarto], "audio", "entre 1 y 3"),
        ([alumnos[0], alumnos[0]], "audio", "repetido"),
        ([alumnos[0], UserFactory()], "audio", "no es de este grupo"),
        ([alumnos[0]], "foto", "audio o vídeo"),
    ]
    for lista, tipo, mensaje in casos:
        with pytest.raises(ValueError, match=mensaje):
            evaluar.guardar_grabacion(group=group, instrumento=lectura, alumnos=lista, fichero=_audio(), tipo=tipo, user=profesor)
    assert not Evidencia.objects.exists()


def test_la_grabacion_de_grupo_por_http(client, profesor, otro_profesor, otro_group, alumnos, elemento):
    """C379, C382 y C377, por la misma puerta que usa la franja."""
    url = reverse("clases:evaluar_grabacion", args=[elemento.pk])
    client.force_login(profesor)
    r = client.post(url, {"alumnos": [alumnos[0].pk, alumnos[2].pk], "tipo": "audio", "archivo": _audio()})
    assert r.status_code == 200
    assert sorted(e["alumno"] for e in r.json()["evidencias"]) == sorted([alumnos[0].pk, alumnos[2].pk])

    r = client.post(url, {"alumnos": [a.pk for a in alumnos] + [UserFactory().pk], "tipo": "audio", "archivo": _audio()})
    assert r.status_code == 400

    client.force_login(otro_profesor)
    assert client.post(url, {"alumnos": [alumnos[0].pk], "tipo": "audio", "archivo": _audio()}).status_code == 404

    client.force_login(profesor)
    elemento.instrumento = None
    elemento.save()
    assert client.post(url, {"alumnos": [alumnos[0].pk], "tipo": "audio", "archivo": _audio()}).status_code == 404
    assert Evidencia.objects.count() == 2


def test_la_franja_es_pequena(client, profesor, elemento):
    """C381: la franja no pasa de 12 px de letra ni del 45 % de alto."""
    client.force_login(profesor)
    html = client.get(reverse("clases:class_session_present", args=[elemento.session_id])).content.decode()
    estilo = html[html.index("#panel-evaluar {"):html.index("#panel-evaluar.abierto")]
    assert "font-size: 12px" in estilo and "max-height: 45vh" in estilo and "bottom: 8px" in estilo
    assert "evaluar/grabacion/" in html


def test_una_grabacion_vacia_no_se_guarda(group, profesor, alumnos, lectura):
    """Visto en el navegador: un MediaRecorder sin datos dejaba evidencias de 0 bytes."""
    vacio = SimpleUploadedFile("clase.webm", b"", content_type="audio/webm")
    with pytest.raises(ValueError, match="vacía"):
        evaluar.guardar_grabacion(group=group, instrumento=lectura, alumnos=alumnos[:2], fichero=vacio, tipo="audio", user=profesor)
    assert not Evidencia.objects.exists()


# =============================================================================
# Pantalla encendida (2026-10-04)
# =============================================================================


def test_la_pantalla_no_se_apaga_en_la_app(client, profesor, group, plan, elemento):
    """El script de Wake Lock va en las páginas de la app: base, presentación y registro."""
    client.force_login(profesor)
    paginas = [
        reverse("clases:class_session_present", args=[elemento.session_id]),
        reverse("calificaciones:registro", args=[group.pk]),
        reverse("clases:lectura"),
    ]
    for url in paginas:
        html = client.get(url).content.decode()
        assert html.count("js/pantalla_encendida.js") == 1, url
        assert html.index("pantalla_encendida.js") < html.index("</head>"), url
