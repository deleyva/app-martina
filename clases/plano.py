"""El plano de clase: su forma, sus reglas y el pase de lista que va encima.

Es lo único que escribe `PlanoDeClase.disposicion`. Lo llaman la pantalla del
editor, la de la clase y la API, y las tres pasan por `guardar`, así que las
tres validan igual y las tres dejan versión.

La disposición, en unidades de una rejilla fija (no píxeles: el mismo plano se
pinta en el portátil y en la pizarra digital)::

    {
      "referencia": {"x": 440, "y": 20},          # pantalla / mesa del profesor
      "mesas": [
        {"id": "m1", "x": 80, "y": 160, "plazas": 2, "giro": 0,
         "ocupantes": [12, null]},
      ]
    }

Una mesa de 1 a 3 plazas va en una fila; de 4 a 6, en dos. `giro` 90 la pone
de lado. `ocupantes` tiene una casilla por plaza, `null` si está libre.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from clases.models import AULAS
from clases.models import MATERIALES
from clases.models import Asistencia
from clases.models import PaseDeLista
from clases.models import PlanoDeClase
from clases.models import PlanoVersion

ANCHO = 1000
ALTO = 700
PLAZA_ANCHO = 80
PLAZA_ALTO = 60
MAX_PLAZAS = 6
CLAVES_AULA = {clave for clave, _ in AULAS}
CLAVES_MATERIAL = {clave for clave, _ in MATERIALES}


# -----------------------------------------------------------------------------
# Forma
# -----------------------------------------------------------------------------


def filas_y_columnas(plazas, giro=0):
    filas = 1 if plazas <= 3 else 2
    columnas = -(-plazas // filas)
    return (columnas, filas) if giro == 90 else (filas, columnas)


def disposicion_vacia():
    return {"referencia": {"x": ANCHO // 2 - 60, "y": 20}, "mesas": []}


def alumnado(group):
    """Matrícula activa del grupo, por nombre. Es el universo de quién cabe en el plano."""
    User = get_user_model()
    return list(
        User.objects.filter(enrollments__group=group, enrollments__is_active=True)
        .order_by("name", "email")
        .distinct()
    )


def alumnado_json(group):
    return [{"id": u.pk, "nombre": u.name or u.email} for u in alumnado(group)]


def _entero(valor, nombre):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValidationError(f"{nombre} tiene que ser un número")
    return int(round(valor))


def validar(disposicion, group):
    """La disposición limpia, o `ValidationError` con todos los fallos.

    O entra entera o no entra: un plano a medias en clase es peor que el de ayer.
    """
    if not isinstance(disposicion, dict):
        raise ValidationError("La disposición tiene que ser un objeto")
    errores = []
    permitidos = {u.pk for u in alumnado(group)}

    ref = disposicion.get("referencia") or {}
    if not isinstance(ref, dict):
        raise ValidationError("`referencia` tiene que ser un objeto con x e y")
    try:
        referencia = {
            "x": _entero(ref.get("x", ANCHO // 2 - 60), "referencia.x"),
            "y": _entero(ref.get("y", 20), "referencia.y"),
        }
        if not (0 <= referencia["x"] <= ANCHO and 0 <= referencia["y"] <= ALTO):
            errores.append("La referencia está fuera del aula")
    except ValidationError as e:
        errores.extend(e.messages)
        referencia = disposicion_vacia()["referencia"]

    mesas_entrada = disposicion.get("mesas", [])
    if not isinstance(mesas_entrada, list):
        raise ValidationError("`mesas` tiene que ser una lista")

    mesas, vistos, ids = [], set(), set()
    for n, mesa in enumerate(mesas_entrada, start=1):
        etiqueta = f"Mesa {n}"
        if not isinstance(mesa, dict):
            errores.append(f"{etiqueta}: no es un objeto")
            continue
        try:
            plazas = _entero(mesa.get("plazas", 1), f"{etiqueta}.plazas")
            x = _entero(mesa.get("x", 0), f"{etiqueta}.x")
            y = _entero(mesa.get("y", 0), f"{etiqueta}.y")
            giro = _entero(mesa.get("giro", 0), f"{etiqueta}.giro")
        except ValidationError as e:
            errores.extend(e.messages)
            continue
        if not 1 <= plazas <= MAX_PLAZAS:
            errores.append(f"{etiqueta}: de 1 a {MAX_PLAZAS} plazas, no {plazas}")
            continue
        if giro not in (0, 90):
            errores.append(f"{etiqueta}: el giro es 0 o 90")
            continue
        if not (0 <= x <= ANCHO and 0 <= y <= ALTO):
            errores.append(f"{etiqueta}: fuera del aula")
        mid = str(mesa.get("id") or f"m{n}")
        if mid in ids:
            mid = f"{mid}-{n}"
        ids.add(mid)

        ocupantes = mesa.get("ocupantes") or []
        if not isinstance(ocupantes, list):
            errores.append(f"{etiqueta}: `ocupantes` tiene que ser una lista")
            continue
        ocupantes = list(ocupantes)
        if len(ocupantes) > plazas:
            errores.append(f"{etiqueta}: {len(ocupantes)} ocupantes para {plazas} plazas")
            ocupantes = ocupantes[:plazas]
        ocupantes += [None] * (plazas - len(ocupantes))
        limpios = []
        for ocupante in ocupantes:
            if ocupante is None:
                limpios.append(None)
                continue
            if isinstance(ocupante, bool) or not isinstance(ocupante, int):
                errores.append(f"{etiqueta}: «{ocupante}» no es un id de alumno")
                limpios.append(None)
                continue
            if ocupante not in permitidos:
                errores.append(f"{etiqueta}: el alumno {ocupante} no tiene matrícula activa en {group.name}")
            elif ocupante in vistos:
                errores.append(f"{etiqueta}: el alumno {ocupante} ya tiene otro sitio")
            vistos.add(ocupante)
            limpios.append(ocupante)
        mesas.append({"id": mid, "x": x, "y": y, "plazas": plazas, "giro": giro, "ocupantes": limpios})

    if errores:
        raise ValidationError(errores)
    return {"referencia": referencia, "mesas": mesas}


def plano_de(group, aula):
    if aula not in CLAVES_AULA:
        raise ValidationError(f"Aula desconocida: {aula}")
    plano, _ = PlanoDeClase.objects.get_or_create(
        group=group, aula=aula, defaults={"disposicion": disposicion_vacia()}
    )
    if not plano.disposicion:
        plano.disposicion = disposicion_vacia()
    plano.disposicion = sin_bajas(plano.disposicion, plano.group)
    return plano


def sin_bajas(disposicion, group):
    """La disposición sin quien ya no tiene matrícula activa: su plaza queda libre.

    Sin esto, una baja deja un ocupante invisible en el editor y el siguiente
    guardado se rechaza entero sin que el profesor vea por qué.
    """
    permitidos = {u.pk for u in alumnado(group)}
    return {
        **disposicion,
        "mesas": [
            {**m, "ocupantes": [o if o in permitidos else None for o in (m.get("ocupantes") or [])]}
            for m in disposicion.get("mesas", [])
            if isinstance(m, dict)
        ],
    }


def sin_sitio(plano):
    """Quién del grupo no tiene plaza en este plano: la bandeja del editor."""
    sentados = {o for m in plano.disposicion.get("mesas", []) for o in m.get("ocupantes", []) if o}
    return [u for u in alumnado(plano.group) if u.pk not in sentados]


# -----------------------------------------------------------------------------
# Guardar y deshacer
# -----------------------------------------------------------------------------


@transaction.atomic
def guardar(plano, disposicion, autor=None, origen=PlanoVersion.PANTALLA, motivo=""):
    limpia = validar(disposicion, plano.group)
    plano.disposicion = limpia
    plano.save(update_fields=["disposicion", "updated_at"])
    version = PlanoVersion.objects.create(
        plano=plano, disposicion=limpia, autor=autor, origen=origen, motivo=motivo.strip()
    )
    return version


def restaurar(version, autor=None):
    """Vuelve a una versión anterior. Es un guardado más: se puede deshacer."""
    fecha = timezone.localtime(version.created_at).strftime("%d/%m %H:%M")
    # Se valida otra vez: entre medias alguien ha podido darse de baja, y la
    # versión vieja lo sentaría. Se le quita la plaza en vez de fallar.
    disposicion = sin_bajas(version.disposicion, version.plano.group)
    return guardar(
        version.plano, disposicion, autor=autor, origen=PlanoVersion.RESTAURAR,
        motivo=f"Vuelta a la versión del {fecha}",
    )


def versiones_json(plano, cuantas=20):
    return [
        {
            "id": v.pk,
            "fecha": timezone.localtime(v.created_at).isoformat(),
            "origen": v.origen,
            "motivo": v.motivo,
            "autor": (v.autor.name or v.autor.email) if v.autor else "",
        }
        for v in plano.versiones.select_related("autor")[:cuantas]
    ]


# -----------------------------------------------------------------------------
# Pasar lista
# -----------------------------------------------------------------------------


def aula_por_defecto(group):
    """La última en la que se pasó lista a este grupo; si nunca, su aula."""
    ultimo = (
        PaseDeLista.objects.filter(session__group=group)
        .order_by("-session__date", "-pk")
        .values_list("aula", flat=True)
        .first()
    )
    return ultimo or "referencia"


def pase_de(session):
    pase = getattr(session, "pase_de_lista", None)
    if pase is None:
        pase, _ = PaseDeLista.objects.get_or_create(
            session=session, defaults={"aula": aula_por_defecto(session.group)}
        )
    return pase


@transaction.atomic
def marcar(session, alumno_id, estado=None, sin_material=None, nota=None, ahora=None):
    """Aplica lo que llegue (lo que no llega no se toca) y devuelve la fila o None.

    Una fila que se queda sin nada marcado se borra: «sin fila» es «presente».
    Todo se valida antes de tocar la base, y la fila se bloquea mientras se
    escribe: dos toques seguidos (material y falta) no se pisan uno al otro.
    """
    if alumno_id not in {u.pk for u in alumnado(session.group)}:
        raise ValidationError("Ese alumno no está matriculado en el grupo")
    estados = {Asistencia.PRESENTE, Asistencia.FALTA, Asistencia.RETRASO}
    if estado is not None and (not isinstance(estado, str) or estado not in estados):
        raise ValidationError(f"Estado desconocido: {estado}")
    if sin_material is not None:
        if not isinstance(sin_material, list) or not all(isinstance(c, str) for c in sin_material):
            raise ValidationError("`sin_material` tiene que ser una lista de textos")
        desconocidos = set(sin_material) - CLAVES_MATERIAL
        if desconocidos:
            raise ValidationError(f"Material desconocido: {', '.join(sorted(desconocidos))}")
    if nota is not None and not isinstance(nota, str):
        raise ValidationError("La nota tiene que ser texto")

    Asistencia.objects.get_or_create(session=session, alumno_id=alumno_id)
    fila = Asistencia.objects.select_for_update().get(session=session, alumno_id=alumno_id)
    if estado is not None:
        if estado == Asistencia.RETRASO and fila.estado != Asistencia.RETRASO:
            fila.hora_llegada = timezone.localtime(ahora or timezone.now()).time().replace(microsecond=0)
        if estado != Asistencia.RETRASO:
            fila.hora_llegada = None
        fila.estado = estado
    if sin_material is not None:
        fila.sin_material = [c for c, _ in MATERIALES if c in sin_material]
    if nota is not None:
        fila.nota = nota.strip()
    if fila.vacia:
        fila.delete()
        return None
    fila.save()
    return fila


def asistencia_json(fila):
    return {
        "estado": fila.estado,
        "hora": fila.hora_llegada.strftime("%H:%M") if fila.hora_llegada else "",
        "sin_material": fila.sin_material,
        "nota": fila.nota,
    }


def resumen_sigad(session):
    """Texto plano para copiar a SIGAD: solo faltas y retrasos, que es lo que va allí."""
    filas = list(
        session.asistencias.select_related("alumno").exclude(estado=Asistencia.PRESENTE)
    )

    def nombre(f):
        return f.alumno.name or f.alumno.email

    faltas = sorted((f for f in filas if f.estado == Asistencia.FALTA), key=nombre)
    retrasos = sorted((f for f in filas if f.estado == Asistencia.RETRASO), key=nombre)
    lineas = [f"{session.group.name} · {session.date.strftime('%d/%m/%Y')}"]
    lineas.append("Faltas: " + (", ".join(nombre(f) for f in faltas) or "ninguna"))
    lineas.append(
        "Retrasos: "
        + (", ".join(f"{nombre(f)} ({f.hora_llegada.strftime('%H:%M')})" if f.hora_llegada else nombre(f) for f in retrasos) or "ninguno")
    )
    return "\n".join(lineas)


def datos_de_lista(session, aula=None):
    """Todo lo que pinta el plano en modo «pasar lista» para una sesión."""
    pase = pase_de(session)
    if aula and aula in CLAVES_AULA and aula != pase.aula:
        pase.aula = aula
        pase.save(update_fields=["aula"])
    plano = plano_de(session.group, pase.aula)
    return {
        "aula": pase.aula,
        "aulas": [{"clave": c, "nombre": n} for c, n in AULAS],
        "pasada": pase.pasada_at is not None,
        "disposicion": plano.disposicion,
        "alumnado": alumnado_json(session.group),
        "sin_sitio": [u.pk for u in sin_sitio(plano)],
        "asistencia": {str(f.alumno_id): asistencia_json(f) for f in session.asistencias.all()},
        "materiales": [{"clave": c, "nombre": n} for c, n in MATERIALES],
        "resumen": resumen_sigad(session),
        "rejilla": rejilla(),
    }


def rejilla():
    return {"ancho": ANCHO, "alto": ALTO, "plaza_ancho": PLAZA_ANCHO, "plaza_alto": PLAZA_ALTO}


def dar_por_pasada(session):
    pase = pase_de(session)
    if pase.pasada_at is None:
        pase.pasada_at = timezone.now()
        pase.save(update_fields=["pasada_at"])
    return pase


def faltan_en(session):
    """Ids con falta en la sesión: Evaluar al azar no debe elegirlos."""
    return set(session.asistencias.filter(estado=Asistencia.FALTA).values_list("alumno_id", flat=True))

