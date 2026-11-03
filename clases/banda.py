"""La banda del grupo (fase 92): quién toca cada puesto en cada turno del curso.

Es lo único que escribe `BandaDeGrupo.plan`. Lo llaman la rejilla del curso y
el panel de la clase, y todo pasa por `_guardar`, así que todo valida igual y
todo deja versión.

Dos datos que cambian a ritmos distintos, y la app los cruza:

- **El plan**: quién está en cada plaza en cada turno. Se genera una vez, con
  la regla justa, y se corrige a mano en la rejilla.
- **El turno vigente**: no se guarda. Sale de contar las sesiones cerradas
  (en el aula de música, o todas), más el ajuste hecho a mano.

Dos reglas de reparto:

- **Rotación** (1º y 3º): entra en la banda quien menos turnos lleva y, a
  igualdad, quien más tiempo lleva sin entrar; el empate, al azar. Después se
  reparten las plazas entre los que entran con una asignación óptima que
  castiga repetir el instrumento del turno anterior y premia el que no han
  tocado.
- **Intercambio** (4º): nadie sale. Cada turno es el anterior con un cambio
  entre dos, el que más acerca a todos a haberlo tocado todo.

Y tres anillos por alumno (fase 98), encima de las dos reglas:

- **Rota** (por defecto): entra en la bolsa como siempre, con sus vetos (`no`).
- **Fijo** en unos puestos, por orden de preferencia: en cada turno se siembra
  antes del reparto en el primero de su lista que quede libre. Si dos piden el
  mismo, lo toca quien menos veces lo ha tocado; el que se queda sin su puesto
  ese turno rota como los demás.
- **Fuera**: no entra en el reparto (toca xilófono). Se puede poner a mano, y
  como sustituto va después de los rotantes.
"""

import random
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from clases.models import BandaDeGrupo
from clases.models import BandaVersion
from clases.models import CambioDeHoy
from clases.models import ClassSession


@dataclass(frozen=True)
class Puesto:
    clave: str
    nombre: str
    icono: str
    filas: tuple  # filas del bloque de ritmo del ChordPro que le tocan (fase 75)
    portatil: bool  # viaja con su titular a las otras aulas


PUESTOS = {
    p.clave: p
    for p in (
        Puesto("bateria", "Batería", "🥁", ("SH", "CA", "BO"), False),
        Puesto("cajon", "Cajón", "🪘", ("SH", "CA", "BO"), True),
        Puesto("ukebajo", "Ukebajo", "🎸", ("BA",), True),
        Puesto("bajo", "Bajo eléctrico", "🎸", ("BA",), False),
        Puesto("teclado", "Teclado", "🎹", ("MD", "MI"), False),
        Puesto("electrica", "Guitarra eléctrica", "🎸", ("GU",), False),
        Puesto("guitalele", "Guitalele", "🎸", ("GU",), True),
        Puesto("espanola", "Guitarra española", "🎸", ("GU",), True),
        Puesto("voz", "Voz solista", "🎤", (), False),
    )
}

# 1º y 3º: los seis de los artículos de repertorio. 4º: los cinco de su banda,
# más el segundo teclado y la segunda guitarra española que hay para los siete
# de este curso (Jesús, 2026-11-01).
PUESTOS_ROTACION = ["bateria", "ukebajo", "teclado", "electrica", "guitalele", "espanola"]
PUESTOS_4 = ["bateria", "bajo", "teclado", "teclado", "electrica", "espanola", "voz"]

MAX_PLAZAS = 12
MAX_TURNOS = 40
MAX_SESIONES_POR_TURNO = 10

# Costes de la asignación de plazas. Repetir el instrumento del turno anterior
# solo se acepta si no queda otra; un bloqueo, nunca.
_REPITE_SEGUIDO = 1000
_POR_VEZ_EN_EL_INSTRUMENTO = 10
_IMPOSIBLE = 10**6


# -----------------------------------------------------------------------------
# Nombres
# -----------------------------------------------------------------------------


def nombre_corto(nombre):
    """«LEO MIÑANA HERMOSO DE MENDOZA» → «Leo Miñana». Lo mismo que `plano.js`."""
    partes = [p[:1].upper() + p[1:].lower() for p in (nombre or "").split()]
    return " ".join(partes[:2])


def nombre_de(user):
    return nombre_corto(user.name or user.email)


def etiquetas_de_plazas(plazas):
    """«Teclado 1» y «Teclado 2» cuando un instrumento se repite; si no, su nombre."""
    total = {c: plazas.count(c) for c in set(plazas)}
    vistos = {}
    etiquetas = []
    for clave in plazas:
        vistos[clave] = vistos.get(clave, 0) + 1
        nombre = PUESTOS[clave].nombre
        etiquetas.append(f"{nombre} {vistos[clave]}" if total[clave] > 1 else nombre)
    return etiquetas


# -----------------------------------------------------------------------------
# Alumnado y valores por defecto
# -----------------------------------------------------------------------------


def alumnado(group):
    """Matrícula activa del grupo, por nombre. Es la bolsa de la que sale la banda."""
    User = get_user_model()
    return list(
        User.objects.filter(enrollments__group=group, enrollments__is_active=True)
        .order_by("name", "email")
        .distinct()
    )


def por_defecto(group):
    """Modo, plazas y turnos con los que nace la banda de un grupo, según su curso."""
    if group.curso == 4:
        return {"modo": BandaDeGrupo.INTERCAMBIO, "puestos": list(PUESTOS_4), "turnos": 15}
    return {"modo": BandaDeGrupo.ROTACION, "puestos": list(PUESTOS_ROTACION), "turnos": 16}


def plan_vacio(puestos, turnos):
    return {"turnos": [_turno_vacio(puestos) for _ in range(turnos)]}


def _turno_vacio(puestos):
    return {"plazas": list(puestos), "alumnos": [None] * len(puestos), "fijadas": []}


@transaction.atomic
def crear(group, autor=None, hoy=None):
    valores = por_defecto(group)
    banda = BandaDeGrupo.objects.create(
        group=group,
        modo=valores["modo"],
        puestos=valores["puestos"],
        turnos=valores["turnos"],
        empieza=hoy or timezone.localdate(),
        plan=plan_vacio(valores["puestos"], valores["turnos"]),
    )
    BandaVersion.objects.create(
        banda=banda, plan=banda.plan, autor=autor, origen=BandaVersion.CONFIGURAR,
        motivo="Banda creada",
    )
    return banda


