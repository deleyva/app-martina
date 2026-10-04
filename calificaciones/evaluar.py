"""Evaluar en clase (fase 62): de un elemento de la sesión a una nota del registro.

Un elemento de la sesión se marca evaluable con un instrumento. En clase, el
profesor elige a un alumno (o uno al azar entre los que aún no tienen nota en
ese instrumento), puntúa una rúbrica de 1 a 3 y la nota cae en la columna del
instrumento, la misma que se ve y se edita en el registro.

**Una nota por alumno e instrumento** (decisión de Jesús, 2026-10-04). Crear
una columna por ejercicio llenaría el registro de huecos, y con «celda vacía =
0» cada hueco es un cero.
"""

from __future__ import annotations

import random
from decimal import Decimal

from django.db import transaction

from .models import Instrumento, Nota, Plan, alumnos_del_grupo
from .plantillas import ESCALA

LETRAS = ["SB", "NT", "BI", "SU", "IN"]

# Los cortes de la media de la rúbrica (1 = no lo consigue, 2 = con errores,
# 3 = lo consigue). Elegidos por Jesús el 2026-10-04 frente a uno más exigente y
# a uno lineal. Se escriben como fracciones (numerador, denominador) porque se
# comparan sin dividir: `media >= 5/2` es `2 * suma >= 5 * n`, y así una media
# de 2,4999… por redondeo no cae nunca en el tramo equivocado.
CORTES = [
    ("SB", 3, 1),
    ("NT", 5, 2),
    ("BI", 2, 1),
    ("SU", 3, 2),
]


def letra_de_rubrica(puntos) -> str:
    """SB · NT · BI · SU · IN a partir de los puntos (cada uno 1, 2 o 3)."""
    puntos = list(puntos)
    if not puntos or any(p not in (1, 2, 3) for p in puntos):
        raise ValueError("Cada apartado se puntúa con 1, 2 o 3")
    suma, n = sum(puntos), len(puntos)
    for letra, numerador, denominador in CORTES:
        if suma * denominador >= numerador * n:
            return letra
    return "IN"


def valor_de_letra(instrumento: Instrumento, letra: str) -> Decimal:
    """El número con el que entra la letra en el cálculo, en la escala del instrumento.

    Si el instrumento califica con lista de opciones y tiene esa letra, manda su
    valor: así la nota se guarda exactamente igual que si se hubiera tecleado en
    el registro. Si no (escala numérica, u opciones de otra escala), el valor de
    la escala del curso: SB 9,5 · NT 8 · BI 6,5 · SU 5,5 · IN 4.
    """
    if letra not in LETRAS:
        raise ValueError(f"«{letra}» no es una calificación")
    if instrumento.escala == Instrumento.ESCALA_OPCIONES:
        for opcion in instrumento.opciones_normalizadas():
            if opcion["etiqueta"].strip().upper() == letra:
                return opcion["valor"]
        # Una lista de opciones sin esa letra (la A·B·C·D de antes): meter el
        # número a escondidas dejaría en el registro una nota que su escala no
        # admite. Mejor decirlo.
        etiquetas = ", ".join(o["etiqueta"] for o in instrumento.opciones_normalizadas())
        raise ValueError(f"«{instrumento.nombre}» califica con {etiquetas}, no con {letra}")
    return Decimal(str(next(o["valor"] for o in ESCALA if o["etiqueta"] == letra)))


def trimestre_de(fecha) -> int:
    """El trimestre escolar de una fecha: septiembre-diciembre 1, enero-marzo 2, el resto 3.

    Aproximado a propósito: solo decide qué plan sale ARRIBA al marcar un
    elemento como evaluable; los demás siguen a un toque. La nota cae siempre
    en el plan del instrumento elegido, no en el de la fecha.
    """
    if fecha.month >= 9:
        return 1
    return 2 if fecha.month <= 3 else 3


