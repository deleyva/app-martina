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

@register.filter
def filter_pending_status(pending_statuses, evaluation_item_id):
    """
    Filtra y devuelve el estado pendiente específico para un item de evaluación.
    Uso en plantillas: {{ student.pending_statuses.all|filter_pending_status:evaluation_item.id }}
    """
    try:
        # Convertir ID a entero si es una cadena
        if isinstance(evaluation_item_id, str) and evaluation_item_id.isdigit():
            evaluation_item_id = int(evaluation_item_id)
        
        # Buscar el estado pendiente que coincida con el item de evaluación
        for status in pending_statuses:
            if status.evaluation_item_id == evaluation_item_id:
                return status
        return None
    except Exception:
        return None
