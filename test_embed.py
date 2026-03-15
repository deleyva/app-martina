import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from wagtail.embeds.embeds import get_embed
try:
    embed = get_embed("https://www.youtube.com/watch?v=123456789")
    print("Is instance of Model?", hasattr(embed, 'pk'))
    print("PK:", embed.pk)
except Exception as e:
    print(e)