def instrumentos_del_grupo(group, fecha=None) -> list[dict]:
    """Los instrumentos con los que se puede marcar un elemento de este grupo.

    `[{trimestre, plan, instrumentos, actual}]`. El plan del trimestre de
    `fecha` (la de la sesión) va primero y marcado como `actual`; el resto,
    por trimestre. Antes iba el trimestre más alto primero, y en octubre eso
    ofrecía arriba los instrumentos de la 2ª evaluación (visto en el navegador,
    2026-10-04): un toque descuidado metía la nota en otro trimestre.
    """
    actual = trimestre_de(fecha) if fecha else None
    planes = (
        Plan.objects.filter(groups=group)
        .order_by("trimestre", "pk")
        .prefetch_related("instrumentos")
    )
    salida = [
        {
            "trimestre": p.trimestre,
            "plan": p,
            "instrumentos": list(p.instrumentos.all()),
            "actual": p.trimestre == actual,
        }
        for p in planes
    ]
    return sorted(salida, key=lambda p: not p["actual"])


def instrumento_del_grupo(group, instrumento_id) -> Instrumento | None:
    """El instrumento si es de un plan de este grupo; si no, `None`."""
    try:
        pk = int(instrumento_id)
    except (TypeError, ValueError):
        return None
    return Instrumento.objects.filter(pk=pk, plan__groups=group).select_related("plan").first()


def situacion(group, instrumento: Instrumento) -> dict:
    """Lo que necesita el panel de evaluar: el alumnado con su nota en esa columna."""
    prueba = instrumento.prueba_para_evaluar()
    alumnos = list(alumnos_del_grupo(group))
    notas = prueba.notas_de(alumnos) if prueba else {}
    return {
        "prueba": prueba,
        "alumnos": [
            {
                "alumno": a,
                "nota": notas.get(a.pk) if notas.get(a.pk) and notas[a.pk].valor is not None else None,
            }
            for a in alumnos
        ],
    }


def sin_nota(group, instrumento: Instrumento) -> list:
    """El alumnado que aún no tiene nota en la columna del instrumento."""
    return [f["alumno"] for f in situacion(group, instrumento)["alumnos"] if f["nota"] is None]


def al_azar(group, instrumento: Instrumento, excluir=(), azar=random):
    """Un alumno sin nota, que no esté en `excluir`. `None` si no queda ninguno.

    `excluir` es para volver a tirar cuando sale alguien que no está en clase:
    se le salta sin ponerle nada.
    """
    excluir = {int(e) for e in excluir}
    candidatos = [a for a in sin_nota(group, instrumento) if a.pk not in excluir]
    return azar.choice(candidatos) if candidatos else None


@transaction.atomic
def evaluar(
    *,
    group,
    instrumento: Instrumento,
    alumno,
    user,
    puntos=None,
    letra: str | None = None,
    comentario: str = "",
    elemento=None,
) -> Nota:
    """Escribe la nota de `alumno` en la columna del instrumento.

    Con `puntos`, la letra propuesta sale de la rúbrica; `letra` la sustituye si
    viene (es la que el profesor deja al final). Sin rúbrica, `letra` es
    obligatoria. Evaluar otra vez al mismo alumno sustituye la nota, y el
    cambio queda en el historial de `Nota.poner`.
    """
    prueba = instrumento.prueba_para_evaluar()
    if prueba is None:
        raise ValueError("Este instrumento no tiene ninguna columna activa en el registro")
    if not alumnos_del_grupo(group).filter(pk=alumno.pk).exists():
        raise ValueError("Ese alumno no es de este grupo")

    apartados = list(instrumento.rubrica or [])
    detalle = {}
    if puntos:
        puntos = [int(p) for p in puntos]
        if apartados and len(puntos) != len(apartados):
            raise ValueError("Falta puntuar algún apartado de la rúbrica")
        propuesta = letra_de_rubrica(puntos)
        detalle = {"apartados": apartados, "puntos": puntos, "propuesta": propuesta}
        letra = letra or propuesta
    if not letra:
        raise ValueError("Falta la calificación")
    letra = letra.strip().upper()
    if elemento is not None:
        detalle["elemento"] = elemento.get_content_title()
        detalle["sesion"] = elemento.session_id
    detalle["letra"] = letra

    nota = Nota.poner(prueba, alumno, valor_de_letra(instrumento, letra), user, comentario=comentario.strip())
    Nota.objects.filter(pk=nota.pk).update(rubrica=detalle)
    nota.rubrica = detalle
    return nota
