"""Radiografía de solo lectura de la sesión de estudio de un usuario.

Existe porque medir esto por el navegador es adivinar: la vista previa solo
enseña los 8 elegidos, así que no se ve cuántos GRUPOS de material sin tocar
compiten por los huecos de novedad ni en qué orden van. El 2026-08-26 eso costó
dos despliegues para descubrir que el arreglo era insuficiente.

**No escribe nada.** En particular no llama a `rellenar_para_sesion`, que crea
elementos: aquí se informa de lo que crearía, no se crea.

    just production-command estado_estudio --email jlopez@ejemplo.es
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Estado de la sesión de estudio de un usuario. Solo lectura."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--tamano", type=int, default=None)

    def handle(self, *args, **opciones):
        from django.contrib.auth import get_user_model
        from django.db.models import Count

        from my_library import libros
        from my_library.models import LibraryGoal, LibraryItem, ReviewLog
        from my_library.session import (
            PROPORCION_NOVEDAD,
            TAMANO_SESION_POR_DEFECTO,
            _dias_sin_practicar,
            _libro_de,
            _repartir_por_libro,
            construir_sesion,
            unidades_de_practica,
        )

        User = get_user_model()
        try:
            user = User.objects.get(email=opciones["email"])
        except User.DoesNotExist:
            raise CommandError(f"no hay usuario con ese correo")

        tamano = opciones["tamano"] or TAMANO_SESION_POR_DEFECTO
        cuota = max(1, round(tamano * PROPORCION_NOVEDAD))

        items = list(
            LibraryItem.objects.filter(user=user, descartado=False).select_related(
                "source_page"
            )
        )
        practicados = set(
            ReviewLog.objects.filter(user=user).values_list("item_id", flat=True)
        )

        self.stdout.write(f"biblioteca sin descartar: {len(items)}")
        self.stdout.write(f"con al menos un repaso:   {len(practicados)}")
        self.stdout.write(f"sesión de {tamano}, cuota de novedad {cuota}\n")

        self.stdout.write("OBJETIVOS ACTIVOS")
        objetivos = list(
            LibraryGoal.objects.filter(user=user, activo=True).order_by(
                "created_at", "pk"
            )
        )
        if not objetivos:
            self.stdout.write("  (ninguno)")
        reserva = -(-cuota // len(objetivos)) if objetivos else 0
        paths_con_objetivo = set()
        for o in objetivos:
            libro = o.libro.specific
            sin_tocar = libros._sin_tocar_del_libro(user, libro, practicados)
            capitulos = libros.capitulos_de(libro)
            paths_con_objetivo.add(libro.path)
            faltan = max(0, reserva - sin_tocar)
            self.stdout.write(
                f"  {libro.title[:44]:<44} sin_tocar={sin_tocar:<3} "
                f"reserva={reserva} crearía={faltan}"
            )

        # Los grupos que de verdad compiten por los huecos de novedad, en el
        # orden en que `_repartir_por_libro` los sirve.
        unidades = unidades_de_practica(items)
        dias = _dias_sin_practicar(unidades)
        nuevos = [u for u in unidades if dias[u.clave_de_practica] is None]
        nuevos.sort(key=lambda u: (getattr(u, "orden", 0), u.pk))

        self.stdout.write("\nGRUPOS SIN TOCAR, en el orden en que se sirven")
        grupos = {}
        for u in nuevos:
            grupos.setdefault(_libro_de(u), []).append(u)
        repartido = _repartir_por_libro(nuevos)
        vistos = []
        for u in repartido:
            clave = _libro_de(u)
            if clave not in vistos:
                vistos.append(clave)
        for n, clave in enumerate(vistos, 1):
            titulo = "(suelto, sin página)" if clave is None else _titulo_del_path(clave)
            objetivo = " ← objetivo" if clave in paths_con_objetivo else ""
            entra = "SÍ" if n <= cuota else "no"
            self.stdout.write(
                f"  {n}. {titulo[:46]:<46} {len(grupos[clave]):>3} sin tocar "
                f"· ¿entra? {entra}{objetivo}"
            )
        if len(vistos) > cuota:
            self.stdout.write(
                f"  → {len(vistos) - cuota} grupo(s) se quedan fuera de TODAS "
                f"las sesiones: hay {len(vistos)} grupos y solo {cuota} huecos."
            )

        self.stdout.write("\nLA SESIÓN DE AHORA (sin crear nada)")
        for n, u in enumerate(construir_sesion(items, tamano=tamano), 1):
            d = dias[u.clave_de_practica]
            cuando = "sin tocar" if d is None else f"hace {d} d"
            self.stdout.write(f"  {n:>2}. {_titulo(u)[:56]:<56} {cuando}")

        # Para el presupuesto en minutos: cuánto dura de verdad cada elemento.
        self.stdout.write("\nDURACIÓN MEDIDA (para el presupuesto en minutos)")
        con_duracion = (
            ReviewLog.objects.filter(user=user, duration_seconds__isnull=False)
            .values("item")
            .annotate(n=Count("id"))
        )
        medianas = []
        for fila in con_duracion:
            valores = sorted(
                ReviewLog.objects.filter(
                    user=user, item_id=fila["item"], duration_seconds__isnull=False
                ).values_list("duration_seconds", flat=True)
            )
            medianas.append(valores[len(valores) // 2])
        self.stdout.write(f"  elementos con duración: {len(medianas)}")
        if medianas:
            medianas.sort()
            self.stdout.write(f"  mediana de las medianas: {medianas[len(medianas)//2]}s")
            self.stdout.write(f"  mínimo / máximo: {medianas[0]}s / {medianas[-1]}s")
            total = sum(medianas[:tamano])
            self.stdout.write(
                f"  una sesión de {tamano} de los más cortos duraría ~{total//60} min"
            )


def _titulo_del_path(path):
    from wagtail.models import Page

    pagina = Page.objects.filter(path=path).first()
    return pagina.title if pagina else f"(path {path})"


def _titulo(unidad):
    """El titulo que se ve, no el `__str__` del modelo.

    `LibraryItem.__str__` empieza por el correo del usuario, asi que la lista
    entera salia con el correo repetido en cada linea y el titulo cortado.
    """
    item = getattr(unidad, "item", None) or unidad
    objeto = getattr(item, "content_object", None)
    return getattr(objeto, "title", None) or str(unidad)
