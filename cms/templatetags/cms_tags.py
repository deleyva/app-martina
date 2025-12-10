from django import template

register = template.Library()


@register.filter
def unique_document_tags(blocks_tuple):
    """Filtra tags únicas de una tupla (pdf_blocks, audio_blocks, tipo).

    Args:
        blocks_tuple: Tupla con (pdf_blocks, audio_blocks, 'pdf'|'audio')

    Returns:
        Lista de tags únicas para ese tipo de bloque
    """
    try:
        blocks, block_type = blocks_tuple
        seen = set()
        unique = []

        for block in blocks:
            doc = None
            if block_type == "pdf" and hasattr(block, "pdf_file"):
                doc = block.pdf_file
            elif block_type == "audio" and hasattr(block, "audio_file"):
                doc = block.audio_file

            if doc and hasattr(doc, "tags"):
                for tag in doc.tags.all():
                    key = tag.name.lower()
                    if key not in seen:
                        seen.add(key)
                        unique.append(tag)

        return unique
    except:
        return []
