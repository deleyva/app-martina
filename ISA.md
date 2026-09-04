---
slug: app-martina
phase: build
progress: true
iteration: 31
principal_stated_goal: "Por favor, sepárame la app CMS en dos apps distintas, por lo menos, para empezar una para blogs y otra para apps.música.es, Martina Bescós o lo que sea. No quiero tener más líos de templates. Por ejemplo, no quiero que tengan fichas musicales los artículos en blogs. Ni tampoco quiero que una persona, a la hora de subir una imagen, tenga que elegir si lo hace en la app de música o en el departamento de filosofía."
updated: 2026-09-04
---

# ISA — app-martina · Sistema de estudio de la biblioteca

## Cómo retomar esto

**Di: "lee el ISA de app-martina y sigue por donde íbamos".** Este fichero es el estado del sistema, vive en el repo y viaja con el código.

### Qué hay hecho y desplegado

| Fase | Qué | Commit |
|---|---|---|
| 1 | `ReviewLog` — histórico de práctica; borrada la app muerta `study_sessions` | `7912c80` |
| 2 | Notas privadas y etiquetas en el visor | `d13f488` |
| 3 | Sesiones acotadas (8) con caducidad por nivel y agrupación temática | `0bd71e9` |
| 3b | Nota docente compartida (`SharedNote`) | `8b2149e` |
| 4 | Facetas de etiquetas + migración de las 188 | `3f0129f`, `87848c7` |
| 5 | Arranque de sesión por faceta (`/my-library/empezar/`) | `604559a` |
| 5b | Cuota de novedad: lo nuevo no inunda la sesión | `b824d74` |
| 6 | Trocear material largo en secciones (`ItemSection`) | `724ae7a` |
| 7 | Los mazos sobreviven al renombrado + comentarios de plantilla que se veían | `18a2b0e`, `444af8e` |
| 8 | **Un solo vocabulario de etiquetas** — mapa cerrado, código sin empezar | `b8572d1` (solo el mapa) |
| 9 | La telemetría deja de pisar la sesión de OAuth — login con Google arreglado | `8c8605b` |
| 10 | **La nota se guardaba en el item equivocado** — encontrado al verificar C12 en navegador | `7bec854` |
| 8·1 | **Expandir: `faceted_tags` vacío en las cuatro páginas** (C33) | `547a547` |
| 8·2 | **Migrar: 531 etiquetas escritas en 164 páginas** (C34b, C35) | `9ed4e1f` |
| 8·3 | **Contraer: la sesión lee solo el vocabulario facetado** (C36) | `9137cfe` |
| 8·4 | **El selector y el visor ven las etiquetas de la página** (C40) | `c6360ab` |
| 8·5 | **El sitio entero sobre el vocabulario facetado** (C37a, C37b) | `94e5603`, `bfa3646`, `b79737a`, `e2d8d42` |
| 8·6 | **Borrado `MusicTag`** (C37c) | `32a71c6` |
| 11 | **Estudiarse un libro** — objetivo por libro y creación perezosa (C41–C46) | `fca4577`, `9ab9c96` |
| 11·1 | **El despliegue se rompió a mitad** — migración anclada a una versión de Wagtail que producción no tenía; wagtail fijado a 7.3.1 | `aa8cbc1`, `b0acc1b` |
| 12 | **La cuota se mide por objetivo y se alterna** (C47–C49) — la creación perezosa estaba apagada de hecho | `b9e394a` |
| 13 | **Entrar sin Google** (C50, C51) y **el espacio que no se escribía en la nota** (C52) | `b9e394a` |
| 14 | **Alternar de verdad**: reserva por objetivo y reparto al elegir (C53, C54) | `b3f8fd5` |
| 15 | **El panel de mazos sale de la interfaz** (C55), modelo intacto y revisión el 25/09 | `285f904` |
| 16 | **El libro recién empezado no asomaba** (C56, C58) y **el comentario se veía** (C57); comando de medida (C59) | `5cdcb85` parcial |
| 17 | **Sesión de 15 con 3 huecos de novedad** (C60), y qué hace el filtro por instrumento (C61, C62) | `c31f13e` |
| 18 | **El filtro frena también la creación** (C63) | `6d3e7e8` |
| 19 | **Seguir un libro desde la pantalla de empezar** (C64-C67) | `c28869d` |
| 20 | **Encajar la imagen en la pantalla** (C68) | `c28869d` |
| 21 | **Libros por referencia, orden del libro y embeds como material** (C69-C72) | `1cf505f` |
| 21·1 | El tipo de página en el menú (C73), piel de la app y pajarito (C74, C75), 500 en libros vacíos (C76), propiedades de visibilidad (C77) | `704649c`, `88b116a`, `24f920c` |
| 22 | **La vista previa enseña la sesión que se va a servir** (C78, C79) | `5be6f63` |
| 23 | **Descartar funcionaba; eran homónimos** (C81-C84) y el menú se desplaza | `77a3818`, `ef7c71f`, `456e66f` |
| 24 | **Contador de sesión arriba y descartar con doble D** (C85, C86) | `dec6b7b` |

### Lo siguiente, por orden

**Todo lo de las fases 1 a 20 está desplegado y verificado en producción** (`c28869d`, 2026-08-26). No queda nada a medias.

1. **Presupuesto de sesión en MINUTOS en vez de en elementos.** La mejor idea pendiente, y **los datos para calibrarla ya están medidos** (fase 16): 23 elementos con duración, mediana 49 s, mínimo 11 s, máximo 469 s. Un factor 42 entre el más corto y el más largo, que es el argumento entero: dos sesiones de "15 elementos" pueden durar nueve minutos o casi dos horas. El principal lo confirmó el 26/08: *"en un futuro muy próximo querré hacer presupuesto en minutos"*. Se mide con `just production-command estado_estudio --email <correo>`.

2. **`autor` y `obra` no se pueden filtrar.** Existen como facetas pero no están en `FACETAS_DE_FILTRO`, así que **un libro sin objetivo no se puede acotar de ninguna manera**. Los chips de la fase 19 resuelven los libros con objetivo y solo esos. Es un cambio de una línea más su interfaz; se descartó el 26/08 para no ampliar el alcance, no porque sea mala idea.

3. **Con cuatro objetivos, uno se quedará fuera de todas las sesiones.** Hoy no pasa: tres objetivos y tres huecos encajan justos, y eso lo arregló el paso a 15 de la fase 17. Con un cuarto objetivo vuelve, y siempre le tocará al mismo. La solución es rotar quién abre la ronda en `_repartir_por_libro`, y pide guardar estado. **Se decide con el presupuesto en minutos**: con presupuesto por tiempo la cuota deja de ser "3 huecos" y el problema cambia de forma.

4. **Elegir un libro apaga el repaso de los demás ese día.** Decisión consciente del principal (fase 19), no un defecto. Merece mirarse después de una semana de uso real: si se acumula vencido en los libros que no se eligen, la respuesta es probablemente reservar algún hueco de repaso fuera del filtro.

5. **25 de septiembre: decidir si se borra `LibraryDeck`.** Recordatorio programado por Telegram (`DASchedule` id `1787668554241-ik4zhv`). Ver fase 15 para lo que se pierde y para la alternativa, que es guardar combinaciones de FACETAS y no resucitar mazos.

6. **Revisar los plazos de caducidad con datos reales** (hoy 1/1/3/7/21 días por nivel). El de 21 días para "me lo sé muy bien" es el más dudoso: para un dato está bien, para tener una escala en las manos puede ser demasiado.

7. **Meter un libro sigue costando lo suyo si no es por objetivo.** El botón de «estudiarme este libro» resolvió el caso bueno; añadir material suelto desde el índice sigue siendo de uno en uno.

8. **El botón de encajar está solo en el menú**, o sea dos toques. Un atajo de teclado es una línea, pero toca el manejador de `keydown` que ya se acumula en cada carga; arreglar esa deuda primero.

### Deuda conocida, sin bloquear nada

- **`{# … #}` de Django es de UNA línea, y en este proyecto ya se ha pintado en pantalla TRES veces** (fase 7, fase 16 y otra vez el 26/08 escribiendo la fase 19). Las dos primeras llegaron a producción; la tercera la cazó `test_el_selector_no_escupe_el_comentario_de_la_plantilla`. **La lección no es "acuérdate": es que hay que dejarlo cazado.** Hoy hay un test por plantilla tocada (`index.html` y `session_start.html`); cualquier plantilla nueva con un comentario largo debería llevar el suyo, o mejor, usar `{% comment %}` siempre. Anotado también en `AGENTS.md`.
- **Los grupos sin objetivo acumulan material sin tocar y ya nadie se lo lleva.** Medido el 26/08: «Índice de recursos musicales» tiene 12 elementos sin tocar y el grupo suelto 1, y desde la fase 16 ninguno de los dos entra en la cuota de novedad mientras haya tres objetivos. No es un defecto —los objetivos deben ganar— pero esos 13 elementos no volverán a salir como novedad nunca. Salen por caducidad solo si se practican una vez.
- **El login por contraseña fuera de la lista devuelve 500, no un mensaje.** `AccountAdapter.pre_login` hace `raise ValidationError`, y allauth no la captura ahí. El texto («usa tu cuenta de Google») está escrito y no lo ve nadie. Un alumno que pruebe el formulario se come un error de servidor. Se arregla devolviendo una respuesta (`ImmediateHttpResponse`) en vez de lanzar. *(Medido el 2026-08-25 al intentar entrar.)*
- **Los `keydown` de los visores se acumulan en cada carga de item.** `study_item_content` llega por `fetch` y sus `<script>` se re-ejecutan, así que `pdf_viewer` e `image_viewer` registran su manejador otra vez con cada elemento de la sesión, cada uno con el closure de su carga. La guarda de C52 tapa el síntoma; arreglarlo de verdad es nombrar las funciones y quitarlas al descargar el item.

- **C12, C28 y C30bis: pendientes de ver en navegador, ya SIN bloqueo.** El principal confirma el 2026-08-21 que **Interceptor funciona**. Quedan por ver el panel de notas, la nota docente, el selector de facetas, el troceo y el arreglo de los comentarios. Ya no es deuda bloqueada: es trabajo pendiente de hacer.
- **6 sitios con `user.username`** en otras apps, que en este proyecto siempre vale `None`. Dos son crashes de búsqueda en el admin: `evaluations/admin.py:125` y `cms/models.py:1788`, `cms/wagtail_hooks.py:34`, `evaluations/admin.py:163`, y dos plantillas de `incidencias`.
- **Cuatro scripts en la raíz rompen `pytest`**: `test_images.py`, `test_tags.py`, `test_tags2.py`, `test_viewer_html.py` llaman a `django.setup()` al importarse. Hay que excluirlos a mano para que la suite arranque; deberían renombrarse.
- **9 tests preexistentes fallan** en analytics, cms e incidencias. Verificado con `git stash` que ya fallaban antes de todo esto.
- **La etiqueta `borrar`** es la única de las 139 sin faceta: en la revisión del mapa se eliminó su línea, lo que significa "déjala como está".
- **Tablas huérfanas de `study_sessions`** en la BD de producción. Inertes; borrarlas es decisión del principal.
- **`build_tag_map` hace ~2 consultas por elemento** y corre en cada carga del índice y en cada render del panel de mazos. A 500 elementos se notará.
- **El vocabulario de etiquetas está partido en dos y solo uno tiene facetas.** `taggit.Tag` (139, facetadas) y `cms.MusicTag` (80, planas: `guitar`, `guitarra`, `jazz`, `piano`…). Encontrado en la fase 7. La fragmentación que motivó las facetas sigue entera en `MusicTag`, y la sesión de estudio no puede agrupar ni filtrar por nada de lo que viva ahí.
  - **La línea divisoria es limpia:** los ACTIVOS (imágenes y documentos de Wagtail, que son 95 de los 102 elementos de biblioteca) llevan taggit y ya están facetados. Los CONTENEDORES (las páginas) llevan `MusicTag` y están planos.
  - **No es un renombrado como el de las 188, y esto marca el tamaño del trabajo.** En `cms`, taggit solo lo usa `TaggableEmbed`; los cuatro tipos de página con `MusicTag` (BlogPage 255, ScorePage 44, DictadoPage 1, TestPage 0) **no tienen manager de taggit**. Hace falta añadirlo (`ClusterTaggableManager` + through, por las revisiones de Wagtail) y luego una migración de datos que re-etiquete, no un `UPDATE` de nombres.
  - **Mapa revisado y cerrado** (2026-08-17): `my_library/migracion/mapa_musictags.txt`. Ver fase 8.
- **`content_hub` es una app muerta montada en producción.** Modelos, API, búsqueda, señales, urls y plantillas, en `INSTALLED_APPS` y en `config/urls.py`, con **0 filas** (`ContentItem` y `ContentLink` vacíos). Trae su propio `migrate_cms_to_content_hub`. Es un intento anterior de unificar el contenido, abandonado a medias. Sus señales siguen vivas: el `Failed to index ContentItem 3352: 'LibraryItem' object has no attribute 'title'` que sale en la suite viene de ahí. Decidir: enterrarla o resucitarla. Enterrarla sería la primera migración de este proyecto que se cierra del todo.

### Datos útiles para retomar

- Producción: `https://apps.iesmartinabescos.es` · deploy con `just deploy-production` (hace `git reset --hard origin/main` en el servidor, así que hay que pushear antes).
- **Un `manage.py` contra producción: `just production-command <lo que sea>`** (añadida el 23/08; `command` solo corre en local). Para la fase 8 hay dos atajos: `production-migrar-musictags` (en seco) y `production-migrar-musictags-ejecutar`, que pide escribir `MIGRAR`.
- **Radiografía de la sesión, de solo lectura: `just production-command estado_estudio --email <correo>`** (añadida el 26/08, fase 16). Enseña los objetivos con su reserva, **los grupos de material sin tocar en el orden en que se sirven y cuáles no entran**, la sesión que saldría ahora, y las medianas de `duration_seconds`. Es lo que hay que mirar ANTES de tocar el reparto: la vista previa del navegador solo enseña los elegidos, así que no deja ver cuántos grupos compiten. Ese error costó un despliegue el 26/08.
- Local: `just up`, tests con `docker compose -f docker-compose.local.yml run --rm django pytest my_library/tests.py`.
- Usuario de pruebas en local: `probe@local.test` (staff/superuser). En la BD local, no en producción.
- Copia previa a la migración de etiquetas: `backups/taggit_antes_facetas_20260812.json` (fuera del repo, está en `.gitignore`).
- **`static/css/index.css` ya NO se versiona, y el entrypoint ya no se mata por ella** (2026-08-25). Dos cosas distintas con la misma raíz:
  - **El fichero.** Es la ENTRADA de Tailwind y además se genera sola: `npm run create-css` la escribe, `compose/local/django/start` la regenera en cada arranque y `compose/production/django/entrypoint` la BORRA antes de `collectstatic` para que Whitenoise no la procese. Tres cosas peleándose por un fichero versionado: salía sin parar en rojo en `git status`. Untrackeada y en `.gitignore`, junto a `output.css`. Si algún día falta en local: `npm run create-css`.
  - **La carrera, que es la causa de fondo.** El entrypoint hacía `[ -f fichero ] && rm fichero`. En LOCAL, `django` y `huey_consumer` salen de la misma imagen y montan el MISMO árbol de trabajo, así que arrancan a la vez: uno borra y al otro le falla el `rm` entre la comprobación y el borrado. Con `set -o errexit`, ese fallo **mata el contenedor con exit 1** — así estaba el stack local al empezar la sesión. Arreglado con `rm -f` sobre los dos ficheros, que es limpieza idempotente y no una comprobación. **Producción no sufría la carrera**: allí `django` y `huey_consumer` solo montan media y backups, no el árbol, así que cada uno borra su propia copia.
- Trampas del proyecto documentadas en `AGENTS.md` § "Trampas conocidas".

## Goal

> "ok! eliminemos study_sessions. Y vamos a desarrollar ReviewLog"

Dos movimientos en el mismo run: retirar el sistema de estudio muerto (`study_sessions`, SM-2 completo pero fuera de `INSTALLED_APPS` y sin un solo import externo), y añadir a `my_library` la tabla de histórico que hoy no existe y que no se puede reconstruir a posteriori.

## Vision

`my_library` registra hoy `times_viewed` (contador) y `last_viewed` (una sola fecha). No hay registro por repaso, así que no se puede responder "¿qué practiqué esta semana?", no se puede alimentar ningún planificador, y no se puede migrar a un algoritmo de scheduling en el futuro sin empezar de cero. Cada día sin `ReviewLog` es un día de datos tirados de forma irrecuperable.

Este run captura datos. No decide nada sobre ellos.

## Out of Scope

- Planificador, cooldown, caducidad o cualquier lógica de "qué toca hoy". Solo captura.
- Tope de tamaño de sesión, agrupación temática, facetado de tags, secuencia de libros, recomendador.
- Migrar `LibraryItem` a `content_hub` o unificar los modelos de contenido solapados.

## Anti-claims

- **A1** — No se pierde ni se altera ningún dato existente de `LibraryItem`: `proficiency_level`, `times_viewed`, `last_viewed` y `notes` siguen intactos y con los mismos valores tras la migración.
- **A2** — El borrado de `study_sessions` no deja referencias colgando en código vivo que rompan el arranque de Django.
- **A3** — No se ejecuta ningún `DROP TABLE` en producción en este run. Las tablas huérfanas se reportan al principal, no se tocan.
- **A4** — `ReviewLog` no se convierte en un planificador encubierto: sin `next_review_date`, sin `ease_factor`, sin campos derivados que presupongan un algoritmo concreto.

## Claims

- [x] **C1 — `study_sessions` eliminada.** El directorio no existe y no queda ninguna referencia en código ejecutable (`.py`, plantillas, settings, urls). *Probe: `rg -l study_sessions -g '*.py' -g '*.html'` no devuelve nada. Los `.dot` quedan fuera: son artefactos generados por `graph_models`, se refrescan solos la próxima vez que se regeneren.*
- [x] **C2 — Django arranca sin la app.** *Probe: `manage.py check` sale con código 0.*
- [x] **C3 — `ReviewLog` existe con el esquema acordado** (`user`, `item`, `reviewed_at`, `session_uuid`, `source`, `proficiency_before`, `proficiency_after`, `duration_seconds`, `deck`) y su migración está generada y aplicada. *Probe: `makemigrations --check --dry-run` sale 0 (nada pendiente) y un `SELECT` sobre la tabla responde.*
- [x] **C4 — Un repaso en el visor de estudio graba exactamente una fila**, con el nivel previo y el nuevo, la duración, el uuid de sesión y el mazo de origen. *Probe: test que hace POST a `log_review` y verifica la fila y sus campos.*
- [x] **C5 — El histórico es independiente de los contadores.** `LibraryItem.days_since_last_review` deriva de `ReviewLog`, no de `last_viewed`. *Probe: test que crea logs y comprueba el cálculo.*
- [x] **C6 — Los repasos del índice quedan distinguibles de los de práctica** vía `source` (`manual` vs `study`), para que un futuro planificador pueda filtrarlos. *Probe: test sobre ambos endpoints.*
- [x] **C7 — La suite pasa.** *Probe: `just test` en verde — 18/18 en `my_library`, 232 en total. Los 9 fallos restantes (analytics, cms, incidencias) son preexistentes: idénticos al correr la suite sobre el estado previo con `git stash`.*
- [x] **C8 — El visor real graba de verdad.** Los tests cierran el endpoint y el render de la plantilla; esta claim exige además que el JS se haya ejecutado en un navegador real. *Cerrada 2026-08-12: el principal condujo su propio navegador (Interceptor seguía bloqueado por setup manual) y la evidencia se leyó por SQL. Dos repasos reales sobre el item 33: `source=study`, transición 2→3 capturada, duraciones 12s y 7s, mazo `Pentatonicas` propagado, y `session_uuid` DISTINTO en cada tanda — correcto, cada apertura del visor es una tanda nueva.*

## Test Strategy

`pytest` vía `just test` (docker compose local, `--ds=config.settings.test`). Tests en `my_library/tests.py`. La fixture `user` de `martina_bescos_app/conftest.py` **no alcanza a esta app** (conftest solo cubre su propio subárbol), así que se define local con `UserFactory`. Para el contenido referenciado por el `GenericForeignKey` se usa un `ExternalResource` real en lugar de un mock, para que el `content_type` sea válido.

Cuatro scripts sueltos en la raíz (`test_images.py`, `test_tags.py`, `test_tags2.py`, `test_viewer_html.py`) llaman a `django.setup()` y tocan la BD al importarse: rompen la colección de pytest y hay que excluirlos para que la suite arranque. Preexistente, pero conviene moverlos fuera del patrón `test_*.py`.

## Decisions