def banda_de(group):
    return BandaDeGrupo.objects.filter(group=group).first()


# -----------------------------------------------------------------------------
# El turno vigente
# -----------------------------------------------------------------------------


def _sesiones_que_cuentan(banda):
    qs = ClassSession.objects.filter(
        group_id=banda.group_id, closed_at__isnull=False, date__gte=banda.empieza
    )
    if banda.cuenta == BandaDeGrupo.CUENTA_MUSICA:
        qs = qs.filter(pase_de_lista__aula="musica")
    return qs


def cuenta_la_sesion(banda, session):
    """Si esta sesión, al cerrarse, hace avanzar el turno."""
    if session.date < banda.empieza:
        return False
    if banda.cuenta == BandaDeGrupo.CUENTA_TODAS:
        return True
    pase = getattr(session, "pase_de_lista", None)
    return pase is not None and pase.aula == "musica"


@dataclass(frozen=True)
class Posicion:
    turno: int  # 1, 2, …
    sesion: int  # en qué sesión del turno: 1 … sesiones_por_turno
    sesiones_por_turno: int

    @property
    def es_relevo(self):
        """La última sesión del turno: el que sale enseña al que entra."""
        return self.sesion == self.sesiones_por_turno

    @property
    def empezado(self):
        return self.sesion > 1


