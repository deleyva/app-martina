"""El pase en vivo (tramo 76·2): tarjetas, lecturas, revelar, cerrar.

Lo que decide algo vive aquí; las vistas de `views_pase.py` solo comprueban
permisos y traducen a JSON. El servidor es la única verdad del pase: la
pantalla proyectada y el iPad que mira la clase consultan `estado_de` por
`fetch` (sin WebSockets, decisión de la fase 76).
"""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from calificaciones.models import alumnos_del_grupo
from clases.models import ClassSessionItem, Enrollment
from clases.plano import faltan_en

from .composicion import crear_pase
from .models import Pase, PasePregunta, Pregunta, Respuesta

# `cv2.aruco.DICT_4X4_100`: ids 0–99. El 0 se deja libre para que el número de
# tarjeta empiece en 1, como se numera una lista.
TARJETA_MAXIMA = 99


# =============================================================================
# TARJETAS (C478)
# =============================================================================


def asignar_tarjetas(group):
    """Da número a las matrículas activas que aún no lo tienen y devuelve todas.

    El número más bajo libre, en el orden en que se pasa lista. Idempotente:
    quien ya tiene tarjeta la conserva aunque entre alumnado nuevo, así el
    juego impreso sigue valiendo y solo hay que imprimir las que faltan.

    Una baja (`is_active=False`) conserva su número y lo sigue ocupando: la
    tarjeta impresa existe, y si vuelve (`matricular` reactiva) encuentra la
    suya. Lo cazó el test: contar solo las activas chocaba con la restricción
    única al dar su número a otro.
    """
    matriculas = list(
        Enrollment.objects.filter(group=group, is_active=True)
        .select_related("user")
        .order_by("user__name", "user__email")
    )
    usados = set(
        Enrollment.objects.filter(group=group, tarjeta__isnull=False).values_list("tarjeta", flat=True)
    )
    siguiente = 1
    with transaction.atomic():
        for m in matriculas:
            if m.tarjeta:
                continue
            while siguiente in usados:
                siguiente += 1
            if siguiente > TARJETA_MAXIMA:
                raise ValueError(f"No caben más de {TARJETA_MAXIMA} tarjetas en un grupo")
            m.tarjeta = siguiente
            usados.add(siguiente)
            m.save(update_fields=["tarjeta"])
    return matriculas


def tarjetas_de(group):
    """Lo que necesita el PDF: id del marcador, número y nombre, por número."""
    return sorted(
        (
            {"id": m.tarjeta, "numero": m.tarjeta, "nombre": m.user.name or m.user.email}
            for m in asignar_tarjetas(group)
        ),
        key=lambda t: t["numero"],
    )


def alumno_por_tarjeta(group):
    return {
        m.tarjeta: m.user_id
        for m in Enrollment.objects.filter(group=group, is_active=True, tarjeta__isnull=False)
    }


def juego_generico(n):
    """N tarjetas sin nombre (C550). Un solo juego para todos los grupos: los
    números 1–N se reutilizan entre grupos y el grupo lo da la sesión, así que
    la tarjeta no necesita saber de quién es. El nombre va en una pegatina en el
    dorso (decisión de Jesús, 2026-10-28)."""
    n = max(1, min(int(n), TARJETA_MAXIMA))
    return [{"id": i, "numero": i, "nombre": ""} for i in range(1, n + 1)]


def pegatinas_de(user):
    """Una pegatina por número con «grupo: nombre» de cada grupo del día a día
    del profesor, en el orden de los números.

    Reparte los números que falten en todos sus grupos. Es la app quien los
    da, nunca la mano: la lectura busca «tarjeta 7 del grupo de la sesión» en
    la base de datos, y una pegatina escrita a mano se la daría a otro. Los
    grupos archivados y las plantillas quedan fuera (`Group.del_profesor`).
    """
    from clases.models import Group

    por_numero = {}
    for grupo in Group.del_profesor(user).order_by("name"):
        for t in tarjetas_de(grupo):
            por_numero.setdefault(t["numero"], []).append(f"{grupo.name}: {t['nombre']}")
    return [{"numero": n, "lineas": por_numero[n]} for n in sorted(por_numero)]


# =============================================================================
# EL PASE COMO ELEMENTO DE LA SESIÓN (C479)
# =============================================================================


def crear_desde_sesion(session, preguntas, user):
    """Un pase con esas preguntas, metido en la sesión como elemento de Teoría."""
    with transaction.atomic():
        pase = crear_pase(session.group, session.date, preguntas, session=session, creado_por=user)
        item = ClassSessionItem.objects.create(
            session=session,
            content_type=ContentType.objects.get_for_model(Pase),
            object_id=pase.pk,
            order=session.get_next_order(),
            seccion="teoria",
        )
    return pase, item