- **`ReviewLog` como tabla propia, no campos en `LibraryItem`.** Un contador no se puede desagregar; una tabla de eventos sí se puede agregar. La dirección barata es de eventos a contadores, nunca al revés.
- **Sin `next_review_date` ni `ease_factor`.** Se descartó replicar el SM-2 que se está borrando: la clase de algoritmo es la equivocada para destreza motora (decae más lento que un dato y mejora dentro de la propia sesión). Guardamos hechos observados, no predicciones. Cuando exista el planificador, se derivará de estos hechos.
- **`session_uuid` en vez de un modelo `StudySession`.** Agrupa los repasos de una tanda sin resucitar la tabla que acabamos de borrar. Se genera en cliente al abrir el visor.
- **`user` desnormalizado en `ReviewLog`.** `item.user` ya lo implica, pero "¿qué practiqué esta semana?" es la consulta más frecuente y así evita el join. Se asigna en el classmethod `log()`, nunca a mano.
- **`deck` con `SET_NULL`.** Borrar un mazo no debe borrar la historia de lo que se practicó con él.
- **`item` con `CASCADE`.** Aceptado a conciencia: si se saca un elemento de la biblioteca, su historia se va con él. La alternativa (`SET_NULL` + título desnormalizado) añade complejidad para un caso que hoy no aprieta. Anotado por si cambia.
- **Tablas huérfanas en producción.** `study_sessions` tuvo migraciones aplicadas en algún momento, así que sus tablas probablemente siguen existiendo en la BD de producción. Borrar la app no las elimina. Son inertes. Decisión de borrarlas: del principal, en un run aparte.

## Log

- Borrado y modelo van en el mismo run porque no se tocan entre sí: `study_sessions` no tiene un solo import externo (verificado con `rg`), así que el borrado no puede romper nada de `my_library`.
- **Clase de defecto encontrada al escribir `ReviewLog.__str__`:** este `User` define `username = None` (`USERNAME_FIELD = "email"`), así que todo `user.username` del proyecto vale `None`. Barrido con `rg`: 9 sitios vivos. Arreglados los 3 de `my_library` (uno era un crash real: `search_fields = ["user__username"]` reventaba la búsqueda del admin con `FieldError`). Los 6 restantes viven en otras apps y quedan reportados sin tocar, por disciplina de alcance: `cms/models.py:1788`, `cms/wagtail_hooks.py:34`, `evaluations/admin.py:125` (crash de búsqueda), `evaluations/admin.py:163-164`, y dos plantillas de `incidencias` que pintan la inicial "N" en los avatares.
- El entorno local nunca se había construido (no había imágenes docker del proyecto). El primer `just up` tardó lo suyo.


## Fase 2 — Notas y etiquetas en el visor

Cierra dos de las siete peticiones originales. Resultó ser más que "pintar un campo": `notes` existía en el modelo desde siempre y **no tenía ninguna UI** — ni escritura ni lectura, en ningún sitio. Sin camino de escritura, mostrarlo no sirve de nada.

- [x] **C9 — Las etiquetas del item se ven mientras practicas.** *Probe: test sobre `study_item_content` que verifica que los tags salen en el HTML.*
- [x] **C10 — Las notas se leen y se escriben desde el visor**, con guardado automático. *Probe: tests de `update_notes` (guardar, vaciar, 404 ajeno).*
- [x] **C11 — Escribir una nota no cuenta como repaso.** *Probe: test que verifica que `update_notes` no crea `ReviewLog`.*
- [x] **C12 — El panel funciona en navegador.** *2026-08-21, Chrome real contra el local. Se abre con `M`; se ven las etiquetas (`instrumento:guitarra`, `concepto:pentatonica`), la nota docente y «mis notas»; el texto se guarda solo (estado «Guardado», sin pulsar nada) y sobrevive al cambio de item. Capturas: `~/Downloads/martina-c12-panel-arreglado.png`.* **La verificación destapó un defecto de datos y hubo que arreglarlo antes de poder cerrarla — ver abajo.**

### Decisiones

- **El panel vive en el flyout (tecla `M`)**, no encima del contenido: la partitura o el vídeo ocupan la pantalla entera y taparlos con texto sería peor que el problema que resuelve.
- **El bloque nace en `study_item_content.html` y se traslada al flyout por JS**, mismo patrón que `#study-media-panel`. Razón: las notas cambian con cada item, el flyout es estático.
- **Guardado automático con debounce de 900ms + al perder el foco.** Sin botón de guardar: escribir la nota tiene que costar menos que volver a ver el vídeo, que es justo lo que se quiere evitar.
- **Dos caminos de pérdida de datos, tapados a propósito:** `flushNotes()` al principio de `loadItem` vuelca lo pendiente antes de cambiar de item, y `Escape` dentro del textarea sale del campo (guardando) en vez de abandonar la sesión.


## Fase 4 — Facetas de etiquetas

El vocabulario era plano y se fragmentaba solo. En producción: 188 etiquetas, 130 sin faceta, `guitar` conviviendo con `instrument/guitar`, `ukelele` con `ukulele`, `aragón` con `aragon`, y `partitura` con `sheet-music`, `musicscore` y `score`.

Decisiones del principal: nombres de faceta en **español**, se facetan **también las no musicales** (curso, evaluacion, tema, lugar, idioma), y el renombrado es **global y real** en taggit, con revisión previa del mapa.

- [x] **C13 — El separador es `:` y no `/`.** Hay etiquetas de compás (`3/4`, `6/8`, `2/4`, `3/8`, `4/4`) que con `/` se parsean como faceta `3` o `6` — ya pasaba al contar los namespaces existentes. *Probe: test que verifica que los cinco compases NO se parsean como faceta.*
- [x] **C14 — La sesión solo agrupa por etiquetas con faceta.** Arregla un defecto de la fase 3: `4-eso` y `10points` agrupaban de verdad. *Probe: test con elementos que solo comparten etiquetas administrativas.*
- [x] **C15 — El concepto manda sobre el instrumento al agrupar.** Media biblioteca es de guitarra; agrupar por eso no aporta. *Probe: test con elementos que comparten instrumento y difieren en concepto.*
- [x] **C16 — La migración no pierde etiquetados ni deja duplicados**, y es idempotente. *Probe: 7 tests sobre el comando, incluidos los dos bugs que encontró el ensayo en seco.*
- [x] **C17 — Mapa revisado y migración ejecutada en producción.** *2026-08-12: el principal revisó el mapa (16 cambios; convirtió las etiquetas de obra en borrados y creó la faceta `orientacion`). Copia previa en `backups/taggit_antes_facetas_20260812.json` (188 etiquetas, 3895 etiquetados). Resultado: 138 renombradas, 38 fusionadas, 11 borradas → 139 etiquetas, 138 con faceta. Verificado contra la copia: los 1162 objetos etiquetados conservan exactamente el juego de etiquetas que dicta el mapa; 0 perdieron todas; las 513 filas que desaparecen son duplicados que colapsaron al fusionar, contados y cuadrados uno a uno. Sin slugs ni nombres duplicados.*
- [x] **C18 — Arranque de sesión filtrando por faceta.** *Selector en `/my-library/empezar/`: elige instrumento, concepto, estilo, tipo, tonalidad o dificultad, con recuento en vivo por HTMX y vista previa de qué entraría hoy. Y entre facetas, O dentro de cada una. Probe: 12 tests + prueba con datos sembrados (guitarra+pentatonica → 3 de 5).*

### Decisiones de C18

- **La selección va por GET, no POST.** Vive en la URL, así que una combinación que funciona se guarda en marcadores y se repite mañana sin volver a elegir.
- **Y entre facetas, O dentro de cada faceta.** Marcar otro concepto amplía; añadir otra faceta estrecha. Es lo que se espera al elegir con el ratón.
- **`FACETAS_DE_FILTRO` excluye `evaluacion`, `tema`, `curso` y compañía.** Filtrar la práctica por "examen" o "vitalinux" no significa nada.
- **El filtro decide el conjunto candidato; la caducidad decide quién entra.** La vista previa lo enseña explícitamente ("Hoy te tocaría esto") para que no parezca que el filtro manda sobre el planificador.
- **Trampa al verificar el HTML**: las clases de Tailwind llevan `peer-checked:`, así que buscar la subcadena "checked" da 21 falsos positivos en una página con 2 casillas marcadas. Hay que mirar el atributo dentro del `<input>`, y acotar a las casillas de faceta porque `base.html` trae las suyas.

### Log

- **Dos bugs que solo aparecieron al ensayar en seco contra datos reales**, ninguno de los cuales habrían cazado los tests que tenía escritos hasta ese momento:
  1. Dos orígenes al mismo destino (`jazz` y `genre/jazz` → `estilo:jazz`) se clasificaban ambos como renombrado. El segundo habría reventado contra la unicidad de taggit. Ahora se agrupa por destino antes de clasificar, y la fila que sobrevive es la más usada.
  2. taggit solo genera el slug al CREAR (`if self._state.adding and not self.slug`), nunca al renombrar. Dejarlo vacío hacía chocar dos renombrados contra `taggit_tag_slug_key`.
- **taggit es global**: la misma etiqueta la usan biblioteca, blog y documentos. Por eso el comando no hace nada sin `--ejecutar` y todo va en una transacción.


## Fase 5 — Cuota de novedad

Defecto encontrado al preguntar el principal "¿e irá metiendo elementos nuevos por orden?". Reproducido en simulación antes de tocar código: 3 elementos vencidos hace 60 días + 10 recién añadidos, sesión de 8 → **entraban 8 nuevos y 0 de repaso**.

Origen: en la fase 3 di a lo nunca practicado prioridad máxima (`float("inf")`), razonando que si no, el material nuevo nunca entraría en rotación. El razonamiento era correcto; la implementación, demasiado bruta. TODO lo nuevo iba antes que TODO lo demás, así que añadir un libro de 60 ejercicios borraba el repaso durante un mes.

- [x] **C19 — El material nuevo no puede inundar la sesión.** La sesión reserva `PROPORCION_NOVEDAD` (0.25 → 2 de 8) para lo nunca practicado; el resto es repaso. *Probe: el escenario exacto que falló, ahora con los 3 vencidos dentro.*
- [x] **C20 — Sin repaso suficiente, la sesión se llena con material nuevo.** Dejarla a medias habiendo cosas sin tocar sería absurdo. *Probe: 1 conocido + 10 nuevos → sesión de 8 completa, con el conocido dentro.*
- [x] **C21 — Lo nuevo entra por orden de alta en la biblioteca.** Es lo más parecido al orden del libro que existe hoy en el modelo: no hay ningún ordinal de capítulo/ejercicio. *Probe: test de monotonía por pk.*

### Pendiente, y es lo mismo que trocear

El principal preguntaba por el **orden del libro**, y hoy no existe: entre elementos nuevos el desempate es por clave primaria, o sea el orden en que se añadieron. Coincide con el libro solo si se añadieron en ese orden. Modelar libro → sección → ejercicio con un ordinal es la misma pieza que hace falta para trocear el material largo, así que van en una sola fase.


## Fase 6 — Trocear el material largo

Una partitura de veinte páginas no es una unidad de práctica: nadie practica "la sonata entera", practica los compases 30-60. Mientras el PDF fuera un solo elemento con una sola valoración, el sistema no podía saber que la primera parte sale y la tercera no.

Datos que guiaron el diseño: la biblioteca real son **61 imágenes, 27 PDFs, 6 audios y 5 vídeos** repartidos entre 16 usuarios. Lo corto domina, así que trocear tiene que ser opcional y barato, no algo que haya que hacer con los 102 elementos.

Decisiones del principal: **nombre + localizador opcional**, las secciones **sustituyen** al elemento, y se crean **en el visor** mientras practicas.

- [x] **C22 — Un elemento troceado deja de salir entero.** Sus secciones lo sustituyen como unidad de práctica. *Probe: `unidades_de_practica` devuelve las secciones, no el elemento.*
- [x] **C23 — Cada sección lleva su propio historial, nivel y notas.** *Probe: repasar la intro deja el estribillo a `None`.*
- [x] **C24 — Un repaso de sección no cuenta como repaso del elemento entero.** Si contara, trocear haría que la pieza pareciera repasada entera al tocar un trozo. *Probe: test dedicado; `last_review` filtra `section__isnull=True`.*
- [x] **C25 — Las claves de elemento y sección no se pisan.** Los pk de las dos tablas se solapan; la clave lleva el tipo delante. *Probe: test de colisión.*
- [x] **C26 — Los enlaces antiguos siguen funcionando.** Los números pelados en `?items=` siguen siendo elementos; las secciones van con `s` delante. *Probe: test de retrocompatibilidad.*
- [x] **C27 — El visor abre en la página de la sección** si tiene localizador. *Probe: render con `?section=`; `paginaInicial` en el visor de PDF.*
- [x] **C28 — Trocear en un navegador real.** *2026-08-24, cerrada entera.*
  - **El panel, visto y usado** (21/08): crear la sección «Estribillo» desde el visor funciona; el panel se repinta y la fila aparece en la BD.
  - **El salto de página, ahora sí con píxeles.** Con una sección en la página 5 de un PDF de 6, el visor abre en `currentPage = 5`, el indicador pinta **«5 / 6»** y la captura muestra el compás 68 de la partitura, no la primera página: `~/Downloads/martina-c28-pdf-pagina5.png`.
  - **Pasar página funciona**, y lo que parecía un fallo no lo era: la flecha avanza tres cuartos de pantalla dentro de la página y solo cambia de página al llegar al borde. Al llegar, pasa de 5/6 a 6/6.
  - **El `rendering = true` atascado era la pestaña oculta, no un defecto.** Con `document.visibilityState = "hidden"` pdf.js dibuja el canvas pero no resuelve la promesa de `page.render`, así que el guardia de `renderPage` bloquea. **Desbloqueo:** la ventana del perfil de pruebas estaba maximizada pero `focused: false`; `interceptor window focus <id>` la trae al frente y todo resuelve. *Anotado como gotcha del proyecto: cualquier verificación de pdf.js o de transiciones CSS necesita la ventana visible de verdad, no solo `--activate`.*

### Log

- **Dos bugs, ambos cazados por los tests, no por el diseño:**
  1. Al insertar `_tokens_de_sesion` justo encima de `study_session_view`, el `@login_required` que decoraba la vista se quedó decorando el helper. Síntoma: `'list' object has no attribute 'user'`.
  2. `LibraryItem.last_review` contaba los repasos de secciones, porque llevan el `item_id`. Trocear habría hecho que la pieza pareciera repasada entera cada vez que se tocaba un trozo — exactamente lo contrario de lo que se buscaba.
- **El historial previo al troceo se queda en el elemento, sin usarse.** No se puede repartir hacia atrás: nadie sabe a qué trozo correspondía cada repaso.
- **Sin HTMX en el panel**: el visor es una página suelta que no extiende `base.html` y no lo carga. Todo lo suyo va con `fetch`.


## Fase 7 — Los mazos sobreviven al renombrado

Dos defectos que el principal vio en producción el 14/08, los dos regresiones de fases anteriores.

El de fondo: `LibraryDeck` guarda su filtro como una lista de **nombres** en `tags_json` (`models.py:24`) y empareja por comparación de cadenas (`models.py:61`). La migración de la fase 4 renombró filas de `Tag` y no tocó los mazos. Los tres mazos del principal quedaron apuntando a nombres muertos: `guitarra jazz` y `Piano` cuentan 0.

Lo que falló en la verificación de C17: se comprobó que ningún **objeto etiquetado** perdiera etiquetas, y eso estaba bien comprobado. No se buscó si había nombres de etiqueta guardados **fuera de taggit**. La clase de defecto es "copia de un nombre en texto plano que un renombrado deja obsoleta", y `tags_json` era el único sitio.

- [x] **C29 — Ningún comentario de plantilla se ve en la página.** `{# … #}` en Django es de UNA línea; en cuanto ocupa dos, el texto sale renderizado. *Cerrada al nivel de render: barrido de clase sobre todas las plantillas → 2 hermanos, los dos convertidos a `{% comment %}`; y 2 tests de regresión que comprueban que el texto no sale en el HTML. Verificados como falsadores reales: con las plantillas revertidas por `git stash`, los dos fallan.*
- [x] **C30bis — Las dos páginas vistas en un navegador real.** *2026-08-21. Las dos que tocó el arreglo: `/my-library/empezar/` (session_start.html) y el contenido del visor (study_item_content.html). En ninguna aparece el texto de los comentarios en `document.body.innerText`. Interceptor dejó de estar bloqueado el 2026-08-21.*
- [x] **C30 — Renombrar una etiqueta arrastra los mazos que la usan.** *Probe: 11 tests nuevos, incluido el escenario exacto de producción (etiqueta ya migrada, mazo atrás). 105/105 en `my_library`.*
- [x] **C31 — Un mazo nunca se queda sin etiquetas al migrar.** Un `tags_json` vacío hace que `get_matching_item_pks` devuelva la biblioteca entera: el mazo pasaría de contar 0 a contar 51 mintiendo. *Probe: test del mazo huérfano — se queda apuntando al nombre muerto y cuenta 0.*
- [x] **C32 — Los tres mazos del principal vuelven a contar en producción.** *2026-08-15. Antes: `guitarra jazz` 0, `Piano` 0, `caged-system` 11. Ensayo en seco: 2 a arrastrar, `caged-system` no aparece — la salvaguarda funcionando contra datos reales. Después de `--solo-mazos --ejecutar`: **`guitarra jazz` 23, `Piano` 9, `caged-system` 11**. Anti-claim comprobado: taggit sigue en 139 nombres y `MusicTag` en 80, idénticos.*

### Anti-claims

- **No se pierde ningún mazo.** La reparación reescribe `tags_json`; no borra filas de `LibraryDeck` bajo ninguna circunstancia.
- **La reparación no vuelve a tocar etiquetas.** Las 139 de producción ya están migradas y verificadas; `--solo-mazos` existe para no re-ejecutar el renombrado sobre un estado ya migrado.
- **El comentario no se arregla borrándolo.** El texto explica por qué existe el partial; se convierte a `{% comment %}`, no se tira.

### Decisiones

- **El arrastre aplica el MAPA, no el estado actual de `Tag`.** Es lo que permite reparar mazos que se quedaron atrás en una ejecución anterior — el caso de producción, donde las etiquetas ya migraron. Y es idempotente porque ningún destino del mapa es a su vez un origen (comprobado sobre las 187 entradas).
- **Un mazo que se quedaría sin etiquetas se deja roto a la vista.** Contar 0 es visiblemente incorrecto; contar 51 es silenciosamente falso, y el silencio es peor.
- **El arrastre va dentro de la misma transacción que el renombrado.** Quedarse a medias es exactamente el estado del que venimos.
- **Un nombre que sigue vivo no se reescribe.** El defecto es que un mazo apunte a un nombre MUERTO. Si la etiqueta existe, no hay nada que arreglar y reescribirla rompería un mazo que funciona. Al migrar de verdad el conjunto de vivos está vacío (los orígenes acaban de desaparecer en la misma transacción), así que el arrastre alcanza a todos.

### Log

- **La simulación en seco cazó un fallo que habría roto el mazo bueno.** `caged-system -> concepto:caged` también está en el mapa. Aplicarlo a ciegas habría llevado el único mazo que cuenta (11 elementos) a una etiqueta vacía: de 11 a 0, arreglando dos mazos y rompiendo el tercero. De ahí la salvaguarda de nombres vivos.
- **HAY DOS VOCABULARIOS DE ETIQUETAS Y LA MIGRACIÓN SOLO TOCÓ UNO.** Lo destapó el misterio del mazo CAGED. `caged-system` NO existe en `taggit.Tag` desde el 12/08 — y aun así el mazo cuenta 11. Vive en **`cms.MusicTag`** (`cms/models.py:1264`), un modelo aparte con su propia tabla, enganchado como `ParentalManyToManyField` en `ScorePage` y otras tres páginas (`cms/models.py:628, 871, 1014, 1561`). 80 nombres planos, intactos: `guitar`, `guitarra`, `jazz`, `piano`, `modern jazz`… exactamente la fragmentación que las facetas venían a resolver, viva en la otra mitad del sistema. `LibraryDeck.build_tag_map` recoge los nombres de los dos sin distinguir, así que un mazo puede emparejar por `MusicTag`.
- **Eso invalidó la primera versión de la salvaguarda**, que solo miraba taggit: habría dado `caged-system` por muerta y habría arrastrado el mazo bueno a `concepto:caged` — de 11 a 0. Arreglando dos mazos habríamos roto el tercero, que es peor que no tocar nada. Ahora `nombres_de_etiqueta_vivos` consulta los dos vocabularios, y el camino normal usa `nombres_de_musictag_vivos` porque renombrar en taggit no borra el nombre en `MusicTag`.
- **La hipótesis inicial era falsa y solo la mató un dato.** Se conjeturó que `caged-system` había renacido en taggit al añadir material nuevo. `dumpdata` sobre producción lo refutó: no existe. Sin esa consulta, la reparación habría roto el mazo bueno con dos tests en verde respaldándola.
- **Barrido de clase de los comentarios multilínea**: `rg '\{#' --glob '*.html'` filtrando las líneas sin `#}` → exactamente 2 en todo el proyecto, los dos de la semana pasada (`session_start.html:20`, `study_item_content.html:3`). Ampliado a `.txt/.md/.xml/.svg`: ninguno más.
- **Un test escrito antes que la salvaguarda se volvió falso y hubo que reescribirlo.** `test_solo_mazos_no_toca_ninguna_etiqueta` ponía la etiqueta vieja viva y esperaba que el mazo se arrastrase: exactamente el caso CAGED, donde lo correcto es no tocar. El código estaba bien y la expectativa mal. Ahora monta el estado real de producción (etiqueta ya migrada, mazo apuntando al nombre muerto) y comprueba además que el juego de etiquetas no cambia.
- **Docker Desktop no arranca desde una shell no interactiva** (`open -a Docker` vuelve sin error y no deja proceso). Lo abrió el principal a mano. Para la próxima: pedirlo antes de empezar, no a mitad.


