"""Ganchos de Wagtail de la app de musica.

Wagtail solo descubre los ganchos que estan en `<app>/wagtail_hooks.py`, asi que
este fichero existe para importar los que viven en otro sitio. El de servido
esta en `servido.py` porque va pegado a la vista que entrega el rango, y
separarlos dejaria la mitad de la decision en cada fichero.
"""

from musica.servido import servido_selectivo  # noqa: F401
