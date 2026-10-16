"""El índice de recursos musicales, volcado a un solo fichero Markdown.

Existe para alimentar un GPT de ChatGPT (fase 77). Un GPT no vuelve a leer una
URL en cada conversación: lo único que consulta de forma fiable es un archivo
de Knowledge. Así que en vez de darle el enlace al índice, se le da el índice
entero, con una ficha por página y todo lo que un músico preguntaría en voz
alta: en qué tono va, qué acordes tiene, a qué tempo, dónde está la tablatura.

**Solo lectura.** Aquí no se crea nada: la letra con acordes se lee de
`page.chordpro` y no de `obtener_letra_con_acordes()`, que crea una fila.

**Todo cabe en un fichero.** El orden es el del árbol, los libros anidan sus
capítulos con un nivel más de título, y antes de las fichas va una tabla con
título, tipo, artista y URL: la búsqueda semántica del GPT aterriza ahí y
después baja a la ficha.
"""

from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

# Etiquetas de bloque: al convertir a texto plano, cada una abre párrafo.
_BLOQUES = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr"}


def texto_plano(html: str | None) -> str:
    """Prosa sin etiquetas, entidades decodificadas, un párrafo por bloque.

    `<br>` es un salto de línea dentro del párrafo; los bloques (`<p>`, `<li>`,
    títulos) abren párrafo nuevo. Los `<embed>` de Wagtail (imágenes incrustadas
    en el cuerpo) desaparecen: en un fichero de texto no aportan nada.
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for embed in soup.find_all("embed"):
        embed.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(_BLOQUES):
        tag.insert_before("\n\n")
        tag.insert_after("\n\n")
    texto = soup.get_text()
    # Cada línea limpia por los lados; nunca más de una línea en blanco seguida.
    lineas = [linea.strip() for linea in texto.splitlines()]
    texto = "\n".join(lineas)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def _url_absoluta(pagina, ruta: str | None) -> str:
    """Una URL de documento o imagen, con el host del sitio delante si es relativa."""
    if not ruta:
        return ""
    if ruta.startswith("http://") or ruta.startswith("https://"):
        return ruta
    sitio = pagina.get_site()
    raiz = sitio.root_url if sitio else ""
    return f"{raiz}{ruta}"


def _linea(etiqueta: str, valor) -> str:
    """Una fila `- **Etiqueta:** valor`, o nada si el valor está vacío."""
    if valor in (None, "", [], ()):
        return ""
    return f"- **{etiqueta}:** {valor}\n"


def _etiquetas(pagina) -> str:
    gestor = getattr(pagina, "faceted_tags", None)
    if gestor is None:
        return ""
    return ", ".join(sorted(gestor.names()))


def _categorias(pagina) -> str:
    gestor = getattr(pagina, "categories", None)
    if gestor is None:
        return ""
    return ", ".join(c.name for c in gestor.all())


# --- Qué lleva cada tipo de página -------------------------------------------


def _adjuntos_recurso(pagina) -> list[str]:
    """Una línea por adjunto, con su URL cuando la tiene."""
    lineas = []
    for bloque in pagina.attachments:
        tipo, valor = bloque.block_type, bloque.value
        if tipo == "pdf_score":
            doc = valor.get("pdf_file")
            if doc:
                lineas.append(f"PDF/Guitar Pro: {doc.title} — {_url_absoluta(pagina, doc.url)}")
        elif tipo == "audio":
            doc = valor.get("audio_file")
            if doc:
                lineas.append(f"Audio: {doc.title} — {_url_absoluta(pagina, doc.url)}")
        elif tipo == "video":
            doc = valor.get("video_file")
            if doc:
                lineas.append(f"Vídeo: {doc.title} — {_url_absoluta(pagina, doc.url)}")
        elif tipo == "image":
            imagen = valor.get("image")
            if imagen:
                pie = valor.get("caption") or ""
                lineas.append(f"Imagen: {imagen.title}" + (f" — {pie}" if pie else ""))
        elif tipo == "external_link":
            recurso = valor.get("resource")
            if recurso:
                titulo = valor.get("override_title") or recurso.title
                lineas.append(f"Enlace: {titulo} — {recurso.url}")
        elif tipo == "recorte":
            recorte = valor.get("recorte")
            if recorte:
                lineas.append(
                    f"Recorte de PDF: {recorte.nombre} "
                    f"(pp. {recorte.pagina_desde}-{recorte.pagina_hasta} de {recorte.documento.title})"
                )
    return lineas


def _ficha_recurso(pagina) -> str:
    """Una canción, un capítulo o un recurso suelto: la única página con ficha."""
    partes = []
    partes.append(_linea("Artista / compositor", pagina.artist))
    partes.append(_linea("Tonalidad", pagina.key_display))
    partes.append(_linea("Compás", pagina.time_signature_display))
    partes.append(_linea("Tempo", f"{pagina.tempo_bpm} BPM" if pagina.tempo_bpm else ""))
    partes.append(_linea("Duración", pagina.duration_display))
    partes.append(_linea("Referencia", pagina.reference))
    partes.append(_linea("Tablatura (Songsterr)", pagina.songsterr_url))
    partes.append(_linea("Fecha", pagina.date.isoformat() if pagina.date else ""))
    partes.append(_linea("Etiquetas", _etiquetas(pagina)))
    partes.append(_linea("Categorías", _categorias(pagina)))
    if pagina.is_protected:
        partes.append(_linea("Acceso", "requiere iniciar sesión"))

    varias_lenguas = len(pagina.idiomas_disponibles) > 1
    for codigo, nombre in pagina.idiomas_disponibles:
        texto = pagina.texto(codigo)
        partes.append(f"\n#### Texto ({nombre})\n\n")
        if varias_lenguas:
            partes.append(f"URL en esta lengua: {pagina.full_url}?lang={codigo}\n\n")
        if texto["intro"]:
            partes.append(f"*{texto['intro'].strip()}*\n\n")
        cuerpo = texto_plano(texto["body"])
        if cuerpo:
            partes.append(cuerpo + "\n\n")

    if pagina.chordpro:
        partes.append("\n#### Letra con acordes (ChordPro)\n\n```chordpro\n")
        partes.append(pagina.chordpro.strip() + "\n```\n\n")

    adjuntos = _adjuntos_recurso(pagina)
    if adjuntos:
        partes.append("\n#### Adjuntos\n\n")
        partes.extend(f"- {linea}\n" for linea in adjuntos)
        partes.append("\n")

    externos = list(pagina.enlaces_externos.all())
    if externos:
        partes.append("\n#### Material externo\n\n")
        partes.extend(
            f"- {e.titulo} ({e.get_proveedor_display()}) — {e.url}\n" for e in externos
        )
        partes.append("\n")

    return "".join(partes)


def _ficha_partitura(pagina) -> str:
    """`ScorePage`: el tipo antiguo de partitura con PDF y metadatos en bloques."""
    partes = []
    if pagina.composer:
        partes.append(_linea("Compositor", pagina.composer.name))
    partes.append(_linea("Etiquetas", _etiquetas(pagina)))
    partes.append(_linea("Categorías", _categorias(pagina)))
    for bloque in pagina.content:
        tipo, valor = bloque.block_type, bloque.value
        if tipo == "metadata":
            partes.append(_linea("Compositor (ficha)", valor.get("composer")))
            partes.append(_linea("Tonalidad", valor.get("key_signature")))
            partes.append(_linea("Tempo", valor.get("tempo")))
            partes.append(_linea("Dificultad", valor.get("difficulty")))
            partes.append(_linea("Duración (min)", valor.get("duration_minutes")))
            partes.append(_linea("Referencia", valor.get("reference")))
        elif tipo == "pdf_score":
            doc = valor.get("pdf_file")
            if doc:
                partes.append(_linea("PDF", f"{valor.get('title') or doc.title} — {_url_absoluta(pagina, doc.url)}"))
        elif tipo == "audio":
            doc = valor.get("audio_file")
            if doc:
                partes.append(_linea("Audio", f"{valor.get('title') or doc.title} — {_url_absoluta(pagina, doc.url)}"))
        elif tipo == "url":
            partes.append(_linea("Enlace", f"{valor.get('title')} — {valor.get('url')}"))
        elif tipo == "embed":
            partes.append(_linea("Embed", getattr(valor, "url", str(valor))))
        elif tipo == "notes":
            notas = texto_plano(str(valor))
            if notas:
                partes.append(f"\n{notas}\n\n")
        elif tipo == "bookmarks":
            marcadores = [
                f"p. {m.get('page_number')}: {m.get('title')}" for m in valor if m.get("title")
            ]
            if marcadores:
                partes.append(_linea("Marcadores", "; ".join(marcadores)))
    return "".join(partes)


def _ficha_libro(pagina) -> str:
    partes = [_linea("Etiquetas", _etiquetas(pagina))]
    if pagina.is_protected:
        partes.append(_linea("Acceso", "requiere iniciar sesión"))
    intro = texto_plano(pagina.intro)
    if intro:
        partes.append(f"\n{intro}\n\n")
    return "".join(partes)


def _ficha_generica(pagina) -> str:
    """Listas, dictados, tests, libros de estudio: título, etiquetas e intro."""
    partes = [_linea("Etiquetas", _etiquetas(pagina)), _linea("Categorías", _categorias(pagina))]
    for campo in ("intro", "description"):
        intro = texto_plano(getattr(pagina, campo, "") or "")
        if intro:
            partes.append(f"\n{intro}\n\n")
            break
    return "".join(partes)


def _ficha(pagina) -> str:
    nombre = type(pagina).__name__
    if nombre == "RecursoPage":
        return _ficha_recurso(pagina)
    if nombre == "ScorePage":
        return _ficha_partitura(pagina)
    if nombre == "LibroPage":
        return _ficha_libro(pagina)
    return _ficha_generica(pagina)


# --- Qué páginas entran --------------------------------------------------------


def _es_privada(pagina) -> bool:
    return bool(getattr(pagina, "is_private", False))


def es_cancion(pagina) -> bool:
    """Un recurso con ficha musical o con letra: lo que `--solo-canciones` pide."""
    if type(pagina).__name__ != "RecursoPage":
        return False
    return bool(pagina.tiene_ficha_musical or pagina.chordpro)


def paginas_del_indice(indice, *, incluir_privadas=False, solo_canciones=False):
    """Las páginas publicadas bajo el índice, en orden de árbol, ya `specific`.

    Una página privada se cae, y con ella todo lo que cuelga de ella: un
    capítulo de un libro privado hereda la restricción, así que no basta con
    mirar la bandera de cada página.
    """
    paginas = indice.get_descendants().live().order_by("path").specific()
    elegidas = []
    raices_privadas: list[str] = []
    for pagina in paginas:
        if not incluir_privadas:
            if any(pagina.path.startswith(raiz) for raiz in raices_privadas):
                continue
            if _es_privada(pagina):
                raices_privadas.append(pagina.path)
                continue
        if solo_canciones and not es_cancion(pagina):
            continue
        elegidas.append(pagina)
    return elegidas


# --- El fichero ----------------------------------------------------------------


def _tipo_legible(pagina) -> str:
    return str(pagina._meta.verbose_name)


def _artista(pagina) -> str:
    if type(pagina).__name__ == "RecursoPage":
        return pagina.artist or ""
    if type(pagina).__name__ == "ScorePage" and pagina.composer:
        return pagina.composer.name
    return ""


def _celda(texto: str) -> str:
    return (texto or "").replace("|", "\\|").replace("\n", " ")


def exportar_indice(indice, *, incluir_privadas=False, solo_canciones=False, hoy=None):
    """El Markdown entero del índice y los recuentos por tipo.

    Devuelve `(markdown, recuentos)`; `recuentos` es `{tipo legible: n}` para
    que el comando lo cuente en el resumen sin volver a recorrer nada.
    """
    hoy = hoy or date.today()
    paginas = paginas_del_indice(
        indice, incluir_privadas=incluir_privadas, solo_canciones=solo_canciones
    )
    recuentos: dict[str, int] = {}
    for pagina in paginas:
        tipo = _tipo_legible(pagina)
        recuentos[tipo] = recuentos.get(tipo, 0) + 1

    partes = [f"# {indice.title}\n\n"]
    partes.append(f"Volcado del {hoy.isoformat()} de {indice.full_url}\n\n")
    intro = texto_plano(indice.intro)
    if intro:
        partes.append(intro + "\n\n")
    partes.append(f"Páginas incluidas: {len(paginas)}")
    if recuentos:
        partes.append(" (" + ", ".join(f"{n} {t}" for t, n in sorted(recuentos.items())) + ")")
    partes.append(".\n\n")

    partes.append("## Índice\n\n| Título | Tipo | Artista | URL |\n|---|---|---|---|\n")
    for pagina in paginas:
        partes.append(
            f"| {_celda(pagina.title)} | {_celda(_tipo_legible(pagina))} "
            f"| {_celda(_artista(pagina))} | {pagina.full_url} |\n"
        )
    partes.append("\n## Fichas\n\n")

    for pagina in paginas:
        # Un nivel por profundidad bajo el índice: hijo directo `##`, capítulo
        # de libro `###`, y tope en `####` para que no se hunda más.
        nivel = min(1 + (pagina.depth - indice.depth), 4)
        partes.append(f"{'#' * nivel} {pagina.title}\n\n")
        partes.append(_linea("Tipo", _tipo_legible(pagina)))
        partes.append(_linea("URL", pagina.full_url))
        padre = pagina.get_parent()
        if padre and padre.pk != indice.pk:
            partes.append(_linea("Dentro de", padre.title))
        partes.append(_ficha(pagina))
        partes.append("\n---\n\n")

    return "".join(partes), recuentos