## Fase 8 — Un solo vocabulario de etiquetas · TERMINADA

> **Cerrada el 2026-08-25.** Seis pasos, cada uno desplegado y verificado por separado: expandir, migrar, contraer la sesión, el selector y el visor, el sitio entero, y borrar. Ni un elemento de biblioteca perdió una etiqueta en todo el recorrido, comprobado elemento a elemento contra un control tomado antes de empezar.

Cierra lo que la fase 4 dejó a medias. La fase 7 destapó que hay **dos vocabularios**: los ACTIVOS (imágenes y documentos de Wagtail — 95 de los 102 elementos de biblioteca) usan taggit y ya están facetados; los CONTENEDORES (las páginas) usan `MusicTag` y están planos. Mientras siga así, la sesión de estudio no puede agrupar ni filtrar por nada que viva en las páginas.

### Estado real hoy (medido en producción 2026-08-17)

| | |
|---|---|
| `taggit.Tag` | 139, facetadas |
| `cms.MusicTag` | 80, planas |
| Páginas con `MusicTag` | BlogPage 255 · ScorePage 44 · DictadoPage 1 · TestPage 0 |
| Manager de taggit en esas páginas | **ninguno** — en `cms` solo lo tiene `TaggableEmbed` |
| `MusicCategory` | 22, una TERCERA taxonomía que nadie ha tocado |

### El mapa, ya cerrado

`my_library/migracion/mapa_musictags.txt` — 80 entradas: **54 mapeadas hacia 38 destinos, 26 borradas**. *(Eran 38, no 39: el recuento del 17/08 se pasó por uno. Contado por el comando el 21/08, que lee el fichero.)* Borrar cuesta 15 etiquetados, catorce de ellos de una sola pieza.

Decisiones del principal (2026-08-17):

1. **No se crea la faceta `caracter:`.** Las seis etiquetas de estado de ánimo se borran. Una faceta nueva con cinco usos se fragmenta sola.
2. **`ejercicios` es un TIPO de material, no una evaluación.** 40 páginas. Corregida también `evaluacion:ejercicios` en el mapa de taggit — tiene 0 usos, así que no mueve ningún etiquetado.
3. **De las 15 sin uso: se fusionan 3 con destino vivo, se borran 12.** Da igual funcionalmente (nadie las lleva), pero deja el vocabulario limpio.
4. **Los subgéneros de una sola pieza colapsan en su género padre.** Crear nueve estilos para nueve piezas es cómo nació la fragmentación que estamos deshaciendo.
5. **`romantic` se borra** — ambigua entre periodo y carácter.

**Validación hecha sobre los dos mapas:** las 80 cubiertas, ninguna inventada, ninguna duplicada, ninguna faceta desconocida, y sin cadenas origen→destino→origen en ninguno de los dos (siguen siendo idempotentes).

**Y un cruce que conviene repetir en el futuro:** de los 33 nombres presentes en los DOS vocabularios, 30 coincidían y **3 contradecían decisiones de agosto**. `fake-book` volvió a `tipo:libro` por eso. Antes de proponer un mapa nuevo, cruzarlo siempre con el ya aprobado.

### Lo que falta, por orden de riesgo

- [x] **C33 — Las cuatro páginas tienen manager de taggit.** *2026-08-22, commit `547a547`, desplegado y verificado en producción.*
  - `ClusterTaggableManager` como `faceted_tags` + un through model por tipo de página (`BlogPageTag`, `ScorePageTag`, `DictadoPageTag`, `TestPageTag`). Migración `cms.0028`.
  - **El SQL son cuatro `CREATE TABLE` con sus claves e índices. Cero `DROP`, `DELETE`, `UPDATE` o `ALTER` sobre tablas que ya existían** — leído con `sqlmigrate`, no supuesto.
  - **Ensayada sobre una copia de la BD de producción del 20/08 restaurada en local:** `MusicTag` 80, taggit 139, `MusicCategory` 22 sin tocar; `build_tag_map` idéntico elemento a elemento al control previo (102 elementos, 469 etiquetados); los tres mazos siguen en 23 / 9 / 11; `faceted_tags` existe en los cuatro modelos y está a 0 en las 300 páginas.
  - **El editor de Wagtail abre y guarda** — comprobado en navegador real sobre BlogPage 111 y ScorePage 5: el panel «Etiquetas facetadas» aparece, guardar lleva la ScorePage de revisión 5 a 6 y `tags` sigue con `['Coro']`. Es la prueba de que el through model hace su trabajo con el ciclo de revisiones.
  - **Verificado en producción tras desplegar** (2026-08-22, lo lanzó el principal porque el clasificador de permisos bloqueó el comando desde la sesión): `cms.0028` aplicada; `MusicTag` 80, taggit 139, `MusicCategory` 22 y las páginas 255/44/1/0 **idénticos a antes**; `faceted_tags` a **0 en todo el sitio**; los tres mazos siguen en 23 / 9 / 11. En navegador real contra producción abren sin error una BlogPage, una ScorePage y una DictadoPage — los tres tipos que tocó la migración.
  - ⚠️ **Efecto secundario a tener presente: ya no hay guardia.** El aborto de `--ejecutar` existía porque faltaba el campo. Ahora que existe, lo único que separa un ensayo en seco de la migración de verdad es no escribir `--ejecutar`. C34b es un comando, no un accidente posible.
- [x] **C34a — El comando lee el mapa, lo valida y PLANIFICA el re-etiquetado.** *2026-08-22, ensayo en seco contra una copia de la BD de producción del 20/08 restaurada en local. Las cuatro validaciones pasan sobre los datos reales: el mapa cubre las 80 `MusicTag` vivas, ningún destino es a su vez origen, ningún par de orígenes colisiona en minúsculas, ninguna faceta de destino es desconocida. **Plan: 164 páginas (BlogPage 148, ScorePage 15, DictadoPage 1), 531 etiquetados hacia 35 destinos; 9 etiquetas nuevas en taggit y 26 que fusionan con las que ya existen.** 15 tests.*
- [x] **C34b — `--ejecutar` escribe las etiquetas en las páginas.** *2026-08-23, commit `9ed4e1f`, ejecutado y verificado en producción.*
  - **Son dos escrituras por página, y la segunda no es opcional.** La fila viva se actualiza con `.set()` + `save()`. Pero las revisiones que existen hoy se serializaron ANTES de que `faceted_tags` existiera y su JSON no lleva `tagged_items`: **publicar una de ellas después de migrar deja la página sin etiquetas.** No es hipotético — de las 300 páginas de producción, **37 tienen un borrador sin publicar**. Sin sincronizar la revisión, la migración se deshace sola semanas más tarde, una página cada vez, sin que nadie toque nada.
  - **Medido, no supuesto:** `test_publicar_un_borrador_viejo_no_se_lleva_las_etiquetas` falla contra la versión que solo escribe la fila viva. Comprobado desactivando `_sincronizar_revision` y volviendo a lanzarlo.
  - `_sincronizar_revision` reescribe **solo** la lista `tagged_items` del JSON de la última revisión. No crea revisión nueva a propósito: eso enterraría el borrador a medias de esas 37 páginas.
  - **Ensayo con `--ejecutar` sobre la copia de producción del 20/08:** 164 páginas y 531 etiquetados escritos; taggit 139 → 148 (las 9 nuevas previstas); `MusicTag` sigue en 80; **C35 pasa — 0 elementos de biblioteca pierden ninguna etiqueta**; los tres mazos siguen en 23 / 9 / 11; 164/164 revisiones sincronizadas; segunda pasada idéntica **hasta en los pk del through**, así que una ejecución interrumpida se retoma sin pensar.
  - **El editor de Wagtail, en navegador:** pinta `voz:coro` en la ScorePage 5 y guardar desde el admin la conserva (revisión 6 → 7, con `tagged_items` dentro). El envío del formulario se disparó desde la página porque el árbol de accesibilidad del admin vuelve truncado y Interceptor no localiza el botón; el camino de servidor es el mismo.
  - **Desplegado el 2026-08-23** (commit `ab49874` en el servidor) y **ensayo en seco lanzado contra producción**: el plan sale **idéntico al ensayado** — mismo 164 páginas (148 BlogPage, 15 ScorePage, 1 DictadoPage), mismos 531 etiquetados hacia 35 destinos, mismas 9 etiquetas por crear, mismos 15 etiquetados que se pierden en 9 páginas. Comparado con `diff`, no a ojo; lo único que difería eran los marcadores `NUEVA`, porque en la copia local esas 9 etiquetas ya existen tras el ensayo.
  - **Estado de producción justo antes de migrar:** `MusicTag` 80, taggit 139, `faceted_tags` 0, mazos 23 / 9 / 11, y **36 páginas con borrador sin publicar** (eran 37 en la copia del 20/08 — el número se mueve solo, que es exactamente por qué la sincronización de revisiones no es opcional). Copia de seguridad del día: `production_backup_2026_08_23T12_33_22.sql.gz`.
  - **Ejecutado en producción el 2026-08-23** con `just production-migrar-musictags-ejecutar`, y verificado ahí mismo: **148 BlogPage (507 etiquetados) + 15 ScorePage (21) + 1 DictadoPage (3) = 164 páginas y 531 etiquetados**, exactamente el plan. taggit 139 → 148. `MusicTag` sigue en 80: C34b no borra nada. **164/164 revisiones sincronizadas, 0 desincronizadas.** Y las tres tipologías de página siguen abriendo sin error en navegador real contra producción.
- [x] **C35 — Ningún elemento de biblioteca pierde etiquetas.** *2026-08-23, cerrada sobre producción y no por conteo: se comparó el `build_tag_map` completo, elemento a elemento. La huella SHA-256 del mapa canónico de los 102 elementos sale `17ddad1c56f61534` **idéntica** a la del control tomado antes de migrar (`backups/control_c35_antes.json`, 102 elementos, 469 etiquetados). Los tres mazos siguen en 23 / 9 / 11.*
- [x] **C36 — `build_tag_map` lee solo taggit y los mazos van arrastrados.** *2026-08-24, commit `9137cfe`, desplegado y verificado en producción.*
  - `build_tag_map` deja de leer el `MusicTag` plano de `source_page` y pasa a `faceted_tags`. Los tres tests nuevos **fallan contra la lectura vieja**, comprobado revirtiéndola.
  - **El arrastre de mazos va como migración de datos (`my_library.0009`), no como comando a mano.** `deploy-production` lanza `migrate` justo después de levantar el código nuevo, así que el arrastre ocurre en el mismo despliegue y no hay ventana entre las dos cosas. El parseo del mapa se repite dentro de la migración a propósito: tiene que seguir corriendo cuando C37 borre el comando.
  - **El fallo que evita, medido sobre la copia de producción:** con el código nuevo y **sin** arrastrar, el mazo `caged-system` cae a **0**. Es el fallo del 12/08 exacto. Después de arrastrar vuelve a 11 y los tres quedan en **23 / 9 / 11**.
  - **Verificado en producción tras desplegar:** `my_library.0009` aplicada; los mazos quedan en **23 / 9 / 11** y `caged-system` ya apunta a `concepto:caged`. La biblioteca pasa de 469 a 320 etiquetados y de **169 planas a 1**, que es la caída esperada al irse el vocabulario viejo. **Ningún elemento pierde una etiqueta facetada** (comparación elemento a elemento contra el control previo): 0 pierden, **42 ganan, 45 facetas ganadas**. Las páginas siguen abriendo sin error en navegador real.
- [x] **C37a — El API escribe en los dos vocabularios y se limpian las huérfanas.** *2026-08-24, commit `94e5603`, desplegado y verificado: `MusicTag` 80 → 65 en producción.* Los tres endpoints escribían solo el `MusicTag` plano, y por ahí publica **PublishIES**: cada artículo nuevo nacía con etiquetas que la sesión ya no lee. Migración `cms.0029`: fuera las **15 `MusicTag` sin ninguna página**, quedan 65 todas en uso. *(Superada en parte por C37b, que retira el vocabulario viejo del API entero.)*

- [x] **C37b — El sitio entero corre sobre el vocabulario facetado.** *2026-08-24, commits `bfa3646`, `b79737a`, `e2d8d42`, desplegado y verificado en producción.*
  - **Lectores migrados:** búsqueda y filtro del índice de la biblioteca musical, la lista de etiquetas de la UI de filtros (`all_tags` pasa de `MusicTag.objects.all()` a las que de verdad cuelgan de alguna página: **35 en vez de 65**), `ScorePage.get_all_tags`, la vista de partituras filtradas y **15 plantillas**.
  - **Escritores migrados**, y aquí el conteo inicial se quedó corto: los tres endpoints del API, `my_library.suggest_tags` (combinaba los dos vocabularios) y **`content_publisher._get_or_create_tag`**, que creaba `MusicTag` desde el publicador de IA y que la primera medición no separó de los lectores.
  - **El API cambia de contrato:** `tag_ids` → `tags` con nombres facetados. `tag_ids` sigue en el esquema **solo para devolver un 400 explícito**; ignorarlo en silencio dejaría a un cliente viejo publicando sin etiquetas. Una faceta inventada también da 400.
  - **El color de las etiquetas era un campo de `MusicTag` que taggit no tiene** — 65 etiquetas con 8 colores puestos a mano. Ahora lo da la **faceta** (`cms_tags.color_de_faceta`): el color pasa a decir "esto es un instrumento" en vez de no decir nada, y una etiqueta nueva nace con el suyo sin que nadie se lo ponga.
  - **Estado: `MusicTag` ya no lo toca ningún camino vivo.** Quedan el modelo, sus cuatro campos y tres comandos de migración gastados (`migrar_etiquetas`, `migrar_musictags`, `migrate_tags`).
  - **Ensayado contra una copia de producción del 24/08** (2026-08-24, commit `e2d8d42`): con el código nuevo aplicado sale **idéntico a producción** en todo — páginas 255/44/1/0, taggit 148, 531 etiquetados, mazos 23 / 9 / 11, selector 20 valores en 6 facetas, y la huella del `build_tag_map` de los 102 elementos `f22a14cf7574f3c3`, la misma. **El barrido no mueve ni un dato**: solo cambia de dónde se lee.
  - **Verificado en navegador contra la copia:** el índice pinta las etiquetas facetadas con el color de su faceta (`estilo:` rosa, `instrumento:` azul) y filtrar por `voz:coro` estrecha de 6 elementos a 4. Captura: `~/Downloads/martina-c37b-etiquetas-por-faceta.png`.
  - **Tres lectores más aparecieron fuera de `cms/`**, que el primer barrido no cubrió: la búsqueda de `ScorePage` en `clases/views.py`, las etiquetas de la partitura relacionada en `clases/models.py` y el visor de blog de `clases`. Es la tercera vez en esta fase que el alcance sale mayor al medirlo; anotado como patrón, no como accidente.
  - **PublishIES actualizada** (`~/.claude`, commit `88d4a30`): la opción pasa de `--tag-ids` a `--tags`, y su SKILL.md lista las 18 facetas válidas. Documentación del repo al día (`docs/AI_PUBLISHING.md` decía "MusicTag: color aleatorio").
  - **Verificado en producción tras desplegar** (2026-08-24, servidor en `073e74c`): los ocho indicadores **idénticos al ensayo y a antes del despliegue**, huella del `build_tag_map` `f22a14cf7574f3c3` incluida; `MusicTag` en 65 tras la `0029`. En navegador contra el sitio real: el índice pinta 10 etiquetas facetadas coloreadas por faceta y filtrar por `voz:coro` estrecha de 6 elementos a 4. Captura: `~/Downloads/martina-produccion-etiquetas-faceta.png`.
  - **C37b no tenía comando que correr.** Su único cambio de datos es la migración `cms.0029`, que `deploy-production` aplica solo. Lo demás es de dónde se lee, y eso viaja con el código. Antes hay que decidir qué se hace con esos tres comandos, porque borrar el modelo los rompe al importar, y las pruebas de `migrar_etiquetas` son ~20 tests que documentan defectos reales de las fases 4 y 7. También falta desplegar todo esto y ensayarlo contra la copia.
  - **Sin decidir, la misma pregunta de siempre:** `MusicCategory` (22) sigue intacta. Se mantiene el anti-claim de la fase: no se toca aquí.
  - **Deuda encontrada de paso, no tocada:** `test_pagination_logic_js_loading` y `test_tag_filter_links` esperan una barra de filtros que la plantilla `_app` ya no tiene. Fallaban desde antes de la fase 8. Los otros 3 que fallaban eran de `RequestFactory` sin `user` y quedan arreglados (`98663e1`).

- [x] **C37c — Borrado `MusicTag`, sus cuatro campos y los comandos gastados.** *2026-08-25, commit `32a71c6`, desplegado y verificado en producción.*
  - Migración `cms.0030`: **cinco `DROP TABLE` y nada más**, leído con `sqlmigrate`.
  - **Se van con el modelo:** `migrar_musictags` (430 líneas, su trabajo está hecho y verificado en producción), `cms.migrate_tags`, y 25 tests que solo tenían sentido con dos vocabularios. **`migrar_etiquetas` se queda**, sin la salvaguarda del vocabulario doble: renombrar etiquetas de taggit sigue siendo útil. **`mapa_musictags.txt` se queda también**: lo lee `my_library.0009` al migrar.
  - **Y tres sitios más del mismo tipo que el barrido no cubría.** Un `LibraryItem` puede apuntar a un **documento**, a una **imagen** o **a una página**; los dos primeros etiquetan en `tags` y la página en `faceted_tags`. Mirar solo `tags` dejó al **elemento 69 sin su `concepto:canon`**. Son 2 elementos de 102 y por eso pasó desapercibido. Cubierto ahora con un test, y arreglado igual en `clases/models.py`, en `library_filter_controls.html` y en cuatro `prefetch_related("tags")` sobre querysets de páginas.
  - **Efecto medido sobre la copia:** la biblioteca vuelve a **320 etiquetados**, **cero planas** (quedaba una) y el selector **gana un valor**: `concepto:canon`, que antes llegaba sin faceta y no se podía elegir. **21 valores en 6 facetas.**
  - **Verificado en producción tras desplegar** (2026-08-25, servidor en `38d61f0`): `cms.0030` aplicada, **cero tablas del vocabulario viejo** (`cms_musictag` y los cuatro `*_page_tags` ya no existen) y el modelo no se puede ni importar. La biblioteca: **102 elementos, 320 etiquetados, cero planas**; los mazos en 23 / 9 / 11; el selector en **21 valores**. El elemento 69 lleva su `concepto:canon`. En navegador contra el sitio real: el índice sin error con 10 etiquetas coloreadas, y **filtrar por `concepto:canon` devuelve 1 elemento** — una etiqueta que antes no se podía elegir.
  - **El nombre `faceted_tags` se queda.** El plan original lo renombraba a `tags` al final; no se hace. Renombrar son veinte ficheros para ganar cinco letras, y el nombre actual dice lo que es. Reversible si el principal prefiere lo otro.

### Decisión de secuencia — expandir, migrar, contraer (2026-08-21)

El campo `tags` de las cuatro páginas **ya está ocupado** por el `ParentalManyToManyField` a `MusicTag`. No se puede añadir el manager de taggit con ese nombre, y renombrar de golpe abre una ventana en la que `build_tag_map` lee un campo vacío y los mazos cuentan 0. Es exactamente el fallo del 12/08 otra vez.

Así que se hace en tres tiempos, y ninguno rompe el sitio por sí solo:

1. **Expandir** (C33) — el manager nuevo entra como `faceted_tags`, junto al `tags` de siempre. Nadie lo lee todavía.
2. **Migrar** (C34b, C35) — el comando llena `faceted_tags` desde el mapa y se comprueba la paridad elemento a elemento. Las dos vías coexisten.
3. **Contraer** (C36, C37) — `build_tag_map` pasa a leer solo taggit, y solo entonces se borra `tags` y `faceted_tags` se renombra a `tags`.

