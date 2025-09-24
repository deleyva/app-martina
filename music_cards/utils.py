from django.db.models import Max
from .models import Text


def get_max_order():
    texts = Text.objects.all()
    if not texts.exists():
        return 1
    else:
        current_max = texts.aggregate(max_order=Max("order"))["max_order"]
        return current_max
