from wagtail.documents.models import Document
from wagtail.images.models import Image
from wagtail.embeds.models import Embed
from django.utils import timezone
from typing import List, Dict, Any

class ResourceSearchService:
    @staticmethod
    def search(query: str = '', type_filter: str = '', tags: list = None, user=None) -> List[Dict[str, Any]]:
        """
        Busca recursos en Wagtail (Documentos, Imágenes, Embeds).
        """
        results = []
        tags = [t.strip().lower() for t in (tags or []) if t.strip()]

        # 1. Search Documents (PDFs, Audios)
        if not type_filter or type_filter == 'document':
            docs = Document.objects.all()
            if query:
                docs = docs.filter(title__icontains=query)
            if tags:
                for tag in tags:
                    docs = docs.filter(tags__name__iexact=tag)
            
            for doc in docs:
                is_audio = doc.file.name.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac'))
                icon = '🎵' if is_audio else '📄'
                
                results.append({
                    'id': f"doc_{doc.id}",
                    'content_object': doc,
                    'title': doc.title,
                    'type': 'document',
                    'icon': icon,
                    'url': doc.url,
                    'created_at': doc.created_at,
                })

        # 2. Search Images
        if not type_filter or type_filter == 'image':
            images = Image.objects.all()
            if query:
                images = images.filter(title__icontains=query)
            if tags:
                for tag in tags:
                    images = images.filter(tags__name__iexact=tag)
            
            for img in images:
                results.append({
                    'id': f"img_{img.id}",
                    'content_object': img,
                    'title': img.title,
                    'type': 'image',
                    'icon': '🖼️',
                    'url': img.file.url if img.file else '',
                    'created_at': img.created_at,
                })

        # 3. Search Embeds
        if not type_filter or type_filter == 'embed':
            embeds = Embed.objects.all()
            if query:
                # Embed doesn't have title field explicitly in the same way, but it has `title` from oEmbed usually
                embeds = embeds.filter(url__icontains=query) | embeds.filter(title__icontains=query)
            
            # Embeds don't have tags in Wagtail by default. 
            if tags:
                embeds = embeds.none()

            for emb in embeds:
                results.append({
                    'id': f"emb_{emb.id}",
                    'content_object': emb,
                    'title': getattr(emb, 'title', None) or emb.url,
                    'type': 'embed',
                    'icon': '▶️',
                    'url': emb.url,
                    'created_at': getattr(emb, 'last_updated', timezone.now()),
                })

        # Sort combined results by created_at descending
        results.sort(key=lambda x: x.get('created_at') or timezone.now(), reverse=True)

        return results
