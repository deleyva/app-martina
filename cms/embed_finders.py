import re

from wagtail.embeds.finders.base import EmbedFinder
from wagtail.embeds.finders.oembed import OEmbedFinder
from wagtail.embeds.oembed_providers import youtube

class HooktheoryEmbedFinder(EmbedFinder):
    def __init__(self, **options):
        pass

    def accept(self, url):
        return "hooktheory.com/hookpad/iframe" in url

    def find_embed(self, url, max_width=None, max_height=None):
        html = f'<iframe src="{url}" frameborder="0" allowfullscreen allow="autoplay; fullscreen"></iframe>'
        return {
            'title': 'Hookpad',
            'author_name': 'Hooktheory',
            'provider_name': 'Hooktheory',
            'type': 'rich',
            'thumbnail_url': '',
            'width': max_width or 100,
            'height': max_height or 100,
            'html': html,
        }


# Un vídeo largo y bueno se cita varias veces, cada una en el segundo donde
# empieza lo que interesa. El oEmbed de YouTube devuelve el iframe sin el
# inicio, así que se lee de la URL y se añade al `src` (2026-10-21).
_INICIO_YOUTUBE = re.compile(r"[?&](?:t|start)=([\dhms]+)")
_ES_YOUTUBE = re.compile(r"^https?://(?:www\.|m\.)?(?:youtube\.com/watch|youtu\.be/)")


def segundos_de_inicio(url):
    """`t=95`, `t=95s`, `t=1m35s`, `start=95` → 95. Sin inicio → None."""
    m = _INICIO_YOUTUBE.search(url)
    if not m:
        return None
    valor = m.group(1)
    if valor.isdigit():
        return int(valor)
    partes = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", valor)
    if not partes or not any(partes.groups()):
        return None
    h, mi, se = (int(x or 0) for x in partes.groups())
    return h * 3600 + mi * 60 + se


class YouTubeInicioEmbedFinder(OEmbedFinder):
    """oEmbed de YouTube que respeta el segundo de inicio de la URL."""

    def __init__(self, **options):
        super().__init__(providers=[youtube], **options)

    def accept(self, url):
        return bool(_ES_YOUTUBE.match(url)) and segundos_de_inicio(url) is not None

    def find_embed(self, url, max_width=None, max_height=None):
        datos = super().find_embed(url, max_width=max_width, max_height=max_height)
        inicio = segundos_de_inicio(url)
        datos["html"] = re.sub(
            r'src="([^"]+)"',
            lambda m: f'src="{m.group(1)}{"&" if "?" in m.group(1) else "?"}start={inicio}"',
            datos["html"],
            count=1,
        )
        return datos
