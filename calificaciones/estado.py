"""Lo que la pantalla de calificaciones necesita saber, en un solo JSON.

**Por qué existe.** La pantalla es la de la SPA del curso pasado (`notas`),
copiada: una isla de React que pinta lo que recibe. Aquí se decide qué recibe.

**Todas las cifras salen ya escritas.** La nota del trimestre, la de cada
competencia y la final de curso se calculan en `calculo.py` y viajan como texto
con un decimal. El navegador no redondea ni pondera nada de lo legal: si lo
hiciera habría dos cálculos, y 8,35 es «8.4» aquí y «8.3» en JavaScript.

**Leer y escribir devuelven lo mismo.** Cada escritura contesta con
`bloque_alumno()`, que es exactamente el trozo de `estado()` de ese alumno. No
hay un camino corto que recalcule «solo lo que cambió».
"""

from __future__ import annotations

from decimal import Decimal

from clases.models import Group

from . import calculo, plantillas
from .models import CambioNota, Evidencia, Nota, NotaManual, Plan, alumnos_del_grupo

TRIMESTRES = (1, 2, 3)


def _num(valor: Decimal | None) -> str:
    """Un valor de celda como se teclea: «8», «7.5», o vacío."""
    return CambioNota.texto(valor)


def _planes(group) -> dict[int, Plan]:
    # Si un grupo tuviera dos planes en un trimestre, manda el mismo que elige
    # `Plan.para_grupo`: el primero.
    planes: dict[int, Plan] = {}
    for plan in group.planes_calificacion.select_related("marco"):
        planes.setdefault(plan.trimestre, plan)
    return planes


# ----- el plan de un trimestre ---------------------------------------------------


def _corto(instrumento, posicion: int, total: int) -> str:
    """La cabecera de la columna. Con varias pruebas, la abreviatura y su número."""
    return instrumento.abreviatura if total == 1 else f"{instrumento.abreviatura} {posicion}"


def _trimestre(plan: Plan) -> dict:
    instrumentos = list(plan.instrumentos.prefetch_related("pruebas", "repartos__criterio"))
    columnas, fichas = [], []
    for instrumento in instrumentos:
        pruebas = list(instrumento.pruebas.all())
        activas = [p for p in pruebas if p.activa]
        opciones = [
            {"etiqueta": o["etiqueta"], "valor": _num(o["valor"])}
            for o in instrumento.opciones_normalizadas()
        ]
        tipo = "opciones" if instrumento.escala == instrumento.ESCALA_OPCIONES and opciones else "numero"
        peso = instrumento.peso
        for posicion, prueba in enumerate(activas, start=1):
            columnas.append(
                {
                    "prueba": prueba.pk,
                    "instrumento": instrumento.pk,
                    "nombre": prueba.nombre if len(activas) > 1 else instrumento.nombre,
                    "corto": _corto(instrumento, posicion, len(activas)),
                    "fecha": prueba.fecha.isoformat(),
                    "tipo": tipo,
                    "opciones": opciones,
                }
            )
        fichas.append(
            {
                "id": instrumento.pk,
                "nombre": instrumento.nombre,
                "corto": instrumento.abreviatura,
                "peso": _num(peso),
                "tipo": tipo,
                "opciones": opciones,
                "agregacion": instrumento.agregacion,
                "agregacion_texto": instrumento.get_agregacion_display(),
                "pruebas": [
                    {
                        "id": p.pk,
                        "nombre": p.nombre,
                        "fecha": p.fecha.isoformat(),
                        "activa": p.activa,
                    }
                    for p in pruebas
                ],
            }
        )

    # Las competencias: sus criterios, lo que pesan y qué instrumentos las alimentan.
    competencias: dict[str, dict] = {}
    for criterio in plan.marco.criterios.all():
        ficha = competencias.setdefault(
            criterio.competencia,
            {"codigo": criterio.competencia, "peso": Decimal(0), "criterios": [], "instrumentos": []},
        )
        ficha["peso"] += criterio.peso
        ficha["criterios"].append(
            {"codigo": criterio.codigo, "peso": _num(criterio.peso), "descripcion": criterio.descripcion}
        )
    for instrumento in instrumentos:
        for reparto in instrumento.repartos.all():
            ficha = competencias[reparto.criterio.competencia]
            if instrumento.abreviatura not in [i["corto"] for i in ficha["instrumentos"]]:
                ficha["instrumentos"].append({"corto": instrumento.abreviatura, "nombre": instrumento.nombre})
    for ficha in competencias.values():
        ficha["peso"] = _num(ficha["peso"])

    cuadre = plan.cuadre()
    return {
        "plan": {
            "id": plan.pk,
            "nombre": plan.nombre,
            "marco": str(plan.marco),
            "hueco_cuenta_cero": plan.hueco_cuenta_cero,
            "cuadra": cuadre["cuadra"],
            "total": _num(cuadre["total"]),
            "compartido_con": plan.groups.count() - 1,
        },
        "columnas": columnas,
        "instrumentos": fichas,
        "competencias": list(competencias.values()),
        "empezar": None,
    }


