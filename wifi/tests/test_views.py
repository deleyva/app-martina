import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.urls import reverse

from ..models import DispositivoWifi
from ..permissions import GRUPO_GESTION
from ..permissions import GRUPO_PERSONAL
from .factories import AlumnadoFactory
from .factories import DispositivoWifiFactory
from .factories import PersonalFactory

SOLICITAR = "/wifi/"
GESTION = "/wifi/gestion/"


def _gestor():
    user = PersonalFactory()
    grupo, _ = Group.objects.get_or_create(name=GRUPO_GESTION)
    user.groups.add(grupo)
    return user


@pytest.mark.django_db
class TestRutas:
    def test_la_app_cuelga_de_wifi(self):
        assert reverse("wifi:solicitar") == SOLICITAR
        assert reverse("wifi:gestion") == GESTION


@pytest.mark.django_db
class TestAcceso:
    def test_sin_sesion_todo_redirige_al_login(self, client):
        for url in (SOLICITAR, GESTION):
            respuesta = client.get(url)
            assert respuesta.status_code == 302
            assert "/accounts/login/" in respuesta.url

    def test_el_profesorado_entra_a_solicitar(self, client):
        client.force_login(PersonalFactory())
        assert client.get(SOLICITAR).status_code == 200

    def test_el_alumnado_no_puede_solicitar(self, client):
        client.force_login(AlumnadoFactory())
        assert client.get(SOLICITAR).status_code == 403

    def test_una_cuenta_de_fuera_del_dominio_no_puede_solicitar(self, client):
        client.force_login(PersonalFactory(email="alguien@gmail.com"))
        assert client.get(SOLICITAR).status_code == 403

    def test_el_grupo_de_excepciones_abre_la_puerta(self, client):
        user = AlumnadoFactory()
        grupo, _ = Group.objects.get_or_create(name=GRUPO_PERSONAL)
        user.groups.add(grupo)
        client.force_login(user)
        assert client.get(SOLICITAR).status_code == 200

    def test_un_profesor_normal_no_entra_en_gestion(self, client):
        client.force_login(PersonalFactory())
        assert client.get(GESTION).status_code == 403

    def test_el_grupo_de_gestion_si_entra(self, client):
        client.force_login(_gestor())
        assert client.get(GESTION).status_code == 200

    def test_un_superusuario_entra_en_gestion(self, client):
        client.force_login(PersonalFactory(is_superuser=True, is_staff=True))
        assert client.get(GESTION).status_code == 200


@pytest.mark.django_db
class TestSolicitar:
    def test_una_solicitud_queda_a_mi_nombre_y_pendiente(self, client):
        user = PersonalFactory()
        client.force_login(user)

        client.post(SOLICITAR, {"mac": "a4:83:e7:1c:90:2b", "descripcion": "Móvil"})

        dispositivo = DispositivoWifi.objects.get()
        assert dispositivo.usuario == user
        assert dispositivo.mac == "A4:83:E7:1C:90:2B"
        assert dispositivo.estado == DispositivoWifi.Estado.PENDIENTE

    def test_solo_veo_mis_dispositivos(self, client):
        mio = DispositivoWifiFactory(descripcion="Mi portátil")
        DispositivoWifiFactory(descripcion="El de otra persona")

        client.force_login(mio.usuario)
        contenido = client.get(SOLICITAR).content.decode()

        assert "Mi portátil" in contenido
        assert "El de otra persona" not in contenido

    def test_los_cinco_tutoriales_estan_en_la_pagina(self, client):
        client.force_login(PersonalFactory())
        contenido = client.get(SOLICITAR).content.decode()

        for sistema in ("iOS", "Android", "Windows", "Mac", "VitaLinux"):
            assert sistema in contenido, f"falta el tutorial de {sistema}"


