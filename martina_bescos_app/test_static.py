"""Todo lo que sirve `collectstatic` tiene que poder procesarlo el almacenamiento de producción.

En local no se nota: producción usa CompressedManifestStaticFilesStorage, que lee
el `sourceMappingURL` de cada .js y .css y aborta si el `.map` no está. El
2026-10-29 el procesador de SpessaSynth (fase 85) llegó sin su `.map`, django
quedó en bucle de reinicios y la web dio 502 unos minutos.
"""

import fnmatch
import re

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import HashedFilesMixin

# Los mismos patrones con los que el almacenamiento de producción busca los
# source maps, para no avisar de lo que él no mira ni callar lo que sí.
PATRONES = [
    (extension, re.compile(patron[0] if isinstance(patron, (tuple, list)) else patron))
    for extension, patrones in HashedFilesMixin.patterns
    for patron in patrones
    if "sourceMappingURL" in (patron[0] if isinstance(patron, (tuple, list)) else patron)
]


def test_cada_source_map_de_static_existe():
    """Si falla: copiar el `.map` junto al fichero o quitarle la línea `sourceMappingURL`."""
    faltan = []
    for finder in finders.get_finders():
        for ruta, almacen in finder.list([]):
            for extension, patron in PATRONES:
                if not fnmatch.fnmatchcase(ruta, extension):
                    continue
                with almacen.open(ruta) as f:
                    texto = f.read().decode("utf-8", errors="ignore")
                carpeta = ruta.rsplit("/", 1)[0] + "/" if "/" in ruta else ""
                for m in patron.finditer(texto):
                    url = m.group("url").strip()
                    if url.startswith(("data:", "http:", "https:", "//")):
                        continue
                    if not almacen.exists(carpeta + url):
                        faltan.append(f"{ruta} -> {url}")
    assert not faltan, "source maps que no están:\n" + "\n".join(faltan)