def _posicion(sesiones, banda):
    pos = max(0, sesiones + banda.ajuste)
    spt = banda.sesiones_por_turno
    return Posicion(turno=pos // spt + 1, sesion=pos % spt + 1, sesiones_por_turno=spt)


def posicion(banda, session=None):
    """Dónde estamos: la siguiente sesión que se dé, o la sesión que se pase.

    Para una sesión cuenta lo cerrado ANTES que ella, así que una sesión ya
    cerrada sigue viéndose en su turno.
    """
    qs = _sesiones_que_cuentan(banda)
    if session is not None:
        qs = qs.exclude(pk=session.pk).filter(
            Q(date__lt=session.date) | Q(date=session.date, pk__lt=session.pk)
        )
    return _posicion(qs.count(), banda)


def primer_turno_libre(banda):
    """El primero que aún no ha empezado: desde ahí, generar puede mover a cualquiera."""
    p = posicion(banda)
    return p.turno + 1 if p.empezado else p.turno


# -----------------------------------------------------------------------------
# Validar y guardar
# -----------------------------------------------------------------------------


def _ids_del_grupo(group, solo_activos):
    from clases.models import Enrollment

    qs = Enrollment.objects.filter(group=group)
    if solo_activos:
        qs = qs.filter(is_active=True)
    return set(qs.values_list("user_id", flat=True))


def validar(plan, banda):
    """El plan limpio, o `ValidationError` con todos los fallos.

    En los turnos ya jugados se admite a quien se dio de baja después: es lo
    que pasó. Del vigente en adelante, solo matrícula activa.
    """
    if not isinstance(plan, dict) or not isinstance(plan.get("turnos"), list):
        raise ValidationError("El plan tiene que traer una lista de turnos")
    turnos = plan["turnos"]
    if not 1 <= len(turnos) <= MAX_TURNOS:
        raise ValidationError(f"De 1 a {MAX_TURNOS} turnos, no {len(turnos)}")
    activos = _ids_del_grupo(banda.group, solo_activos=True)
    alguna_vez = _ids_del_grupo(banda.group, solo_activos=False)
    vigente = posicion(banda).turno
    errores = []
    limpios = []
    for n, turno in enumerate(turnos, start=1):
        etiqueta = f"Turno {n}"
        if not isinstance(turno, dict):
            errores.append(f"{etiqueta}: no es un objeto")
            continue
        plazas = turno.get("plazas") or []
        alumnos = list(turno.get("alumnos") or [])
        fijadas = turno.get("fijadas") or []
        if not isinstance(plazas, list) or not 1 <= len(plazas) <= MAX_PLAZAS:
            errores.append(f"{etiqueta}: de 1 a {MAX_PLAZAS} plazas")
            continue
        desconocidas = [p for p in plazas if p not in PUESTOS]
        if desconocidas:
            errores.append(f"{etiqueta}: puesto desconocido {', '.join(map(str, desconocidas))}")
            continue
        if len(alumnos) > len(plazas):
            errores.append(f"{etiqueta}: {len(alumnos)} alumnos para {len(plazas)} plazas")
            alumnos = alumnos[: len(plazas)]
        alumnos += [None] * (len(plazas) - len(alumnos))
        permitidos = alguna_vez if n < vigente else activos
        vistos = set()
        for a in alumnos:
            if a is None:
                continue
            if isinstance(a, bool) or not isinstance(a, int):
                errores.append(f"{etiqueta}: «{a}» no es un id de alumno")
            elif a not in permitidos:
                errores.append(f"{etiqueta}: el alumno {a} no tiene matrícula activa en el grupo")
            elif a in vistos:
                errores.append(f"{etiqueta}: el alumno {a} tiene dos plazas")
            vistos.add(a)
        if not isinstance(fijadas, list) or not all(
            isinstance(i, int) and not isinstance(i, bool) and 0 <= i < len(plazas) for i in fijadas
        ):
            errores.append(f"{etiqueta}: plazas fijadas fuera de rango")
            fijadas = []
        fijadas = sorted({i for i in fijadas if alumnos[i] is not None})
        limpios.append({"plazas": list(plazas), "alumnos": alumnos, "fijadas": fijadas})
    if errores:
        raise ValidationError(errores)
    return {"turnos": limpios}


def _guardar(banda, plan, autor, origen, motivo="", campos=()):
    banda.plan = validar(plan, banda)
    banda.save(update_fields=["plan", "updated_at", *campos])
    return BandaVersion.objects.create(
        banda=banda, plan=banda.plan, autor=autor, origen=origen, motivo=(motivo or "").strip()
    )


def restaurar(version, autor=None):
    """Vuelve a una versión anterior. Es un guardado más: se puede deshacer.

    Lo jugado desde entonces no se toca, y quien se ha dado de baja pierde sus
    plazas futuras en vez de hacer fallar la vuelta.
    """
    banda = version.banda
    vieja = version.plan.get("turnos", [])
    libre = primer_turno_libre(banda)
    actual = banda.plan["turnos"]
    # Nunca más corto que lo jugado: una versión vieja con menos turnos no los borra.
    turnos = []
    for i in range(max(len(vieja), min(libre - 1, len(actual)))):
        turnos.append(actual[i] if i + 1 < libre and i < len(actual) else vieja[i])
    plan = _sin_bajas({"turnos": turnos}, banda, desde=posicion(banda).turno)
    banda.turnos = len(turnos)
    fecha = timezone.localtime(version.created_at).strftime("%d/%m %H:%M")
    return _guardar(
        banda, plan, autor, BandaVersion.RESTAURAR, f"Vuelta a la versión del {fecha}",
        campos=("turnos",),
    )


def _sin_bajas(plan, banda, desde):
    """Quita a quien ya no tiene matrícula activa de los turnos `desde` en adelante."""
    activos = _ids_del_grupo(banda.group, solo_activos=True)
    turnos = []
    for n, turno in enumerate(plan["turnos"], start=1):
        if n < desde:
            turnos.append(turno)
            continue
        alumnos = [a if a in activos else None for a in turno["alumnos"]]
        fijadas = [i for i in turno.get("fijadas", []) if alumnos[i] is not None]
        turnos.append({**turno, "alumnos": alumnos, "fijadas": fijadas})
    return {"turnos": turnos}


def versiones(banda, cuantas=15):
    return list(banda.versiones.select_related("autor")[:cuantas])


# -----------------------------------------------------------------------------
# Lo que lleva cada alumno: la base de las dos reglas
# -----------------------------------------------------------------------------


class Historial:
    """Cuántos turnos en banda, qué instrumentos y cuándo, de los turnos ya decididos."""

    def __init__(self):
        self.total = {}
        self.veces = {}  # alumno → {instrumento: n}
        self.ultimo = {}  # alumno → número del último turno en la banda
        self.instrumento_en = {}  # (alumno, turno) → instrumento

    def anotar(self, n, turno):
        for clave, a in zip(turno["plazas"], turno["alumnos"]):
            if a is None:
                continue
            self.total[a] = self.total.get(a, 0) + 1
            self.veces.setdefault(a, {})
            self.veces[a][clave] = self.veces[a].get(clave, 0) + 1
            self.ultimo[a] = n
            self.instrumento_en[(a, n)] = clave

    @classmethod
    def hasta(cls, plan, turno):
        """El historial de los turnos anteriores a `turno`."""
        h = cls()
        for n, t in enumerate(plan["turnos"][: turno - 1], start=1):
            h.anotar(n, t)
        return h


def _coste(historial, alumno, clave, turno, bloqueos):
    if clave in bloqueos.get(alumno, ()):
        return _IMPOSIBLE
    if historial.instrumento_en.get((alumno, turno - 1)) == clave:
        return _REPITE_SEGUIDO
    return historial.veces.get(alumno, {}).get(clave, 0) * _POR_VEZ_EN_EL_INSTRUMENTO


def _asignar(plazas, candidatos, coste):
    """La asignación de `candidatos` a `plazas` de coste mínimo (exacta, por máscara de bits).

    Hay tantos o más candidatos que plazas, o menos y alguna plaza se queda
    vacía. Devuelve una lista paralela a `plazas` con el candidato o None. A
    igualdad de coste gana el primero en el orden de `candidatos`, que llega
    barajado: así el empate es al azar.
    """
    m = len(candidatos)
    # Plazas sin candidato posible: se dejan vacías antes que asignar un bloqueo.
    # Si sobran plazas, se vacían las últimas: las primeras son las de siempre.
    hueco = _IMPOSIBLE // 10
    costes = [[coste(c, p) for c in candidatos] for p in plazas]
    mejor = {0: (0, ())}
    for i in range(len(plazas)):
        siguiente = {}
        for mascara, (total, eleccion) in mejor.items():
            opciones = [(total + hueco + len(plazas) - i, mascara, eleccion + (None,))]
            for j in range(m):
                if mascara & (1 << j):
                    continue
                opciones.append((total + costes[i][j], mascara | (1 << j), eleccion + (j,)))
            for t, mk, el in opciones:
                if mk not in siguiente or t < siguiente[mk][0]:
                    siguiente[mk] = (t, el)
        mejor = siguiente
    _, eleccion = min(mejor.values(), key=lambda v: v[0])
    return [
        None if j is None or costes[i][j] >= _IMPOSIBLE else candidatos[j]
        for i, j in enumerate(eleccion)
    ]


ANILLOS = ("rota", "fijo", "fuera")


def preferencias(banda):
    """`alumnos` limpio: {id: {"anillo", "puestos", "no"}}, solo entradas con id numérico."""
    limpias = {}
    for k, v in (banda.alumnos or {}).items():
        if not str(k).isdigit() or not isinstance(v, dict):
            continue
        anillo = v.get("anillo") if v.get("anillo") in ANILLOS else "rota"
        puestos = [p for p in (v.get("puestos") or []) if p in PUESTOS] if anillo == "fijo" else []
        no = [p for p in (v.get("no") or []) if p in PUESTOS]
        limpias[int(k)] = {"anillo": anillo, "puestos": puestos, "no": no}
    return limpias


def _bloqueos(banda):
    return {a: set(v["no"]) for a, v in preferencias(banda).items() if v["no"]}


def _fuera(banda):
    return {a for a, v in preferencias(banda).items() if v["anillo"] == "fuera"}


def _sembrar_fijos(turno, fijos, prefs, historial, activos, bloqueos):
    """`fijos` ({plaza: alumno}) ampliado con los fijos de configuración que caben.

    Por rondas de preferencia: primero cada fijo aspira a su primera opción;
    para cada plaza gana quien menos veces la ha tocado, a igualdad quien más
    tiempo lleva sin banda, después el orden de lista. Los que pierden pasan a
    la ronda de su segunda opción, y así. Lo puesto a mano manda.
    """
    fijos = dict(fijos)
    ocupados = set(fijos.values())
    orden = {a: i for i, a in enumerate(activos)}
    huecos = {}
    for i, clave in enumerate(turno["plazas"]):
        if i not in fijos:
            huecos.setdefault(clave, []).append(i)
    pendientes = [a for a in activos if a not in ocupados and prefs.get(a, {}).get("anillo") == "fijo"]
    ronda = 0
    while pendientes:
        aspiran = {}
        for a in pendientes:
            lista = prefs[a]["puestos"]
            if ronda < len(lista):
                aspiran.setdefault(lista[ronda], []).append(a)
        if not aspiran:
            break
        pendientes = []
        for clave, candidatos in aspiran.items():
            candidatos.sort(
                key=lambda a: (historial.veces.get(a, {}).get(clave, 0), historial.ultimo.get(a, 0), orden[a])
            )
            for a in candidatos:
                if huecos.get(clave) and clave not in bloqueos.get(a, ()):
                    fijos[huecos[clave].pop(0)] = a
                else:
                    pendientes.append(a)
        ronda += 1
    return fijos


# -----------------------------------------------------------------------------
# Rotación
# -----------------------------------------------------------------------------


def _turno_rotacion(n, turno, fijos, historial, activos, bloqueos, azar):
    """Rellena las plazas de `turno` que no están en `fijos` ({plaza: alumno})."""
    plazas = turno["plazas"]
    ocupados = set(fijos.values())
    libres = [i for i in range(len(plazas)) if i not in fijos]
    claves_libres = {plazas[i] for i in libres}
    bolsa = [
        a for a in activos
        if a not in ocupados and not claves_libres <= bloqueos.get(a, set())
    ]
    azar.shuffle(bolsa)
    # Orden estable: tras barajar, ordenar deja el empate al azar.
    bolsa.sort(key=lambda a: (historial.total.get(a, 0), historial.ultimo.get(a, 0)))
    elegidos = bolsa[: len(libres)]
    reparto = _asignar(
        [plazas[i] for i in libres],
        elegidos,
        lambda a, clave: _coste(historial, a, clave, n, bloqueos),
    )
    alumnos = list(turno["alumnos"])
    for i in range(len(plazas)):
        alumnos[i] = fijos.get(i)
    for i, a in zip(libres, reparto):
        alumnos[i] = a
    return alumnos


# -----------------------------------------------------------------------------
# Intercambio
# -----------------------------------------------------------------------------


def _por_tocar(historial, alumno, claves):
    return len(claves - set(historial.veces.get(alumno, {})))


def mejor_intercambio(plazas, alumnos, historial, intocables=(), azar=random, bloqueos=None):
    """El cambio entre dos (o el paso a una plaza vacía) que más reduce lo que les falta.

    Devuelve `(i, j, ganancia)` o None si no hay ninguno posible. Nunca entre
    dos plazas del mismo instrumento: no cambia nada. A igualdad de ganancia,
    los que más turnos llevan en su plaza; después, el azar.
    """
    bloqueos = bloqueos or {}
    claves = set(plazas)
    pares = []
    for i in range(len(plazas)):
        for j in range(i + 1, len(plazas)):
            if i in intocables or j in intocables or plazas[i] == plazas[j]:
                continue
            a, b = alumnos[i], alumnos[j]
            if a is None and b is None:
                continue
            if (a is not None and plazas[j] in bloqueos.get(a, ())) or (
                b is not None and plazas[i] in bloqueos.get(b, ())
            ):
                continue
            ganancia = 0
            for alumno, nueva in ((a, plazas[j]), (b, plazas[i])):
                if alumno is not None and nueva not in historial.veces.get(alumno, {}):
                    ganancia += 1
            pares.append((i, j, ganancia))
    if not pares:
        return None
    azar.shuffle(pares)

    def quieto(p):
        i, j, _ = p
        return sum(_turnos_quieto(historial, alumnos[k], plazas[k]) for k in (i, j) if alumnos[k] is not None)

    return max(pares, key=lambda p: (p[2], quieto(p)))


def _turnos_quieto(historial, alumno, clave):
    """Cuántos turnos seguidos lleva el alumno en ese instrumento, hasta el último anotado."""
    n = 0
    t = max((tt for (a, tt) in historial.instrumento_en if a == alumno), default=0)
    while t > 0 and historial.instrumento_en.get((alumno, t)) == clave:
        n += 1
        t -= 1
    return n


def _turno_intercambio(n, turno, fijos, anterior, historial, activos, bloqueos, azar):
    plazas = turno["plazas"]
    if n == 1 or anterior is None or anterior["plazas"] != plazas:
        # Sin turno anterior con las mismas plazas: un reparto de partida.
        return _turno_rotacion(n, turno, fijos, historial, activos, bloqueos, azar)
    alumnos = [a if a in activos else None for a in anterior["alumnos"]]
    # Lo fijado manda: si el fijado estaba en otra plaza, se cambian.
    for i, a in fijos.items():
        if a in alumnos and alumnos.index(a) != i:
            k = alumnos.index(a)
            alumnos[k], alumnos[i] = alumnos[i], alumnos[k]
        else:
            alumnos[i] = a
    # Las altas, a las plazas vacías.
    sueltos = [a for a in activos if a not in alumnos]
    azar.shuffle(sueltos)
    for i in range(len(plazas)):
        if alumnos[i] is None and sueltos:
            alumnos[i] = sueltos.pop()
    cambio = mejor_intercambio(plazas, alumnos, historial, intocables=set(fijos), azar=azar, bloqueos=bloqueos)
    if cambio is not None:
        i, j, _ = cambio
        alumnos[i], alumnos[j] = alumnos[j], alumnos[i]
    return alumnos


# -----------------------------------------------------------------------------
# Generar el curso
# -----------------------------------------------------------------------------


def planificar(banda, desde, azar=random):
    """El plan con los turnos `desde` en adelante generados de nuevo. No guarda.

    Respeta las plazas fijadas. Del turno en curso, si `desde` lo deja atrás, no
    se toca nada: eso lo hace `generar`, que sí rellena sus huecos.
    """
    prefs = preferencias(banda)
    fuera = _fuera(banda)
    activos = [u.pk for u in alumnado(banda.group) if u.pk not in fuera]
    activos_set = set(activos)
    bloqueos = _bloqueos(banda)
    plan = _sin_bajas(banda.plan, banda, desde=min(desde, posicion(banda).turno))
    turnos = [dict(t) for t in plan["turnos"]]
    historial = Historial.hasta({"turnos": turnos}, desde)
    matricula = _ids_del_grupo(banda.group, solo_activos=True)
    for n in range(desde, len(turnos) + 1):
        turno = turnos[n - 1]
        # Lo fijado a mano (📌) manda, aunque sea alguien de fuera; después, los fijos de configuración.
        fijos = {i: turno["alumnos"][i] for i in turno.get("fijadas", []) if turno["alumnos"][i] in matricula}
        fijos = _sin_repetidos(fijos)
        fijadas = sorted(fijos)
        fijos = _sembrar_fijos(turno, fijos, prefs, historial, activos, bloqueos)
        if banda.modo == BandaDeGrupo.INTERCAMBIO:
            anterior = turnos[n - 2] if n > 1 else None
            alumnos = _turno_intercambio(n, turno, fijos, anterior, historial, activos, bloqueos, azar)
        else:
            alumnos = _turno_rotacion(n, turno, fijos, historial, activos, bloqueos, azar)
        turnos[n - 1] = {**turno, "alumnos": alumnos, "fijadas": fijadas}
        historial.anotar(n, turnos[n - 1])
    return {"turnos": turnos}


def _sin_repetidos(fijos):
    vistos, limpios = set(), {}
    for i in sorted(fijos):
        if fijos[i] not in vistos:
            limpios[i] = fijos[i]
            vistos.add(fijos[i])
    return limpios


def _rellenar_huecos(banda, n, plan, azar):
    """Las plazas vacías del turno en curso, sin mover a nadie de las ocupadas."""
    turnos = [dict(t) for t in plan["turnos"]]
    if not 1 <= n <= len(turnos):
        return plan
    turno = turnos[n - 1]
    if None not in turno["alumnos"]:
        return plan
    fuera = _fuera(banda)
    activos = [u.pk for u in alumnado(banda.group) if u.pk not in fuera]
    fijos = {i: a for i, a in enumerate(turno["alumnos"]) if a is not None}
    historial = Historial.hasta({"turnos": turnos}, n)
    bloqueos = _bloqueos(banda)
    fijos = _sembrar_fijos(turno, fijos, preferencias(banda), historial, activos, bloqueos)
    alumnos = _turno_rotacion(n, turno, fijos, historial, activos, bloqueos, azar)
    turnos[n - 1] = {**turno, "alumnos": alumnos}
    return {"turnos": turnos}


@transaction.atomic
def generar(banda, autor=None, azar=random, motivo=""):
    """Genera desde el primer turno libre y rellena los huecos del turno en curso."""
    banda = BandaDeGrupo.objects.select_for_update().get(pk=banda.pk)
    libre = primer_turno_libre(banda)
    plan = planificar(banda, libre, azar=azar) if libre <= len(banda.plan["turnos"]) else banda.plan
    vigente = posicion(banda).turno
    if vigente < libre:
        plan = _rellenar_huecos(banda, vigente, _sin_bajas(plan, banda, desde=vigente), azar)
    texto = f"Generado desde el turno {libre}" + (f". {motivo.strip()}" if motivo.strip() else "")
    _guardar(banda, plan, autor, BandaVersion.GENERAR, texto)
    return banda


# -----------------------------------------------------------------------------
# Cambiar a mano
# -----------------------------------------------------------------------------


def _turno_editable(banda, turno):
    if not 1 <= turno <= len(banda.plan["turnos"]):
        raise ValidationError(f"No hay turno {turno}")
    if turno < posicion(banda).turno:
        raise ValidationError(f"El turno {turno} ya se ha jugado: no se cambia")


@transaction.atomic
def poner(banda, turno, plaza, alumno_id, autor=None, motivo=""):
    """Pone a un alumno en una plaza y la deja fijada.

    Si ese alumno ya estaba en otra plaza del mismo turno, se cambian; la otra
    queda fijada también, porque también la has decidido tú. `alumno_id` None
    vacía la plaza.
    """
    banda = BandaDeGrupo.objects.select_for_update().get(pk=banda.pk)
    _turno_editable(banda, turno)
    t = banda.plan["turnos"][turno - 1]
    if not 0 <= plaza < len(t["plazas"]):
        raise ValidationError("Esa plaza no existe en el turno")
    if alumno_id is not None and alumno_id not in _ids_del_grupo(banda.group, solo_activos=True):
        raise ValidationError("Ese alumno no está matriculado en el grupo")
    alumnos = list(t["alumnos"])
    fijadas = set(t.get("fijadas", []))
    antes = alumnos[plaza]
    if alumno_id is not None and alumno_id in alumnos and alumnos.index(alumno_id) != plaza:
        otra = alumnos.index(alumno_id)
        alumnos[otra] = antes
        if antes is not None:
            fijadas.add(otra)
        else:
            fijadas.discard(otra)
    alumnos[plaza] = alumno_id
    if alumno_id is None:
        fijadas.discard(plaza)
    else:
        fijadas.add(plaza)
    turnos = list(banda.plan["turnos"])
    turnos[turno - 1] = {**t, "alumnos": alumnos, "fijadas": sorted(fijadas)}
    texto = motivo.strip() or f"Turno {turno}, {etiquetas_de_plazas(t['plazas'])[plaza]}"
    _guardar(banda, {"turnos": turnos}, autor, BandaVersion.CASILLA, texto)
    return banda


@transaction.atomic
def soltar(banda, turno, plaza, autor=None):
    """Quita el 📌: el próximo «Generar» ya puede mover esa plaza."""
    banda = BandaDeGrupo.objects.select_for_update().get(pk=banda.pk)
    _turno_editable(banda, turno)
    t = banda.plan["turnos"][turno - 1]
    turnos = list(banda.plan["turnos"])
    turnos[turno - 1] = {**t, "fijadas": [i for i in t.get("fijadas", []) if i != plaza]}
    _guardar(banda, {"turnos": turnos}, autor, BandaVersion.CASILLA, f"Turno {turno}: plaza suelta")
    return banda


@transaction.atomic
def ajustar(banda, hacia, autor=None):
    """Adelanta (+1) o atrasa (-1) el turno vigente, al principio de un turno.

    Es para el día que no se pasó lista o se dio la clase fuera del aula: el
    recuento no lo ha visto, pero el turno tiene que cambiar.
    """
    banda = BandaDeGrupo.objects.select_for_update().get(pk=banda.pk)
    sesiones = _sesiones_que_cuentan(banda).count()
    pos = max(0, sesiones + banda.ajuste)
    spt = banda.sesiones_por_turno
    dentro = pos % spt
    if hacia > 0:
        pos += spt - dentro
    elif dentro:
        pos -= dentro
    else:
        pos = max(0, pos - spt)
    banda.ajuste = pos - sesiones
    banda.save(update_fields=["ajuste", "updated_at"])
    return banda


# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------


def _entero(valor, nombre, minimo, maximo):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise ValidationError(f"{nombre} tiene que ser un número") from None
    if not minimo <= n <= maximo:
        raise ValidationError(f"{nombre}: de {minimo} a {maximo}")
    return n


@transaction.atomic
def configurar(banda, *, modo, puestos, sesiones_por_turno, turnos, empieza, cuenta, autor=None):
    """Guarda la configuración. Lo jugado no cambia, ni el turno en curso.

    Si cambian las plazas, el modo o el número de turnos, los turnos que aún no
    han empezado se rehacen con la configuración nueva, conservando lo fijado
    que siga cabiendo, y se generan otra vez si el plan ya tenía alguien.
    """
    banda = BandaDeGrupo.objects.select_for_update().get(pk=banda.pk)
    if modo not in dict(BandaDeGrupo.MODOS):
        raise ValidationError("Modo desconocido")
    if cuenta not in dict(BandaDeGrupo.CUENTAS):
        raise ValidationError("Qué sesiones cuentan: valor desconocido")
    if not isinstance(puestos, list) or not 1 <= len(puestos) <= MAX_PLAZAS:
        raise ValidationError(f"La banda lleva de 1 a {MAX_PLAZAS} plazas")
    if any(p not in PUESTOS for p in puestos):
        raise ValidationError("Puesto desconocido")
    spt = _entero(sesiones_por_turno, "Sesiones por turno", 1, MAX_SESIONES_POR_TURNO)
    n_turnos = _entero(turnos, "Turnos", 1, MAX_TURNOS)

    libre = primer_turno_libre(banda)
    if n_turnos < libre - 1:
        raise ValidationError(f"Ya se han jugado {libre - 1} turnos: el curso no puede tener menos")

    estructura = (modo, list(puestos), n_turnos) != (banda.modo, list(banda.puestos), banda.turnos)
    banda.modo = modo
    banda.puestos = list(puestos)
    banda.turnos = n_turnos
    # Cambiar qué sesiones cuentan o desde cuándo SÍ puede mover el turno: es
    # para eso. Cambiar las sesiones por turno no: el ajuste absorbe el cambio.
    banda.cuenta = cuenta
    banda.empieza = empieza
    if spt != banda.sesiones_por_turno:
        antes = posicion(banda)
        sesiones = _sesiones_que_cuentan(banda).count()
        banda.sesiones_por_turno = spt
        banda.ajuste = (antes.turno - 1) * spt + min(antes.sesion - 1, spt - 1) - sesiones
    campos = ["modo", "puestos", "cuenta", "empieza", "turnos", "sesiones_por_turno", "ajuste"]

    if not estructura:
        banda.save(update_fields=[*campos, "updated_at"])
        return banda

    actuales = banda.plan["turnos"]
    turnos_nuevos = []
    for n in range(1, n_turnos + 1):
        if n < libre and n <= len(actuales):
            turnos_nuevos.append(actuales[n - 1])
            continue
        nuevo = _turno_vacio(puestos)
        if n <= len(actuales):
            viejo = actuales[n - 1]
            for i in viejo.get("fijadas", []):
                if i < len(puestos) and viejo["plazas"][i] == puestos[i]:
                    nuevo["alumnos"][i] = viejo["alumnos"][i]
                    nuevo["fijadas"].append(i)
        turnos_nuevos.append(nuevo)
    había_alguien = any(a is not None for t in actuales for a in t["alumnos"])
    banda.plan = {"turnos": turnos_nuevos}
    banda.save(update_fields=[*campos, "updated_at"])
    plan = planificar(banda, libre) if había_alguien and libre <= n_turnos else banda.plan
    _guardar(banda, plan, autor, BandaVersion.CONFIGURAR, "Configuración cambiada")
    return banda


def validar_alumnos(alumnos, banda):
    """`alumnos` limpio ({id: {anillo, puestos, no}}) o `ValidationError`. Las entradas «rota sin vetos» no se guardan."""
    if not isinstance(alumnos, dict):
        raise ValidationError("Las preferencias tienen que ser un objeto por alumno")
    matricula = _ids_del_grupo(banda.group, solo_activos=False)
    errores, limpias = [], {}
    for k, v in alumnos.items():
        if not str(k).isdigit() or int(k) not in matricula:
            errores.append(f"El alumno {k} no está matriculado en el grupo")
            continue
        if not isinstance(v, dict) or v.get("anillo", "rota") not in ANILLOS:
            errores.append(f"Alumno {k}: anillo desconocido")
            continue
        anillo = v.get("anillo", "rota")
        puestos = list(dict.fromkeys(v.get("puestos") or []))
        no = list(dict.fromkeys(v.get("no") or []))
        raros = [p for p in puestos + no if p not in PUESTOS]
        if raros:
            errores.append(f"Alumno {k}: puesto desconocido {', '.join(map(str, raros))}")
            continue
        if anillo == "fijo" and not puestos:
            errores.append(f"Alumno {k}: fijo, pero sin ningún puesto")
            continue
        entrada = {"anillo": anillo, "puestos": puestos if anillo == "fijo" else [], "no": no if anillo == "rota" else []}
        if entrada != {"anillo": "rota", "puestos": [], "no": []}:
            limpias[str(k)] = entrada
    if errores:
        raise ValidationError(errores)
    return limpias


@transaction.atomic
def configurar_alumnos(banda, alumnos, autor=None):
    """Guarda los anillos y regenera los turnos que no han empezado, si el plan ya tenía a alguien."""
    banda = BandaDeGrupo.objects.select_for_update().get(pk=banda.pk)
    banda.alumnos = validar_alumnos(alumnos, banda)
    banda.save(update_fields=["alumnos", "updated_at"])
    libre = primer_turno_libre(banda)
    había_alguien = any(a is not None for t in banda.plan["turnos"] for a in t["alumnos"])
    plan = planificar(banda, libre) if había_alguien and libre <= len(banda.plan["turnos"]) else banda.plan
    _guardar(banda, plan, autor, BandaVersion.CONFIGURAR, "Preferencias cambiadas")
    return banda


def fijos_sin_plaza(banda):
    """Fijos cuyo primer puesto no tiene plaza en los turnos que vienen: avisar, no fallar."""
    claves = set(banda.puestos)
    return [a for a, v in preferencias(banda).items() if v["anillo"] == "fijo" and not claves & set(v["puestos"])]


# -----------------------------------------------------------------------------
# La rejilla y la hoja de la pared
# -----------------------------------------------------------------------------


def rejilla(banda):
    """Lo que pinta la pantalla de preparar y la hoja: filas por plaza y columnas por turno."""
    User = get_user_model()
    turnos = banda.plan["turnos"]
    ids = {a for t in turnos for a in t["alumnos"] if a is not None}
    usuarios = {u.pk: u for u in User.objects.filter(pk__in=ids)}
    activos = alumnado(banda.group)
    for u in activos:
        usuarios.setdefault(u.pk, u)
    p = posicion(banda)
    prefs = preferencias(banda)
    columnas = []
    for n, t in enumerate(turnos, start=1):
        etiquetas = etiquetas_de_plazas(t["plazas"])
        casillas = []
        for i, (clave, a) in enumerate(zip(t["plazas"], t["alumnos"])):
            casillas.append({
                "plaza": i,
                "clave": clave,
                "etiqueta": etiquetas[i],
                "icono": PUESTOS[clave].icono,
                "alumno": a,
                "nombre": nombre_de(usuarios[a]) if a in usuarios else "",
                "fijada": i in t.get("fijadas", []),
                # 🔒: está en su puesto por la configuración, no por un 📌.
                "fijo": a is not None and i not in t.get("fijadas", []) and clave in prefs.get(a, {}).get("puestos", []),
            })
        columnas.append({
            "turno": n,
            "jugado": n < p.turno,
            "vigente": n == p.turno,
            "casillas": casillas,
        })
    resumen = {}
    for col in columnas:
        for c in col["casillas"]:
            if c["alumno"] is not None:
                resumen.setdefault(c["alumno"], []).append((col["turno"], c["etiqueta"]))
    alumnos = [
        {
            "id": u.pk,
            "nombre": nombre_de(u),
            "completo": u.name or u.email,
            "turnos": resumen.get(u.pk, []),
            **prefs.get(u.pk, {"anillo": "rota", "puestos": [], "no": []}),
        }
        for u in activos
    ]
    fijos_por_puesto = []
    for clave, etiqueta in zip(dict.fromkeys(banda.puestos), etiquetas_de_plazas(list(dict.fromkeys(banda.puestos)))):
        nombres = [a["nombre"] for a in alumnos if a["anillo"] == "fijo" and clave in a["puestos"]]
        if nombres:
            fijos_por_puesto.append({"clave": clave, "icono": PUESTOS[clave].icono, "nombre": PUESTOS[clave].nombre, "nombres": nombres})
    # Las filas de la pantalla: las plazas de los turnos que vienen.
    filas = [
        {"etiqueta": e, "icono": PUESTOS[c].icono, "portatil": PUESTOS[c].portatil}
        for c, e in zip(banda.puestos, etiquetas_de_plazas(banda.puestos))
    ]
    sin_plaza = [] if banda.modo == BandaDeGrupo.ROTACION else [
        a for a in alumnos if a["anillo"] != "fuera" and not any(t == p.turno for t, _ in a["turnos"])
    ]
    sin_plaza_de_su_puesto = fijos_sin_plaza(banda)
    return {
        "posicion": p,
        "libre": primer_turno_libre(banda),
        "columnas": columnas,
        "filas": filas,
        "alumnos": alumnos,
        "fijos_por_puesto": fijos_por_puesto,
        "de_fuera": [a for a in alumnos if a["anillo"] == "fuera"],
        "fijos_sin_plaza": [a for a in alumnos if a["id"] in sin_plaza_de_su_puesto],
        "sin_plaza_en_intercambio": sin_plaza,
        "max_filas": max((len(c["casillas"]) for c in columnas), default=0),
    }


# -----------------------------------------------------------------------------
# La banda de hoy (fase B)
# -----------------------------------------------------------------------------


def _quien_tuvo(turno, clave, plaza):
    """En otro turno, quién tuvo ese instrumento: en la misma plaza si se puede."""
    if turno is None:
        return None
    plazas, alumnos = turno["plazas"], turno["alumnos"]
    if plaza < len(plazas) and plazas[plaza] == clave and alumnos[plaza] is not None:
        return alumnos[plaza]
    for c, a in zip(plazas, alumnos):
        if c == clave and a is not None:
            return a
    return None


def banda_de_hoy(session):
    """Todo lo que pinta el panel de la clase (tecla B) para una sesión."""
    from clases.plano import faltan_en

    banda = banda_de(session.group)
    if banda is None:
        return {"hay_banda": False}
    p = posicion(banda, session)
    turnos = banda.plan["turnos"]
    base = {
        "hay_banda": True,
        "modo": banda.modo,
        "turno": p.turno,
        "sesion": p.sesion,
        "sesiones_por_turno": p.sesiones_por_turno,
        "relevo": p.es_relevo,
        "cuenta": cuenta_la_sesion(banda, session),
        "total_turnos": len(turnos),
    }
    if p.turno > len(turnos):
        return {**base, "fuera_del_plan": True, "filas": [], "libres": []}
    turno = turnos[p.turno - 1]
    anterior = turnos[p.turno - 2] if p.turno > 1 else None
    siguiente = turnos[p.turno] if p.turno < len(turnos) else None
    faltan = faltan_en(session)
    cambios = {c.plaza: c.alumno_id for c in session.cambios_de_banda.all()}

    User = get_user_model()
    activos = alumnado(session.group)
    ids = {a for t in (turno, anterior, siguiente) if t for a in t["alumnos"] if a is not None}
    ids |= set(cambios.values())
    usuarios = {u.pk: u for u in User.objects.filter(pk__in=ids)}
    for u in activos:
        usuarios.setdefault(u.pk, u)
    historial = Historial.hasta(banda.plan, p.turno)
    fuera = _fuera(banda)

    def nombre(a):
        return nombre_de(usuarios[a]) if a in usuarios else ""

    # Quién toca hoy: los titulares presentes cuya plaza no ha cambiado, y los cambios.
    tocan = {
        a for i, a in enumerate(turno["alumnos"])
        if a is not None and a not in faltan and i not in cambios
    } | set(cambios.values())
    propuestos = set()
    filas = []
    etiquetas = etiquetas_de_plazas(turno["plazas"])
    for i, (clave, titular) in enumerate(zip(turno["plazas"], turno["alumnos"])):
        # En intercambio casi todos siguen en su plaza: el que «ayuda» o «entra»
        # solo se dice si es otro.
        ayuda = _quien_tuvo(anterior, clave, i)
        ayuda = None if ayuda == titular else ayuda
        entra = _quien_tuvo(siguiente, clave, i)
        entra = None if entra == titular else entra
        falta = titular is not None and titular in faltan
        fila = {
            "plaza": i,
            "etiqueta": etiquetas[i],
            "icono": PUESTOS[clave].icono,
            "titular": titular,
            "titular_nombre": nombre(titular) if titular else "",
            "falta": falta,
            "cambio": cambios.get(i),
            "cambio_nombre": nombre(cambios[i]) if i in cambios else "",
            "propuesto": None,
            "propuesto_nombre": "",
            "lo_cubre_el_profesor": False,
            "ayuda": ayuda,
            "ayuda_nombre": nombre(ayuda) if ayuda else "",
            "ayuda_falta": ayuda in faltan if ayuda else False,
            "entra": entra,
            "entra_nombre": nombre(entra) if entra else "",
        }
        if (falta or titular is None) and i not in cambios:
            if banda.modo == BandaDeGrupo.INTERCAMBIO:
                fila["lo_cubre_el_profesor"] = True
            else:
                propuesto = proponer_sustituto(
                    clave, ayuda, activos, faltan, tocan | propuestos, historial, fuera
                )
                if propuesto is not None:
                    propuestos.add(propuesto)
                    fila["propuesto"] = propuesto
                    fila["propuesto_nombre"] = nombre(propuesto)
        filas.append(fila)
    # Los rotantes primero; los de fuera, al final y marcados.
    libres = sorted(
        (
            {"id": u.pk, "nombre": nombre_de(u), "turnos": historial.total.get(u.pk, 0), "fuera": u.pk in fuera}
            for u in activos
            if u.pk not in faltan and u.pk not in tocan
        ),
        key=lambda a: a["fuera"],
    )
    return {**base, "fuera_del_plan": False, "filas": filas, "libres": libres}


def proponer_sustituto(clave, ayuda, activos, faltan, ocupados, historial, fuera=frozenset()):
    """Quién toca hoy la plaza del que falta.

    Primero, quien tuvo ese instrumento el turno anterior: ya sabe la parte. Si
    no está o ya toca otra cosa, el presente sin plaza que menos banda lleva; a
    igualdad, por orden de lista, para que el panel no cambie al recargarlo.
    Nunca alguien con falta ni alguien que ya toca. Los de fuera (xilófono)
    solo cuando no queda ningún rotante.
    """
    if ayuda is not None and ayuda not in faltan and ayuda not in ocupados:
        return ayuda
    candidatos = [u for u in activos if u.pk not in faltan and u.pk not in ocupados]
    if not candidatos:
        return None
    return min(candidatos, key=lambda u: (u.pk in fuera, historial.total.get(u.pk, 0))).pk


@transaction.atomic
def cambiar_hoy(session, plaza, alumno_id):
    """Quién toca hoy la plaza; `alumno_id` None devuelve la plaza al titular."""
    from clases.plano import faltan_en

    banda = banda_de(session.group)
    if banda is None:
        raise ValidationError("Este grupo no tiene banda")
    p = posicion(banda, session)
    if p.turno > len(banda.plan["turnos"]):
        raise ValidationError("Esta sesión cae fuera de los turnos del curso")
    turno = banda.plan["turnos"][p.turno - 1]
    if not isinstance(plaza, int) or isinstance(plaza, bool) or not 0 <= plaza < len(turno["plazas"]):
        raise ValidationError("Esa plaza no existe hoy")
    if alumno_id is None:
        CambioDeHoy.objects.filter(session=session, plaza=plaza).delete()
        return None
    if alumno_id not in {u.pk for u in alumnado(session.group)}:
        raise ValidationError("Ese alumno no está matriculado en el grupo")
    if alumno_id in faltan_en(session):
        raise ValidationError("Ese alumno tiene falta hoy")
    faltan = faltan_en(session)
    otros_cambios = dict(
        session.cambios_de_banda.exclude(plaza=plaza).values_list("plaza", "alumno_id")
    )
    ocupado = {
        a for i, a in enumerate(turno["alumnos"])
        if a is not None and a not in faltan and i != plaza and i not in otros_cambios
    } | set(otros_cambios.values())
    if alumno_id in ocupado:
        raise ValidationError("Ese alumno ya toca otro puesto hoy")
    cambio, _ = CambioDeHoy.objects.update_or_create(
        session=session, plaza=plaza, defaults={"alumno_id": alumno_id}
    )
    return cambio


def tiene_banda(group):
    return BandaDeGrupo.objects.filter(group=group).exists()
