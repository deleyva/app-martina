from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Filter to access dictionary items by a variable key
    Usage: {{ my_dict|get_item:my_key_var }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
