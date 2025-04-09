from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Obtiene un elemento de un diccionario por su clave.
    Uso en plantillas: {{ diccionario|get_item:clave }}
    """
    try:
        # Convertir la clave a entero si es posible (para IDs)
        if isinstance(key, str) and key.isdigit():
            key = int(key)
        return dictionary.get(key)
    except (KeyError, AttributeError):
        return None
