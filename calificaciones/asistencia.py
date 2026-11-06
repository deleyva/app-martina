"""Las faltas, los retrasos y el material de cada alumno, por trimestre (fase 102).

Lo que se marca al pasar lista (`clases.Asistencia`, fase 70) se lee aquí para
dos sitios de calificaciones, y cada uno recibe una cosa distinta:

- **La pestaña ASISTENCIA** es del profesor y lo enseña todo: cada marca con su
  fecha y su nota, esté o no marcada para el informe.
- **El informe del alumno** recibe solo `informe`, que se arma aquí y no en el
  navegador: faltas, retrasos y material siempre, y de las notas solo las que
  el profesor marcó. Una nota sin marcar no viaja en ese bloque, así que no hay
  manera de que la pinte un descuido en `Informes.jsx`.

Dos reglas que vienen de antes:

- Solo cuentan **las sesiones que da el profesor que mira**, como en
  `clases.api._sesiones` y en `lista_marcar`: la lista y sus notas son de quien
  da la clase, y es el único que puede marcarlas para el informe.
- El trimestre de una sesión es `trimestre_de(fecha)`, el mismo que usa Evaluar.
"""

from __future__ import annotations

from clases.models import MATERIALES, Asistencia, ClassSession

from .evaluar import trimestre_de
from .models import alumnos_del_grupo

TRIMESTRES = (1, 2, 3)


def _vacio() -> dict:
    return {
        "faltas": 0,
        "retrasos": 0,
        "sin_material": {clave: 0 for clave, _ in MATERIALES},
        "marcas": [],
        "informe": {
            "faltas": [],
            "retrasos": [],
            "sin_material": {clave: [] for clave, _ in MATERIALES},
            "notas": [],
        },
    }


def _con_lista(sesion) -> bool:
    """Si en esa clase se pasó lista: se dio por pasada o se marcó a alguien."""
    pase = getattr(sesion, "pase_de_lista", None)
    return bool(pase and pase.pasada_at) or bool(sesion.asistencias.all())


def resumen(group, user) -> dict:
    alumnos = list(alumnos_del_grupo(group))
    activos = {a.pk for a in alumnos}
    sesiones = list(
        ClassSession.objects.filter(group=group, teacher=user)
        .select_related("pase_de_lista")
        .prefetch_related("asistencias")
        .order_by("date", "pk")
    )

    por_alumno = {a.pk: {str(t): _vacio() for t in TRIMESTRES} for a in alumnos}
    clases = {str(t): 0 for t in TRIMESTRES}

    for sesion in sesiones:
        trimestre = str(trimestre_de(sesion.date))
        if _con_lista(sesion):
            clases[trimestre] += 1
        fecha = sesion.date.isoformat()
        for fila in sesion.asistencias.all():
            if fila.alumno_id not in activos:
                continue
            bloque = por_alumno[fila.alumno_id][trimestre]
            informe = bloque["informe"]
            hora = fila.hora_llegada.strftime("%H:%M") if fila.hora_llegada else ""
            if fila.estado == Asistencia.FALTA:
                bloque["faltas"] += 1
                informe["faltas"].append(fecha)
            elif fila.estado == Asistencia.RETRASO:
                bloque["retrasos"] += 1
                informe["retrasos"].append({"fecha": fecha, "hora": hora})
            for clave in fila.sin_material or []:
                if clave in bloque["sin_material"]:
                    bloque["sin_material"][clave] += 1
                    informe["sin_material"][clave].append(fecha)
            nota = (fila.nota or "").strip()
            if nota and fila.nota_en_informe:
                informe["notas"].append({"fecha": fecha, "texto": nota})
            bloque["marcas"].append(
                {
                    "sesion": sesion.pk,
                    "fecha": fecha,
                    "titulo": sesion.title,
                    "estado": fila.estado,
                    "hora": hora,
                    "sin_material": list(fila.sin_material or []),
                    "nota": nota,
                    "nota_en_informe": bool(nota and fila.nota_en_informe),
                }
            )

    return {
        "materiales": [{"clave": c, "nombre": n} for c, n in MATERIALES],
        "clases": clases,
        "alumnos": {str(pk): trimestres for pk, trimestres in por_alumno.items()},
    }
