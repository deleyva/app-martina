"""C335, C336: el paquete de React que sirve producción es el de git, y corresponde al código."""

import hashlib
import re
from pathlib import Path

APP = Path(__file__).parents[1]
FRONTEND = APP / "frontend"
BUNDLE = APP / "static" / "calificaciones" / "registro.js"
RAIZ = APP.parent


def _huella() -> str:
    """La misma cuenta que `frontend/build.mjs`."""
    rutas = [p for p in (FRONTEND / "src").rglob("*") if p.is_file() and not p.name.endswith(".test.js")]
    rutas += [FRONTEND / "package.json", FRONTEND / "build.mjs"]
    hash_ = hashlib.sha256()
    for ruta in sorted(rutas, key=lambda p: p.relative_to(FRONTEND).as_posix()):
        hash_.update(ruta.relative_to(FRONTEND).as_posix().encode())
        hash_.update(b"\0")
        hash_.update(ruta.read_bytes())
        hash_.update(b"\0")
    return hash_.hexdigest()


def test_el_bundle_esta_y_esta_al_dia():
    """Si falla: `cd calificaciones/frontend && bun install && bun run build`, y confirmar el resultado."""
    assert BUNDLE.exists(), "falta calificaciones/static/calificaciones/registro.js"
    cabecera = BUNDLE.read_text(encoding="utf-8").splitlines()[0]
    assert cabecera == f"/* fuente: {_huella()} */", "el paquete no corresponde al código de frontend/src"


def test_el_bundle_no_trae_source_map():
    """Con el almacenamiento con manifiesto, esa línea sin su `.map` tumba `collectstatic`."""
    assert "sourceMappingURL" not in BUNDLE.read_text(encoding="utf-8")
    assert not list(BUNDLE.parent.glob("*.map"))


def test_el_bundle_es_el_de_produccion():
    """El React de desarrollo pesa el doble y avisa por consola."""
    texto = BUNDLE.read_text(encoding="utf-8")
    assert BUNDLE.stat().st_size < 900_000
    assert "react.development" not in texto


def test_no_hay_clases_construidas_en_ejecucion():
    """Tailwind genera las clases leyendo el código: `bg-${color}-600` no la encuentra."""
    for ruta in (FRONTEND / "src").rglob("*.jsx"):
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1):
            # Un prefijo de utilidad de Tailwind seguido de una interpolación. El
            # nombre de un fichero (`grabacion-${Date.now()}`) no es una clase.
            assert not re.search(r"\b(bg|text|border|ring|fill|stroke|from|via|to|shadow|outline|divide)-\$\{", linea), (
                f"{ruta.name}:{n}: {linea.strip()}"
            )


def test_el_codigo_no_esta_en_una_carpeta_que_git_ignora():
    """`lib/`, `dist/` y `build/` están en `.gitignore`: ni se confirman ni los lee Tailwind."""
    for ruta in (FRONTEND / "src").rglob("*"):
        partes = set(ruta.relative_to(FRONTEND).parts)
        assert not partes & {"lib", "dist", "build"}, ruta


def test_la_raiz_no_sabe_nada_de_react():
    """La imagen de producción y el contenedor local instalan el `package.json` de la raíz."""
    raiz = (RAIZ / "package.json").read_text(encoding="utf-8")
    assert "react" not in raiz
    assert "recharts" not in raiz
    assert "**/node_modules" in (RAIZ / ".dockerignore").read_text(encoding="utf-8")
