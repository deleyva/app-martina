import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.template import Context, Template
from wagtail.embeds.models import Embed

url = "https://www.youtube.com/watch?v=nVDsIt-hWL0"

template_str = """
{% load wagtailembeds_tags %}
<div class="embed-fullscreen-container" style="height: 100vh; display: flex; align-items: center; justify-content: center; background: #000; padding-top: 48px;">
    <div style="width: 100%; height: 100%; max-width: 100%; display: flex; justify-content: center; align-items: center;">
        {% embed url %}
    </div>
</div>
"""

t = Template(template_str)
c = Context({"url": url})
print(t.render(c))

