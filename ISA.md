---
slug: app-martina
phase: complete
progress: true
iteration: 7
principal_stated_goal: "ok! eliminemos study_sessions. Y vamos a desarrollar ReviewLog"
updated: 2026-08-15
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

### Lo siguiente, por orden

1. **Presupuesto de sesión en MINUTOS en vez de en elementos.** Es la mejor idea pendiente y la que arregla que "8 elementos" sea una unidad mentirosa cuando uno es un lick de 40 segundos y otro una pieza de 14 minutos. **Necesita datos**: `ReviewLog.duration_seconds` lleva recogiendo desde el 12/08/2026. Con dos semanas de práctica real, cada elemento tiene su mediana y el presupuesto se calibra solo. *Antes del 26/08 no tiene sentido tocarlo.*
2. **Orden real dentro de un libro.** Hoy el material nuevo entra por orden de alta en la biblioteca, que coincide con el libro solo por casualidad. Hace falta modelar libro → sección → ejercicio con un ordinal. Es la misma pieza que pedía el troceo, así que encaja encima de `ItemSection`.
3. **Revisar los plazos de caducidad con datos reales** (hoy 1/1/3/7/21 días por nivel). El de 21 días para "me lo sé muy bien" es el más dudoso: para un dato está bien, para tener una escala en las manos puede ser demasiado.

### Deuda conocida, sin bloquear nada

- **C12, C28 y C30bis: nada del visor se ha verificado en un navegador real.** Ni el panel de notas, ni la nota docente, ni el selector de facetas, ni el troceo, ni el arreglo de los comentarios. Interceptor sigue bloqueado por un setup manual de Chrome que requiere clicks humanos. **Desbloqueo, una vez y para siempre:** en la ventana del perfil de pruebas, icono de Interceptor → Context ID = `interceptor-test` → Guardar, y poner esa misma cadena en `~/.claude/LIFEOS/USER/CUSTOMIZATIONS/SKILLS/Interceptor/preferences.env`. Son dos minutos y desatasca cinco claims acumuladas.
- **6 sitios con `user.username`** en otras apps, que en este proyecto siempre vale `None`. Dos son crashes de búsqueda en el admin: `evaluations/admin.py:125` y `cms/models.py:1788`, `cms/wagtail_hooks.py:34`, `evaluations/admin.py:163`, y dos plantillas de `incidencias`.
- **Cuatro scripts en la raíz rompen `pytest`**: `test_images.py`, `test_tags.py`, `test_tags2.py`, `test_viewer_html.py` llaman a `django.setup()` al importarse. Hay que excluirlos a mano para que la suite arranque; deberían renombrarse.
- **9 tests preexistentes fallan** en analytics, cms e incidencias. Verificado con `git stash` que ya fallaban antes de todo esto.
- **La etiqueta `borrar`** es la única de las 139 sin faceta: en la revisión del mapa se eliminó su línea, lo que significa "déjala como está".
- **Tablas huérfanas de `study_sessions`** en la BD de producción. Inertes; borrarlas es decisión del principal.
- **`build_tag_map` hace ~2 consultas por elemento** y corre en cada carga del índice y en cada render del panel de mazos. A 500 elementos se notará.
- **El vocabulario de etiquetas está partido en dos y solo uno tiene facetas.** `taggit.Tag` (139, facetadas) y `cms.MusicTag` (80, planas: `guitar`, `guitarra`, `jazz`, `piano`…). Encontrado en la fase 7. La fragmentación que motivó las facetas sigue entera en `MusicTag`, y la sesión de estudio no puede agrupar ni filtrar por nada de lo que viva ahí. Decidir: migrar `MusicTag` al mismo mapa, o fundir los dos vocabularios. No bloquea nada hoy, pero deja media biblioteca fuera del sistema de facetas.

### Datos útiles para retomar

- Producción: `https://apps.iesmartinabescos.es` · deploy con `just deploy-production` (hace `git reset --hard origin/main` en el servidor, así que hay que pushear antes).
- Local: `just up`, tests con `docker compose -f docker-compose.local.yml run --rm django pytest my_library/tests.py`.
- Usuario de pruebas en local: `probe@local.test` (staff/superuser). En la BD local, no en producción.
- Copia previa a la migración de etiquetas: `backups/taggit_antes_facetas_20260812.json` (fuera del repo, está en `.gitignore`).
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
- [ ] **C12 — `[DEFERRED-VERIFY]` El panel funciona en navegador.** Falta abrir el visor, pulsar `M` y comprobar que se ven etiquetas y notas, que el texto se guarda solo y que sobrevive al cambio de item.

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
- [ ] **C28 — `[DEFERRED-VERIFY]` Trocear en un navegador real.** Ni el panel ni el salto de página se han visto ejecutándose.

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
- [ ] **C30bis — `[DEFERRED-VERIFY]` Las dos páginas vistas en un navegador real.** Intentado el 15/08 tras desplegar: Interceptor paró en el gate de aislamiento por rotación del UUID del contexto, y no se sustituye por un curl. Se suma a la deuda de C12 y C28. *Desbloqueo, una vez y para siempre: en la ventana del perfil de pruebas, icono de Interceptor → Context ID = `interceptor-test` → Guardar, y la misma cadena en `preferences.env`.*
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
