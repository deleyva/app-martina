"""El dado del cuaderno (fase 78): dos libretas por sesión, al pasar lista.

Mientras se pasa lista, el profesor tira el dado y salen dos alumnos: hoy se
les mira la libreta. Se califican con una letra y un comentario desde la
franja baja de la clase, y la casilla de Cuaderno del registro pasa a ser la
**letra de la media** de todas las veces que se les ha mirado la libreta en
ese instrumento (es decir, en ese trimestre).

**Una revisión es una fila propia** (`RevisionCuaderno`), nunca una columna
del registro: con «celda vacía = 0» (fase 60), una columna por día daría un
cero a los veinte que no salieron, la misma razón por la que evaluar en clase
(fase 62) escribe en la columna del instrumento. La casilla se escribe con
`Nota.poner`, como si se hubiera tecleado en el registro (queda
`CambioNota`), y el detalle (cuántas veces, cuándo, qué letra, qué se dijo)
va en `Nota.rubrica["acumulado"]`, que es lo que el registro enseña al pulsar
la casilla. Es el mismo patrón que la casilla de Teoría de la fase 76·3.

**El dado no es azar puro.** Elige entre los presentes con MENOS revisiones
con letra en el instrumento, y desempata al azar. Con 23 alumnos, 2 por
sesión y unas 24 sesiones por trimestre, un dado puro deja sin revisar a un
13 % del grupo (e⁻²) y mira cuatro veces a otros; así todo el mundo tiene una
antes de que nadie tenga dos.

Quedan fuera del sorteo: quien tiene falta en la sesión, quien tiene marcado
«sin libreta» (la libreta que no viene se castiga por la marca de material,
no por el cuaderno; decisión pendiente de Jesús, propuesta aplicada), quien
ya ha salido hoy, y quien el profesor salta con «otro».
"""

from __future__ import annotations

import random
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count

from . import calculo
from .evaluar import instrumento_del_grupo, instrumentos_del_grupo, valor_de_letra
from .models import LETRAS, Instrumento, Nota, RevisionCuaderno, alumnos_del_grupo

POR_SESION = 2
# «Dos al día o, mucho, tres» (Jesús, 2026-10-17): con «+ otro» se llega a tres y ahí se para.
MAXIMO_POR_SESION = 3
CENTESIMA = Decimal("0.01")