def presentes(pase):
    """El alumnado que cuenta en este pase: matriculados activos sin falta en la sesión."""
    alumnos = list(alumnos_del_grupo(pase.group))
    faltas = faltan_en(pase.session) if pase.session_id else set()
    return [a for a in alumnos if a.pk not in faltas]


# =============================================================================
# EN CLASE (C480, C481)
# =============================================================================


def abrir(pase):
    if pase.estado == Pase.BORRADOR:
        pase.estado = Pase.ABIERTO
        pase.abierto = timezone.now()
        pase.save(update_fields=["estado", "abierto"])
    return pase


def registrar(pase, marcadores):
    """Las lecturas de un fotograma, sobre la pregunta que está en pantalla.

    Devuelve `(contadas, desconocidas)`. Vale la última lectura de cada alumno
    antes de revelar (C481). No cuentan, y se suman a `desconocidas`: un id sin
    matrícula en el grupo y cualquier lectura con la pregunta ya revelada. Una
    tarjeta en ángulo ambiguo (`letra` nula) no es ni una cosa ni otra: se
    espera al siguiente fotograma.
    """
    validos = [m for m in marcadores if m.get("letra") in Pregunta.LETRAS]
    with transaction.atomic():
        pase = Pase.objects.select_for_update().get(pk=pase.pk)
        actual = (
            PasePregunta.objects.select_for_update()
            .filter(pase=pase, posicion=pase.posicion)
            .first()
        )
        if pase.estado != Pase.ABIERTO or actual is None:
            return 0, len(validos)
        if actual.revelada or pase.revision:
            actual.desconocidas += len(validos)
            actual.save(update_fields=["desconocidas"])
            return 0, len(validos)
        por_tarjeta = alumno_por_tarjeta(pase.group)
        contadas = desconocidas = 0
        for m in validos:
            alumno_id = por_tarjeta.get(m["id"])
            if alumno_id is None:
                desconocidas += 1
                continue
            actual.lecturas[str(alumno_id)] = Pregunta.LETRAS.index(m["letra"])
            contadas += 1
        actual.desconocidas += desconocidas
        actual.save(update_fields=["lecturas", "desconocidas"])
    return contadas, desconocidas


def revelar(pase):
    actual = pase.actual()
    if actual is not None and not actual.revelada:
        actual.revelada = True
        actual.save(update_fields=["revelada"])
    return actual


def siguiente(pase):
    """Pasa a la siguiente pregunta. Más allá de la última, el pase queda «terminado»
    (sin pregunta en pantalla) a la espera de cerrarse."""
    if pase.posicion < pase.n_preguntas:
        pase.posicion += 1
        pase.save(update_fields=["posicion"])
    return pase.actual()


def reparto(actual):
    cuenta = [0, 0, 0, 0]
    for opcion in actual.lecturas.values():
        if isinstance(opcion, int) and 0 <= opcion < 4:
            cuenta[opcion] += 1
    return cuenta


# =============================================================================
# LA VUELTA DE COMPROBACIÓN (76·4: C560, C561)
# =============================================================================


def empezar_revision(pase):
    """Terminadas las preguntas, vuelve a la primera con `revision=True`.

    Solo desde «terminado» (sin pregunta en pantalla): a mitad de pase no hay
    nada que comprobar todavía. Idempotente si ya está en la vuelta.
    """
    if pase.estado != Pase.ABIERTO:
        raise ValueError("El pase no está abierto.")
    if pase.revision:
        return pase
    if pase.actual() is not None:
        raise ValueError("Quedan preguntas por pasar.")
    pase.revision = True
    pase.posicion = 0
    pase.save(update_fields=["revision", "posicion"])
    return pase


def anterior(pase):
    if pase.posicion > 0:
        pase.posicion -= 1
        pase.save(update_fields=["posicion"])
    return pase.actual()


def corregir(pase, alumno_id, letra):
    """El profesor cambia a mano la lectura de un presente en la pregunta en
    pantalla (en la vuelta, o ya revelada). Queda en `correcciones` para que la
    `Respuesta` salga marcada. `letra` vacía = sin lectura."""
    if letra not in ("", *Pregunta.LETRAS):
        raise ValueError(f"«{letra}» no es una opción.")
    with transaction.atomic():
        pase = Pase.objects.select_for_update().get(pk=pase.pk)
        actual = PasePregunta.objects.select_for_update().filter(pase=pase, posicion=pase.posicion).first()
        if pase.estado != Pase.ABIERTO or actual is None:
            raise ValueError("No hay ninguna pregunta en pantalla.")
        if not (pase.revision or actual.revelada):
            raise ValueError("Solo se corrige con la pregunta revelada.")
        if int(alumno_id) not in {a.pk for a in presentes(pase)}:
            raise ValueError("Ese alumno no está en este pase.")
        clave = str(int(alumno_id))
        if letra == "":
            actual.lecturas.pop(clave, None)
        else:
            actual.lecturas[clave] = Pregunta.LETRAS.index(letra)
        correcciones = dict(actual.correcciones or {})
        correcciones[clave] = actual.lecturas.get(clave)
        actual.correcciones = correcciones
        actual.save(update_fields=["lecturas", "correcciones"])
    return actual