El coste es un nombre feo viviendo unos días. Lo que compra es que en ningún momento hay un despliegue con las etiquetas de las páginas en el aire.

### El hallazgo de C36: la fase no compra lo que decía comprar

**Verificar C36 destapó un error de diagnóstico en el planteamiento de toda la fase 8.** La fase se justificó con esta frase, que está escrita arriba: *"mientras siga así, la sesión de estudio no puede agrupar ni filtrar por nada que viva en las páginas"*. Es cierta. Lo que no es cierto es que el vocabulario partido fuera la causa.

**Hay dos caminos de etiquetas, no uno**, y solo uno pasa por `build_tag_map`:

| Camino | Quién lo usa | ¿Mira `source_page`? |
|---|---|---|
| `build_tag_map` | emparejar mazos (`views.py:866`, `:892`) | Sí. C36 lo arregla. |
| `get_content_tags` → `session._etiquetas` | **el selector de facetas, la agrupación temática** y las etiquetas que pinta el visor | **No. Nunca ha mirado la página.** |

*Probe, sobre la copia de producción:* el elemento 121 recibe `estilo:jazz-moderno` por `build_tag_map` y **no** por `_etiquetas`. Y el selector de facetas da **19 valores en 6 facetas idénticos antes y después de C36** — medido revirtiendo la lectura y volviéndola a poner.

**Lo que la fase 8 sí ha comprado**, sin adornos: un solo vocabulario; **169 etiquetas planas que ensuciaban `build_tag_map` reducidas a 1**; el emparejamiento de mazos por fin sobre nombres facetados; y la precondición sin la cual arreglar el otro camino no serviría de nada — si `get_content_tags` empezara a leer la página con el vocabulario viejo, metería esas 169 planas, que no agrupan ni filtran.

- [x] **C40 — El selector de facetas y la agrupación ven las etiquetas de la página.** *2026-08-24, commit `c6360ab`, desplegado y verificado en producción: el selector da 20 valores en 6 facetas con `estilo:jazz-moderno` dentro, y los mazos siguen en 23 / 9 / 11. Opción A, elegida por el principal: una sola definición de "las etiquetas de este elemento", las suyas más las de su `source_page`, y se pintan también en el visor.*
  - **Efecto medido sobre la biblioteca real:** el selector pasa de 19 a 20 valores y aparece `estilo:jazz-moderno`, que cubre los capítulos del libro de Jens Larsen y **antes no se podía elegir**. Solo entran las facetadas: el `MusicTag` plano no.
  - **Los tres tests clave fallan** contra la versión sin el aporte de la página, comprobado desactivándolo.
  - **La precarga, que salió de medir el coste.** Subir a `source_page.specific` por elemento son ~3 consultas cada uno: 51 elementos pasaban de 107 a **254 consultas** y de 74 a **222 ms**, y crece en línea recta — a 500 elementos, más de dos segundos en la página con la que se arranca cada sesión. `precargar_etiquetas_de_pagina` lo deja en **124 consultas y 84 ms**, o sea **+17 consultas y +10 ms** sobre no tener etiquetas de página en absoluto. `build_tag_map` la usa también. Un test comprueba que precargar y no precargar dan exactamente lo mismo.

### Anti-claims

- **Ningún mazo cambia de recuento** salvo por ganar elementos. Los tres actuales cuentan 11 / 23 / 9; ese es el control.
- **No se toca `MusicCategory`** en esta fase. Pero queda escrito que es la tercera taxonomía y que unificar etiquetas sin decidir qué pasa con ella repite la media migración.
- **No se cambia ningún tipo de página.** El debate ScorePage → BlogPage es aparte (ver abajo) y no bloquea nada de esto.

### Log de la fase 8

- **El ensayo en seco se hizo contra una copia, no contra producción.** Backup del 20/08 bajado con `just production-download-backup postgres …` y restaurado en local con `just restore-db`. Se reutilizó el backup que ya había en el servidor en vez de crear uno nuevo: la receta `production-backup-db` borra los antiguos y deja solo 2. La copia cuadra con el ISA en los ocho números que había medidos (80 MusicTag, 139 taggit, 22 MusicCategory, BlogPage 255 / ScorePage 44 / DictadoPage 1 / TestPage 0, 102 elementos de biblioteca).
- **Los 15 etiquetados que cuesta borrar están confirmados.** El mapa lo predijo el 17/08 y los datos reales dan exactamente 15, repartidos en 9 páginas. `romantic` es la única que aparece dos veces. **Ninguna página se queda sin etiquetas**, así que no hay que decidir nada a mano.
- **De los 38 destinos del mapa, solo 35 llegan a usarse.** Los tres que faltan —`concepto:lectura-musical`, `concepto:solfeo`, `autor:willems`— vienen de orígenes con 0 usos: las `fusiones sin coste` de la decisión 3. Coherente, no hay nada roto.
- **El informe se cambió a mitad del ensayo para que enseñe la pérdida.** Enseñaba las 531 etiquetas que se ganan y callaba las 15 que se van. Un resumen que solo cuenta lo que gana invita a aprobar sin mirar.
- **De las 44 ScorePage solo 15 llevan MusicTag**, y de las 255 BlogPage, 148. El resto entra en la migración sin cambios.

### El debate ScorePage → BlogPage, para no repetirlo

El principal propuso el 17/08 eliminar `ScorePage` y pasar todo a `BlogPage` bajo la biblioteca musical. Análisis crítico hecho ese día; conclusión: **la parte de las etiquetas es la buena y la de los tipos de página es limpieza disfrazada de arreglo.** Los tres argumentos, con los números:

1. **Sería la tercera unificación y las dos anteriores están a medias.** `content_hub` vacío y montado; las facetas, a medio vocabulario. El patrón no es "el modelo está mal elegido", es "las migraciones se empiezan y no se cierran".
2. **`source_page` está en 98 de los 102 elementos y es de donde salen las etiquetas.** Cambiar el tipo de página en Wagtail no es editar: o creas páginas nuevas —y revientas las 98— o haces cirugía sobre `page_ptr`. Y `clases.GroupLibraryItem.get_related_scorepage()` busca ScorePages hacia atrás; habría que reescribirlo.
3. **`BlogPage` no es más simple, es especializado en otra cosa.** Obliga a `date` e `intro`; y se pierden `composer` (**43 de 44** ScorePages lo usan), el bloque `metadata` (12) y `embed` (4). El candidato honesto para "un solo tipo" sería un `MaterialPage` genérico, no BlogPage.

Datos que salieron de paso: los `bookmarks` de ScorePage **no se usan en ninguna de las 44** — y `ItemSection` (fase 6) ya hace eso mejor y por usuario. Y `BlogPage.parent_page_types` **ya incluye** `MusicLibraryIndexPage`, así que se puede dejar de crear ScorePages hoy mismo sin migrar nada.

Secuencia acordada: **A)** esta fase 8. **B)** congelar `ScorePage` y crear lo nuevo como BlogPage — cero riesgo, y el problema deja de crecer. **C)** enterrar o resucitar `content_hub`. **D)** las 44 ScorePages, solo si sigue doliendo, y con un plan explícito para las 98 `source_page`.

## Fase 9 — La telemetría deja de escribir en la sesión de autenticación

> Run 9 · 2026-08-19 · Goal verbatim: *"ok, quiero que hagas lo más limpio y con visión de futuro"*
> Disparador: el login con Google fallaba con `Codigo: unknown` y sin línea de `Excepcion`.

### El defecto, medido antes de tocar código

La pantalla de error de allauth se reprodujo por HTTP contra producción **antes** de leer el código sospechoso.
La ausencia de la línea `Excepcion` es el discriminador: la plantilla solo la pinta si hay excepción, y en
allauth 65.3.1 solo dos rutas fallan sin excepción. Los logs de nginx descartan una (los dos callbacks traían
`code` y `state` y **ningún** `error=`), así que queda `_get_state()` devolviendo `None`:
`render_authentication_error(request, provider)` con sus defaults `error=UNKNOWN, exception=None`.

Es decir: Google consintió bien y allauth no encontró **su propio `state`** en la sesión.

Dos defectos independientes, ambos de la misma clase — *plomería de UI/telemetría escribiendo en la sesión de auth*:

- **D1 · `analytics/views.py:16-19` llamaba a `request.session.create()`.** En Django 5.0.11 (verificado con
  `inspect.getsource` dentro del contenedor de producción) `create()` acuña una clave nueva, guarda una sesión
  vacía y marca `modified = True`, así que `SessionMiddleware` emite un `Set-Cookie: __Secure-sessionid` nuevo.
  Una petición de telemetría sin cookie **reescribía la cookie de sesión del navegador** a mitad del login.
- **D2 · `AppModeMiddleware` escribía `app_mode` en cada petición no exenta, y `/analytics/track/` no estaba
  exenta.** `SessionBase.__setitem__` marca `modified = True` siempre, aunque el valor no cambie. El backend de
  sesión en BD serializa el diccionario **entero**, así que dos peticiones concurrentes son un
  read-modify-write sin bloqueo: la que carga antes y guarda después **borra `socialaccount_states`**.
  Esto ocurre aunque la cookie no cambie, y por sí solo basta para romper el login.

Cuadra con la cronología de nginx al segundo: `18:09:21` authorize y `POST /analytics/track/` en el **mismo
segundo**; `18:09:27` callback y otro `track/` en el mismo segundo.

### Anti-claims

- **A9.1** — La analítica no pierde su continuidad histórica: las 338 filas de `UserSession` y sus 3.917
  `PageVisit` / 5.579 `Interaction` sobreviven con sus mismos valores y relaciones.
- **A9.2** — El endpoint de telemetría no vuelve a tocar `request.session` en ninguna de sus ramas. Ni leer
  para escribir, ni `create()`, ni `save()`.
- **A9.3** — No se cambia el comportamiento visible de `app_mode`: quien navega por `/incidencias/` sigue
  viendo su plantilla base, y el logout sigue devolviéndole a su landing.
- **A9.4** — No se ejecuta ningún borrado de datos en producción en este run. La limpieza de sesiones caducadas
  usa el comando estándar de Django, que por definición solo toca filas ya expiradas.

### Claims

- [x] **C9.1 — La telemetría no toca la sesión.** *Probe: `grep -rnE 'request\.session[.\[]|request\.session *=' analytics/*.py` → 0 usos en código. La única aparición de la cadena es el docstring de `resolve_visitor_id` que explica la prohibición.*
- [x] **C9.2 — Un POST de telemetría no altera la cookie de sesión.** *Probe: `TelemetryDoesNotTouchSessionTests::test_tracking_does_not_issue_a_session_cookie` y `::test_tracking_does_not_rotate_an_existing_session`. El primero FALLA contra el middleware antiguo y pasa contra el nuevo — comprobado revirtiendo el fichero y volviéndolo a poner.*
- [x] **C9.3 — El `state` de OAuth sobrevive a la telemetría.** Cerrada por `test_tracking_performs_no_session_write_at_all`, que es la condición necesaria y sí es comprobable: **sin escritura no hay read-modify-write y sin eso no hay carrera**. *Probe: el test falla contra el middleware antiguo (metía `app_mode='main'` en cada POST a `/analytics/track/`) y pasa contra el nuevo.* **Anotado con honestidad:** la carrera en sí necesita concurrencia real y un cliente de test secuencial no la reproduce; `test_oauth_state_survives_a_tracking_request` documenta el invariante pero pasaría también sobre el código viejo.
- [x] **C9.4 — `AppModeMiddleware` solo escribe cuando el modo cambia.** *Probe: `AppModeMiddlewareTests`, 6 tests — el defecto no se persiste, repetir incidencias no vuelve a marcar `modified`, y `/analytics/` nunca decide el modo.*
- [x] **C9.5 — La identidad de analítica es propia, validada y compatible.** *Probe: `VisitorIdentityTests` — UUID válido mide, `session_key` antiguo sigue midiendo, y basura (path traversal, 200 caracteres, vacío, entero, nulo) se ignora con 202 sin crear filas.*
- [x] **C9.6 — La suite sigue en verde, sin regresiones nuevas.** *Probe: suite completa con `--create-db` a ambos lados de un `git stash`. **Antes: 9 failed / 323 passed. Después: 7 failed / 339 passed.** Los 9 de partida son exactamente los preexistentes documentados; los 2 de analytics eran un `reverse('track_activity')` sin namespace y quedan arreglados de paso. Los 7 restantes (5 cms, 2 incidencias) siguen intactos: no los toca este run.*
- [x] **C9.7 — Verificado en producción tras desplegar.** Desplegado el 2026-08-20; `analytics.0003` aplicada OK. **El principal confirma que ya entra con Google.** El mecanismo estaba además verificado de extremo a extremo por HTTP contra producción: se arranca el login, se dispara una petición de telemetría con esa misma cookie (la que antes rompía el flujo) y se vuelve por el callback; el `state` sigue ahí y el flujo llega al token endpoint de Google, fallando solo por el `code` falso y pintando la línea de `Excepcion` que la captura original NO tenía. Y la página de login está vista en navegador real: `~/Downloads/martina-login-verificado.png`.

### Decisiones

- **La identidad de analítica se toma del cliente, no del servidor.** `analytics.js` ya generaba un UUID v4 y
  lo guardaba en `localStorage`, mandándolo en el cuerpo como `session_key`; el backend lo **ignoraba** y usaba
  la sesión de Django. El arreglo limpio no es inventar un mecanismo nuevo: es usar el que ya estaba escrito.
  El servidor lo valida como UUID y descarta lo que no lo sea.
- **Sin `visitor_id` válido no se registra nada (202), no se genera uno en servidor.** Generarlo crearía una
  fila por petición para cualquier bot que golpee un endpoint que es `csrf_exempt`. El JS siempre manda uno,
  así que ningún usuario real pierde medición.
- **`app_mode` deja de persistir el valor `'main'`.** Es el defecto: los dos únicos consumidores
  (`utils/context_processors.py:10` y `users/adapters.py:114`) comparan contra `'incidencias'` y nada más, así
  que su ausencia ya significa "main". No guardarlo es lo que corta de raíz una fila de sesión por visitante
  anónimo — el origen real de las 107.016 sesiones en la tabla frente a solo 338 `UserSession`.
- **`/analytics/` pasa a ser ruta no navegacional.** Además de la carrera, había un bug latente: navegando por
  `/incidencias/`, el POST de telemetría caía en la rama `else` y devolvía el modo a `'main'`.
- **Renombrado `session_key` → `visitor_id` en `UserSession`.** El campo llevaba meses mintiendo. Son 338
  filas y en Postgres `RENAME COLUMN` es metadata, así que es barato hacerlo bien ahora.
- **El backend acepta `visitor_id` y `session_key` durante la transición.** Los navegadores con el JS viejo
  cacheado siguen midiendo sin día de corte.

### Log

- **El bug se reprodujo antes de leer el código sospechoso**, por HTTP contra producción: un callback sin cookie de sesión pinta `Codigo: unknown` sin línea de `Excepcion`, idéntico a la captura del principal; el mismo callback CON cookie llega hasta el token endpoint de Google y pinta `Excepcion: invalid_grant`. Ese A/B es lo que localizó el fallo en `_get_state()` y descartó todo lo demás.
- **Barrido de la clase de defecto** (`plomería escribiendo en la sesión de auth`): `grep -rn "session\.create()\|session\.save()\|session\.cycle_key\|session\.flush"` sobre todo el árbol devuelve dos sitios vivos, los dos arreglados. El tercer hit, `clases/views.py:379`, es un `ClassSession.save()` del ORM, no una sesión de Django — verificado leyendo el bloque.
- **La migración se escribió a mano.** `makemigrations` no detecta renombrados sin preguntar por consola y proponía drop + add, que habría tirado las 338 filas. `RenameField` + `AlterField` las conserva. `makemigrations --check --dry-run` sale limpio.
- **`unique=True` se comprobó contra producción antes de escribirlo**: 338 filas, 0 grupos duplicados, 0 vacías, todas de 32 caracteres. Las nuevas serán UUID de 36; `max_length=40` cubre ambas.
- **Deuda encontrada, no tocada:** `config/settings/test.py:36` tiene `MEDIA_URL = "http://media.testserver"` sin barra final, lo que rompe `manage.py <lo que sea>` bajo settings de test con `urls.E006`. `pytest` no ejecuta system checks, así que la suite nunca lo notó. Se esquivó con `--skip-checks`; el arreglo es un carácter, pero es de otro run.
- **Docker Desktop no arranca en esta máquina** (el proceso muere sin dejar el daemon en pie), así que la suite se corrió en un venv con `uv` contra el Postgres local de homebrew en vez de `just test`. Mismo `--ds=config.settings.test`.

### Deploy — 2026-08-20

- Copia de la BD de producción **antes** de tocar el esquema: `production_backup_2026_08_20T12_55_20.sql.gz`.
- `analytics.0003_usersession_visitor_id` aplicada OK. **Datos intactos tras el RENAME**: 338 `UserSession`, 3.917 `PageVisit`, 5.579 `Interaction`, idénticos a la medición previa (A9.1 cerrada).
- Los cinco contenedores en `running`. La página de login responde 200 con el botón de Google.
- Los dos únicos `ERROR` posteriores al deploy son de la propia prueba de extremo a extremo, con `code` falso. Que digan `exception=Error retrieving access token` en vez de `exception=None` **es la prueba**: el `state` se encontró.
- `martina_bescos_app.users.tasks.clear_expired_sessions` registrada en el consumidor de huey; primer barrido a las 04:30. Hoy la tabla `django_session` tiene 107.016 filas y solo ~17.400 vivas; mañana debería bajar sola.
- La fila de analítica que creó la prueba se borró después (2 objetos: la sesión y su visita en cascada). Vuelta a 338.

## Fase 10 — La nota se guardaba en el item equivocado

> Encontrado el 2026-08-21 al ir a cerrar C12, la claim que llevaba desde el 12/08 esperando un navegador. Es el argumento entero a favor de la verificación en navegador: **ningún test de la suite podía cazarlo**, porque el defecto vive en el orden del DOM, no en Python.

### El defecto, medido antes de tocar código

El bloque de notas y etiquetas (`#study-item-meta`) nace dentro de `#study-content` y `moveMetaToFlyout()` lo **mueve** al panel. La trampa: `#flyout-meta-section` va ANTES que `#study-content` en el documento, así que a partir del segundo item `document.getElementById('study-item-meta')` devolvía el bloque **viejo** —el que ya estaba en el panel— en vez del recién cargado.

Consecuencias, las dos medidas en Chrome real contra el local:

1. **El panel pintaba el item anterior.** Con el visor enseñando «Pentatonica pos 2» (1/6 → 2/6), el panel llevaba `data-item-pk=34`, que es el item 1, y mostraba su nota.
2. **Y escribir ahí guardaba en el item anterior.** `saveNota` usa `meta.dataset.itemPk` del mismo bloque rancio. *A/B con la BD: con el visor en el item 2, escribí «NOTA ESCRITA MIRANDO EL ITEM 2» → `LibraryItem 34.notes` = ese texto, `35.notes` = `''`.* Después del arreglo, la misma acción → `34` intacto, `35` con el texto.

Síntoma lateral que lo delató: `document.querySelectorAll('#study-item-meta').length === 2`. Un id duplicado.

### El arreglo

Dejar de buscar por id global y buscar dentro del contenedor que toca en cada caso: `moveMetaToFlyout` toma el bloque de `#study-content`, y `saveNota` lo toma de `#flyout-meta-section`, que es donde vive el del item actual. Los listeners se enganchan sobre `meta.querySelector`, no sobre el documento.

- [x] **C38 — El panel enseña el item que está en pantalla.** *Probe: `data-item-pk` del bloque del panel == item cargado, y `querySelectorAll('#study-item-meta').length === 1`. Antes: 34 vs 35 y length 2. Después: 35 vs 35 y length 1.*
- [x] **C39 — La nota se guarda en el item que estás mirando.** *Probe: el A/B contra la BD de arriba. Es el falsador real: con el código viejo la fila que cambia es la equivocada.*

### Anti-claims

- **No se toca `moveMediaToFlyout`.** Usa el mismo `getElementById`, pero COPIA el html a otros ids en vez de mover el nodo, y el original muere con cada `innerHTML` de `#study-content`. No duplica nada. Comprobado, no supuesto.
- **Ningún test de Python cambia de resultado.** 122/122 en `my_library` antes y después. Eso no es una virtud del arreglo: es la prueba de que la suite era ciega a esto.

### Log

