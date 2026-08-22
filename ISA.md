---
slug: app-martina
phase: build
progress: true
iteration: 10
principal_stated_goal: "ok, quiero que hagas lo más limpio y con visión de futuro"
updated: 2026-08-21
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

### Lo siguiente, por orden

0. **Fase 8 — `MusicTag` → taggit facetado. EN MARCHA.** El comando de re-etiquetado (C34a) está escrito, con 14 tests, y su ensayo en seco valida el mapa entero. Lo que falta para poder ejecutarlo es **C33, la migración de esquema**, que es el paso que querías confirmar antes. Ver la sección "Fase 8", con la decisión de secuencia expandir → migrar → contraer.
1. **Presupuesto de sesión en MINUTOS en vez de en elementos.** Es la mejor idea pendiente y la que arregla que "8 elementos" sea una unidad mentirosa cuando uno es un lick de 40 segundos y otro una pieza de 14 minutos. **Necesita datos**: `ReviewLog.duration_seconds` lleva recogiendo desde el 12/08/2026. Con dos semanas de práctica real, cada elemento tiene su mediana y el presupuesto se calibra solo. *Antes del 26/08 no tiene sentido tocarlo.*
2. **Orden real dentro de un libro.** Hoy el material nuevo entra por orden de alta en la biblioteca, que coincide con el libro solo por casualidad. Hace falta modelar libro → sección → ejercicio con un ordinal. Es la misma pieza que pedía el troceo, así que encaja encima de `ItemSection`.
3. **Revisar los plazos de caducidad con datos reales** (hoy 1/1/3/7/21 días por nivel). El de 21 días para "me lo sé muy bien" es el más dudoso: para un dato está bien, para tener una escala en las manos puede ser demasiado.

### Deuda conocida, sin bloquear nada

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
- [~] **C28 — Trocear en un navegador real. Mitad hecha.** *2026-08-21.*
  - **El panel, visto y usado:** crear la sección «Estribillo» desde el visor funciona — el panel se repinta con «1 Estribillo ✕» y la fila aparece en la BD (`ItemSection` 5, item 34, orden 0). Se ve en la captura del panel.
  - **El salto de página, comprobado a nivel de estado pero no de píxeles.** Con una sección en la página 5 de un PDF de 15, el visor abre con `paginaInicial = 5` y `currentPage = 5` — no en la 1. Lo que NO se pudo ver es el pixel de esa página, ni pasar página después: la pestaña nunca llegó a `visibilityState = "visible"` ni con `--activate`, y con la pestaña oculta el `requestAnimationFrame` de pdf.js no corre, así que la promesa de `page.render` no resuelve y `rendering` se queda en `true` para siempre. **Con esa bandera atascada, `renderPage` sale por el guardia `if (rendering) return` y no se puede cambiar de página.** Queda por decidir si eso es solo el estrangulamiento de la pestaña oculta —lo más probable— o un fallo real: hace falta una ventana visible de verdad, que es justo lo que no puedo forzar sin robarte el foco. *Reproducirlo cuesta 10 segundos: abre `/my-library/study/?items=s7` en local y mira si puedes pasar de página.*

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


## Fase 8 — Un solo vocabulario de etiquetas · PLANIFICADA, SIN EMPEZAR

> **Punto de retorno.** El mapa está cerrado y revisado. No se ha escrito ni una línea de código. Lo siguiente es la migración de esquema, y el principal pidió confirmarla antes de empezar porque toca cuatro modelos de página en producción.

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