@pytest.mark.django_db
class TestGestionAltas:
    def test_las_pendientes_salen_listas_para_copiar(self, client):
        DispositivoWifiFactory(mac="A4:83:E7:1C:90:2B")
        ya_dada = DispositivoWifiFactory(mac="00:1B:44:11:3A:B7")
        ya_dada.marcar_anadida()

        client.force_login(_gestor())
        contenido = client.get(GESTION).content.decode()

        # El texto por defecto solo lleva la pendiente, no la que ya está dada.
        assert "A4:83:E7:1C:90:2B" in contenido
        assert contenido.count("00:1B:44:11:3A:B7") == 1  # solo en la tabla de activos

    def test_marcar_como_anadidas_sella_el_alta_y_manda_el_correo(self, client, settings):
        settings.WIFI_PASSWORD = "clave-de-prueba"
        dispositivo = DispositivoWifiFactory()
        client.force_login(_gestor())

        client.post("/wifi/gestion/anadidas/", {"ids": str(dispositivo.pk)})

        dispositivo.refresh_from_db()
        assert dispositivo.estado == DispositivoWifi.Estado.ANADIDA
        assert dispositivo.anadida_at is not None
        assert dispositivo.notificado_at is not None
        assert len(mail.outbox) == 1

    def test_marcar_dos_veces_no_manda_dos_correos(self, client, settings):
        settings.WIFI_PASSWORD = "clave-de-prueba"
        dispositivo = DispositivoWifiFactory()
        client.force_login(_gestor())

        client.post("/wifi/gestion/anadidas/", {"ids": str(dispositivo.pk)})
        client.post("/wifi/gestion/anadidas/", {"ids": str(dispositivo.pk)})

        assert len(mail.outbox) == 1

    def test_solo_se_marca_lo_copiado_aunque_entre_algo_nuevo(self, client, settings):
        """El caso que justifica todo el diseño de dos pasos.

        El administrativo copia dos MACs, se va al otro programa, y mientras
        tanto entra una tercera solicitud. Al volver y marcar, la tercera NO
        puede quedar sellada: nadie la ha pegado en ningún sitio.
        """
        settings.WIFI_PASSWORD = "clave-de-prueba"
        copiadas = [DispositivoWifiFactory(), DispositivoWifiFactory()]
        client.force_login(_gestor())

        rezagada = DispositivoWifiFactory()  # entra entre el copiar y el marcar

        client.post(
            "/wifi/gestion/anadidas/",
            {"ids": ",".join(str(d.pk) for d in copiadas)},
        )

        for d in copiadas:
            d.refresh_from_db()
            assert d.estado == DispositivoWifi.Estado.ANADIDA
        rezagada.refresh_from_db()
        assert rezagada.estado == DispositivoWifi.Estado.PENDIENTE
        assert len(mail.outbox) == 2

    def test_un_profesor_no_puede_marcar_altas(self, client):
        dispositivo = DispositivoWifiFactory()
        client.force_login(PersonalFactory())

        assert client.post("/wifi/gestion/anadidas/", {"ids": str(dispositivo.pk)}).status_code == 403
        dispositivo.refresh_from_db()
        assert dispositivo.estado == DispositivoWifi.Estado.PENDIENTE


@pytest.mark.django_db
class TestGestionBajas:
    def test_el_flujo_de_baja_completo(self, client):
        dispositivo = DispositivoWifiFactory()
        dispositivo.marcar_anadida()
        gestor = _gestor()
        client.force_login(gestor)

        client.post(f"/wifi/gestion/baja/{dispositivo.pk}/")
        dispositivo.refresh_from_db()
        assert dispositivo.estado == DispositivoWifi.Estado.BAJA_PENDIENTE

        # Aparece en su propia lista copiable.
        assert dispositivo.mac in client.get(GESTION).content.decode()

        client.post("/wifi/gestion/bajas-hechas/", {"ids": str(dispositivo.pk)})
        dispositivo.refresh_from_db()
        assert dispositivo.estado == DispositivoWifi.Estado.DADA_DE_BAJA
        assert dispositivo.baja_at is not None

    def test_dar_de_baja_no_manda_ningun_correo(self, client):
        dispositivo = DispositivoWifiFactory()
        dispositivo.marcar_anadida()
        client.force_login(_gestor())
        mail.outbox.clear()

        client.post(f"/wifi/gestion/baja/{dispositivo.pk}/")
        client.post("/wifi/gestion/bajas-hechas/", {"ids": str(dispositivo.pk)})

        assert len(mail.outbox) == 0

    def test_la_busqueda_filtra_los_activos(self, client):
        uno = DispositivoWifiFactory(descripcion="Portátil de secretaría")
        uno.marcar_anadida()
        otro = DispositivoWifiFactory(descripcion="Tablet de biblioteca")
        otro.marcar_anadida()

        client.force_login(_gestor())
        contenido = client.get(GESTION, {"q": "secretaría"}).content.decode()

        assert "Portátil de secretaría" in contenido
        assert "Tablet de biblioteca" not in contenido