def _clave(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn").strip().lower()


def es_cuaderno(instrumento: Instrumento) -> bool:
    """Si el instrumento se llama «Cuaderno», sin mirar mayúsculas ni acentos."""
    return _clave(instrumento.nombre) == "cuaderno"


def instrumento_por_defecto(group, fecha) -> Instrumento | None:
    """El «Cuaderno» del plan del trimestre de `fecha`. `None` si no hay plan o no lo tiene."""
    for bloque in instrumentos_del_grupo(group, fecha):
        if bloque["actual"]:
            for instrumento in bloque["instrumentos"]:
                if es_cuaderno(instrumento):
                    return instrumento
    return None


def instrumento_de(session) -> Instrumento | None:
    """Con qué instrumento se revisa en esta sesión.

    Si ya hay sorteados, el suyo (la elección queda en las filas de la sesión:
    así un plan que cambie a mitad de clase no mueve lo ya sorteado). Si no,
    el «Cuaderno» del trimestre de la sesión.
    """
    fila = session.revisiones_cuaderno.select_related("instrumento__plan").order_by("pk").first()
    if fila is not None:
        return fila.instrumento
    return instrumento_por_defecto(session.group, session.date)


def opciones_de(session) -> list[Instrumento]:
    """Los instrumentos entre los que elegir cuando el trimestre no tiene «Cuaderno»."""
    return [i for bloque in instrumentos_del_grupo(session.group, session.date) for i in bloque["instrumentos"]]


# -----------------------------------------------------------------------------
# Sortear
# -----------------------------------------------------------------------------


def contadores(instrumento: Instrumento, ids) -> dict[int, int]:
    """Cuántas revisiones CON LETRA tiene cada alumno en el instrumento."""
    filas = (
        RevisionCuaderno.objects.filter(instrumento=instrumento, alumno_id__in=list(ids))
        .exclude(letra="")
        .values("alumno_id")
        .annotate(n=Count("pk"))
    )
    return {f["alumno_id"]: f["n"] for f in filas}


def fuera_del_sorteo(session, excluir=()) -> set[int]:
    """Quién no puede salir hoy: falta, sin libreta, ya sorteado, o saltado por el profesor."""
    from clases.plano import faltan_en, sin_material_en

    fuera = set(faltan_en(session)) | sin_material_en(session, "libreta")
    fuera |= set(session.revisiones_cuaderno.values_list("alumno_id", flat=True))
    fuera |= {int(e) for e in excluir}
    return fuera


def candidatos(session, excluir=()) -> list:
    fuera = fuera_del_sorteo(session, excluir)
    return [a for a in alumnos_del_grupo(session.group) if a.pk not in fuera]


@transaction.atomic
def sortear(session, instrumento: Instrumento, n: int = POR_SESION, excluir=(), azar=random, autor=None) -> list:
    """Saca hasta `n` alumnos y les crea la fila pendiente. Los que menos veces han salido.

    Devuelve las filas creadas (puede ser menos de `n`, o ninguna, si no queda
    nadie que pueda salir o si hoy ya han salido `MAXIMO_POR_SESION`: los que
    ya tienen fila en la sesión, con letra o sin ella, cuentan para el tope).
    `azar` se inyecta para los tests.
    """
    if not 1 <= int(n) <= 10:
        raise ValueError("Se sortean de 1 a 10 alumnos cada vez")
    n = min(int(n), MAXIMO_POR_SESION - session.revisiones_cuaderno.count())
    if n <= 0:
        return []
    if instrumento_del_grupo(session.group, instrumento.pk) is None:
        raise ValueError("Ese instrumento no es de un plan de este grupo")
    if instrumento.prueba_para_evaluar() is None:
        raise ValueError("Este instrumento no tiene ninguna columna activa en el registro")
    en_sesion = instrumento_de(session)
    if en_sesion is not None and en_sesion.pk != instrumento.pk:
        raise ValueError(f"En esta sesión ya se revisa con «{en_sesion.nombre}»")

    bolsa = candidatos(session, excluir)
    azar.shuffle(bolsa)
    cuentas = contadores(instrumento, [a.pk for a in bolsa])
    # Orden estable: tras barajar, ordenar por cuenta deja el empate al azar.
    bolsa.sort(key=lambda a: cuentas.get(a.pk, 0))
    return [
        RevisionCuaderno.objects.create(session=session, alumno=a, instrumento=instrumento, autor=autor)
        for a in bolsa[: int(n)]
    ]


@transaction.atomic
def descartar(session) -> int:
    """Quita TODOS los pendientes de la sesión: cerrar la franja es «lo dejo».

    Las revisiones con letra se quedan. Devuelve cuántas filas se han quitado.
    El siguiente toque al dado reparte de nuevo, sin los ya calificados hoy.
    """
    borradas, _ = RevisionCuaderno.objects.filter(session=session, letra="").delete()
    return borradas


@transaction.atomic
def saltar(session, alumno_id) -> bool:
    """Quita a un sorteado SIN nota (no está, no la trae). Una revisión con letra no se toca."""
    borradas, _ = RevisionCuaderno.objects.filter(session=session, alumno_id=alumno_id, letra="").delete()
    return borradas > 0


# -----------------------------------------------------------------------------
# Calificar y la casilla
# -----------------------------------------------------------------------------


def revisiones_de(alumno, instrumento: Instrumento) -> list[RevisionCuaderno]:
    """Las revisiones con letra del alumno en el instrumento, por fecha."""
    return list(
        RevisionCuaderno.objects.filter(alumno=alumno, instrumento=instrumento)
        .exclude(letra="")
        .select_related("session")
        .order_by("session__date", "pk")
    )


def media_de(filas) -> Decimal | None:
    valores = [f.valor for f in filas if f.valor is not None]
    if not valores:
        return None
    return (sum(valores, Decimal(0)) / Decimal(len(valores))).quantize(CENTESIMA, rounding=ROUND_HALF_UP)


def acumulado_de(filas) -> dict:
    """Lo que el registro enseña al pulsar la casilla."""
    media = media_de(filas)
    return {
        "tipo": "cuaderno",
        "n": len(filas),
        "media": str(media) if media is not None else "",
        "letra": calculo.cualitativa(media),
        "revisiones": [
            {
                "sesion": f.session_id,
                "fecha": f.session.date.isoformat(),
                "letra": f.letra,
                "comentario": f.comentario,
            }
            for f in filas
        ],
    }


@transaction.atomic
def recalcular(alumno, instrumento: Instrumento, user) -> Nota | None:
    """Deja la casilla del alumno como la letra de la media de sus revisiones con letra.

    Sin ninguna revisión con letra, la casilla no se toca (y se devuelve
    `None`): un sorteo pendiente no es una nota.
    """
    prueba = instrumento.prueba_para_evaluar()
    if prueba is None:
        raise ValueError("Este instrumento no tiene ninguna columna activa en el registro")
    filas = revisiones_de(alumno, instrumento)
    if not filas:
        return None
    acumulado = acumulado_de(filas)
    nota = Nota.poner(prueba, alumno, valor_de_letra(instrumento, acumulado["letra"]), user)
    rubrica = {**(nota.rubrica or {}), "acumulado": acumulado, "letra": acumulado["letra"]}
    Nota.objects.filter(pk=nota.pk).update(rubrica=rubrica)
    nota.rubrica = rubrica
    return nota


@transaction.atomic
def calificar(session, alumno, letra: str, user, comentario: str = "") -> tuple[RevisionCuaderno, Nota]:
    """Escribe la revisión de hoy y recalcula la casilla. Devuelve `(fila, nota)`.

    Calificar otra vez al mismo alumno en la misma sesión corrige la revisión
    de hoy (sigue siendo una), y la casilla se recalcula con la nueva letra.
    """
    letra = (letra or "").strip().upper()
    if letra not in LETRAS:
        raise ValueError(f"«{letra}» no es una calificación")
    instrumento = instrumento_de(session)
    if instrumento is None:
        raise ValueError("Esta sesión no tiene con qué revisar: tira el dado primero")
    if not alumnos_del_grupo(session.group).filter(pk=alumno.pk).exists():
        raise ValueError("Ese alumno no es de este grupo")
    valor = valor_de_letra(instrumento, letra)
    fila, _ = RevisionCuaderno.objects.select_for_update().get_or_create(
        session=session, alumno=alumno, defaults={"instrumento": instrumento}
    )
    fila.letra = letra
    fila.valor = valor
    fila.comentario = (comentario or "").strip()
    fila.autor = user
    fila.save()
    return fila, recalcular(alumno, instrumento, user)


# -----------------------------------------------------------------------------
# Lo que pinta la franja
# -----------------------------------------------------------------------------


def _instrumento_json(instrumento: Instrumento) -> dict:
    return {"id": instrumento.pk, "nombre": instrumento.nombre, "trimestre": instrumento.plan.trimestre}


def estado_de_lista(session) -> dict:
    """Todo lo que pinta la franja del cuaderno en el pase de lista de una sesión."""
    instrumento = instrumento_de(session)
    filas = list(session.revisiones_cuaderno.select_related("alumno").order_by("pk"))
    sorteados = []
    for f in filas:
        salida = {
            "alumno": f.alumno_id,
            "nombre": f.alumno.name or f.alumno.email,
            "letra": f.letra,
            "comentario": f.comentario,
        }
        if f.letra and instrumento is not None:
            acumulado = acumulado_de(revisiones_de(f.alumno, instrumento))
            salida["casilla"] = {"letra": acumulado["letra"], "n": acumulado["n"], "media": acumulado["media"]}
        sorteados.append(salida)
    return {
        "instrumento": _instrumento_json(instrumento) if instrumento else None,
        "opciones": [] if instrumento else [_instrumento_json(i) for i in opciones_de(session)],
        "letras": LETRAS,
        "por_sesion": POR_SESION,
        "maximo": MAXIMO_POR_SESION,
        "sorteados": sorteados,
        "pendientes": sum(1 for f in filas if f.pendiente),
        "candidatos": len(candidatos(session)),
    }
