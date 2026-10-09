# ruff: noqa: E501, PLR2004
"""Fase 73: etiquetas que escribe la gente y referencias entre incidencias.

Lo que importa: que «Proyector» y «proyéctor» sean la misma etiqueta, que la
pasada semanal no pierda ninguna incidencia, que `#123` deje rastro en las dos
incidencias, y que una referencia no enseñe el título de una privada.
"""

import json

import pytest
from django.urls import reverse

from api_keys.models import APIKey
from incidencias.models import Etiqueta
from incidencias.models import Incidencia
from incidencias.models import Referencia
from incidencias.services import acciones
from incidencias.templatetags.menciones import con_referencias

from .factories import ComentarioFactory
from .factories import EtiquetaFactory
from .factories import IncidenciaFactory
from .factories import TecnicoFactory
from .factories import UbicacionFactory

API = "/api/incidencias/"


@pytest.fixture(autouse=True)
def sin_etiquetas_sembradas(request):
    """La migración 0002 siembra etiquetas; aquí se cuentan, así que se empieza sin ninguna."""
    if "db" in request.fixturenames or request.node.get_closest_marker("django_db"):
        request.getfixturevalue("db")
        Etiqueta.objects.all().delete()


@pytest.fixture
def tecnico(db):
    return TecnicoFactory(user__email="tecnica@iesmartinabescos.es", nombre_display="Técnica")


@pytest.fixture
def clave(tecnico):
    return APIKey.objects.create(name="skill", user=tecnico.user)


def _crear(client, **extra):
    data = {
        "titulo": "Con etiquetas nuevas",
        "descripcion": "",
        "urgencia": "media",
        "reportero_nombre": "eromero",
        "ubicacion": UbicacionFactory().pk,
        "es_privada": False,
        "etiquetas_ids": "",
        **extra,
    }
    return client.post(reverse("incidencias:crear"), data)


# --- Etiquetas: modelo ----------------------------------------------------------


@pytest.mark.django_db
def test_misma_etiqueta_sin_tildes_ni_mayusculas():
    a = Etiqueta.obtener_o_crear("Proyector", por="ana")
    assert Etiqueta.obtener_o_crear("PROYECTOR") == a
    assert Etiqueta.obtener_o_crear("  proyéctor ") == a
    assert Etiqueta.objects.count() == 1
    assert a.creada_por == "ana"
    assert a.revisada is False


@pytest.mark.django_db
def test_nombre_sin_letras_no_crea_nada():
    assert Etiqueta.obtener_o_crear("¿?!") is None
    assert Etiqueta.objects.count() == 0


@pytest.mark.django_db
def test_color_estable_y_de_la_paleta():
    e = Etiqueta.obtener_o_crear("Internet")
    assert e.color in Etiqueta.COLORES
    assert e.color == Etiqueta.color_para(e.slug)
    assert e.tono == Etiqueta.COLORES[e.color]


@pytest.mark.django_db
def test_fusionar_no_pierde_incidencias():
    buena, mala = EtiquetaFactory(nombre="Proyector"), EtiquetaFactory(nombre="Cañón")
    i1, i2, i3 = IncidenciaFactory(), IncidenciaFactory(), IncidenciaFactory()
    i1.etiquetas.add(mala)
    i2.etiquetas.add(mala, buena)
    i3.etiquetas.add(buena)
    assert mala.fusionar_en(buena) == 2
    assert not Etiqueta.objects.filter(pk=mala.pk).exists()
    for i in (i1, i2, i3):
        assert list(i.etiquetas.values_list("slug", flat=True)) == ["proyector"]


# --- Etiquetas: formulario ------------------------------------------------------


@pytest.mark.django_db
def test_crear_con_etiqueta_nueva_y_existente(client):
    existente = Etiqueta.obtener_o_crear("Proyector", revisada=True)
    r = _crear(client, etiquetas_ids=str(existente.pk), etiquetas_nuevas=json.dumps(["Pizarra digital", "proyéctor"]))
    assert r.status_code == 302
    inc = Incidencia.objects.get(titulo="Con etiquetas nuevas")
    assert sorted(inc.etiquetas.values_list("slug", flat=True)) == ["pizarra-digital", "proyector"]
    nueva = Etiqueta.objects.get(slug="pizarra-digital")
    assert (nueva.revisada, nueva.creada_por) == (False, "eromero")
    assert Etiqueta.objects.count() == 2


@pytest.mark.django_db
def test_mas_de_ocho_nuevas_se_rechaza(client):
    r = _crear(client, etiquetas_nuevas=json.dumps([f"Cosa {n}" for n in range(9)]))
    assert r.status_code == 200
    assert not Incidencia.objects.exists()
    assert not Etiqueta.objects.exists()