@pytest.mark.django_db
class TestAvisoDeClaveAusente:
    """Sin clave en el entorno la app no puede avisar a nadie, y lo dice."""

    def test_la_pantalla_avisa_de_que_falta_la_clave(self, client, settings):
        settings.WIFI_PASSWORD = ""
        client.force_login(_gestor())
        assert "No hay clave de WiFi configurada" in client.get(GESTION).content.decode()

    def test_con_clave_no_hay_aviso(self, client, settings):
        settings.WIFI_PASSWORD = "clave-de-prueba"
        client.force_login(_gestor())
        assert "No hay clave de WiFi configurada" not in client.get(GESTION).content.decode()

    def test_no_promete_un_correo_que_no_ha_salido(self, client, settings):
        settings.WIFI_PASSWORD = ""
        dispositivo = DispositivoWifiFactory()
        client.force_login(_gestor())

        respuesta = client.post(
            "/wifi/gestion/anadidas/", {"ids": str(dispositivo.pk)}, follow=True,
        )
        texto = respuesta.content.decode()

        assert "NO se ha enviado ningún correo" in texto
        assert "Se ha enviado el correo con la clave" not in texto
        assert len(mail.outbox) == 0

        # El alta sí se registra: el trasvase al otro programa ya se ha hecho.
        dispositivo.refresh_from_db()
        assert dispositivo.estado == DispositivoWifi.Estado.ANADIDA
        assert dispositivo.notificado_at is None


