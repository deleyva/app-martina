from wagtail.embeds.finders.base import EmbedFinder

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