- 🧹 CLASE BARRIDA: «`getElementById` sobre un nodo que se mueve entre contenedores». Enumerada con `grep -rn "appendChild\|outerHTML" my_library/templates/` → un solo nodo movido en todo el visor (`#study-item-meta`, consultado en dos sitios). Los dos arreglados; `moveMediaToFlyout` descartado por inspección, no por parecido.
- **Sin test de regresión en Python, a conciencia.** El defecto es orden del DOM en el navegador; un test de Django renderiza la plantilla y no ejecuta el JS que mueve el nodo. El falsador de esta clase es la comprobación en navegador, y por eso C12 existía.
- **La plantilla no se recargó sola.** Editar `study_viewer.html` y recargar seguía sirviendo el HTML viejo; hizo falta `docker compose restart django`. Media hora de creer que el arreglo no funcionaba. Anotado para la próxima.

## Fase 11 — Estudiarse un libro · DESPLEGADA

> **Lo que el principal pidió el 2026-08-25:** *"tener las cosas ordenadas en un libro y que la cola de estudio, cuando me pongo como objetivo estudiarme ese libro, se vaya rellenando con material nuevo"*. Y el 2026-08-26, sobre la interfaz: *"un botón en el que pueda haber información sobre ese elemento añadido: texto que acompaña a esa imagen en el libro o un enlace a la página del libro"* y *"poder eliminar ese elemento de la lista de estudio si resulta que no me convence"*.

### Lo que ya funciona, para no reconstruirlo

- **La cola ya se rellena sola con novedad**: una cuarta parte de cada sesión (fase 5).
- **`ItemSection` ya trocea** un capítulo largo y lo devuelve en orden.
- **`BlogPage.get_images/get_pdf_blocks/get_audios`** ya enumeran los medios de un capítulo, incluidas las imágenes incrustadas en el texto, que son las que de verdad usan estos libros.

### El plan cambió al medirlo, y esto es lo que lo cambió

El plan original era un botón que metiera el libro entero. **Medido sobre datos reales, ese botón es una mala idea:**

- *Ukulele Aerobics*: 40 capítulos, **283 medios practicables**, cero en la biblioteca. Meterlos todos deja una biblioteca de 51 elementos convertida en 334, el 85% un solo libro.
- *Jens Larsen*: 93 medios, y el principal metió **23**. Comparados los 23 elegidos con los 70 descartados: **indistinguibles** por tipo o por título. «Example 1c» dentro, «Example 1a» fuera. Eligió por criterio musical, y no hay regla que lo reproduzca.

**Decisión del principal (opción C, 2026-08-26): no se copia nada por adelantado.** El objetivo guarda la intención, y el `LibraryItem` se crea **cuando al elemento le toca salir en la cola**. La biblioteca deja de ser un almacén que hay que llenar antes de estudiar y pasa a ser el registro de lo que has tocado. El volumen deja de ser un problema en vez de amortiguarse.

### Criterios

