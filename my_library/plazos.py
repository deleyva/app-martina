"""El plazo de repaso de cada unidad, calculado con su historial (fase 91).

Hasta la fase 90 el plazo era una tabla fija por nivel
(`session.INTERVALO_POR_NIVEL`): un ejercicio en «Me lo sé muy bien» esperaba
21 días tanto si te había salido una vez como diecinueve. Medido en producción
el 2026-11-01: tres «Example 3.1c» de CAGED, con 17 a 19 repasos y nivel 4,
seguían entrando en la sesión cada pocos días.

Aquí el plazo sale de FSRS, el algoritmo que usa Recall. Cada repaso con nota
mueve la ESTABILIDAD de la unidad, que es cuánto aguanta sin practicarse, y el
plazo es el tiempo en que la probabilidad de que te salga baja a `RETENCION`.
Los aciertos seguidos lo alargan cada vez más y un fallo lo encoge.

Se reproduce el historial entero cada vez, sin guardar nada: así no puede
desincronizarse de `ReviewLog`, que es la verdad. Son unos pocos cientos de
repasos por usuario, y la cuenta es aritmética.
"""

from datetime import timezone

from fsrs import Card, Rating, Scheduler

# El plazo es el tiempo en que la probabilidad de que salga baja al 90 %.
RETENCION = 0.9

# Techo del plazo, en días. FSRS está calibrado con tarjetas de memoria, y con
# «Me lo sé muy bien» repetido se dispara: sobre el historial real de Jesús
# (2026-11-01), las tres «Example 3.1c» de CAGED, con 18 a 20 cuatros seguidos,
# salían a 572-631 días. Un lick de guitarra no aguanta año y medio sin tocarse
# como aguanta una palabra. Con el techo, lo que dominas vuelve al menos cada
# trimestre. Es un número para ajustar con el uso, no una constante de la física.
PLAZO_MAXIMO = 90

# Las notas del visor son cinco y FSRS tiene cuatro. «Apenas lo conozco» cuenta
# como fallo: si apenas lo conoces, no te ha salido.
NOTA_FSRS = {
    0: Rating.Again,  # No me sale
    1: Rating.Again,  # Apenas lo conozco
    2: Rating.Hard,  # Lo estoy aprendiendo
    3: Rating.Good,  # Lo conozco bien
    4: Rating.Easy,  # Me lo sé muy bien
}

# Sin pasos de aprendizaje en minutos: la sesión piensa en días, y un paso de
# diez minutos no significa nada para un ejercicio de guitarra. Sin aleatoriedad,
# para que dos llamadas den lo mismo y la vista previa coincida con el
# lanzamiento (C78).
_PLANIFICADOR = Scheduler(
    desired_retention=RETENCION,
    learning_steps=(),
    relearning_steps=(),
    maximum_interval=PLAZO_MAXIMO,
    enable_fuzzing=False,
)


def plazo_en_dias(repasos):
    """Días que debería aguantar la unidad después de su último repaso.

    `repasos` es `[(cuando, nivel_tras_el_repaso), ...]` en orden de tiempo.
    Los repasos sin nota no cuentan. Sin ninguno con nota devuelve None, y la
    sesión cae a la tabla fija por nivel.
    """
    # `card_id` explícito: sin él, la librería lo genera con la hora del
    # sistema y espera un milisegundo para que no se repita, por cada unidad.
    tarjeta = Card(card_id=0)
    hubo_nota = False
    for cuando, nivel in repasos:
        nota = NOTA_FSRS.get(nivel)
        if nota is None:
            continue
        tarjeta, _ = _PLANIFICADOR.review_card(
            tarjeta, nota, review_datetime=cuando.astimezone(timezone.utc)
        )
        hubo_nota = True
    if not hubo_nota:
        return None
    return (tarjeta.due - tarjeta.last_review).total_seconds() / 86400
