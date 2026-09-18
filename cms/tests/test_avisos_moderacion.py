"""Los avisos de moderacion que le llegan a la moderadora (2026-09-18).

Dos defectos en el mismo correo:

1. El enlace estaba roto. Las plantillas de aviso de Wagtail concatenan
   `{{ base_url }}{% url ... %}` en crudo, y `WAGTAILADMIN_BASE_URL` llevaba
   barra final, asi que salia `https://.../` + `/cms/pages/866/edit/` =
   `//cms/pages/866/edit/`. Esa ruta no casa con ninguna de `config/urls.py`
   y terminaba en el 404 del front — de ahi lo de "me manda a una plantilla".

2. El correo salia en ingles. `LANGUAGE_CODE` era `en-us`, y como ninguno de
   los ocho perfiles de Wagtail tiene idioma elegido (comprobado en
   produccion el 2026-09-18), `UserProfile.get_preferred_language()` caia en
   ese valor.
"""

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from wagtail.users.models import UserProfile

User = get_user_model()

PRODUCCION = Path(settings.BASE_DIR) / "config" / "settings" / "production.py"


def base_url_de_produccion():
    fuente = PRODUCCION.read_text()
    return re.search(r'^WAGTAILADMIN_BASE_URL = "([^"]+)"', fuente, re.M).group(1)


class EnlaceDeLosAvisosTest(SimpleTestCase):
    def test_la_base_url_de_produccion_no_lleva_barra_final(self):
        self.assertFalse(base_url_de_produccion().endswith("/"))

    def test_apunta_al_dominio_de_blogs(self):
        """Quien recibe estos avisos son las moderadoras de los blogs."""
        self.assertEqual(
            base_url_de_produccion(), "https://blogs.iesmartinabescos.es"
        )

    def test_concatenada_con_la_ruta_del_admin_da_una_sola_barra(self):
        """El mecanismo exacto que rompia el enlace."""
        enlace = base_url_de_produccion() + reverse(
            "wagtailadmin_pages:edit", args=[866]
        )
        self.assertNotIn("//cms", enlace)
        self.assertEqual(
            enlace, "https://blogs.iesmartinabescos.es/cms/pages/866/edit/"
        )


class IdiomaDeLosAvisosTest(TestCase):
    def test_un_perfil_sin_idioma_elegido_recibe_castellano(self):
        """El caso de los ocho perfiles que hay en produccion."""
        usuario = User.objects.create_user(
            email="moderadora@example.com", password="x123456789"
        )
        perfil = UserProfile.get_for_user(usuario)
        self.assertEqual(perfil.preferred_language, "")
        self.assertEqual(perfil.get_preferred_language(), "es")

    @override_settings(LANGUAGE_CODE="en-us")
    def test_el_defecto_es_lo_que_decidia_el_idioma(self):
        """Contraprueba: con el valor viejo, el mismo perfil da ingles."""
        usuario = User.objects.create_user(
            email="moderadora2@example.com", password="x123456789"
        )
        self.assertEqual(
            UserProfile.get_for_user(usuario).get_preferred_language(), "en-us"
        )
