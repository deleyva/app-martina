import os
import sys

# Add the app directory to sys.path
sys.path.append('/app/martina_bescos_app')

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

import wagtail
from wagtail.models import Page

def inspect():
    print(f"Wagtail Version: {wagtail.VERSION}")
    try:
        p = Page.objects.get(id=84)
        spec = p.specific
        print(f"Page Title: {p.title}")
        print(f"Page Type: {type(spec)}")
        
        # Check RichText fields
        # StandardPage, BlogPage both have 'body'
        # Let's check all attributes
        for field_name in ['body', 'intro']:
            if hasattr(spec, field_name):
                content = getattr(spec, field_name)
                print(f"\n--- Field: {field_name} ---")
                print(content)
                if hasattr(content, 'source'):
                    print(f"\n--- Field: {field_name} (Source) ---")
                    print(content.source)
                
    except Page.DoesNotExist:
        print("Page 84 not found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect()