# =============================================================================
# CERRAR (C482)
# =============================================================================


def cerrar(pase):
    """Una `Respuesta` por alumno presente y pregunta; sin lectura = opción nula
    (errónea, por decisión de Jesús). Los ausentes no tienen fila."""
    with transaction.atomic():
        pase = Pase.objects.select_for_update().get(pk=pase.pk)
        if pase.estado == Pase.CERRADO:
            return pase
        alumnos = presentes(pase)
        for pp in pase.orden.select_related("pregunta"):
            for alumno in alumnos:
                Respuesta.objects.update_or_create(
                    pase=pase,
                    pregunta=pp.pregunta,
                    alumno=alumno,
                    defaults={
                        "opcion": pp.lecturas.get(str(alumno.pk)),
                        "corregida": str(alumno.pk) in (pp.correcciones or {}),
                    },
                )
        pase.estado = Pase.CERRADO
        pase.cerrado = timezone.now()
        pase.save(update_fields=["estado", "cerrado"])
    return pase


# =============================================================================
# LO QUE VE LA PANTALLA
# =============================================================================


def _imagen_url(pregunta):
    if pregunta.imagen_id is None:
        return None
    try:
        return pregunta.imagen.get_rendition("width-1200").url
    except Exception:
        return None


def estado_de(pase, con_letras=False):
    """El JSON que pintan la pantalla proyectada y el iPad, cada segundo.

    Antes de revelar no sale ninguna respuesta: solo quién ha respondido. Al
    revelar salen la correcta, la explicación, el reparto A/B/C/D y, junto a
    cada nombre, ✓ o ✗. La letra que eligió cada uno solo va con `con_letras`,
    que la vista concede al profesorado del grupo (la pantalla con la cámara,
    76·4), nunca al alumnado ni al proyector.

    En la vuelta de comprobación (`pase.revision`) cada pregunta sale revelada,
    con todos los presentes y su ✓/✗ (sin lectura = ✗), y al final, solo con
    `con_letras`, la puntuación de cada uno (`totales`).
    """
    actual = pase.actual()
    alumnos = {a.pk: (a.name or a.email) for a in presentes(pase)}
    datos = {
        "pk": pase.pk,
        "estado": pase.estado,
        "posicion": pase.posicion,
        "total": pase.n_preguntas,
        "revision": pase.revision,
        "terminado": actual is None,
        "n_presentes": len(alumnos),
        "desconocidas": sum(pp.desconocidas for pp in pase.orden.all()),
    }
    if actual is None:
        if pase.revision and con_letras:
            datos["totales"] = _totales(pase, alumnos)
        return datos
    pregunta = actual.pregunta
    revelada = actual.revelada or pase.revision
    correcciones = actual.correcciones or {}

    def fila(alumno_id, nombre):
        opcion = actual.lecturas.get(str(alumno_id))
        fila = {"id": alumno_id, "nombre": nombre, "acierto": (opcion == pregunta.correcta) if revelada else None}
        if revelada:
            fila["sin_lectura"] = opcion is None
            fila["corregida"] = str(alumno_id) in correcciones
        if con_letras:
            fila["letra"] = Pregunta.LETRAS[opcion] if isinstance(opcion, int) and 0 <= opcion < 4 else ""
        return fila

    if pase.revision:
        filas = [fila(pk, nombre) for pk, nombre in alumnos.items()]
    else:
        filas = [fila(int(k), alumnos[int(k)]) for k in actual.lecturas if int(k) in alumnos]
    filas.sort(key=lambda f: f["nombre"])
    datos.update(
        revelada=revelada,
        respondido=filas,
        n_respondido=sum(1 for f in filas if not f.get("sin_lectura")) if pase.revision else len(filas),
        pregunta={
            "pk": pregunta.pk,
            "enunciado": pregunta.enunciado,
            "opciones": list(pregunta.opciones),
            "imagen": _imagen_url(pregunta),
        },
    )
    if revelada:
        datos["pregunta"].update(
            correcta=pregunta.correcta,
            letra=pregunta.letra_correcta,
            explicacion=pregunta.explicacion,
        )
        datos["reparto"] = reparto(actual)
    return datos


def _totales(pase, alumnos):
    """Aciertos de cada presente en todo el pase, por nombre. Solo para el iPad."""
    preguntas = list(pase.orden.select_related("pregunta"))
    filas = []
    for alumno_id, nombre in alumnos.items():
        aciertos = sum(1 for pp in preguntas if pp.lecturas.get(str(alumno_id)) == pp.pregunta.correcta)
        filas.append({"id": alumno_id, "nombre": nombre, "aciertos": aciertos, "total": len(preguntas)})
    return sorted(filas, key=lambda f: f["nombre"])