- [x] **C41 — El material de un libro se enumera en orden de libro.** *`libros.material_del_libro`: capítulos por el árbol de Wagtail, y dentro, los medios en orden de aparición. Medido: Ukulele Aerobics 283 medios en 40 capítulos, Jens Larsen 93 en 6.*
- [x] **C42 — "Estudiarme este libro" es un objetivo que se fija y se quita.** *`LibraryGoal`, único por (usuario, libro). No depende de ninguna etiqueta, así que funciona con un libro que no tenga ninguna. **Botón en la página del libro**, el mismo pone y quita. Quitarlo no borra lo practicado: el objetivo es la intención, no el material.*
- [x] **C43 — La cola crea el elemento cuando le toca, no antes.** *Probado: fijar el objetivo deja la biblioteca en 0 elementos; `rellenar_para_sesion` crea exactamente los que hacen falta para la cuota de novedad, en orden de libro. Contra datos reales: fijar Jens Larsen creó 0, y una sesión creó 2, los dos primeros del libro.*
- [x] **C44 — Desde el visor se ve de dónde viene el elemento.** *Ventana emergente, no navegación. Verificado en navegador con el libro real: trae el párrafo del capítulo 1 («Let's begin by looking at the construction of the basic major scale…») y el enlace al capítulo.*
- [x] **C45 — Descartar un elemento, y que no vuelva.** *Verificado en navegador: descartar avanza el visor de 1/2 a 1/1, la fila queda marcada y el objetivo pasa a ofrecer 1c y 1d, saltándose lo descartado. El falsador: borrar la fila a secas no vale, la creación perezosa la recrearía.*
- [x] **C46 — Se ve por dónde vas.** *Con el objetivo puesto, el progreso sale al lado del botón: «1 de 6». Cuenta **capítulos tocados, no elementos** — «Semana 12 de 40» dice algo y «87 de 283 elementos» no dice nada. Un capítulo cuenta en cuanto hay un repaso suyo.*

### Anti-claims

- **La cuota de novedad no se toca.** El objetivo acota QUÉ entra, no cuánto ni el equilibrio con el repaso. Saltárselo convierte estudiar un libro en un atracón y rompe lo que arregló la fase 5.
- **Un objetivo no obliga.** Poner un libro como objetivo no puede impedir practicar otra cosa: la sesión sigue siendo del principal, no del plan.
- **Descartar no borra el historial.** Si el elemento llegó a practicarse, su `ReviewLog` y sus notas se quedan. Descartar dice "no me lo ofrezcas más", no "haz como si no hubiera pasado".
- **No se toca `MusicCategory`.** Sigue siendo la tercera taxonomía sin decidir, y sigue fuera de alcance.

### Verificación del bucle entero (2026-08-26)

Contra la copia de producción, con el libro de Jens Larsen y por la interfaz de verdad, no por la shell:

1. Pulsar «Estudiarme este libro» → el botón pasa a «✓ Estudiando este libro», sale «0 de 6» y se crean **cero elementos**.
2. Lanzar una sesión → se crean **los dos primeros del libro, en orden** (`Example 1a` y la primera imagen del capítulo 1) y el visor abre con ellos.
3. «De dónde viene» → trae el párrafo real del capítulo («Let's begin by looking at the construction of the basic major scale…») y el enlace.
4. «Descartar» → el visor avanza de 1/2 a 1/1, la fila queda marcada y el objetivo pasa a ofrecer 1c y 1d.
5. Valorar un elemento → al volver a la página del libro el progreso dice **«1 de 6»**.

*No hay captura de pantalla: `Capture.sh` falló con `tabCapture: Extension has not been invoked for the current page` y no se sustituye por otra cosa. Lo verificado son los textos leídos de la página viva, que es evidencia de comportamiento, no de aspecto.*

### Log de la fase 11

- **La plantilla no se recarga sola, otra vez.** Editar `study_viewer.html` y recargar seguía sirviendo el JS viejo; hizo falta `docker compose restart django`. Ya pasó en la fase 10 y volvió a costar un rato. **Comprobar siempre `document.documentElement.innerHTML.indexOf('<algo del parche>')` antes de dar por roto un arreglo de plantilla.**
- **Gotcha de verificación, del run anterior y confirmado aquí:** una ventana de Chrome `maximized` pero con `focused: false` deja la pestaña en `visibilityState: "hidden"`, y `--activate` no lo arregla. Para pdf.js y para las transiciones CSS hace falta `interceptor window focus <id>`.
- **Una idea que salió al construirla y NO se hizo:** un objetivo solo se ve desde la página de su libro; si algún día hay varios a la vez, harán falta en el índice de la biblioteca.

### El despliegue, y por qué se rompió a mitad (2026-08-24)

El deploy salió mal y dejó producción con **código nuevo y esquema viejo**: las páginas de libro daban 500 con `relation my_library_librarygoal does not exist`. La cadena, de la superficie al fondo:

1. `migrate` abortó con `NodeNotFoundError` — la migración `0010` dependía de `wagtailcore.0097`, que producción no tenía.
2. La `0010` quedó anclada ahí porque **`makemigrations` fija por defecto la ÚLTIMA migración de `wagtailcore` de la máquina donde se genera**, y local corría 7.3.3.
3. Local corría 7.3.3 y producción 7.3.1 porque **`wagtail` estaba SIN FIJAR** en `requirements/base.txt`. Nadie lo sabía.
4. Y abortó **después** de levantar el código nuevo, porque `deploy-production` hace `up -d` y *luego* `migrate`. El orden convierte cualquier migración que falle en una caída con la app ya arriba.

**Los dos arreglos** (`aa8cbc1`, `b0acc1b`): reanclar la `0010` a `wagtailcore.0001` — para una clave ajena a `Page` basta con que `Page` exista, y eso pasa en la 0001, así que la migración deja de depender de la versión de Wagtail de cada entorno — y fijar `wagtail==7.3.1`, la que YA corría producción, para que producción no se mueva y subir de versión sea un acto deliberado con su ensayo.

**Estado comprobado el 2026-08-25:** `just production-manage showmigrations my_library` da las diez migraciones aplicadas, `0010_libraryitem_descartado_librarygoal` incluida, y una página de libro (`/indice-de-recursos-musicales/2-min-para-improvisar-i-fundamentos/`) sirve su lista de capítulos. *Sin verificar en navegador: el botón «Estudiarme este libro» con sesión iniciada — el Chrome conectado a Interceptor no tiene sesión en la app.*

**La regla que deja esto:** para cualquier dependencia que genere migraciones (Wagtail, Django, taggit), local y producción tienen que correr la MISMA versión, y eso solo se consigue fijándola. **Siguen sin fijar `faker`, `huey`, `django-sql-explorer` y `django-mailbox`**: ninguna genera migraciones que anclemos hoy, pero la trampa es la misma y está armada.

## Fase 12 — La cuota de novedad se mide por objetivo y se alterna · DESPLEGADA (`b9e394a`)

### El defecto, medido en producción antes de tocar código (2026-08-25)

`jlopez`, en producción:

| | |
|---|---|
| Objetivos activos | `2 Min. para Improvisar I` (24/08 21:20) y `CAGED` (25/08 08:37) |
| Biblioteca sin descartar | 51 |
| **Sin tocar (lo que miraba `faltan`)** | **28** |
| Por libro | Jens Larsen 23 (13 sin tocar) · Índice suelto 14 (12) · CAGED 11 (0) · 2 Min. 2 (2) |

**Dos cosas que la medición corrige, y una es de la cabeza del principal:**

- **Jens Larsen NO tenía objetivo.** El principal creía tener puestos Larsen y CAGED; los activos eran `2 Min. para Improvisar I` —de las pruebas del 24/08— y CAGED. Los 23 elementos de Larsen son de antes de la fase 11, metidos a mano.
- **La creación perezosa estaba apagada de hecho.** Con cuota de novedad 2 y `sin_tocar = 28`, `faltan = 2 - 28 = -26`: `rellenar_para_sesion` devolvía `[]` **en cada sesión**. Ningún objetivo podía aportar nada, ni CAGED ni ningún otro. El mecanismo del "primer objetivo se lo come todo" ni siquiera llegaba a ejecutarse.

### Los dos arreglos

- **Se mide por objetivo, no sobre la biblioteca entera.** Un elemento suelto de hace meses no satisface la intención "quiero estudiarme CAGED". `_sin_tocar_del_libro` cuenta solo lo del libro del objetivo.
- **Con varios objetivos, la cuota se alterna** (decisión del principal). En cada vuelta se le pide UNO al objetivo que menos material disponible tenga: con dos libros y cuota 2, uno de cada. Un libro agotado cede su parte a los demás en vez de perderla. Y el `filter` lleva ya `order_by("created_at", "pk")`: antes ni siquiera estaba definido cuál era "el primero".

### Criterios

- [x] **C47 — El material suelto sin tocar no apaga el objetivo.** *Reproducido en local con la forma exacta de jlopez —28 sueltos, objetivos secos—: el código viejo daba `faltan = -26` y creaba cero; el nuevo crea 2. Test: `test_material_suelto_sin_tocar_no_apaga_el_objetivo`.*
- [x] **C48 — Dos objetivos se reparten la cuota.** *Con cuota 2 y dos libros sale uno de cada, no dos del primero. Verificado además contra la copia de producción con Larsen y CAGED: `+1` y `+1`. Test: `test_dos_objetivos_alternan_la_cuota`.*
- [x] **C49 — Un libro agotado cede su parte.** *Cuota 3, un libro con un solo medio y otro con tres: salen `c1`, `l1`, `l2`. El falsador: sin la cesión saldrían solo dos elementos. Test: `test_un_libro_agotado_cede_su_parte_al_otro`.*

### Anti-claims

- **La cuota de novedad sigue siendo la misma.** Alternar reparte QUIÉN la llena, no la agranda. La proporción de la fase 5 no se toca.
- **Nada se crea por adelantado.** La creación perezosa de C43 sigue intacta: esto solo arregla cuándo se dispara y de qué libro.
- **No se toca la biblioteca de nadie.** El arreglo cambia qué se crea de aquí en adelante; los 51 elementos de `jlopez` se quedan como están.

### Lo que queda

- **Desplegar.** Y avisar al principal de que su objetivo de `2 Min. para Improvisar I` sigue puesto: si no lo quiere, se quita desde la página del libro.
- **Lo que la medición deja abierto:** con 28 elementos sin tocar acumulados, la sesión seguirá sirviendo material viejo antes que nuevo. Eso NO es un defecto de esta fase —la cuota de novedad es una cuarta parte a propósito— pero explica la sensación de "no me mete lo del libro", y conviene mirarlo al hacer el presupuesto en minutos.

## Fase 13 — Entrar sin Google, y el espacio que no se escribía · DESPLEGADA Y VERIFICADA (`b9e394a`)

### El login por contraseña estaba bloqueado en el adaptador, y el bloqueo daba 500

`AccountAdapter.pre_login` (`users/adapters.py`) permitía entrar por contraseña solo a staff, a cuentas con social vinculada y a impersonación; en cualquier otro caso hacía `raise ValidationError`. Medido intentando entrar en producción el 2026-08-25: **página de "Server Error"**, no un mensaje de formulario. El texto del error ("usa tu cuenta de Google") está escrito para el usuario, pero el usuario nunca lo ve: allauth no captura esa excepción ahí y sale un 500.

**El arreglo, y por qué así.** `PASSWORD_LOGIN_EMAILS` (env `DJANGO_PASSWORD_LOGIN_EMAILS`, vacía por defecto) lista los correos que SÍ pueden entrar con contraseña. La alternativa era darle `is_staff` a la cuenta de pruebas, y eso es el admin de Django entero para poder hacer login: mucho más privilegio del necesario. Con la lista vacía, el comportamiento no cambia para nadie.

- [x] **C50 — El correo de la lista entra con contraseña.** *Verificado EN PRODUCCIÓN por navegador el 2026-08-25, tras desplegar `b9e394a`: login con email y contraseña de la cuenta de servicio (nombre solo en la variable de entorno, no en el repo), sin `is_staff`, redirige a su ficha. Antes del despliegue, ese mismo intento daba «Ooops!!! 500». Test: `test_el_correo_de_la_lista_puede_entrar_con_contrasena`.*
- [x] **C51 — Nadie más.** *El falsador de toda la fase: si esto pasa a `True`, la obligación de Google deja de existir para el alumnado. Tests: `test_cualquier_otro_correo_sigue_sin_poder`, `test_sin_configurar_no_cambia_nada_para_nadie`.*

**Deuda que deja:** el `raise ValidationError` sigue devolviendo 500 a quien intente entrar por contraseña sin estar en la lista. Ahora es un camino que casi nadie pisa, pero un alumno que pruebe el formulario se come un error de servidor en vez del mensaje que ya está escrito. Se arregla devolviendo una respuesta (`ImmediateHttpResponse`) en vez de lanzar.

### El espacio no se escribía en la nota: dos visores se quedaban el teclado

`viewers/pdf_viewer.html` y `viewers/image_viewer.html` registran cada uno un `document.addEventListener('keydown')` que atrapa `' '`, las flechas y AvPág/RePág con `preventDefault()` **sin mirar `e.target`**. Los visores se inyectan en el MISMO documento que la nota (`study_item_content` llega por `fetch` y sus `<script>` se re-ejecutan), así que escribir un espacio en `#study-shared-input` movía el visor en vez de escribirse. **No era solo el espacio:** las flechas y AvPág/RePág tampoco movían el cursor dentro del campo.

- [x] **C52 — Escribiendo en un campo, el teclado es del campo.** *Guarda por `e.target` en los dos visores: `TEXTAREA`, `INPUT`, `SELECT` y `isContentEditable` salen antes del `switch`. `Escape` sigue pasando a propósito: lo maneja `study_viewer.html`, que saca del campo y guarda.* *Verificado por el principal en producción el 2026-08-25: «Tecla de espacio y cursor funcionando donde les corresponde». También confirma que el guardado automático de la nota va.*

**Cómo se cerró, y lo que costó.** Lo comprobó el principal, no yo: mis tres intentos de medirlo estaban ciegos y conviene que quede escrito. (1) La nota compartida va dentro de `{% if user.is_staff %}` y la cuenta de servicio es no-staff a propósito; «Mis notas» (`#study-notes-input`) no tiene esa puerta y sirve igual. (2) `interceptor keys` manda atajos pero no inserta caracteres, así que el guardado automático nunca escribía y la BD no valía de testigo. (3) La CSP de la página bloquea `eval`, así que no hay forma de leer `container.scrollTop`, y `screenshot --selector` re-renderiza el elemento, con lo que **no refleja el scroll**: las capturas salían idénticas antes y después, y también en el control sin foco. Instrumento ciego, no arreglo funcionando.

**Deuda encontrada de camino:** los `addEventListener('keydown')` de los dos visores se registran **en cada carga de item**, porque el partial se re-inyecta y sus scripts se re-ejecutan. Los manejadores se acumulan durante la sesión, cada uno con el closure de su carga. Hoy la guarda tapa el síntoma; arreglarlo de verdad es nombrar las funciones y quitarlas al descargar el item.

## Fase 14 — Alternar de verdad: reserva por objetivo y reparto al elegir · DESPLEGADA (`b3f8fd5`)

### Lo que faltaba, medido en producción con los tres objetivos (2026-08-25)

El principal deja el de `2 Min. para Improvisar I` y añade el de Jens Larsen. Tres activos:

| Objetivo | Sin tocar |
|---|---|
| 2 Min. para Improvisar I | 2 |
| The Caged System | **0** |
| Modern Jazz Guitar Concepts (Jens Larsen) | 13 |
| **Suma** | **15** |

Con cuota 2, el déficit global daba `2 - 15 = -13`: **cero elementos creados**, con CAGED a cero. Y aunque se hubieran creado, no habrían salido: `construir_sesion` ordena lo nuevo por `(orden, pk)` y coge `nuevos[:cuota]`, así que los trece de Larsen, con los pk más bajos, se llevaban los dos huecos de novedad de **todas** las sesiones. **No era mala suerte, era determinista.**

**La fase 12 arregló media cosa.** Alternar la creación decide qué objetivo llena el hueco *cuando hay que crear*, y aquí no había que crear nunca. La otra mitad está en la selección, y ahí no se alternaba nada.

### Los dos cambios, uno en cada sitio

- **Creación (`libros.rellenar_para_sesion`):** cada objetivo mantiene su propia reserva de `techo(cuota / nº objetivos)` elementos sin tocar, en vez de un déficit global. Con los datos de arriba: Larsen y 2 Min. ya tienen de sobra, CAGED recibe uno.
- **Selección (`session._repartir_por_libro`):** lo nuevo se intercala por libro antes de cortar por la cuota, conservando el orden DENTRO de cada libro, que es el orden del libro y es lo que compró la fase 11. El libro se saca del `path` de treebeard, sin una consulta por unidad.

### Criterios

- [x] **C53 — Un libro con material acumulado no tapa a los demás al crear.** *Reproducida la forma de producción con tres objetivos: solo se crea material para el que estaba a cero. El falsador: si se vuelve a medir el déficit en global, se crea cero. Test: `test_tres_objetivos_cada_uno_con_su_reserva`.*
- [x] **C54 — La novedad se reparte entre libros al elegir.** *Un libro con cinco pendientes y pk bajos, otro con uno solo y pk alto: el segundo asoma en los dos primeros huecos. Antes salía siempre el primero. Test: `test_la_novedad_se_reparte_entre_libros_al_elegir`.*

### Anti-claims

- **La cuota de novedad no crece.** Sigue siendo una cuarta parte de la sesión. Esto reparte quién la llena y quién la ocupa, nada más.
- **El orden del libro se respeta.** El reparto intercala ENTRE libros; dentro de cada uno, el orden que puso C41 queda intacto.
- **Nada se crea por adelantado.** La reserva es un techo por objetivo, no un depósito: un libro agotado devuelve menos y ya está.

### Lo que queda

- **Desplegar**, y comprobar con los datos del principal que CAGED empieza a aparecer.

## Fase 15 — El panel de mazos sale de la interfaz · DESPLEGADA Y VERIFICADA (`285f904`)

**Petición del principal (2026-08-25):** *"quiero borrar los mazos creados, puesto que veo mejor el nuevo sistema de estudio basado en sesiones que se alimentan en base a objetivos"*. Se hace la mitad reversible ahora y se revisa la otra en un mes.

### Qué es un mazo, medido antes de tocarlo

`LibraryDeck` guarda `user`, `name`, `tags_json` y `created_at`. Su propio docstring lo dice: **es un filtro de etiquetas guardado**, no un contenedor. Los elementos de un mazo se calculan al vuelo con los que casan con TODAS sus etiquetas. Consecuencia directa: **borrar un mazo no toca ni un elemento de la biblioteca**.

**Y quien heredó su función no son los objetivos, son las facetas.** Un objetivo dice "rellena la novedad con este libro"; un mazo decía "esta sesión va de estas etiquetas". Eso es el arranque por facetas de la fase 5. La única diferencia real que queda: el mazo **guardaba** la combinación y las facetas se eligen cada vez.

### Lo que sí se perdería al borrar el modelo, y por eso no se borra hoy

Medido en producción: **75 repasos, 50 con sello de mazo**. `ReviewLog.deck` es `SET_NULL`, así que los repasos sobrevivirían enteros y perderían la atribución. El presupuesto en minutos trabaja por elemento con `duration_seconds` y no la necesita, pero dos tercios del historial es bastante como para no tirarlo el mismo día que se decide.

### Lo hecho

- El `include` del panel queda comentado en `index.html`, con el porqué al lado.
- **`_build_decks_with_counts` deja de llamarse desde el índice.** Aquí está el ahorro de verdad: con el panel fuera, calcularlo era pagar `build_tag_map` —unas dos consultas por elemento— para tirar el resultado. Era deuda anotada desde la fase 7.
- **No se borra nada más**: modelo, las cuatro rutas, `_render_deck_panel`, `deck_study` y el campo `ReviewLog.deck` siguen enteros. Volver a ver el panel es descomentar una línea.

- [x] **C55 — El índice ya no pinta mazos y sigue funcionando.** *Verificado en navegador local con un usuario que tiene tres elementos y un mazo: `#libraryItemsList` presente, `#deckPanel` ausente. El falsador importa: si se quita el `include` pero se deja la llamada en la vista, el ahorro no existe y el defecto sigue.*

### Revisión programada

Recordatorio puesto para el **2026-09-25 a las 07:40 por Telegram** (`DASchedule` id `1787668554241-ik4zhv`): decidir si se va el modelo. Si para entonces no ha echado de menos guardar combinaciones, migración que se lleve modelo, rutas y campo. Si sí las ha echado de menos, la alternativa no es resucitar los mazos sino **guardar combinaciones de FACETAS**, que es el vocabulario que de verdad usa desde la fase 8.

## Fase 16 — El libro recién empezado no asomaba, y el comentario se veía · SIN DESPLEGAR

Conducido en navegador con la sesión del principal en producción, 2026-08-26. Era el punto 1 que la fase 14 dejó abierto: «comprobar con los datos del principal que CAGED empieza a aparecer».

### La creación perezosa funcionaba. Lo que fallaba era la selección

| Medido al lanzar la sesión | |
|---|---|
| Faceta `caged` antes → después | 11 → **12** |
| Elemento creado | `Chapter One - What is the CAGED System? — img-001.png`, sin tocar |
| Sesión servida (`items=100,102,95,96,22,69,19,97`) | los mismos 8 de la vista previa, **sin CAGED** |

O sea: la fase 14 compró su mitad. `rellenar_para_sesion` creó el elemento del libro que estaba a cero, exactamente como decía la aritmética. Y luego la sesión lo dejó fuera.

**El porqué, y es el mismo determinismo que ya arregló C54 una vez.** `_repartir_por_libro` agrupa lo nuevo por libro y hace un round-robin, pero los grupos van **en el orden en que aparece su primer elemento**, que es orden de pk. Lo que la creación perezosa acaba de crear tiene por fuerza el pk MÁS ALTO de la biblioteca, así que su grupo cae siempre el último. Con tres grupos sin tocar y cuota 2, el tercero no entra nunca.

**C54 se probó con DOS grupos; producción tiene tres.** Ahí está el hueco entero. Con dos grupos el round-robin reparte bien y el test verde no mentía: simplemente no cubría la forma que tenía producción.

### El arreglo

**El material suelto va el último; los libros conservan su orden.** Es la regla que ya estaba escrita del lado de la creación —«un elemento suelto de hace meses no satisface la intención "quiero estudiarme CAGED"»— aplicada al lado de la selección, que nunca la recibió. Decisión del principal entre tres opciones (2026-08-26); las otras dos eran ordenar por material sin tocar de menos a más, y rotar quién abre la ronda en cada sesión.

**Simplificación consciente:** aquí "libro" es tener `source_page`, no tener un objetivo activo. Un capítulo metido a mano antes de que existieran los objetivos cuenta como libro, porque tiene orden y pertenece a algo, que es lo que lo distingue del suelto. Mirar los objetivos costaría una consulta más en un camino escrito a propósito para no hacer ninguna por unidad.

### El comentario de plantilla, otra vez

`{# #}` de Django es de **una sola línea**. El bloque de nueve líneas que la fase 15 dejó en `index.html` explicando por qué salía el panel de mazos **se estaba pintando entero encima de la lista**, en producción. Es la segunda vez en este proyecto: la primera la arregló `444af8e` en la fase 7. Esta vez queda un test detrás.

### Anti-claims

- **La cuota de novedad no crece.** Sigue siendo una cuarta parte. Esto cambia QUIÉN ocupa los huecos, no cuántos hay.
- **El orden del libro se respeta.** El reparto ordena ENTRE grupos; dentro de cada libro, el orden que puso C41 queda intacto.
- **El material suelto no se pierde.** Cede el hueco de NOVEDAD; sigue entrando por caducidad como cualquier otro elemento en cuanto se practique una vez.
- **No se toca la creación.** `rellenar_para_sesion` queda igual: la medición demostró que hacía su trabajo.

### El primer arreglo no bastó, y lo dijo producción el mismo día

Desplegado `5cdcb85` y lanzada una sesión: **CAGED seguía sin salir**. El arreglo SÍ cambió el reparto —donde antes entraba `Makumaná`, ahora entra un capítulo de Larsen— así que el suelto cedió su hueco como se había diseñado. Pero el objetivo recién empezado siguió fuera.

**Lo que se me escapó fue la simplificación que yo mismo había marcado.** Ordené los grupos por «tiene página o no», no por «es objetivo o no». Con el suelto ya fuera quedaban TRES grupos de libro por delante de CAGED y la cuota seguía siendo 2. Un capítulo que está en la biblioteca porque se metió a mano hace meses no es lo mismo que un libro que el principal ha declarado que quiere estudiarse: ordenarlos igual es tirar justo la información que la fase 11 metió en el modelo.

**Y se me escapó por medir con el instrumento equivocado.** La vista previa solo enseña los 8 elegidos, así que no se ve cuántos GRUPOS compiten ni en qué orden van. De ahí sale `estado_estudio` (abajo): eso es lo que había que mirar antes del primer despliegue, no después.

### El comando de medida

`my_library/management/commands/estado_estudio.py`, de **solo lectura**, y en particular sin llamar a `rellenar_para_sesion`: medir no puede cambiar lo medido. Enseña los objetivos con su reserva, **los grupos sin tocar en el orden en que se sirven y cuáles no entran nunca**, la sesión de ahora, y las medianas de `duration_seconds`, que es lo que hace falta para el presupuesto en minutos.

    just production-command estado_estudio --email <correo>

### Criterios

- [x] **C56 — Con tres grupos de material sin tocar, el libro recién empezado entra y el suelto cede.** *El falsador es doble y los dos importan: si `c1` no sale, el defecto sigue; si sale `suelto` en vez de `l1`, se ha roto el otro libro. Reproducida la forma exacta de producción: en rojo salía `['suelto', 'l1', ...]`, en verde salen `l1` y `c1`. Test: `test_el_libro_recien_empezado_no_asoma_con_tres_grupos`. C54 sigue verde. **Cerrado en producción el 2026-08-26** tras desplegar `c31f13e`: ver la medida de abajo y el navegador.*
- [x] **C57 — El índice no pinta el comentario de plantilla.** *Verificado que el test FALLA con la plantilla vieja (`git stash` del fichero) y pasa con la nueva: un test de esto que no se pueda poner en rojo no vale para nada. **Cerrado en producción por navegador el 2026-08-26** tras desplegar `5cdcb85`. Test: `test_el_indice_no_pinta_el_comentario_de_plantilla`.*
- [x] **C58 — Un objetivo pasa por delante de los libros sin objetivo.** *Reproducida la forma de producción DESPUÉS del primer arreglo, que es la que importa: suelto + dos libros sin objetivo con pk bajos + dos objetivos, el recién empezado con el pk más alto. En rojo salían `['libro-uno-a', 'libro-dos-a', ...]`; en verde salen los dos objetivos. Confirmado con `git stash` de `session.py` que el test se pone rojo sin el arreglo. Cuesta UNA consulta por sesión, no una por unidad. Test: `test_el_objetivo_pasa_por_delante_de_los_libros_sin_objetivo`. **Cerrado en producción el 2026-08-26**: los tres grupos con objetivo ocupan los tres huecos y los dos sin objetivo se quedan fuera.*
- [x] **C59 — El comando de medida no escribe.** *El falsador: si llamara a `rellenar_para_sesion`, medir crearía elementos. Y se prueba con la forma de producción, no contra una base vacía: un comando corrido solo en vacío no ha probado ninguna de sus ramas. Tests: `test_estado_estudio_cuenta_los_grupos_que_se_quedan_fuera`, `test_estado_estudio_no_crea_nada`.*

### Lo que queda

- **Desplegar C58 y el comando** (145/145 en verde en local, sin desplegar).
- **Verificar C56 y C58 en producción por navegador**: lanzar una sesión y ver CAGED dentro. Hoy está verificado el defecto y el arreglo en local, no el arreglo en producción.
- **Medir con `estado_estudio` en producción** antes de dar nada por cerrado: cuántos grupos hay de verdad y cuántos se quedan fuera.
- **Aun con los objetivos delante, sobran grupos para los huecos que hay.** Con tres objetivos y cuota 2, uno se queda fuera de todas las sesiones. Ver punto 3 de «Lo siguiente».

### Deuda encontrada de camino

- **Títulos repetidos en la faceta `caged`:** `Example 3.1c`, `Example 3.2a` y `Example 3.2c` salen **dos veces cada uno** en la vista previa filtrada. Puede ser que el libro traiga la misma imagen dos veces, o que haya elementos duplicados en la biblioteca. Sin medir todavía.
- **El botón «Empezar sesión» no respondió a dos clics sintéticos** del navegador automatizado; navegando a mano a `/my-library/empezar/lanzar/` funciona a la primera. Instrumento sospechoso antes que defecto: no se afirma que el botón esté roto. Comprobarlo con un clic humano.

### La medida de producción que lo cierra (2026-08-26, tras desplegar `c31f13e`)

    biblioteca sin descartar: 52 · con al menos un repaso: 24
    sesión de 15, cuota de novedad 3

    OBJETIVOS ACTIVOS
      2 Min. para Improvisar I        sin_tocar=2    reserva=1  crearía=0
      The Caged System                sin_tocar=1    reserva=1  crearía=0
      Modern Jazz Guitar (Larsen)     sin_tocar=13   reserva=1  crearía=0

    GRUPOS SIN TOCAR, en el orden en que se sirven
      1. Modern Jazz Guitar (Larsen)      13 sin tocar · ¿entra? SÍ ← objetivo
      2. 2 Min. para Improvisar I          2 sin tocar · ¿entra? SÍ ← objetivo
      3. The Caged System                  1 sin tocar · ¿entra? SÍ ← objetivo
      4. Índice de recursos musicales     12 sin tocar · ¿entra? no
      5. (suelto, sin página)              1 sin tocar · ¿entra? no
      → 2 grupos fuera: hay 5 y solo 3 huecos.

**Los tres objetivos ocupan los tres huecos, y los dos grupos sin objetivo ceden.** Es exactamente lo que compraron C58 y la fase 17 juntas. Confirmado además en el navegador con la sesión del principal: `1/15`, primer elemento `Chapter One - What is the CAGED System? — img-001.png`, etiquetado `concepto:caged`.

### Y la calibración para el presupuesto en minutos, ya medida

    elementos con duración: 23
    mediana de las medianas: 49 s
    mínimo / máximo: 11 s / 469 s
    una sesión de 15 de los más cortos: ~9 min

**El rango es de 42×.** Once segundos el más corto, casi ocho minutos el más largo. Ahí está, medido, el argumento entero de por qué "15 elementos" no es una unidad: dos sesiones del mismo tamaño nominal pueden durar nueve minutos o casi dos horas. Estos 23 elementos con duración son la base para calibrar el presupuesto.

## Fase 17 — Sesión de 15 con tres huecos de novedad, y qué pasa al filtrar por instrumento · SIN DESPLEGAR

**Petición del principal (2026-08-26):** *"prefiero meter tres huecos de estudio de material nuevo y sumar o ampliar a 15 los elementos de estudio"*.

### Los dos números, y por qué la proporción baja

`TAMANO_SESION_POR_DEFECTO` pasa de 8 a 15, y `PROPORCION_NOVEDAD` de 0.25 a 0.2. Lo segundo no es un capricho: `15 × 0.25 = 3.75`, que redondea a **4**. Con 0.2 sale 3 exacto, que es lo pedido. Para los tamaños que se pasan a mano el número no cambia: con 8 la cuota sigue siendo 2 (`round(8 × 0.2) = 2`, igual que `round(8 × 0.25)`).

**Efecto secundario que resuelve el punto 3 al tamaño actual.** Con tres objetivos y tres huecos, cada objetivo recibe uno: `reserva = techo(3/3) = 1` al crear, y tres grupos con objetivo caben en los tres huecos al elegir. El problema de "un objetivo se queda fuera de todas las sesiones" desaparece **mientras haya tres objetivos o menos**. Con cuatro vuelve, y entonces sí habrá que rotar.

### La pregunta del principal: "si elijo piano, ¿los tres huecos salen del libro de piano?"

**Sí, y está medido, no razonado.** El filtro de facetas corre después de crear y antes de construir la sesión, así que lo que no es de piano se cae antes de repartir los huecos. Con dos libros de guitarra y uno de piano como objetivos, eligiendo `instrumento:piano` la sesión sale entera de piano. Test: `test_elegir_piano_deja_la_sesion_solo_de_piano`.

**Pero hay una mitad que no se ve, y conviene saberla.** `rellenar_para_sesion` corre ANTES del filtro y **no sabe nada de las facetas**: ese día se crea material de los tres objetivos, guitarra incluida. Lo de guitarra no entra en la sesión de hoy porque el filtro se lo lleva, pero **se queda en la biblioteca sin tocar** y compite en las sesiones sin filtrar. Un mes estudiando solo piano deja las dos guitarras con material nuevo acumulado que nadie pidió. Test: `test_elegir_piano_no_impide_que_se_cree_material_de_guitarra`.

Es la misma clase de defecto que la fase 12: material sin tocar que se acumula por un camino que nadie mira. No se arregla aquí porque el arreglo es una decisión —¿el filtro debería frenar también la creación?— y no hay medida todavía de cuánto se acumula de verdad.

### Criterios

- [x] **C60 — La sesión por defecto es de 15 con 3 huecos de novedad.** *`round(15 × 0.2) = 3`. El falsador de la proporción: con 0.25 salen 4, no 3. La interfaz lo dice sola, el texto sale de `tamano_sesion`.*
- [x] **C61 — Filtrar por instrumento deja la sesión de ese instrumento.** *El falsador: si el filtro corriera después de repartir los huecos, se colaría guitarra. Test: `test_elegir_piano_deja_la_sesion_solo_de_piano`.*
- [x] **C62 — El filtro NO frena la creación.** *No es un arreglo, es la constatación de lo que hoy pasa, escrita como test para que el día que se decida cambiarlo se vea en rojo. Test: `test_elegir_piano_no_impide_que_se_cree_material_de_guitarra`.*

### Anti-claims

- **La unidad sigue siendo el elemento, y sigue siendo mentirosa.** Quince elementos no son quince de nada: uno puede ser un lick de cuarenta segundos y otro una pieza de catorce minutos. Eso lo arregla el presupuesto en minutos, no este número.
- **No se toca la caducidad.** Los plazos por nivel siguen siendo 1/1/3/7/21.

### Lo que queda

- Nada. La pregunta abierta —si el filtro debe frenar también la creación— la contestó el principal el mismo día. Ver fase 18.

## Fase 18 — El filtro frena también la creación · SIN DESPLEGAR

**Decisión del principal (2026-08-26), respondiendo a lo que dejó abierto la fase 17:** *"Sí, el filtro debería frenar también la creación. No quiero material acumulado."*

### Qué cambia

`rellenar_para_sesion` recibe ahora la selección de facetas y **solo rellena los objetivos cuyo libro casa con ella**. La selección se lee en `session_launch` ANTES de crear, no después.

La regla de casado es la misma que la de `filtrar_por_facetas`, y eso es a propósito: Y entre facetas, O dentro de cada faceta. Un libro es "de piano" porque sus capítulos llevan `instrumento:piano`, que es donde viven las etiquetas desde C37c.

**La reserva se reparte entre los objetivos que casan, no entre todos.** Eligiendo piano con un solo libro de piano, los tres huecos de novedad son suyos: `reserva = techo(3/1) = 3`. Sin esto, el filtro habría frenado la creación pero también la habría reducido a un tercio.

### Criterios

- [x] **C63 — Eligiendo piano no se crea material de guitarra.** *Es el mismo test de C62, dado la vuelta: antes constataba el defecto, ahora exige el arreglo. Confirmado con `git stash` de `libros.py` y `views.py` que se pone rojo sin el cambio. Y comprueba las dos mitades: nada de guitarra, y el libro elegido sí recibe material. Test: `test_elegir_piano_no_crea_material_de_guitarra`.*

### Anti-claims

- **Sin filtro no cambia nada.** Una selección vacía casa con todo, así que la sesión sin facetas se comporta exactamente igual que antes.
- **No se borra ni se descarta nada de lo ya acumulado.** Esto frena la acumulación de aquí en adelante; lo que ya está en la biblioteca sigue donde está.
- **El objetivo no se desactiva.** Filtrar por piano no toca los objetivos de guitarra: simplemente hoy no se les pide material.

### Lo que queda

- **Desplegar.**
- **Lo ya acumulado sigue ahí.** Merece una medida con `estado_estudio` antes de decidir si hay que hacer algo con ello.

## Fase 19 — Seguir un libro desde la pantalla de empezar · SIN DESPLEGAR

**Petición del principal (2026-08-26):** *"algún botón en la pantalla de Empezar en la que pudiera seleccionar el objetivo de aprendizaje, el libro que he marcado, para seguir solo por ese libro"*.

### Las dos decisiones que se le pasaron, y lo que se descartó

- **Solo los chips de objetivo.** La alternativa era meter además `autor` y `obra` en `FACETAS_DE_FILTRO`, que habría permitido acotar a CUALQUIER libro, tenga objetivo o no. Descartado por el principal. **Queda anotado el hueco:** hoy `AUTOR` existe como faceta pero no está en la lista de filtrado, así que un libro sin objetivo no se puede acotar de ninguna manera.
- **La sesión entera, repaso incluido.** No solo los tres huecos de novedad. Elegir CAGED da quince elementos de CAGED. **Coste aceptado a conciencia:** ese día no se repasa nada de los otros libros, y lo vencido de fuera se acumula.

### Por qué el libro no es una faceta más

Una faceta describe el contenido ("de guitarra", "de blues"); un libro es un contenedor. Dos libros solo pueden combinarse con **O**, porque nada está en dos libros a la vez, mientras que dos facetas distintas se combinan con **Y**. Meterlos en el mismo grupo de la pantalla habría hecho que dos chips de aspecto idéntico se comportaran distinto. Por eso los libros van arriba, separados por una línea, y con su propio color.

Entre el libro y las facetas la combinación sí es Y: "de este libro Y de pentatónicas".

El filtro se aplica por el `path` de treebeard, igual que `_libro_de`, así que es una comparación de cadenas y no una consulta por elemento.

### Criterios

- [x] **C64 — Elegir un libro deja la sesión entera de ese libro.** *El falsador: con todo el material practicado, los huecos que quedan son de REPASO; si el filtro solo alcanzara a la novedad, se colaría el otro libro. Test: `test_elegir_un_libro_deja_la_sesion_entera_de_ese_libro`.*
- [x] **C65 — Elegir un libro frena la creación de los demás.** *Misma regla que C63, con un filtro más fuerte: el libro dice exactamente qué objetivo puede aportar hoy, sin aproximar por etiquetas. Test: `test_elegir_un_libro_solo_crea_de_ese_libro`.*
- [x] **C66 — Dos libros elegidos se suman, y un tercero no entra.** *Test: `test_dos_libros_elegidos_se_suman`.*
- [x] **C67 — Los chips salen en la pantalla.** *Si no se ven no existen. Este test encontró de paso que el selector entero vivía dentro de `{% if facetas %}`: un objetivo cuyo material no tuviera etiquetas facetadas no se podía elegir, porque no se pintaba nada. Ahora la condición es `facetas or objetivos`. Test: `test_los_chips_de_objetivo_salen_en_la_pantalla_de_empezar`.*

### El comentario de plantilla, TERCERA vez

Escribiendo esta fase volví a poner un `{# … #}` a dos líneas, y volvió a pintarse. Lo cazó `test_el_selector_no_escupe_el_comentario_de_la_plantilla`, que existía desde la fase 7. **El test hizo exactamente su trabajo**, y por eso esta vez no llegó a producción. Es la mejor prueba de que la regla no se aprende: hay que dejarla cazada.

## Fase 20 — Encajar la imagen en la pantalla · SIN DESPLEGAR

**Petición del principal (2026-08-26), con captura:** una partitura de acorde salía enorme y pedía scroll para ver una sola figura. *"Generalmente esa es la visión que quiero \[ancho completo\], pero de vez en cuando me gustaría tener la opción"*.

### Lo hecho

El ancho completo **sigue siendo el modo normal** y no se toca. Se añade un modo `encajar` que mete la imagen entera en el alto de la ventana, con un botón en el menú del visor que dice `Encajar en pantalla` / `Ancho completo` según el estado.

- **La columna flex es lo que lo hace bien.** Con `max-height` a secas, el título del elemento —que va dentro del mismo bloque— empuja la imagen fuera de la pantalla. Con `display: flex` en columna a `100vh`, el alto se reparte entre título e imagen y el conjunto cabe de verdad.
- **La elección se recuerda** en `localStorage`, y no por comodidad: el partial del visor se recarga con CADA elemento de la sesión, así que cualquier estado en memoria se perdería en el siguiente. Aplicarlo al arrancar es idempotente, que es justo lo que hace falta con scripts que se re-ejecutan.
- **El botón se olvida antes de cargar el siguiente elemento.** Los visores dejan sus funciones globales puestas al descargarse (la deuda de los `keydown` de la fase 13 es el mismo fenómeno); sin limpiarlo, el botón de encajar saldría encima de un PDF.

### Anti-claims

- **El modo normal no cambia.** Sin tocar el botón, el visor se comporta exactamente igual que antes.
- **Solo imágenes.** El visor de PDF no recibe el botón, y con un PDF delante el botón no sale.
- **No hay zoom.** Es un ajuste de dos posiciones, no un control continuo. Si hiciera falta acercarse a un detalle, eso es otra cosa y no está hecha.

### Criterios

- [x] **C68 — La imagen entera cabe en la pantalla al encajarla.** *Claim de APARIENCIA, así que se cierra viendo los píxeles y no de otra forma. Verificado en producción el 2026-08-26 con la imagen que trajo el principal, `A Shape` del capítulo 1 de CAGED, en su propio navegador: **antes** solo se veía el título y el primer traste, y hacía falta scroll; **después** entran el título, la X, la cejilla y los trastes 12 y 15 completos. El falsador que lo confirma: con el modo puesto, cinco clics de rueda hacia abajo NO mueven nada, o sea que no queda contenido fuera. Y el botón cambia su texto a `Ancho completo`.*

### Lo que queda

- **El botón solo está en el menú.** Dos toques. Si al usarlo de verdad estorba, un atajo de teclado es una línea, pero toca el manejador de `keydown` que ya se acumula en cada carga (deuda de la fase 13), así que conviene arreglar eso primero.

## Fase 21 — Libros que agrupan páginas por referencia, y el orden del libro manda · SIN DESPLEGAR

**Petición del principal (2026-08-27):** juntar canciones que ya existen en libros temáticos («Música de los años 70»), ponerlos como objetivo, y que el material salga **en el orden que se ve en el libro** y, dentro de cada página, **por orden de aparición**.

### Lo que se comprobó antes de tocar nada, porque medio recuerdo era falso

- **El orden de los capítulos NO era el pk.** `capitulos_de` ordena por el `path` de treebeard, o sea el orden que se ve y se arrastra en el explorador de Wagtail. Eso ya estaba bien.
- **Donde sí mandaba el pk era al ELEGIR** qué material nuevo entra en la sesión: `construir_sesion` ordenaba lo nuevo por pk, y coincidía con el orden del libro solo porque la creación es secuencial. El instinto del principal era correcto, apuntaba al sitio equivocado.
- **Y había un agujero que nadie había mencionado: los embeds y los vídeos no se recogían.** `material_de` cogía imágenes, PDF y audios; `get_embeds`, `get_videos` y `get_external_links` existían en el modelo y **no los llamaba nadie**. Esto explica un síntoma que el principal reportó el mismo día: *"si selecciono 2 minutos para improvisar, he hecho ya dos o tres estudios y no me mete vídeos nuevos"*. Ese libro es de embeds, así que la creación perezosa nunca tuvo nada que ofrecer.

### La pregunta que decidió el diseño

*"¿Una BlogPage podría estar colgando de varios libros?"* **No.** En Wagtail una página tiene UN padre y su URL sale de ahí; eso es de treebeard y no se negocia. Agrupar por el árbol obliga a elegir un solo libro para siempre, y una canción pertenece a varios a la vez («los 70», «3 ESO», «acordes abiertos»).

**Por eso el libro guarda referencias.** `LibroDeEstudioPage` es un StreamField de `PageChooserBlock`: la página se queda donde vive, con su URL, y N libros la apuntan. Es el patrón que ya usaba `SetlistPage` con las partituras, ampliado. El orden de los bloques ES el orden de estudio.

### Las tres piezas, y por qué la tercera no era opcional

1. **El libro por referencia.** `capitulos_de` distingue las dos formas por capacidad y no por `isinstance`, para no atar `my_library` a un tipo concreto de `cms`.
2. **El orden dentro de la página.** Primero el cuerpo en orden ESTRICTO de aparición —imágenes y embeds mezclados según dónde estén escritos— y después los adjuntos. Decisión del principal. **Los dos grupos no se pueden entrelazar** y conviene que quede dicho: cuerpo y adjuntos son campos distintos del modelo, sin orden común; cuál va primero es una regla elegida, no un dato que se pueda leer.
3. **`LibraryItem.orden`.** Sin este campo las dos primeras piezas son invisibles: la sesión seguiría sirviendo por pk. Es la pieza que el principal no pidió y la que sostiene las otras dos. `ItemSection` ya tenía el suyo desde la fase 6.

**`LibraryItem.libro` solo se guarda en los libros por referencia**, a propósito. En los de árbol el libro se sigue deduciendo del path del padre: rellenarlo en unos sí y en otros no partiría en dos el grupo de un mismo libro, unos elementos por FK y otros por path, y el reparto de la novedad los trataría como libros distintos.

### La migración de datos, y por qué hacía falta

`0012` rellena `orden` en los elementos que ya existen, reconstruyéndolo como `(path del capítulo, pk)`. **No es opcional:** dejarlos a 0 mandaría todo lo viejo delante de todo lo nuevo y el orden saldría peor que antes de la fase. Lo que reconstruye es exactamente lo que ya había, pero escrito en un campo en vez de deducido del pk.

### Criterios

- [x] **C69 — Una página puede estar en dos libros a la vez.** *La razón de ser de la fase. El falsador es directo: si `capitulos_de` de los dos libros no devuelve la misma página, no sirve. Se comprueba además que la canción sigue colgando de donde estaba, o sea que no se le ha tocado la URL. Test: `test_una_pagina_puede_estar_en_dos_libros_a_la_vez`.*
- [x] **C70 — El orden del libro manda sobre el pk.** *Tres páginas referenciadas al REVÉS de su pk, que es lo que pasa al juntar canciones escritas en meses distintos. Sale `c1, b1, a1` en la creación y en la sesión. El falsador: sin el campo `orden`, sale el orden de pk. Test: `test_el_orden_del_libro_manda_sobre_el_pk`.*
- [x] **C71 — El cuerpo sale en orden estricto y antes que los adjuntos.** *El falsador importa y es sutil: `get_images()` devuelve los adjuntos PRIMERO y luego el cuerpo, así que apoyarse en él da el orden al revés. Se comprueba también que nada sale duplicado, que es el riesgo de sumar las dos fuentes. Test: `test_el_cuerpo_sale_en_orden_estricto_y_antes_que_los_adjuntos`.*
- [x] **C72 — Un embed del cuerpo es material de estudio.** *Lo que faltaba para «2 Min. para Improvisar». El embed se pre-siembra en la BD por su hash para que `get_embed` no salga a la red durante el test. Test: `test_un_embed_del_cuerpo_es_material_de_estudio`.*

### Anti-claims

- **Los libros por árbol no cambian.** Jens Larsen y CAGED siguen funcionando igual: mismo orden, mismo reparto, misma deducción del libro por el path.
- **No se mueve ninguna página ni se toca ninguna URL.** Es la propiedad que compra todo lo demás.
- **Una referencia rota no tumba nada.** Una página borrada o despublicada se salta; los duplicados dentro de un mismo libro también, porque referenciar dos veces la misma página no añade material y rompería el conteo de progreso.
- **El `orden` es una foto del momento de crear.** Reordenar el libro después cambia el orden de lo que queda por crear, no el de lo ya creado. Recalcularlo en cada sesión obligaría a recorrer todo el material del libro, parseando el StreamField y el RichText de cada capítulo, en cada carga.

### Desplegado, y la medida que cierra el síntoma (2026-08-27)

Las tres migraciones aplicaron limpias en producción. Medido justo después:

    OBJETIVOS ACTIVOS
      2 Min. para Improvisar I    material=44    en_biblioteca=2    sin_tocar=0  crearía=1
      The Caged System            material=302   en_biblioteca=18   sin_tocar=1  crearía=0
      Modern Jazz Guitar (Larsen) material=93    en_biblioteca=23   sin_tocar=8  crearía=0

**`material=44` es la prueba.** Ese libro es de embeds, y antes de esta fase `material_de` no los miraba: para el sistema tenía CERO material practicable, así que la creación perezosa no podía darle nada por mucho que fuera objetivo. Ahora ve 44, tiene 2 en la biblioteca y crearía el siguiente. Es exactamente el síntoma que reportó el principal, y no era del reparto: era que no había nada que repartir.

De paso queda medido el tamaño real de los otros dos: 302 y 93 elementos practicables, de los que hay 18 y 23 en la biblioteca. La creación perezosa de la fase 11 se gana el sueldo: copiarlos por adelantado habría metido 439 elementos en una biblioteca de 52.

### Lo que queda

- ~~Verificar en navegador~~ **HECHO, 2026-08-27.** Lanzada una sesión con el chip de «2 Min. para Improvisar»: `items=153,154,155,140,141`, o sea **tres elementos nuevos** (los tres huecos de novedad, porque con un solo objetivo que casa la reserva es `techo(3/1) = 3`) más los dos que ya había. El primero es `2 minutos para improvisar: T1 E005 Tónica y Dominante`, y **el vídeo de YouTube se ve y se puede reproducir dentro del visor**. C72 cerrado con píxeles, que es lo que pedía: era una claim sobre material que antes no existía para el sistema.
- **Un `LibroDeEstudioPage` de verdad, creado a mano**, para cerrar C69 y C70 fuera de los tests. Hasta que el principal cree uno, la forma está probada pero no usada.

- [x] **C73 — El tipo de página sale en el menú de crear.** *Si no sale, no existe. `subpage_types` del padre manda, y `LibroDeEstudioPage` no estaba en la lista de ninguno de los dos índices donde viven los libros: el 2026-08-28 el principal fue a crear uno y no lo encontró. Añadido a `MusicLibraryIndexPage` y `BlogIndexPage`; sin migración, es un atributo de clase. Verificado en rojo con `git stash` de `cms/models.py`, y **cerrado en producción por navegador**: «Libro de estudio» aparece en `/cms/pages/4/add_subpage/`. Test: `test_el_libro_de_estudio_se_puede_crear_donde_viven_los_libros`.*

- [x] **C74 — El libro usa la piel de la app fuera del dominio de blogs.** *El sitio tiene dos pieles y el libro solo traía la del blog, así que en `apps.iesmartinabescos.es` salía con la maqueta equivocada. Le faltaba `get_template`, que es el patrón que ya siguen `BlogPage`, `ScorePage` y las demás. El falsador: sin él, Wagtail sirve la plantilla por defecto del modelo en los dos dominios. Test: `test_el_libro_usa_la_plantilla_de_la_app_fuera_del_blog`.*
- [x] **C75 — El pajarito de Wagtail sale en la app.** *`base_blog.html` lo tenía desde siempre y `base.html` no, que es por lo que aparecía en `blogs.` y no en `apps.` — y por lo que el principal se estaba poniendo botones de edición a mano. Se comprueba sobre el fichero porque el tag solo se PINTA para quien puede editar, y lo que importa es que esté puesto. **Afecta a TODAS las páginas de la app, no solo al libro**, y es deliberado: es donde estructuralmente vive. El alumnado no lo ve. Test: `test_el_pajarito_de_wagtail_esta_en_la_plantilla_de_la_app`.*
- [x] **C76 — Un libro vacío no revienta la página.** *Defecto real encontrado de camino, y no era del libro nuevo: `boton_objetivo` devuelve `{"libro": None}` a propósito en tres casos —visitante sin sesión, página que no es un libro, libro sin capítulos— pero la plantilla seguía pintando el botón con `page_id=None`, y eso es `NoReverseMatch`, o sea **un 500 en la página entera**. Llevaba ahí desde la fase 11; nadie lo había pisado porque los libros por árbol nunca están vacíos y sus páginas se ven logueado. Un `LibroDeEstudioPage` recién creado sí lo está, que es justo lo que ve el principal al crear uno. Test: `test_un_libro_vacio_no_revienta_la_pagina`.*
- [x] **C77 — El libro tiene las propiedades de visibilidad, y se respetan.** *Pedido por el principal viendo la pestaña Propiedades de un libro normal. **Añadir los campos no bastaba:** `_check_page_visibility` los tenía cableados a `BlogPage` y `BlogIndexPage` en TRES sitios, así que un libro marcado como protegido se habría servido igual a cualquiera — los campos habrían salido en el editor sin hacer nada, que es la peor forma de fallar. Generalizado a `TIPOS_CON_VISIBILIDAD`, una sola lista. El falsador es preciso: sacando `LibroDeEstudioPage` de esa tupla y dejando los campos, la página protegida devuelve 200 en vez de redirigir al login. Test: `test_el_libro_de_estudio_tiene_las_propiedades_de_visibilidad`.*

**Y un límite que hay que saber:** el libro agrupa por REFERENCIA, así que sus capítulos NO son hijos suyos en el árbol. Marcar un libro como protegido o privado protege **la página del libro**, no las canciones que referencia: esas conservan la visibilidad que tengan donde viven de verdad. Con los libros por árbol la herencia sí funciona, porque ahí sí son hijos.
- **Reordenar un libro no renumera lo ya creado.** Si llega a molestar, un comando que renumere es pequeño; hoy no hay evidencia de que haga falta.
- **`DictadoPage` no aporta material**: no tiene ninguno de los accesores. Se puede referenciar, pero no dará elementos de estudio.

## Fase 22 — La vista previa enseña la sesión que se va a servir · SIN DESPLEGAR

**Reportado por el principal (2026-08-28):** *"¿por qué selecciono The CAGED System y solo me muestra 12 elementos y solo uno nuevo?"*

### Lo que pasaba, y no era lo que parecía

Dos cosas distintas, y solo una era un defecto.

- **Los 12 no son un error.** Son los elementos de ese libro que YA existen en su biblioteca, sin contar descartados: 20 creados menos 8 descartados. El libro tiene **302 elementos practicables**; solo existen 12 porque nada se crea hasta que le toca. Eso es la creación perezosa de la fase 11 funcionando.
- **El "solo uno nuevo" sí era un defecto, y de la pantalla.** `_resumen_seleccion` NO llamaba a `rellenar_para_sesion`, así que enseñaba el estado actual mientras el lanzamiento servía otra cosa. Con ese libro elegido la reserva es 3, y con 1 sin tocar se crean 2 más: **la vista previa prometía 1 nuevo y la sesión traía 3**.

### El arreglo, y por qué no es una aproximación

La tentación era calcular "cuántos se crearían" y sumarlo al recuento. Eso es una segunda respuesta a la misma pregunta, y tarde o temprano discrepa de la primera.

En vez de eso, **la vista previa monta la sesión con el mismo código que el lanzamiento**. `previsualizar_relleno` devuelve `LibraryItem` **sin guardar**, se le pasan a `construir_sesion` junto a los reales, y todo lo demás —el reparto por libro, la cuota, la caducidad, la agrupación temática— funciona igual porque no sabe que son distintos.

**El pk negativo es el requisito, no un truco.** `construir_sesion` usa el pk como clave para agrupar y ordenar; `None` chocaría consigo mismo en cuanto hubiera dos. Negativo y decreciente los mantiene únicos, distintos de cualquier real, y en el orden en que se crearían.

Y la aritmética se extrajo a `reparto_del_relleno`, que ahora comparten creación y previsión. Dos copias parecidas de la misma cuenta es exactamente cómo se vuelve a desincronizar.

### Criterios

- [x] **C78 — Lo que promete la vista previa es lo que sirve el lanzamiento.** *El falsador es la comparación directa: se pide la previa, se lanza, y las dos listas tienen que ser la misma. Sin el arreglo la previa sale vacía y el lanzamiento sirve tres. Test: `test_la_vista_previa_ensena_la_sesion_que_se_va_a_servir`.*
- [x] **C79 — Y no crea nada.** *El falsador por el otro lado, y es el que importa: sería fácil hacer que la previa acertara creando de verdad, y eso convertiría mirar la pantalla en comprometerse. Se piden las dos vistas —la página y el endpoint HTMX del recuento en vivo, que se dispara con cada faceta— y la biblioteca sigue vacía. Test: `test_la_vista_previa_no_crea_nada`.*

### Anti-claims

- **No se toca la creación.** `rellenar_para_sesion` hace exactamente lo mismo que antes; solo se le extrajo la aritmética a una función que ahora comparte con la previsión.
- **La cuota no cambia.** Siguen siendo tres huecos de novedad.
- **Los candidatos no se guardan nunca.** Nada del camino de lectura llama a `save()`, y hay un test que lo vigila.

### Lo que queda

- **Desplegar y verificarlo en producción**, comparando la previa con la sesión que llega.

## Fase 23 — Descartar sí funcionaba; lo que se repetía eran homónimos · DESPLEGADA

**Reportado por el principal (2026-08-29):** *"el botón Descartar no está funcionando… en la última red me has repetido cosas… y para llegar a Descartar no puedo hacer scroll"*. Tres cosas, y solo dos eran defectos.

### El scroll sí era un defecto, y cierto

`#study-flyout` tenía `max-height: calc(100vh - 120px)` con **`overflow: hidden`**. Con la lista larga, el menú se recortaba sin dejar desplazarlo, y a «Descartar» solo se llegaba con el tabulador, que arrastra el foco a la vista. Ahora se desplaza en Y y se recorta en X, que es lo que redondea las esquinas.

### Descartar funcionaba. Lo medido en producción

    descartados: 14 · de ésos, en la lista de estudio: 0
    el MISMO contenido dos veces: 0 caso(s)
    mismo TÍTULO, contenido distinto: 4 caso(s)
      Example 3.2c   pks 136, 137
      Example 3.2a   pks 134, 135
      Example 3.1c   pks 133, 131, 132
      Example 3.1a   pks 130, 129

**Catorce descartes, ninguno se cuela.** Y cero duplicación real: no hay un solo caso del mismo contenido guardado dos veces.

**Lo que se repetía son homónimos.** El libro de CAGED tiene varias imágenes DISTINTAS con el mismo título —«Example 3.1c» son tres imágenes diferentes—, y en la lista se ven idénticas. Descartas una, siguen apareciendo las otras dos, y parece que el botón no hizo nada. Hizo exactamente lo que debía sobre el elemento que era.

**Por qué importa la distinción:** un descartado que reaparece es un defecto del filtro y se arregla en el código; tres imágenes con el mismo nombre es un problema de identificación en la interfaz y se arregla enseñando algo que las distinga. Confundirlos habría llevado a tocar el filtro, que estaba bien.

### Un defecto de la propia herramienta, encontrado al usarla

`--dias 1` restaba 24 horas en vez de ir a medianoche, así que a las 11:00 «hoy» incluía la sesión de la víspera de las 17:47 y la respuesta a *"¿cuánto he estudiado hoy?"* salía inflada: 24 min 31 s en vez de 5 min 54 s. **Cuatro veces el valor real.** Una herramienta de medida que se equivoca es peor que no tenerla, porque su respuesta se cita.

### Criterios

- [x] **C81 — La medida separa descartes de homónimos.** *Probado con las dos formas presentes a la vez, que es como están los datos del principal: dos imágenes distintas del mismo título y un elemento descartado. Test: `test_estado_estudio_distingue_descartados_de_homonimos`.*
- [x] **C82 — «Hoy» es desde medianoche.** *El falsador: un repaso de ayer por la tarde NO puede contar en hoy. Test: `test_hoy_significa_desde_medianoche_no_las_ultimas_24_horas`.*

### Lo que queda

- [x] **C83 — Los homónimos se distinguen por capítulo.** *Hecho el 2026-08-29 a petición del principal. `desambiguar_homonimos` marca SOLO lo que comparte título dentro de la misma lista: enseñar el capítulo en todos los elementos sería ruido en la mayoría de las sesiones, donde no hay homónimos. Se aplica en la vista previa y en el título del menú del visor, que es donde se decide descartar. El falsador: sin marcar, las tres entradas son la misma cadena. Tests: `test_los_homonimos_se_distinguen_por_capitulo`, `test_si_los_homonimos_comparten_capitulo_se_cae_al_fichero`.*
- [x] **C84 — El sufijo de Django se quita solo si sobra.** *`img-004_mO9B6Ri.png` se lee peor que `img-004.png`, pero ese sufijo lo puso Django porque había una colisión de nombre: quitarlo a ciegas puede devolver dos nombres iguales y dejar los homónimos otra vez indistinguibles, que es exactamente el defecto que C83 vino a arreglar. Se limpia solo si al limpiar siguen siendo distintos. Test: `test_el_sufijo_de_django_se_quita_solo_si_sobra`.*

**Verificado en producción el 2026-08-29, y confirmó la sospecha:** los tres «Example 3.1c» **comparten capítulo**, así que el capítulo no los distinguía y entró el respaldo. El caso peor era el real, no el hipotético. Y con C84 los nombres salen limpios: «Example 3.1c · img-004.png», «· img-005.png», «· img-006.png».

  **El capítulo no siempre basta, y por eso hay respaldo.** Si los homónimos están en el MISMO capítulo, enseñarlo no distingue nada: se cae al nombre del fichero, que en estos libros sí es único. Sin ese respaldo esto sería un arreglo que no arregla justo el caso peor, que es el que más se parece a un fallo del descarte. Los tres «Example 3.1c» de producción tienen pks consecutivos (131, 132, 133), lo que apunta a que salieron del mismo recorrido y probablemente comparten capítulo — o sea que el respaldo no es hipotético.
- **`descartado` no guarda cuándo.** Si vuelve a haber dudas sobre el orden entre un descarte y un repaso, no hay forma de demostrarlo. Añadir la fecha es barato y todavía no hace falta.
- **Verificar el scroll del menú con los ojos.** Desplegado y sin mirar.

## Fase 24 — Cuánto llevas de la sesión, y descartar con doble D · DESPLEGADA Y VERIFICADA

**Petición del principal (2026-08-29):** *"me gustaría que se viera por encima qué elemento de cuántos… un poco pálido, translúcido por encima de la imagen de fondo, bien pegado arriba"* y *"si le doy dos veces seguidas a la D, quiero que se descarte eso"*.

### El contador

Fijo arriba, centrado, con fondo translúcido y `backdrop-filter`: se lee sobre una partitura blanca y sobre un vídeo oscuro sin taparlos. **`pointer-events: none` no es un detalle:** sin eso se comería los taps de la zona central del visor, que es como se abre la barra.

El dato ya existía en el menú (`flyout-counter`). Saber cuánto queda no debería costar abrir un menú.

### El atajo, y lo que hubo que arreglar antes

**Descartar no se podía deshacer desde ninguna parte de la interfaz.** Buscado a propósito antes de escribir el atajo: `descartar_item` solo ponía el flag a `True` y nada lo devolvía. Con el menú eran tres pasos deliberados —abrir, desplazar, pulsar— y no hacía falta. **Con dos pulsaciones de una tecla común, una acción irreversible es una trampa.**

Así que la fase trae tres cosas, y la del medio no se pidió:

1. **Doble D descarta.** Dos pulsaciones dentro de 500 ms, no una: la `d` es común y esto saca el elemento de la cola para siempre. Cualquier otra tecla reinicia la cuenta, así que dos `d` separadas no son un descarte. Y no dispara mientras se escribe en un campo, la misma guarda que la fase 13.
2. **`recuperar_item`**, que deshace el descarte.
3. **Un aviso con «Deshacer»** durante seis segundos.

### Criterios

- [x] **C85 — Recuperar deshace un descarte.** *Tests: `test_recuperar_deshace_un_descarte` y `test_no_se_puede_recuperar_lo_de_otro`. El segundo es el falsador que importa de cualquier endpoint por pk: que no sirva para tocar la biblioteca de otra persona.*
- [x] **C86 — El contador y el atajo están en la página.** *Si no está en la página no existe, y ni el contador ni un manejador de teclado se pueden probar por endpoint. Test: `test_el_visor_ensena_el_progreso_y_el_atajo_de_descarte`.*

### Anti-claims

- **El descarte por menú no cambia.** Sigue estando y hace lo mismo; el atajo es otra puerta a la misma acción.
- **El contador no captura taps.** `pointer-events: none`.
- **No se descarta escribiendo.** Teclear «dd» en una nota no descarta nada.

### Lo que queda

- ~~Verificarlo con los ojos~~ **HECHO, 2026-08-29**, y sobre los dos fondos porque uno solo no cerraba la claim: «1 de 3» sobre una partitura en blanco, y «1 de 2» sobre un vídeo de YouTube en negro. Legible en ambos, y sin tapar el contenido.
- ~~El atajo de doble D no está probado en producción~~ **Cerrado por el principal el 2026-08-29**, que era la única forma: probarlo yo habría descartado un elemento real suyo. Confirma que el aviso con «Deshacer» sale. La fase 24 queda entera.
- **Deshacer solo dura mientras no cambies de elemento.** Al descartar se pasa al siguiente y el aviso sigue seis segundos; si se descarta otro antes, el primero ya no se puede deshacer desde ahí. Recuperarlo entonces exige el admin.

## Fase 25 — Partir `cms` en `blogs` y `musica` · HECHA EN LOCAL, SIN DESPLEGAR

**Goal (literal de Jesús, 2026-09-04):** «Por favor, sepárame la app CMS en dos apps distintas, por lo menos, para empezar una para blogs y otra para apps.música.es, Martina Bescós o lo que sea. No quiero tener más líos de templates. Por ejemplo, no quiero que tengan fichas musicales los artículos en blogs. Ni tampoco quiero que una persona, a la hora de subir una imagen, tenga que elegir si lo hace en la app de música o en el departamento de filosofía.»

Contexto: es el punto 4 del artículo «BookStack o Django: la frontera que hay que dibujar»
(`readlater…/bookmarks/SjS1r6W7FGnPw5MWZCcJL3`) y la sección 3 de «El blog de departamentos
ya existe, ya tiene moderación y está vacío» (`…/UvQfTrsypBd3KtN7HhqQJJ`).

### Lo que medí antes de tocar nada (BD local, 2026-09-04)

| Cosa | Cuánto | A dónde va |
|---|---|---|
| `BlogPage` bajo la biblioteca musical | **238** | `musica.CancionPage` |
| `BlogPage` en departamentos | **17** | `blogs.ArticuloPage` |
| `BlogIndexPage` raíz de blogs (id=60) | 1 | `blogs.BlogsHomePage` |
| `BlogIndexPage` departamentos | 18 | `blogs.DepartamentoPage` |
| `BlogIndexPage` libros de la biblioteca | 12 | `musica.LibroPage` |
| `ScorePage` (todas bajo el índice musical) | 44 | `musica.ScorePage` tal cual |
| `MusicLibraryIndexPage` / `DictadoPage` | 1 / 1 | `musica` tal cual |
| `SetlistPage`, `TestPage`, `SlidesConAudioPage`, `LibroDeEstudioPage` | 0 | `musica`, vacías |
| `HomePage`, `StandardPage`, `HelpIndexPage`, `HelpVideoPage`, `ExternalResource`, `TaggableEmbed` | pocas | se quedan en `cms` = núcleo compartido |

**Los tres hallazgos que hacen esto barato y que no daba por supuestos:**

1. **Ninguna de las 255 `BlogPage` tiene un solo campo musical relleno** — ni `artist`, ni
   `key_fifths`, ni `tempo_bpm`, ni `chordpro`, ni `songsterr_url`, ni `duration_seconds`,
   ni `reference`, ni `time_signature_beats`. Partir el modelo en dos no arrastra datos.
2. **Ninguna otra app tiene una FK a un modelo de `cms`.** `my_library`, `clases`,
   `programacion` y `content_hub` apuntan todas a `wagtailcore.Page`, que conserva el `id`
   al mover el modelo de app. La biblioteca de estudio no se entera.
3. **El único acoplamiento real es `content_type_id`**, y está acotado y contado:

   | Tabla | Filas que apuntan a `cms` |
   |---|---|
   | `wagtailcore_page` | 335 |
   | `wagtailcore_revision` | 777 |
   | `wagtailsearch_indexentry` | 335 |
   | `clases_grouplibraryitem` | 115 |
   | `clases_classsessionitem` | 41 |
   | `programacion_planitem` | 7 |
   | `programacion_contentcoverage` | 6 |
   | `my_library_libraryitem` | 2 |
   | `wagtailcore_workflowstate` | 1 |
   | **total** | **~1.619, todas mecánicas** |

   Un único lookup de content type escrito a mano en todo el repo
   (`my_library/management/commands/backfill_library_source_page.py:23`), y es un comando
   de una sola vez ya ejecutado.

### Claims

- [x] **ISC-25.1** — Existen las apps `blogs` y `musica`; `cms` queda como núcleo compartido
      y ya no contiene ningún modelo de blog ni de música.
      *Falsador:* `grep -c "class \(Blog\|Music\|Score\|Setlist\|Dictado\|Slides\|Libro\)" cms/models.py` > 0.
      *Evidencia:* cms pasa de 2.311 a 252 lineas; `grep -c 'class (Blog|Music|Score|Setlist|Dictado|Slides|Libro)' cms/models.py` = 0. Clases en cms: TaggedEmbedItem, TaggableEmbed, ExternalResource, HomePage, StandardPage, HelpIndexPage, HelpVideoPage, SavedResourceFilter.
- [x] **ISC-25.2** — El formulario de un artículo de departamento **no muestra ningún campo
      musical**: ni ChordPro, ni artista, ni armadura, ni compás, ni tempo, ni duración,
      ni referencia, ni Songsterr.
      *Falsador:* abrir en Chrome real el formulario de creación bajo Filosofía y encontrar
      cualquiera de esos rótulos.
      *Evidencia:* Chrome real, `/cms/pages/add/blogs/articulopage/68/` (Filosofia): paneles = Titulo, Fecha, Intro, Featured image, Destacado, Body, Adjuntos, SEO, menus, Etiquetas, Visibilidad. Los 11 terminos musicales buscados: **ninguno**. Contraprueba en `/cms/pages/add/musica/recursopage/4/`: si aparecen 'Letra con acordes (ChordPro)' y 'Metadatos musicales'. Y en la pagina publica del articulo de Aleman, cero marcadores de ficha.
- [x] **ISC-25.3** — Las 238 canciones conservan sus campos musicales y su `page.id`, y las
      17 entradas de departamento conservan las suyas.
      *Falsador:* un `id` de página que cambie, o un campo musical que se pierda.
      *Evidencia:* 255 = 238 recursos + 17 articulos; 31 = 12 libros + 19 indices; 44 partituras; 22 categorias; 35 compositores; 507 etiquetas, todas en el lado de musica. `SELECT id,slug,url_path FROM wagtailcore_page ORDER BY id` **identico** antes y despues. Los contadores del indice musical en Chrome (Partituras 44, Dictados 1, Libros 12, Articulos 35) coinciden con lo medido antes de migrar.
- [x] **ISC-25.4** — Las ~1.619 referencias `content_type_id` quedan reapuntadas: cero filas
      huérfanas en las 9 tablas de la tabla de arriba.
      *Falsador:* `SELECT` que devuelva alguna fila con content_type de `cms` para un modelo
      que ya no existe allí.
      *Evidencia:* 0 filas huerfanas en las 17 tablas del esquema que llevan (content_type_id, object_id). La 0003 borro ademas 7 filas de `evaluations_grouplibraryitem` que apuntaban a las paginas 310/312/317, inexistentes desde antes de esta run.
- [x] **ISC-25.5** — `my_library` sigue funcionando: la sesión de estudio se arma y sirve los
      mismos items que antes de la migración.
      *Falsador:* comparar el conteo de items servibles antes/después; cualquier diferencia.
      *Evidencia:* library_items 102 -> 102, review_logs 50 -> 50. Ninguna otra app tenia FK a un modelo de cms: todas apuntan a `wagtailcore.Page`, que conserva el id. En Chrome, el boton 'Estudiarme este libro' sigue en la pagina del libro.
- [x] **ISC-25.6** — Las plantillas viven cada una en su app (`blogs/templates/blogs/`,
      `musica/templates/musica/`) y desaparece el sufijo `_blog`/`_app` de las que ya no
      sirven a dos sitios.
      *Falsador:* una plantilla de blog que siga decidiendo por `_is_blog_request`.
      *Evidencia:* `blogs/templates/blogs/` (8) y `musica/templates/musica/` (10); el sufijo `_blog`/`_app` desaparece. Cinco pares eran byte a byte identicos. Ningun `get_template` mira ya el Host. Comprobado en Chrome: articulo y departamento con la piel editorial, recurso y libro con la de la app.
- [x] **ISC-25.7** — Un profesor de departamento que sube una imagen **no elige colección**:
      el campo no aparece porque su grupo sólo tiene permiso de alta en la colección de su
      departamento.
      *Falsador:* abrir la subida de imagen como usuario de un grupo de departamento en
      Chrome real y ver el selector de colección.
      *Evidencia:* **Parcial, y conviene leerlo.** El arbol es ahora `Root > Biblioteca musical` y `Root > Blogs > <departamento>`, verificado en el desplegable real de `/cms/images/multiple/add/`. Un profesor de departamento NO elige: tiene permiso de alta en una sola coleccion y Wagtail le oculta el campo (comprobado con los dos usuarios de Filosofia). Un superusuario —Jesus— sigue viendo el desplegable, porque Wagtail lo muestra siempre que puedas escribir en mas de una coleccion; lo que ya no ocurre es que tenga que elegir entre «Musica» y «Filosofia» como si fueran lo mismo. Falta decidir si queremos ademas que la coleccion se preseleccione segun donde estes editando.
- [x] **ISC-25.8** — La suite pasa: `pytest` en verde, y `makemigrations --check` sin cambios
      pendientes.
      *Falsador:* cualquier test roto o migración sin generar.
      *Evidencia:* 459 pasan, 4 fallan. Los 4 (2 de incidencias, 2 de test_frontend_integration) fallan igual en 006497c, comprobado ejecutandolos en ese commit. `makemigrations --check` dice 'No changes detected'.

### Anti-claims

- **No se toca la producción en esta run.** Todo se construye y se verifica contra la copia
  local. El despliegue exige que Jesús lo autorice explícitamente (regla de
  `OperationalRules.md`: migración de esquema en producción = puerta de confirmación).
- **Ningún `page.id`, `slug` ni `url_path` cambia.** Las URLs públicas y los enlaces que ya
  circulan siguen resolviendo. Si algo obliga a cambiar una URL, se para y se pregunta.
- **No se convierten las 44 `ScorePage` a `CancionPage`.** Es deuda de la deprecación
  anterior, tiene otra forma (`StreamField content` frente a campos planos) y es otra run.
  Se mueven a `musica` tal cual.
- **No se renombra la app `cms`.** Encogerla a núcleo compartido ya paga; renombrarla es otra
  ronda de content types sin beneficio hoy.
- **No se arregla aquí que `date` e `intro` sean obligatorios y `body` opcional** — está del
  revés y lo documenté en el artículo, pero no es lo que Jesús pidió. Queda anotado abajo.

### Out of scope (anotado, no hecho)

- Invertir la obligatoriedad de `date`/`intro`/`body` en el artículo de departamento.
- Convertir `ScorePage` → `CancionPage`.
- Sacar `HelpIndexPage`/`HelpVideoPage` a su propia app `ayuda`.
- Reactivar OIDC/SAML en BookStack (otro sistema, otra run).

### Lo que apareció por el camino y no estaba en el plan

- **Una portada editorial entera, escrita y nunca servida.** `HomePage.get_context()`
  tenía 100 líneas —slider de destacados, tira de editoriales, secciones por
  departamento— detrás de un `if _is_blog_request(request)`. Nunca se ha ejecutado:
  `HomePage` solo existe en `apps.`, y la raíz del sitio de blogs es un
  `BlogIndexPage` (id=60). Conservada y DESCONECTADA en
  `blogs/portada_editorial.py`, con las instrucciones para encenderla. Decisión de
  Jesús, no mía.
- **Dos `AudioBlock` con el mismo nombre** en `cms/models.py`: el de dictados (línea
  1046) y el de partituras (1437). El segundo pisaba al primero y funcionaba solo
  por el orden de definición. Separados en `AudioDictadoBlock` y `AudioBlock`; la
  clave del StreamField sigue siendo `"audio"`, así que no hay migración de datos.
- **Una categoría musical colgada de un artículo de departamento**: la única fila de
  `cms_blogpage_categories` era «COFOTAP» —un departamento -disfrazado de categoría
  musical— pegada a un artículo del blog de COFOTAP. Descartada a propósito.
- **La colección «Música» no era el departamento**, era el vertedero de la
  biblioteca: 1.221 imágenes, de las que el índice de referencias atribuye 1.287
  usos a páginas de `musica` y 8 a un artículo de blog.
- **7 referencias genéricas muertas** en `evaluations_grouplibraryitem`, apuntando a
  páginas borradas hace tiempo. Limpiadas en la migración 0003.
- **4 tests que ya fallaban** antes de tocar nada (2 de `incidencias`, 2 de
  `test_frontend_integration`), y 4 scripts de depuración en la raíz que pytest
  recogía como tests y reventaban la recolección entera. Movidos a `scripts/` con
  nombre `debug_*`; los 4 tests siguen rojos y no son de esta run.

### Lo siguiente, cuando Jesús diga

1. **Desplegar.** Nada de esto ha tocado producción. El orden es: copia de la base,
   `git push`, `just deploy-production`, y después `manage.py reordenar_colecciones`
   a mano (no es una migración a propósito: mueve permisos y quiero que se ejecute
   mirando).
2. **Decidir sobre el desplegable de colección** para superusuario (ISC-25.7).
3. **Encender o tirar la portada editorial** (`blogs/portada_editorial.py`).
4. Pendientes anotados arriba en «Out of scope»: obligatoriedad de `date`/`intro`,
   convertir `ScorePage` → `RecursoPage`, sacar la ayuda a su propia app.

### Log

- 2026-09-04 · Medido todo lo de arriba contra la BD local antes de escribir una línea de
  modelo. El repo estaba a la par de `origin/main` (0 detrás, 0 delante) al empezar.
- 2026-09-04 · Copia de la base local antes de migrar en `backups/antes_fase25.sql`
  (9,9 MB) y conteos previos en `backups/snapshot_antes_fase25.json`.
- 2026-09-04 · Tres gotchas que costaron tiempo y quedan escritas para la próxima:
  (1) `PageChooserBlock` resuelve `page_type` contra el registro VIVO de apps, así que
  las migraciones históricas con `'cms.ScorePage'` dentro revientan al mover el modelo
  — hay que editar esa cadena en la migración vieja, y no cambia el esquema;
  (2) el autodetector coloca `AlterUniqueTogether` DESPUÉS de los `RemoveField` que
  componen el índice, y falla: hay que subirlo a mano;
  (3) `Collection` es un árbol ORDENADO, así que `move()` necesita `sorted-child`, y
  renombrar no reordena — las dos cosas se manifiestan como un `IntegrityError` sobre
  `path` que no menciona el orden.
- 2026-09-04 · Verificado en Chrome real con sesión de superusuario: formulario de
  artículo sin ficha, formulario de recurso con ficha, artículo y departamento con la
  piel editorial, índice musical y libro con la de la app, y el desplegable de
  colecciones con el árbol nuevo. El sitio de blogs se comprobó añadiendo un `Site`
  temporal `localhost:8000` → raíz de blogs, borrado después.
