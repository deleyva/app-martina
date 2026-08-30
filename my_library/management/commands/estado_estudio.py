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
        parser.add_argument(
            "--dias",
            type=int,
            default=1,
            help="Cuántos días atrás resumir la práctica (1 = hoy)",
        )

    def _practica_reciente(self, user, dias):
        """Qué se ha practicado en los últimos `dias`, y cuánto tiempo.

        Solo cuenta los repasos de sesión (`source=study`): valorar un elemento
        desde el índice no es practicarlo, y mezclarlos inflaría el tiempo con
        eventos que duraron cero.
        """
        from datetime import timedelta

        from django.utils import timezone

        from my_library.models import ReviewLog

        # Desde MEDIANOCHE, no una ventana de 24 horas. No es un matiz: con la
        # ventana móvil, "hoy" a las 11:00 incluía lo practicado ayer a las
        # 17:47, y la respuesta a "¿cuánto he estudiado hoy?" salía inflada
        # con la sesión de la víspera (2026-08-29).
        hoy = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        desde = hoy - timedelta(days=dias - 1)
        repasos = list(
            ReviewLog.objects.filter(
                user=user, source=ReviewLog.SOURCE_STUDY, reviewed_at__gte=desde
            ).select_related("item", "item__source_page")
        )

        etiqueta = "HOY" if dias == 1 else f"ÚLTIMOS {dias} DÍAS"
        self.stdout.write(f"\n{etiqueta} — PRÁCTICA")
        if not repasos:
            self.stdout.write("  (nada)")
            return

        # Sin duración no es cero: es un repaso que no la registró. Se cuentan
        # aparte para no bajar la media con ceros que no ocurrieron.
        con_tiempo = [r for r in repasos if r.duration_seconds]
        total = sum(r.duration_seconds for r in con_tiempo)
        tandas = len({r.session_uuid for r in repasos if r.session_uuid})

        self.stdout.write(
            f"  {len(repasos)} repasos en {tandas} tanda(s) · "
            f"{_minutos(total)} medidos en {len(con_tiempo)} de ellos"
        )

        por_libro = {}
        for r in repasos:
            pagina = r.item.source_page if r.item else None
            libro = pagina.get_parent().title if pagina else "(suelto)"
            n, seg = por_libro.get(libro, (0, 0))
            por_libro[libro] = (n + 1, seg + (r.duration_seconds or 0))
        for libro, (n, seg) in sorted(por_libro.items(), key=lambda p: -p[1][1]):
            self.stdout.write(f"    {libro[:44]:<44} {n:>3} repasos · {_minutos(seg)}")

        primero = min(r.reviewed_at for r in repasos)
        ultimo = max(r.reviewed_at for r in repasos)
        self.stdout.write(
            f"  de {timezone.localtime(primero):%H:%M} a "
            f"{timezone.localtime(ultimo):%H:%M}"
        )

    def _descartados_y_repetidos(self, user, items):
        """Dos cosas que se confunden entre sí al mirar una sesión.

        Un elemento DESCARTADO que reapareciera sería un defecto del filtro.
        Dos elementos DISTINTOS con el mismo título no lo son, pero se ven
        exactamente igual en la lista, así que parecen un descarte que no
        funcionó. Se separan aquí para no discutir sobre la impresión.
        """
        from my_library.models import LibraryItem

        self.stdout.write("\nDESCARTADOS Y REPETIDOS")

        descartados = LibraryItem.objects.filter(user=user, descartado=True).count()
        colados = [i for i in items if i.descartado]
        self.stdout.write(
            f"  descartados: {descartados} · de ésos, en la lista de estudio: "
            f"{len(colados)}"
        )

        # Misma cosa dos veces: eso sí sería duplicación de verdad.
        mismos, por_titulo = {}, {}
        for item in items:
            mismos.setdefault((item.content_type_id, item.object_id), []).append(item)
            titulo = item.get_content_title() or "(sin título)"
            por_titulo.setdefault(titulo, []).append(item)

        dobles = {k: v for k, v in mismos.items() if len(v) > 1}
        self.stdout.write(
            f"  el MISMO contenido dos veces: {len(dobles)} caso(s)"
            + (" ← defecto" if dobles else "")
        )
        for items_del_caso in list(dobles.values())[:5]:
            pks = ", ".join(str(i.pk) for i in items_del_caso)
            self.stdout.write(f"    {items_del_caso[0].get_content_title()[:44]:<44} pks {pks}")

        homonimos = {k: v for k, v in por_titulo.items() if len(v) > 1 and k not in ()}
        homonimos = {
            k: v
            for k, v in homonimos.items()
            if len({(i.content_type_id, i.object_id) for i in v}) > 1
        }
        self.stdout.write(
            f"  mismo TÍTULO, contenido distinto: {len(homonimos)} caso(s)"
            " (se ven igual, pero no son el mismo)"
        )
        for titulo, iguales in list(homonimos.items())[:5]:
            pks = ", ".join(str(i.pk) for i in iguales)
            self.stdout.write(f"    {titulo[:44]:<44} pks {pks}")

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
            # El total de material es lo que responde a "¿por qué no me mete
            # nada nuevo?": si sale 0 o igual a lo que ya hay, el objetivo no
            # tiene de dónde sacar, y eso no es un fallo del reparto.
            total_material = len(libros.material_del_libro(libro))
            # Vivos y descartados por separado: contarlos juntos hacía que el
            # número no cuadrara con lo que enseña el selector de sesión, que
            # sí excluye los descartados. Un número que no cuadra con la
            # pantalla es peor que no darlo.
            del_libro = LibraryItem.objects.filter(
                user=user, source_page__in=capitulos
            )
            vivos = del_libro.filter(descartado=False).count()
            descartados = del_libro.filter(descartado=True).count()
            self.stdout.write(
                f"  {libro.title[:38]:<38} material={total_material:<4} "
                f"en_biblioteca={vivos:<4} descartados={descartados:<3} "
                f"sin_tocar={sin_tocar:<3} reserva={reserva} crearía={faltan}"
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

        # "¿Qué he practicado hoy?" es la pregunta que motivó `ReviewLog` en la
        # fase 1, y hasta ahora no había forma de responderla sin abrir el admin
        # y sumar a mano.
        self._practica_reciente(user, opciones["dias"])

        self._descartados_y_repetidos(user, items)

        troceados = sum(1 for i in items if i.sections.exists())
        self.stdout.write(
            f"\nTROCEADOS EN SECCIONES: {troceados} de {len(items)}"
            "  (la alternativa al presupuesto en minutos para el material largo)"
        )

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
        total_practicables = len(unidades)
        self.stdout.write(
            f"  elementos con duración: {len(medianas)} de {total_practicables} "
            f"({100 * len(medianas) // max(1, total_practicables)}%)"
        )
        if medianas:
            # La distribución, no solo la mediana: un presupuesto en minutos se
            # calibra con la FORMA de los datos. Si casi todo son elementos
            # cortos, el presupuesto dará sesiones más largas que las de ahora,
            # que es lo contrario de lo que se busca.
            tramos = [
                ("menos de 30 s", lambda d: d < 30),
                ("30 s a 1 min", lambda d: 30 <= d < 60),
                ("1 a 3 min", lambda d: 60 <= d < 180),
                ("3 a 8 min", lambda d: 180 <= d < 480),
                ("más de 8 min", lambda d: d >= 480),
            ]
            for nombre, cabe in tramos:
                cuantos = sum(1 for d in medianas if cabe(d))
                barra = "█" * cuantos
                self.stdout.write(f"    {nombre:<14} {cuantos:>3}  {barra}")
            media = sum(medianas) / len(medianas)
            self.stdout.write(f"  media: {media:.0f}s")
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


def _minutos(segundos):
    return f"{segundos // 60} min {segundos % 60:02d} s"