@pytest.mark.django_db
class TestAltaEnNombreDeOtro:
    """El compañero que viene a la mesa de administración con el móvil en la mano.

    El gestor le da de alta desde `/wifi/` tecleando su correo; nadie le obliga
    a entrar con Google para copiar y pegar doce dígitos.
    """

    MAC = "A4:83:E7:1C:90:2B"

    def test_el_gestor_ve_el_campo_y_el_profesor_no(self, client):
        client.force_login(_gestor())
        assert 'name="para_correo"' in client.get(SOLICITAR).content.decode()

        client.force_login(PersonalFactory())
        assert 'name="para_correo"' not in client.get(SOLICITAR).content.decode()

    def test_vacio_queda_a_nombre_del_propio_gestor(self, client):
        gestor = _gestor()
        client.force_login(gestor)

        client.post(SOLICITAR, {"mac": self.MAC, "descripcion": "Mi móvil", "para_correo": ""})

        dispositivo = DispositivoWifi.objects.get()
        assert dispositivo.usuario == gestor
        assert dispositivo.solicitado_por is None

    def test_su_propio_correo_tampoco_cuenta_como_en_nombre_de_otro(self, client):
        gestor = _gestor()
        client.force_login(gestor)

        client.post(SOLICITAR, {"mac": self.MAC, "para_correo": gestor.email})

        dispositivo = DispositivoWifi.objects.get()
        assert dispositivo.usuario == gestor
        assert dispositivo.solicitado_por is None

    def test_con_el_correo_de_un_companero_queda_a_su_nombre_y_la_clave_va_a_el(self, client, settings):
        settings.WIFI_PASSWORD = "clave-de-prueba"
        companero = PersonalFactory()
        gestor = _gestor()
        client.force_login(gestor)

        respuesta = client.post(
            SOLICITAR,
            {"mac": self.MAC, "descripcion": "Portátil", "para_correo": companero.email.upper()},
            follow=True,
        )

        dispositivo = DispositivoWifi.objects.get()
        assert dispositivo.usuario == companero
        assert dispositivo.solicitado_por == gestor
        assert dispositivo.estado == DispositivoWifi.Estado.PENDIENTE
        assert f"Recibido a nombre de {companero.email}" in respuesta.content.decode()

        # El flujo de gestión no cambia: se copia, se pega y se marca. Y el
        # correo con la clave le llega al compañero, no a quien lo tecleó.
        client.post("/wifi/gestion/anadidas/", {"ids": str(dispositivo.pk)})
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [companero.email]

    def test_un_correo_del_centro_sin_cuenta_crea_la_cuenta_sin_contrasena(self, client):
        from martina_bescos_app.users.models import User

        client.force_login(_gestor())
        correo = "nueva.profe@iesmartinabescos.es"

        client.post(SOLICITAR, {"mac": self.MAC, "para_correo": correo})

        usuario = User.objects.get(email=correo)
        assert not usuario.has_usable_password()
        assert usuario.acceso_con_contrasena is False
        assert DispositivoWifi.objects.get().usuario == usuario

    def test_cuando_el_companero_entra_con_google_es_la_misma_cuenta(self, client):
        """La promesa del diseño: crearle la cuenta a mano no le crea un duplicado.

        Reutiliza el adaptador real: `pre_social_login` enlaza por correo.
        """
        from allauth.socialaccount.models import SocialAccount

        from martina_bescos_app.users.adapters import SocialAccountAdapter
        from martina_bescos_app.users.models import User
        from martina_bescos_app.users.tests.test_adapters import _login_social
        from martina_bescos_app.users.tests.test_adapters import _peticion_con_mensajes

        client.force_login(_gestor())
        correo = "nueva.profe@iesmartinabescos.es"
        client.post(SOLICITAR, {"mac": self.MAC, "para_correo": correo})
        creada = User.objects.get(email=correo)

        SocialAccountAdapter().pre_social_login(_peticion_con_mensajes(), _login_social(correo))

        assert User.objects.filter(email__iexact=correo).count() == 1
        assert SocialAccount.objects.get(provider="google", uid="uid-1").user == creada

    def test_rechaza_el_correo_de_un_alumno(self, client):
        from martina_bescos_app.users.models import User

        client.force_login(_gestor())

        respuesta = client.post(
            SOLICITAR, {"mac": self.MAC, "para_correo": "0125eromero@iesmartinabescos.es"},
        )

        assert "no es de personal del centro" in respuesta.content.decode()
        assert not DispositivoWifi.objects.exists()
        assert not User.objects.filter(email="0125eromero@iesmartinabescos.es").exists()

    def test_rechaza_un_correo_de_fuera_del_centro(self, client):
        client.force_login(_gestor())

        respuesta = client.post(SOLICITAR, {"mac": self.MAC, "para_correo": "alguien@gmail.com"})

        assert "no es de personal del centro" in respuesta.content.decode()
        assert not DispositivoWifi.objects.exists()

    def test_una_cuenta_autorizada_a_mano_si_vale_aunque_parezca_de_alumno(self, client):
        autorizado = AlumnadoFactory()
        grupo, _ = Group.objects.get_or_create(name=GRUPO_PERSONAL)
        autorizado.groups.add(grupo)
        client.force_login(_gestor())

        client.post(SOLICITAR, {"mac": self.MAC, "para_correo": autorizado.email})

        assert DispositivoWifi.objects.get().usuario == autorizado

    def test_un_profesor_no_puede_colar_un_dispositivo_a_nombre_de_otro(self, client):
        profe = PersonalFactory()
        otro = PersonalFactory()
        client.force_login(profe)

        client.post(SOLICITAR, {"mac": self.MAC, "para_correo": otro.email})

        dispositivo = DispositivoWifi.objects.get()
        assert dispositivo.usuario == profe
        assert dispositivo.solicitado_por is None

    def test_el_gestor_ve_lo_que_registro_para_otros(self, client):
        gestor = _gestor()
        DispositivoWifiFactory(solicitado_por=gestor, descripcion="Tablet de Ana")
        DispositivoWifiFactory(descripcion="La de alguien ajeno")
        client.force_login(gestor)

        contenido = client.get(SOLICITAR).content.decode()

        assert "Tablet de Ana" in contenido
        assert "La de alguien ajeno" not in contenido

    def test_en_gestion_se_distingue_lo_registrado_a_mano(self, client):
        gestor = _gestor()
        DispositivoWifiFactory(solicitado_por=gestor)
        client.force_login(gestor)

        assert ">a mano<" in client.get(GESTION).content.decode()
