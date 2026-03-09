import os
import sys

# Add the app directory to sys.path
sys.path.append('/app/martina_bescos_app')

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from wagtail.models import Page

def list_pages():
    pages = Page.objects.all().order_by('id')
    print(f"Total Pages: {pages.count()}")
    for p in pages:
        print(f"ID: {p.id} | Title: {p.title} | Slug: {p.slug} | Type: {type(p.specific)}")

if __name__ == "__main__":
    list_pages()