def _empezar(group, trimestre: int) -> dict:
    """Un trimestre sin plan: lo que se puede elegir, con su contenido a la vista."""
    opciones = plantillas.opciones_para_empezar(group, trimestre)

    def resumen(filas):
        return [{"nombre": f["nombre"], "peso": _num(f["peso"])} for f in filas]

    anterior = opciones["anterior"]
    return {
        "plan": None,
        "columnas": [],
        "instrumentos": [],
        "competencias": [],
        "empezar": {
            "anterior": (
                {
                    "id": anterior.pk,
                    "trimestre": anterior.trimestre,
                    "resumen": resumen(opciones["anterior_resumen"]),
                }
                if anterior
                else None
            ),
            "plantillas": [
                {
                    "clave": o["plantilla"].clave,
                    "nombre": o["plantilla"].nombre,
                    "encaja": o["encaja"],
                    "recomendada": o["recomendada"] and anterior is None,
                    "resumen": resumen(o["resumen"]),
                }
                for o in opciones["plantillas"]
            ],
        },
    }


# ----- los alumnos ----------------------------------------------------------------


def _bloques(group, alumnos, planes: dict[int, Plan]) -> dict[int, dict]:
    """El bloque de cada alumno: sus celdas y todas sus cifras, de los tres trimestres."""
    ids = [a.pk for a in alumnos]
    manuales: dict[tuple[int, str], NotaManual] = {
        (m.alumno_id, m.ambito): m for m in NotaManual.objects.filter(group=group, alumno_id__in=ids)
    }
    por_trimestre = {}
    pesos_trimestre = None
    for trimestre, plan in planes.items():
        instrumentos = {i.pk: i for i in plan.instrumentos.all()}
        pruebas = plan.pruebas_activas()
        notas = {
            (n.prueba_id, n.alumno_id): n.valor
            for n in Nota.objects.filter(prueba__in=pruebas, alumno_id__in=ids)
        }
        por_trimestre[trimestre] = (plan.resultados(alumnos), pruebas, instrumentos, notas)
        if pesos_trimestre is None:
            pesos_trimestre = plan.marco.pesos_trimestre()

    salida = {}
    for alumno in alumnos:
        trimestres = {}
        legal, simple = {}, {}
        for trimestre in TRIMESTRES:
            manual = manuales.get((alumno.pk, str(trimestre)))
            if trimestre not in por_trimestre:
                trimestres[str(trimestre)] = {
                    "notas": {},
                    "nota": "",
                    "nota2": "",
                    "cualitativa": "",
                    "simple": "",
                    "simple2": "",
                    "simple_cualitativa": "",
                    "competencias": {},
                    "huecos": 0,
                    "con_datos": False,
                    "manual": manual.calificacion if manual else "",
                    "motivo": manual.motivo if manual else "",
                }
                continue
            resultados, pruebas, instrumentos, notas = por_trimestre[trimestre]
            r = resultados[alumno.pk]
            celdas = {}
            for prueba in pruebas:
                valor = notas.get((prueba.pk, alumno.pk))
                celdas[str(prueba.pk)] = {
                    "valor": _num(valor),
                    "etiqueta": instrumentos[prueba.instrumento_id].etiqueta_de(valor),
                }
            trimestres[str(trimestre)] = {
                "notas": celdas,
                "nota": calculo.a_un_decimal(r.trimestre),
                "nota2": _num(r.trimestre),
                "cualitativa": r.cualitativa,
                "simple": calculo.a_un_decimal(r.simple),
                "simple2": _num(r.simple),
                "simple_cualitativa": calculo.cualitativa(r.simple),
                "competencias": {c: calculo.a_un_decimal(n) for c, n in r.competencias.items()},
                "huecos": r.huecos,
                "con_datos": r.con_datos,
                "manual": manual.calificacion if manual else "",
                "motivo": manual.motivo if manual else "",
            }
            # Una evaluación que nadie ha tocado no entra en la nota de curso.
            legal[trimestre] = r.trimestre if r.con_datos else None
            simple[trimestre] = r.simple if r.con_datos else None

        pesos = pesos_trimestre or {1: Decimal(1), 2: Decimal(1), 3: Decimal(1)}
        curso = calculo.nota_curso(legal, pesos)
        curso_simple = calculo.nota_curso(simple, pesos)
        manual = manuales.get((alumno.pk, "curso"))
        salida[alumno.pk] = {
            "id": alumno.pk,
            "nombre": alumno.name or alumno.email,
            "trimestres": trimestres,
            "curso": {
                "nota": calculo.a_un_decimal(curso),
                "cualitativa": calculo.cualitativa(curso),
                "simple": calculo.a_un_decimal(curso_simple),
                "simple_cualitativa": calculo.cualitativa(curso_simple),
                "manual": manual.calificacion if manual else "",
            },
        }
    return salida


