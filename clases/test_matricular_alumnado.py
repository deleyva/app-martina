"""El comando `matricular_alumnado`: la lista del centro entra en los grupos de la app.

Se va a lanzar cada septiembre y más de una vez el mismo septiembre (la lista
cambia las primeras semanas), así que lo que se prueba es que repetirlo no
duplica, que reactiva bajas, y que no se inventa cuentas para quien no puede
entrar con Google.
"""

import io

import pytest
from allauth.account.models import EmailAddress
from django.core.management import CommandError, call_command

from clases.management.commands.matricular_alumnado import curso_academico_actual
from clases.models import Enrollment, Group, Subject

CSV = (
    "﻿Nombre;Apellidos;Curso;Grupo;mail\n"
    '"Ana";"Pérez Gil";"3º ESO";"3º E";"0001aperez@iesmartinabescos.es"\n'
    '"Luis";"Ruiz";"3º ESO";"3º G";"0002lruiz@iesmartinabescos.es"\n'
    '"Eva";"Sanz";"3º ESO";"3º E";"eva.familia@gmail.com"\n'
    '"Iván";"Mur";"1º ESO";"1º G";"0003imur@iesmartinabescos.es"\n'
    '"Sin";"Mapa";"2º ESO";"2º B";"0004smapa@iesmartinabescos.es"\n'
)

MAPA = ["--grupo", "3º E=3-EG-BIL", "--grupo", "3º G=3-EG-BIL", "--grupo", "1º G=1-G-BIL"]


@pytest.fixture
def grupos(db):
    asignatura = Subject.objects.get_or_create(name="Música", defaults={"code": "MUS"})[0]
    return {
        n: Group.objects.create(name=n, subject=asignatura, academic_year="2026-2027")
        for n in ("3-EG-BIL", "1-G-BIL")
    }


def _csv(tmp_path, texto=CSV):
    ruta = tmp_path / "lista.csv"
    ruta.write_text(texto, encoding="utf-8")
    return str(ruta)


def _lanzar(ruta, *extra):
    salida = io.StringIO()
    call_command("matricular_alumnado", ruta, *MAPA, "--curso", "2026-2027", *extra, stdout=salida)
    return salida.getvalue()


def test_sin_aplicar_no_escribe_nada(db, grupos, tmp_path, django_user_model):
    salida = _lanzar(_csv(tmp_path))

    assert django_user_model.objects.count() == 0
    assert Enrollment.objects.count() == 0
    assert "usuarios a crear: 3" in salida
    assert "sin correo del centro: 1" in salida
    assert "«2º B» 1" in salida
    assert "No se ha escrito nada" in salida


def test_aplicar_precrea_usuarios_y_matricula(db, grupos, tmp_path, django_user_model):
    salida = _lanzar(_csv(tmp_path), "--aplicar")

    ana = django_user_model.objects.get(email="0001aperez@iesmartinabescos.es")
    assert (ana.first_name, ana.last_name, ana.name) == ("Ana", "Pérez Gil", "Ana Pérez Gil")
    assert not ana.has_usable_password(), "no se le inventa contraseña: entra con Google"
    assert EmailAddress.objects.get(user=ana).verified, "allauth enlaza Google por el correo verificado"

    assert set(grupos["3-EG-BIL"].enrollments.values_list("user__email", flat=True)) == {
        "0001aperez@iesmartinabescos.es",
        "0002lruiz@iesmartinabescos.es",
    }
    assert grupos["1-G-BIL"].enrollments.count() == 1
    assert not django_user_model.objects.filter(email__icontains="gmail").exists()
    assert not django_user_model.objects.filter(email__icontains="smapa").exists()
    assert "3-EG-BIL: nueva 2" in salida
    assert "usuarios creados: 3" in salida


def test_repetir_no_duplica_y_reactiva_bajas(db, grupos, tmp_path, django_user_model):
    ruta = _csv(tmp_path)
    _lanzar(ruta, "--aplicar")
    baja = Enrollment.objects.get(user__email="0002lruiz@iesmartinabescos.es")
    baja.is_active = False
    baja.save()

    salida = _lanzar(ruta, "--aplicar")

    assert django_user_model.objects.count() == 3
    assert Enrollment.objects.count() == 3
    assert Enrollment.objects.get(pk=baja.pk).is_active
    assert "3-EG-BIL: reactivada 1, ya_estaba 1" in salida
    assert "usuarios ya existentes: 3" in salida


def test_usuario_existente_conserva_su_nombre(db, grupos, tmp_path, django_user_model):
    """Google pisa el nombre en cada entrada; la lista del centro no gana a eso."""
    django_user_model.objects.create_user(
        email="0001aperez@iesmartinabescos.es", password="x", name="Ana María Pérez Gil"
    )

    _lanzar(_csv(tmp_path), "--aplicar")

    assert django_user_model.objects.get(email="0001aperez@iesmartinabescos.es").name == "Ana María Pérez Gil"


def test_no_imprime_nombres_salvo_que_se_pida(db, grupos, tmp_path):
    ruta = _csv(tmp_path)
    assert "Pérez" not in _lanzar(ruta)
    assert "Pérez" in _lanzar(ruta, "--nombres")


def test_grupo_de_la_app_inexistente_para_antes_de_tocar_nada(db, grupos, tmp_path, django_user_model):
    with pytest.raises(CommandError, match="4-AC-BIL"):
        call_command(
            "matricular_alumnado", _csv(tmp_path), *MAPA, "--grupo", "4º A=4-AC-BIL",
            "--curso", "2026-2027", "--aplicar",
        )
    assert django_user_model.objects.count() == 0


def test_sin_mapa_de_grupos_se_niega(db, grupos, tmp_path):
    with pytest.raises(CommandError, match="--grupo"):
        call_command("matricular_alumnado", _csv(tmp_path))


def test_lee_de_la_entrada_estandar(db, grupos, monkeypatch):
    class Entrada:
        buffer = io.BytesIO(CSV.encode("utf-8"))

    monkeypatch.setattr("sys.stdin", Entrada)
    salida = _lanzar("-", "--aplicar")

    assert Enrollment.objects.count() == 3
    assert "Hecho." in salida


def test_curso_academico_arranca_en_septiembre():
    from datetime import date

    assert curso_academico_actual(date(2026, 9, 28)) == "2026-2027"
    assert curso_academico_actual(date(2027, 6, 1)) == "2026-2027"
    assert curso_academico_actual(date(2027, 9, 1)) == "2027-2028"
