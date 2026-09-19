#!/usr/bin/env python3
"""Publica un borrador de artículo en apps.iesmartinabescos.es por el API.

**Un solo publicador.** Antes había dos: la skill que subía imágenes y armaba
el cuerpo a mano con curl, y el comando de gestión que escribía en la base de
datos sin imágenes ni vídeos. Se olvidaba uno de los dos y el artículo salía a
medias. Este corre fuera del contenedor, con la clave del API, y hace las dos
cosas: sube los binarios y crea la página con sus dos lenguas.

**Los binarios no entran en el repo.** Las portadas con licencia libre sí están
versionadas, pero una tablatura de Songsterr tiene copyright y el remoto es un
GitHub público: el `.gp` se sube por el API desde donde esté en tu disco y no
se copia al repo.

Idempotente: la primera publicación escribe `page_id` en el propio borrador, y
a partir de ahí actualiza esa página en vez de crear otra.

Uso:
    export $(grep -h '^IES_API_KEY=' ~/.claude/.env)
    python3 scripts/publicar_cancion.py with-or-without-you-u2-1987.md
    python3 scripts/publicar_cancion.py --publicar todos
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from musica.articulos import (  # noqa: E402
    CABECERA_EN,
    CABECERA_ES,
    _frontmatter,
    _seccion,
    partir_lengua,
)

API = os.environ.get("IES_API_URL", "https://apps.iesmartinabescos.es")
DIRECTORIO = RAIZ / "musica" / "data" / "articulos"
# Qué imagen del disco corresponde a qué id de Wagtail. Fuera de git: son ids
# de una instalación concreta, no algo que viaje con el código.
CACHE = DIRECTORIO / ".imagenes-subidas.json"
# El índice de recursos musicales.
PADRE_POR_DEFECTO = 4


def clave():
    valor = os.environ.get("IES_API_KEY")
    if not valor:
        sys.exit(
            "Falta IES_API_KEY. Cárgala sin imprimirla:\n"
            "  export $(grep -h '^IES_API_KEY=' ~/.claude/.env)"
        )
    return valor


def _peticion(ruta, datos=None, metodo="GET", cuerpo_multipart=None, tipo=None):
    url = f"{API}{ruta}"
    cabeceras = {"X-API-Key": clave()}
    if cuerpo_multipart is not None:
        cuerpo, cabeceras["Content-Type"] = cuerpo_multipart, tipo
    elif datos is not None:
        cuerpo = json.dumps(datos).encode()
        cabeceras["Content-Type"] = "application/json"
    else:
        cuerpo = None
    peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion) as respuesta:
            return json.loads(respuesta.read())
    except urllib.error.HTTPError as error:
        detalle = error.read().decode()[:400]
        sys.exit(f"{metodo} {ruta} → {error.code}\n{detalle}")


def _multipart(campos, fichero_campo, ruta):
    """Multipart a mano: la biblioteca estándar no trae constructor."""
    limite = uuid.uuid4().hex
    trozos = []
    for nombre, valor in campos.items():
        trozos.append(
            f'--{limite}\r\nContent-Disposition: form-data; name="{nombre}"\r\n\r\n{valor}\r\n'.encode()
        )
    tipo = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
    trozos.append(
        f'--{limite}\r\nContent-Disposition: form-data; name="{fichero_campo}"; '
        f'filename="{ruta.name}"\r\nContent-Type: {tipo}\r\n\r\n'.encode()
    )
    trozos.append(ruta.read_bytes())
    trozos.append(f"\r\n--{limite}--\r\n".encode())
    return b"".join(trozos), f"multipart/form-data; boundary={limite}"


def _cache_leer():
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def _cache_escribir(cache):
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def subir_imagen(nombre, titulo):
    """Sube una imagen de `imagenes/` y devuelve su id. Una vez por fichero."""
    cache = _cache_leer()
    if nombre in cache:
        return cache[nombre]
    ruta = DIRECTORIO / "imagenes" / nombre
    if not ruta.exists():
        sys.exit(f"No está la imagen {ruta}")
    cuerpo, tipo = _multipart({"title": titulo}, "file", ruta)
    salida = _peticion("/api/cms/upload-image", metodo="POST", cuerpo_multipart=cuerpo, tipo=tipo)
    cache[nombre] = salida["id"]
    _cache_escribir(cache)
    print(f"    imagen subida: {nombre} → id {salida['id']}")
    return salida["id"]


def subir_documento(ruta_str, titulo):
    """Sube la tablatura (u otro documento) desde cualquier sitio del disco."""
    ruta = Path(ruta_str).expanduser()
    if not ruta.exists():
        sys.exit(f"No está el fichero {ruta}")
    # La clave del caché es la ruta RESUELTA, no lo que venga escrito: si no,
    # `~/x.pdf` y `/Users/…/x.pdf` son dos entradas y el mismo fichero se sube
    # dos veces, dejando documentos huérfanos en Wagtail (pasó el 2026-09-19).
    clave = str(ruta.resolve())
    cache = _cache_leer()
    if clave in cache:
        return cache[clave]
    cuerpo, tipo = _multipart({"title": titulo}, "file", ruta)
    salida = _peticion("/api/cms/upload-document", metodo="POST", cuerpo_multipart=cuerpo, tipo=tipo)
    cache[clave] = salida["id"]
    _cache_escribir(cache)
    print(f"    documento subido: {ruta.name} → id {salida['id']}")
    return salida["id"]


def guardar_page_id(ruta, page_id):
    """Escribe el id en el borrador para que la próxima vez actualice."""
    texto = ruta.read_text(encoding="utf-8")
    if re.search(r"^page_id:", texto, re.M):
        texto = re.sub(r"^page_id:.*$", f"page_id: {page_id}", texto, count=1, flags=re.M)
    else:
        cabecera, resto = texto.split("\n---\n", 1)
        texto = f"{cabecera}\npage_id: {page_id}\n---\n{resto}"
    ruta.write_text(texto, encoding="utf-8")


def publicar(nombre, publicar_ya=False):
    ruta = DIRECTORIO / nombre
    datos, cuerpo = _frontmatter(ruta.read_text(encoding="utf-8"))

    def resolver(url, alt, fuente):
        return subir_imagen(url, fuente or alt or url)

    intro_es, body_es = partir_lengua(_seccion(cuerpo, CABECERA_ES, CABECERA_EN), resolver)
    intro_en, body_en = partir_lengua(_seccion(cuerpo, CABECERA_EN), resolver)

    print(f"\n{datos['titulo']}  ({datos['slug']})")
    if not (intro_es and body_es and intro_en and body_en):
        sys.exit("  Falta alguna de las dos lenguas.")

    payload = {
        "title": datos["titulo"],
        "date": datos["fecha"],
        "intro": intro_es[:250],
        "body": body_es,
        "idioma": datos.get("idioma", "es"),
        "traducciones": [{"idioma": "en", "intro": intro_en[:250], "body": body_en}],
        "tags": [t.strip() for t in datos.get("etiquetas", "").split(",") if t.strip()],
        "artist": datos.get("artista", ""),
        "songsterr_url": datos.get("songsterr_url", ""),
        "publish_immediately": publicar_ya,
    }
    for campo, destino in (("key_fifths", "key_fifths"), ("tempo_bpm", "tempo_bpm"),
                           ("duracion_segundos", "duration_seconds"),
                           ("time_signature_beats", "time_signature_beats"),
                           ("time_signature_beat_type", "time_signature_beat_type")):
        if datos.get(campo):
            payload[destino] = int(datos[campo])
    if datos.get("key_mode"):
        payload["key_mode"] = datos["key_mode"]
    if datos.get("imagen"):
        payload["featured_image_id"] = subir_imagen(
            datos["imagen"], datos.get("imagen_titulo", datos["imagen"])
        )
    # Adjuntos: la tablatura de Songsterr y, desde 2026-09-19, cualquier otro
    # documento —el chart de JamZone, por ejemplo—. Van en `adjuntos:` separados
    # por comas, cada uno con su nombre visible tras un `|` si se quiere:
    #   adjuntos: ~/charts/saturn.pdf|Chart de banda (JamZone), ~/otro.pdf
    # Cuentan como material de estudio, así que el nombre se lee en la sesión.
    adjuntos = []
    if datos.get("tablatura"):
        adjuntos.append((datos["tablatura"], f"{datos['titulo']} — tablatura"))
    for trozo in (datos.get("adjuntos") or "").split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        ruta_adjunto, _, titulo_adjunto = trozo.partition("|")
        ruta_adjunto = ruta_adjunto.strip()
        adjuntos.append((
            ruta_adjunto,
            titulo_adjunto.strip() or f"{datos['titulo']} — {Path(ruta_adjunto).stem}",
        ))
    if adjuntos:
        payload["attachment_ids"] = [subir_documento(r, t) for r, t in adjuntos]

    page_id = datos.get("page_id")
    if page_id:
        salida = _peticion(f"/api/cms/blog-pages/{page_id}", payload, metodo="PUT")
        print(f"  Actualizada id {salida['id']} — /cms/pages/{salida['id']}/edit/")
        # Un PUT sobre una página YA publicada guarda la revisión y no la
        # publica: el público se queda con el texto viejo y el cambio duerme en
        # un borrador que nadie mira. Corregir una errata y que no se note es
        # peor que no corregirla, así que aquí se dice en voz alta.
        if salida["live"] and not publicar_ya:
            print(
                "  ⚠ La página está publicada y este cambio NO se ve todavía:\n"
                "    queda como borrador pendiente. Repite con --publicar, o\n"
                f"    publica desde /cms/pages/{salida['id']}/edit/"
            )
    else:
        payload["parent_page_id"] = int(datos.get("padre", PADRE_POR_DEFECTO))
        salida = _peticion("/api/cms/blog-pages", payload, metodo="POST")
        guardar_page_id(ruta, salida["id"])
        print(f"  Creada id {salida['id']} — /cms/pages/{salida['id']}/edit/")
    print(f"  live: {salida['live']} · lenguas: es + {[t['idioma'] for t in salida.get('traducciones', [])]}")


def main():
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    publicar_ya = "--publicar" in sys.argv
    if not argumentos or argumentos == ["todos"]:
        argumentos = sorted(p.name for p in DIRECTORIO.glob("*.md"))
    for nombre in argumentos:
        publicar(nombre if nombre.endswith(".md") else f"{nombre}.md", publicar_ya)


if __name__ == "__main__":
    main()
