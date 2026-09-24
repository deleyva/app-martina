"""Lo que tiene que valer para los tests de TODAS las apps.

Los `conftest.py` de dentro de cada app solo alcanzan a esa app, y el de
`martina_bescos_app` no llegaba a `clases`: sus tests de notas de voz escribían
ficheros en la carpeta de medios de verdad. Aquí, en la raíz, cubre a todas.
"""

import pytest


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath
