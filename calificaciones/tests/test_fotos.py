"""Las fotos del alumnado: quién las ve y cómo se emparejan con los listados de secretaría."""

import json

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.urls import reverse

from calificaciones import estado
from calificaciones.management.commands.importar_fotos_alumnado import emparejar
from calificaciones.models import FotoAlumno
from clases.models import Enrollment
from martina_bescos_app.users.tests.factories import UserFactory

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 500


@pytest.fixture
def foto(alumnos):
    foto = FotoAlumno(alumno=alumnos[0])
    foto.imagen.save("a.jpg", ContentFile(JPEG), save=False)
    foto.save()
    return foto


def url(group, alumno):
    return reverse("calificaciones:foto_alumno", args=[group.pk, alumno.pk])


def test_el_profesor_del_grupo_ve_la_foto(client, profesor, group, alumnos, foto):
    client.force_login(profesor)
    respuesta = client.get(url(group, alumnos[0]))
    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "image/jpeg"
    assert respuesta["Cache-Control"].startswith("private")
    assert b"".join(respuesta.streaming_content) == JPEG


def test_otro_profesor_no_la_ve(client, otro_profesor, otro_group, group, alumnos, foto):
    client.force_login(otro_profesor)
    assert client.get(url(group, alumnos[0])).status_code == 404


def test_por_un_grupo_tuyo_no_se_llega_a_un_alumno_de_otro(
    client, otro_profesor, otro_group, alumnos, foto
):
    client.force_login(otro_profesor)
    assert client.get(url(otro_group, alumnos[0])).status_code == 404


def test_el_alumno_no_ve_ni_su_propia_foto(client, group, alumnos, foto):
    client.force_login(alumnos[0])
    assert client.get(url(group, alumnos[0])).status_code != 200


def test_sin_foto_es_404(client, profesor, group, alumnos):
    client.force_login(profesor)
    assert client.get(url(group, alumnos[1])).status_code == 404


def test_el_estado_lleva_la_url_de_la_foto(group, alumnos, profesor, foto):
    filas = {a["id"]: a for a in estado.estado(group, profesor)["alumnos"]}
    assert filas[alumnos[0].pk]["foto"].startswith(url(group, alumnos[0]) + "?v=")
    assert filas[alumnos[1].pk]["foto"] == ""


@pytest.mark.parametrize(
    "en_la_app",
    ["María Balaguer Cebrián", "MARIA BALAGUER CEBRIAN", "Balaguer Cebrián, María"],
)
def test_empareja_sin_acentos_mayusculas_ni_orden(db, en_la_app):
    alumno = UserFactory(name=en_la_app)
    assert emparejar("MARÍA BALAGUER CEBRIÁN", [alumno, UserFactory(name="María Otra Gente")]) == (
        alumno,
        "exacta",
    )


def test_aproximada_solo_si_es_unica(db):
    sin_segundo = UserFactory(name="María Balaguer")
    assert emparejar("MARÍA BALAGUER CEBRIÁN", [sin_segundo]) == (sin_segundo, "aproximada")
    otra = UserFactory(name="María Balaguer")
    assert emparejar("MARÍA BALAGUER CEBRIÁN", [sin_segundo, otra]) == (None, "ambigua")


def test_un_solo_apellido_no_basta(db):
    assert emparejar("MARÍA BALAGUER CEBRIÁN", [UserFactory(name="María")]) == (None, "ninguna")


def test_el_comando_solo_guarda_con_aplicar(tmp_path, group, alumnos):
    alumnos[0].name = "Lucía Comín Tóthová"
    alumnos[0].save()
    (tmp_path / "001.jpg").write_bytes(JPEG)
    (tmp_path / "002.jpg").write_bytes(JPEG)
    manifest = [
        {"fichero": "001.jpg", "nombre": "LUCÍA COMÍN TÓTHOVÁ", "grupo": "1º A", "pdf": "x.pdf", "pagina": 1},
        # La misma alumna, otra vez, en un subgrupo: no cuenta doble.
        {"fichero": "002.jpg", "nombre": "LUCÍA COMÍN TÓTHOVÁ", "grupo": "1º E FRAN", "pdf": "x.pdf", "pagina": 6},
        {"fichero": "002.jpg", "nombre": "NADIE QUE EXISTA", "grupo": "1º A", "pdf": "x.pdf", "pagina": 1},
    ]
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    call_command("importar_fotos_alumnado", str(tmp_path))
    assert not FotoAlumno.objects.exists()

    call_command("importar_fotos_alumnado", str(tmp_path), "--aplicar")
    foto = FotoAlumno.objects.get()
    assert foto.alumno == alumnos[0]
    assert foto.origen == "x.pdf, p. 1"
    assert foto.imagen.name.startswith("calificaciones/fotos/")


def test_el_profesorado_no_recibe_foto(tmp_path, group, profesor):
    profesor.name = "Profe Con Nombre"
    profesor.save()
    (tmp_path / "001.jpg").write_bytes(JPEG)
    (tmp_path / "manifest.json").write_text(
        json.dumps([{"fichero": "001.jpg", "nombre": "PROFE CON NOMBRE", "grupo": "1º A", "pdf": "x", "pagina": 1}])
    )
    call_command("importar_fotos_alumnado", str(tmp_path), "--aplicar")
    assert not FotoAlumno.objects.exists()
    assert not Enrollment.objects.filter(user=profesor).exists()