- [ ] **C33 — Las cuatro páginas tienen manager de taggit.** `ClusterTaggableManager` + through model por tipo de página; el through hace falta por el sistema de revisiones de Wagtail. *Es una migración de esquema en producción: el paso con riesgo, y el que el principal quiere confirmar antes.*
- [x] **C34a — El comando lee el mapa, lo valida y PLANIFICA el re-etiquetado.** *2026-08-22, ensayo en seco contra una copia de la BD de producción del 20/08 restaurada en local. Las cuatro validaciones pasan sobre los datos reales: el mapa cubre las 80 `MusicTag` vivas, ningún destino es a su vez origen, ningún par de orígenes colisiona en minúsculas, ninguna faceta de destino es desconocida. **Plan: 164 páginas (BlogPage 148, ScorePage 15, DictadoPage 1), 531 etiquetados hacia 35 destinos; 9 etiquetas nuevas en taggit y 26 que fusionan con las que ya existen.** 15 tests.*
- [ ] **C34b — `--ejecutar` escribe las etiquetas en las páginas.** Depende de C33: sin manager de taggit no hay dónde escribir. *El guardia está probado contra los datos reales: `--ejecutar` aborta nombrando C33 y no toca nada.* Todo en una transacción; no borra ni una `MusicTag` — el destino del modelo es C37.
- [ ] **C35 — Ningún elemento de biblioteca pierde etiquetas.** *Control ya medido sobre la copia del 20/08 y guardado en `backups/control_c35_antes.json` (fuera del repo): **102 elementos, 469 etiquetados, 16 elementos sin ninguna etiqueta**. Comparar elemento a elemento contra ese fichero después de C34b.*
- [ ] **C36 — `build_tag_map` deja de leer de dos sitios, Y arrastra los mazos en la misma transacción.** Hoy recoge de los dos vocabularios sin distinguir. Al terminar debe leer solo taggit. *Probe: los tres mazos siguen contando 23 / 9 / 11.*
  - ⚠️ **Aquí es donde se rompe el mazo `caged-system`, y es la tercera vez que este defecto se presenta.** Medido el 22/08 contra la copia de producción: `caged-system` existe **solo como `MusicTag`**, no en taggit; el mazo empareja 11 elementos y **los 11** sacan la etiqueta de la `MusicTag` de su página. En cuanto `build_tag_map` lea solo taggit, ese nombre deja de existir y el mazo cuenta 0 — exactamente el fallo del 12/08. El mapa lo manda a `concepto:caged`, que ya existe en taggit.
  - **Los otros dos mazos sobreviven solos:** `guitarra jazz` (`instrumento:guitarra`, `estilo:jazz`) y `Piano` (`instrumento:piano`) ya apuntan a nombres facetados de taggit.
  - **La herramienta ya existe:** `migrar_etiquetas.planificar_mazos` aplica un mapa a `tags_json`. C36 tiene que llamarla con `mapa_musictags.txt` **dentro de la misma transacción** que el cambio de `build_tag_map`. Quedarse a medias aquí es de lo que venimos.
- [ ] **C37 — `MusicTag` queda vacío y se decide su destino.** Borrar el modelo y el campo `tags` de las cuatro páginas, o dejarlo muerto. Dejarlo muerto es lo que produjo `content_hub`.

### Decisión de secuencia — expandir, migrar, contraer (2026-08-21)

El campo `tags` de las cuatro páginas **ya está ocupado** por el `ParentalManyToManyField` a `MusicTag`. No se puede añadir el manager de taggit con ese nombre, y renombrar de golpe abre una ventana en la que `build_tag_map` lee un campo vacío y los mazos cuentan 0. Es exactamente el fallo del 12/08 otra vez.

Así que se hace en tres tiempos, y ninguno rompe el sitio por sí solo:

1. **Expandir** (C33) — el manager nuevo entra como `faceted_tags`, junto al `tags` de siempre. Nadie lo lee todavía.
2. **Migrar** (C34b, C35) — el comando llena `faceted_tags` desde el mapa y se comprueba la paridad elemento a elemento. Las dos vías coexisten.
3. **Contraer** (C36, C37) — `build_tag_map` pasa a leer solo taggit, y solo entonces se borra `tags` y `faceted_tags` se renombra a `tags`.

El coste es un nombre feo viviendo unos días. Lo que compra es que en ningún momento hay un despliegue con las etiquetas de las páginas en el aire.

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