@pytest.mark.django_db
def test_nombre_largo_se_corta_a_cuarenta(client):
    _crear(client, etiquetas_nuevas=json.dumps(["x" * 90]))
    assert len(Etiqueta.objects.get().nombre) == Etiqueta.NOMBRE_MAX


@pytest.mark.django_db
def test_autocompletado_ordena_por_uso_y_trae_tono(client):
    poco, mucho = Etiqueta.obtener_o_crear("Ratón"), Etiqueta.obtener_o_crear("Internet")
    for _ in range(3):
        IncidenciaFactory().etiquetas.add(mucho)
    IncidenciaFactory().etiquetas.add(poco)
    datos = client.get(reverse("incidencias:api_etiquetas")).json()
    assert [d["text"] for d in datos] == ["Internet", "Ratón"]
    assert datos[0]["usos"] == 3
    assert datos[0]["tono"] == mucho.tono
    # Sin tilde encuentra la que la lleva (por el slug).
    assert [d["text"] for d in client.get(reverse("incidencias:api_etiquetas"), {"q": "raton"}).json()] == ["Ratón"]


# --- Etiquetas: API de la pasada semanal ---------------------------------------


@pytest.mark.django_db
def test_api_lista_las_pendientes_de_revisar(client, clave):
    Etiqueta.obtener_o_crear("Vieja", revisada=True)
    nueva = Etiqueta.obtener_o_crear("Nueva", por="eromero")
    IncidenciaFactory().etiquetas.add(nueva)
    r = client.get(f"{API}etiquetas", {"revisada": "false"}, HTTP_X_API_KEY=str(clave.key))
    assert r.status_code == 200
    assert r.json() == [{
        "id": nueva.id, "nombre": "Nueva", "slug": "nueva", "color": nueva.color,
        "revisada": False, "creada_por": "eromero", "usos": 1,
    }]


@pytest.mark.django_db
def test_api_renombra_recolorea_y_revisa(client, clave):
    e = Etiqueta.obtener_o_crear("proyetor")
    r = client.patch(
        f"{API}etiquetas/{e.slug}", json.dumps({"nombre": "Proyector", "color": "verde", "revisada": True}),
        content_type="application/json", HTTP_X_API_KEY=str(clave.key),
    )
    assert r.status_code == 200
    e.refresh_from_db()
    assert (e.nombre, e.color, e.revisada) == ("Proyector", "verde", True)
    malo = client.patch(
        f"{API}etiquetas/{e.slug}", json.dumps({"color": "marron"}),
        content_type="application/json", HTTP_X_API_KEY=str(clave.key),
    )
    assert malo.status_code == 422


@pytest.mark.django_db
def test_api_fusiona(client, clave):
    buena, mala = Etiqueta.obtener_o_crear("Proyector"), Etiqueta.obtener_o_crear("Cañón")
    inc = IncidenciaFactory()
    inc.etiquetas.add(mala)
    r = client.post(
        f"{API}etiquetas/{mala.slug}/fusionar", json.dumps({"destino": buena.slug}),
        content_type="application/json", HTTP_X_API_KEY=str(clave.key),
    )
    assert r.status_code == 200
    assert r.json()["usos"] == 1
    assert list(inc.etiquetas.values_list("slug", flat=True)) == ["proyector"]
    assert not Etiqueta.objects.filter(slug="canon").exists()


# --- Referencias ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("igual que #12 y #7", [12, 7]),
        ("#12, otra vez #12", [12]),
        ("https://x.es/pagina#12", []),
        ("ver /#12 o &#12; o ##12", []),
        ("sin números #abc", []),
    ],
)
def test_numeros_citados(texto, esperado):
    assert Referencia.numeros_citados(texto) == esperado


@pytest.mark.django_db
def test_comentario_con_hash_deja_rastro_en_las_dos(django_capture_on_commit_callbacks):
    a, b = IncidenciaFactory(), IncidenciaFactory()
    with django_capture_on_commit_callbacks(execute=True):
        acciones.comentar(a, "ana", f"Es lo mismo que #{b.pk}, y #{a.pk} es esta; #99999 no existe")
    assert [(r.origen, r.destino, r.tipo) for r in Referencia.objects.all()] == [(a, b, "menciona")]
    assert [(r["incidencia"], r["relaciones"]) for r in a.relacionadas()] == [(b, ["Menciona a"])]
    assert [(r["incidencia"], r["relaciones"]) for r in b.relacionadas()] == [(a, ["Mencionada en"])]


@pytest.mark.django_db
def test_crear_con_hash_en_la_descripcion(client):
    b = IncidenciaFactory()
    _crear(client, descripcion=f"Como la #{b.pk}")
    a = Incidencia.objects.get(titulo="Con etiquetas nuevas")
    assert Referencia.objects.filter(origen=a, destino=b).exists()


