# Plantilla — Artículo de una canción

Contrato de contenido y estilo para las `musica.RecursoPage` que cuelgan de
`/indice-de-recursos-musicales/` y tratan de **una canción concreta**.

Objetivo: que un alumno de 3.º–4.º de ESO (13–15 años) lea la página entera
sin abandonar, entienda **qué hace la música**, y acabe dándole al play.

Referencia de lo ya publicado: `viva-la-vida-coldplay-2`, `paseo-estopa-2005`,
`billie-jean-michael-jackson-1983`, `smells-like-teen-spirit-nirvana-1991`.

---

## 1. Las dos lenguas

**Cada canción existe en castellano y en inglés, en la misma página.** El
inglés es para la bilingüe. Decidido el 2026-09-15 (fase 33 del ISA).

Lo que cambia con la lengua es solo la prosa: entradilla, Por dónde entrar,
Contexto, Cómo suena, Curiosidades, Escucha guiada, Para hacer en clase y
Vocabulario. Lo demás —artista, tonalidad, BPM, compás, etiquetas, videoclip,
tutoriales, partitura, adjuntos— es la misma ficha para las dos, y se escribe
una sola vez.

Tres consecuencias prácticas:

- **No traduzcas: escribe la otra versión.** Un buen artículo en castellano
  sobre Estopa no es la traducción del inglés. El gancho cambia (lo que suena
  en un anuncio aquí no es lo que suena allí) y las curiosidades también. Lo
  que **no** cambia son los datos: el minutaje, la tonalidad y las fechas
  tienen que decir lo mismo en las dos, o una de las dos miente.

- **Las dos se generan en la misma pasada**, desde el mismo prompt de la
  sección 5. Es lo que hace sostenible mantener 68 textos siendo un
  departamento de una persona.

- **El alumno no elige.** El de la bilingüe abre el artículo en inglés y el de
  un grupo ordinario en castellano, con la misma URL. El selector de lengua
  está para el profesor, y solo asoma cuando existen las dos versiones.

Las reglas de estilo de la sección 3 valen igual en las dos lenguas.

---

## 2. Esqueleto de la página

Orden fijo. Las secciones marcadas **NUEVO** no están todavía en los artículos
publicados; son las que cierran el hueco entre "correcto" y "lo terminan de leer".

| # | Sección (ES) | Sección (EN) | Obligatoria |
|---|---|---|---|
| H1 | `{Canción} — {Artista} ({Año})` | igual | sí |
| — | Entradilla: 1–2 frases | search description | sí |
| — | Tags: `artista:`, `estilo:`, `curso:` | igual | sí |
| H2 | **Por dónde entrar** — NUEVO | Why this song | sí |
| H2 | Contexto histórico | Historical Context | sí |
| H2 | Cómo suena | Musical Characteristics | sí |
| H2 | Curiosidades | Trivia and Curiosities | sí |
| H2 | **Escucha guiada** — NUEVO | Guided Listening | sí |
| H2 | **Para hacer en clase** — NUEVO | Classroom Activities | recomendada |
| H2 | **Vocabulario fundamental** — NUEVO | Key Vocabulary | sí |
| H2 | Recursos | Resources | sí |
| H3 | · Videoclip oficial | Official Music Video | sí |
| H3 | · Tutoriales (guitarra / piano / batería / voz) | Tutorials | si los hay |
| H3 | · Partitura / leadsheet (embed de la `ScorePage`) | Score | si la hay |
| H3 | · Backing track / playlist | Backing track | opcional |

**Consistencia**: en `viva-la-vida` los tutoriales son `H2` sueltos y en `paseo`
el videoclip cuelga de `Resources`. A partir de ahora, **todo lo audiovisual va
dentro de `Recursos` como `H3`**. Así el índice lateral queda legible.

---

## 3. Qué va en cada sección, y con qué voz

### Por dónde entrar (2–4 frases) — NUEVO

Empieza por lo que el alumno **ya tiene en el oído**: un anuncio, un partido, un
meme, un videojuego, una serie, un sample. Primero el reconocimiento, después la
fecha. Nunca al revés.

> Modelo de referencia: la sintonía de la Champions es *Zadok the Priest*, que
> Händel escribió para la coronación de Jorge II en 1727.

Si la canción no tiene un gancho externo, el gancho es una pregunta que la
propia canción responde ("¿por qué esta canción no tiene estribillo?").