def bloque_alumno(group, alumno) -> dict:
    """El trozo de `estado()` de un alumno. Es lo que devuelve cada escritura."""
    return _bloques(group, [alumno], _planes(group))[alumno.pk]


# ----- las evidencias ---------------------------------------------------------------


def evidencia_json(evidencia: Evidencia) -> dict:
    fichero = evidencia.fichero
    return {
        "id": evidencia.pk,
        "alumno": evidencia.alumno_id,
        "prueba": evidencia.prueba_id,
        "tipo": evidencia.tipo,
        "texto": evidencia.texto,
        "nombre": evidencia.nombre_original or evidencia.get_tipo_display(),
        "tamano": evidencia.tamano,
        "estado": evidencia.estado,
        "fecha": evidencia.created_at.isoformat(),
        "url": f"/calificaciones/evidencia/{evidencia.pk}/" if fichero else "",
    }


def _evidencias(planes: dict[int, Plan], alumnos) -> list[dict]:
    return [
        evidencia_json(e)
        for e in Evidencia.objects.filter(
            prueba__instrumento__plan__in=list(planes.values()), alumno__in=alumnos
        )
    ]


# ----- el historial -----------------------------------------------------------------


def historial(group, limite: int = 300) -> list[dict]:
    cambios = (
        CambioNota.objects.filter(nota__prueba__instrumento__plan__groups=group)
        .select_related("nota__alumno", "nota__prueba__instrumento__plan", "user")
        .distinct()[:limite]
    )
    salida = []
    for c in cambios:
        instrumento = c.nota.prueba.instrumento
        salida.append(
            {
                "id": c.pk,
                "alumno": c.nota.alumno.name or c.nota.alumno.email,
                "alumno_id": c.nota.alumno_id,
                "trimestre": instrumento.plan.trimestre,
                "columna": c.nota.prueba.nombre,
                "antes": instrumento.etiqueta_de(CambioNota.valor(c.antes)),
                "despues": instrumento.etiqueta_de(CambioNota.valor(c.despues)),
                "fecha": c.ts.isoformat(),
                "quien": (c.user.name or c.user.email) if c.user else "",
                "es_deshacer": c.revertido_de_id is not None,
            }
        )
    return salida


# ----- todo junto -------------------------------------------------------------------


def estado(group, user) -> dict:
    alumnos = list(alumnos_del_grupo(group))
    planes = _planes(group)
    bloques = _bloques(group, alumnos, planes)
    marco = next((p.marco for p in planes.values()), None)
    pesos = marco.pesos_trimestre() if marco else {1: Decimal(1), 2: Decimal(1), 3: Decimal(1)}
    return {
        "grupo": {
            "id": group.pk,
            "nombre": group.name,
            "materia": group.subject.name,
            "curso": group.academic_year,
            "marco": str(marco) if marco else "",
        },
        "grupos": [
            {"id": g.pk, "nombre": g.name}
            for g in Group.del_profesor(user).order_by("name")
        ],
        "trimestres": {
            str(t): _trimestre(planes[t]) if t in planes else _empezar(group, t) for t in TRIMESTRES
        },
        "pesos_trimestre": {str(t): _num(pesos.get(t, Decimal(0))) for t in TRIMESTRES},
        "alumnos": [bloques[a.pk] for a in alumnos],
        "evidencias": _evidencias(planes, alumnos),
        "cualitativas": [{"clave": k, "nombre": v} for k, v in calculo.CUALITATIVAS.items()],
    }