@pytest.mark.django_db
def test_enlace_no_desvela_privada():
    publica = IncidenciaFactory(titulo="Proyector aula 12")
    privada = IncidenciaFactory(titulo="Cerradura despacho director", es_privada=True)
    html = con_referencias(f"<b>ver</b> #{publica.pk} y #{privada.pk} y #99999 y https://x.es/#{publica.pk}")
    assert f'href="/incidencias/{publica.pk}/"' in html
    assert "Proyector aula 12" in html
    assert f'href="/incidencias/{privada.pk}/"' in html
    assert "Cerradura" not in html
    assert "#99999" in html and 'href="/incidencias/99999/"' not in html
    assert "&lt;b&gt;" in html
    assert html.count("<a ") == 3  # pública, privada y la URL entera


@pytest.mark.django_db
def test_detalle_enseña_relacionadas_sin_titulo_privado(client):
    a = IncidenciaFactory()
    privada = IncidenciaFactory(titulo="Cerradura despacho director", es_privada=True)
    ComentarioFactory(incidencia=a)
    acciones.registrar_referencias(privada, f"ver #{a.pk}")
    html = client.get(reverse("incidencias:detalle", args=[a.pk])).content.decode()
    assert "Relacionadas" in html
    assert f"#{privada.pk}" in html
    assert "Cerradura" not in html


# --- Unir ----------------------------------------------------------------------


@pytest.mark.django_db
def test_unir_cierra_y_lleva_lo_que_contaba(django_capture_on_commit_callbacks):
    a = IncidenciaFactory(titulo="No va el proyector", descripcion="Se apaga a los cinco minutos", reportero_nombre="eromero")
    b = IncidenciaFactory(titulo="Proyector aula 12")
    with django_capture_on_commit_callbacks(execute=True):
        acciones.unir(a, b, "jlopez", "Es el mismo aparato")
    a.refresh_from_db()
    assert a.estado == Incidencia.Estado.RESUELTA
    assert a.unida_a == b
    assert b.estado == Incidencia.Estado.PENDIENTE
    aviso = a.comentarios.get().texto
    assert f"Unida a #{b.pk}" in aviso and "Es el mismo aparato" in aviso
    llevado = b.comentarios.get().texto
    assert f"#{a.pk}" in llevado and "eromero" in llevado and "Se apaga a los cinco minutos" in llevado
    # La relación es la unión, sin una mención repetida encima.
    assert list(Referencia.objects.values_list("tipo", flat=True)) == ["unida"]
    assert [r["relaciones"] for r in b.relacionadas()] == [["Se le unió"]]


@pytest.mark.django_db
def test_unir_no_admite_circulos_ni_a_si_misma():
    a, b, c = IncidenciaFactory(), IncidenciaFactory(), IncidenciaFactory()
    with pytest.raises(acciones.UnionInvalida):
        acciones.unir(a, a, "x")
    acciones.unir(b, a, "x")
    acciones.unir(c, b, "x")
    with pytest.raises(acciones.UnionInvalida):
        acciones.unir(a, c, "x")  # c → b → a: cerraría el círculo
    with pytest.raises(acciones.UnionInvalida):
        acciones.unir(b, c, "x")  # b ya está unida


@pytest.mark.django_db
def test_unir_desde_el_detalle_solo_tecnico(client, tecnico):
    a, b = IncidenciaFactory(), IncidenciaFactory()
    url = reverse("incidencias:unir", args=[a.pk])
    assert client.post(url, {"destino": b.pk}).status_code == 302
    assert not Referencia.objects.exists()
    client.force_login(tecnico.user)
    r = client.post(url, {"destino": f"#{b.pk}", "nota": ""})
    assert r.status_code == 302 and r.url == reverse("incidencias:detalle", args=[b.pk])
    a.refresh_from_db()
    assert a.unida_a == b
    html = client.get(reverse("incidencias:detalle", args=[a.pk])).content.decode()
    assert "se unió a" in html


@pytest.mark.django_db
def test_unir_por_api(client, clave):
    a, b = IncidenciaFactory(), IncidenciaFactory()
    r = client.post(
        f"{API}{a.pk}/unir", json.dumps({"destino": b.pk, "nota": "duplicada"}),
        content_type="application/json", HTTP_X_API_KEY=str(clave.key),
    )
    assert r.status_code == 200
    datos = r.json()
    assert datos["id"] == b.pk
    assert datos["relacionadas"] == [{"id": a.pk, "titulo": a.titulo, "estado": "resuelta", "relaciones": ["Se le unió"]}]
    otra = client.post(
        f"{API}{a.pk}/unir", json.dumps({"destino": b.pk}),
        content_type="application/json", HTTP_X_API_KEY=str(clave.key),
    )
    assert otra.status_code == 422
    assert client.get(f"{API}{a.pk}", HTTP_X_API_KEY=str(clave.key)).json()["unida_a"] == b.pk