### Contexto histórico (2–3 párrafos)

La historia sirve al oído, no al revés. Cada dato tiene que explicar algo de
**cómo suena** o de **por qué existe**: el productor que cambió el rumbo (Eno en
*Viva la Vida*), la escena de la que sale, lo que hizo posible la tecnología del
momento. Fuera las listas de premios que no cambian nada.

### Cómo suena (el núcleo)

Aquí es donde los artículos actuales se quedan cortos: enumeran datos
(`138 BPM`, `Ab major`) sin decir qué le hacen al oído.

Regla: **cada elemento musical se explica por su efecto, y el término técnico
llega después, como premio, no como peaje.**

- ❌ "Presenta textura homofónica."
- ✅ "Una melodía manda y el resto la sostiene, como una voz con la banda
  detrás. A eso se le llama **textura homofónica**."

- ❌ "Progresión de cuatro acordes Ab–Eb–Bbm–F."
- ✅ "Son cuatro acordes que se repiten de principio a fin, sin cambiar nunca.
  Toda la sensación de que la canción *crece* viene de los instrumentos que se
  van sumando encima, no de la armonía: **Ab–Eb–Bbm–F**, una y otra vez."

Datos que sí van, siempre juntos y al final del bloque: tonalidad, BPM, compás,
duración, forma.

### Curiosidades (3–6 viñetas)

Ya funcionan bien. Única regla nueva: **si la anécdota se puede quitar y el
párrafo sigue igual, es decoración — fuera.** La buena curiosidad demuestra
algo (el pleito de Satriani demuestra lo poco que hace falta para que dos
melodías se parezcan; el "pienso, luego aún existo" de Estopa demuestra que la
letra popular juega con la culta).

### Escucha guiada (3–4 puntos con minutaje) — NUEVO

Es lo que convierte la página en clase. Cada punto: **minuto + qué escuchar +
qué concepto demuestra**.

```
0:00  Campanas y cuerda sola. Todavía no hay pulso: la música aún no "anda".
0:16  Entra el timbal marcando. Ese redoble militar es lo que hace que suene
      a coronación y no a balada.
1:22  Vuelve la misma vuelta de cuatro acordes, pero ahora con coro. Nada ha
      cambiado en la armonía; lo único que ha cambiado es cuánta gente canta.
```

### Para hacer en clase (2–4 propuestas) — NUEVO

Cortas, ejecutables en una sesión, con el recurso enlazado:

- **Tocar**: la progresión en ukelele/teclado (enlaza el leadsheet).
- **Cantar**: qué parte y en qué tesitura (ojo a la muda de la voz).
- **Analizar**: una pregunta cerrada y comprobable ("¿dónde está el estribillo?
  Justifica por qué no lo hay").
- **Crear**: reusar el procedimiento de la canción, no la canción.

### Vocabulario fundamental (5 términos como mucho) — NUEVO

Va justo antes de Recursos, y es lo último que se lee. No es un glosario: es
**lo que hay que llevarse de esta canción**, y por eso tiene tope de cinco. Con
diez, no se queda ninguno.

Reglas duras:

- **Solo entran términos que el artículo ya ha explicado.** Si una palabra
  aparece aquí y no antes, o sobra aquí o falta arriba. El orden es el de
  aparición en el texto, no el alfabético.

- **En castellano: término y definición.** Una línea, con la misma voz del
  resto — por el efecto que produce, no por el manual.

  > **Textura homofónica** — Una melodía manda y el resto la sostiene, como una
  > voz con la banda detrás.

- **En inglés: término y traducción al castellano.** El alumno de la bilingüe
  necesita amarrar la palabra inglesa a la que ya tiene. Si la traducción sola
  no basta para entenderla, añade media línea; si basta, no la añadas.

  > **Homophonic texture** — textura homofónica
  >
  > **Backbeat** — el golpe a contratiempo (2 y 4)

- **Nada de palabras que no son de música.** *Coronación*, *pleito* o
  *videoclip* no son vocabulario fundamental por mucho que salgan en el texto.

### Recursos

Orden fijo dentro de `Recursos`:

1. **Videoclip oficial** — `youtube` embed. Siempre el primero.
2. **Tutoriales** — guitarra, piano, batería, voz. Uno por instrumento, el más
   claro, no el más visto.
3. **Partitura / leadsheet** — embed de la `ScorePage` correspondiente
   (p. ej. `VivalaVidaSAT`). Si no existe, créala antes.
4. **Backing track / playlist** — opcional.

---

## 4. Reglas de voz (valen para todo el artículo)

- **Frases cortas.** Media de 15–20 palabras. Un concepto nuevo por párrafo.
- **Segunda persona sin infantilizar.** "Fíjate en el bajo" sí. "¿A que mola?" no.
- **Cifras concretas y comparables.** El asombro lo produce el dato, no el adjetivo.
- **Honestidad sobre lo que no se sabe.** "Probablemente", "no está claro".
- **Cada bloque grande termina en una escucha**, no en un resumen.
- **La broma es de adulto compartida**, no de profe simpático.

### Antipatrones (hunden el texto a los 14)

- Narrador-niño protagonista, exclamaciones, diminutivos.
- `¿Sabías que...?` de muletilla.
- Adjetivos de catálogo: *genial*, *maravilloso*, *icónico*, *insuperable*, *legendario*.
- Listas de fechas y premios sin oído detrás.
- Párrafos de más de cuatro líneas.

---

## 5. Prompt reutilizable

Pega esto y rellena los huecos. El resultado se pega en el `StreamField` de la
`RecursoPage` en Wagtail.

```text
Escribe las DOS versiones —castellano e inglés— de un artículo para el Índice
de recursos musicales de apps.iesmartinabescos.es sobre:

  CANCIÓN:  {título}
  ARTISTA:  {artista}
  AÑO:      {año}
  CURSO:    {3º ESO | 4º ESO}
  UNIDAD:   {qué se está dando — p. ej. "texturas", "la música de los 80"}
  GANCHO:   {si lo sabes: anuncio, película, meme, sample donde lo han oído}

Sigue el contrato docs/PLANTILLA_ARTICULO_CANCION.md: secciones en el orden
fijo, con Escucha guiada minutada, Para hacer en clase y Vocabulario
fundamental (cinco términos como mucho, justo antes de Recursos).

Estado ideal del texto — se cumple o no se cumple:
- Un alumno de 14 años lo lee entero sin abandonar.
- Todo elemento musical se explica por su efecto en el oído antes de nombrarse.
- Cada curiosidad demuestra algo; ninguna es decoración.
- La Escucha guiada tiene minutaje real y verificable contra el videoclip.
- Cero adjetivos de catálogo; cero "¿sabías que...?".
- Los datos duros (tonalidad, BPM, compás, duración, forma) aparecen una sola
  vez, agrupados, al final de "Cómo suena".
- El Vocabulario solo recoge términos que el artículo ya ha explicado, en el
  orden en que salen: en castellano con definición, en inglés con traducción.

Las dos versiones no son la misma traducida: el gancho y las curiosidades
pueden cambiar. Los datos NO cambian — minutaje, tonalidad, BPM y fechas dicen
lo mismo en las dos.

Devuélvelo como un solo JSON, listo para POST /api/cms/blog-pages:

  {
    "title": "...", "date": "AAAA-MM-DD",
    "idioma": "es",
    "intro": "entradilla en castellano",
    "body": "<artículo en castellano>",
    "traducciones": [
      {"idioma": "en", "intro": "entradilla en inglés", "body": "<artículo en inglés>"}
    ]
  }

Para los recursos, dame los enlaces candidatos con su URL y por qué ese y no
otro. No inventes enlaces: si no estás seguro de que un vídeo existe, dilo.
```

---

## 6. Checklist antes de publicar

- [ ] El minutaje de la Escucha guiada está comprobado contra el vídeo enlazado.
- [ ] Los datos duros (tonalidad, BPM, año, sello) contrastados con una fuente.
- [ ] Todos los embeds cargan y ningún vídeo está en privado o geobloqueado.
- [ ] Existe la `ScorePage` enlazada, o se ha quitado el `H3` de partitura.
- [ ] Tags puestos: `artista:`, `estilo:`, `curso:`.
- [ ] Entradilla de 1–2 frases rellenada (es lo que sale en el índice).
- [ ] Ningún adjetivo de la lista de antipatrones.
- [ ] Vocabulario fundamental: cinco términos como mucho, todos explicados
      antes en el texto, y ninguno que no sea de música.
- [ ] Existen las dos versiones, y los datos duros coinciden entre ellas.
- [ ] La página abre en inglés con `?lang=en` y en castellano con `?lang=es`.
