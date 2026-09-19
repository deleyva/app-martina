"""Traducir «de los 70 con 3 acordes» a filtros, con reglas y sin modelo.

**Por qué por reglas.** La gramática que hace falta aquí es diminuta y cerrada:
décadas, número de acordes, instrumento, idioma, nivel. Un LLM costaría dinero
por consulta, tardaría, y fallaría de formas raras justo cuando el profesor
tiene prisa. Doscientas líneas de expresiones regulares no fallan y se pueden
probar.

**Y nunca es una caja negra.** Además de los filtros, esta función devuelve las
etiquetas de lo que ha entendido, para pintarlas como chips borrables. Si
interpreta mal, se ve y se quita con un clic; no hay que adivinar por qué salen
esos resultados.
"""

import re

NUMEROS = {
    "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}

INSTRUMENTOS = {
    "ukelele": "Ukulele", "ukulele": "Ukulele", "uke": "Ukulele",
    "guitarra": "Guitar", "guitarras": "Guitar",
    "teclado": "Keyboard", "piano": "Keyboard", "teclados": "Keyboard",
    "bateria": "Drums", "batería": "Drums", "percusion": "Drums", "percusión": "Drums",
    "bajo": "Bass",
    "banda": "Modern Band", "grupo": "Modern Band", "conjunto": "Modern Band",
}

IDIOMAS = {
    "español": "spanish", "espanol": "spanish", "castellano": "spanish",
    "inglés": "english", "ingles": "english",
    "francés": "french", "frances": "french",
    "japonés": "japanese", "japones": "japanese",
    "coreano": "korean",
    "hawaiano": "hawaiian",
}

NIVELES = {
    "fácil": "Beginner", "facil": "Beginner", "fáciles": "Beginner",
    "faciles": "Beginner", "sencilla": "Beginner", "sencillas": "Beginner",
    "principiante": "Beginner", "principiantes": "Beginner",
    "intermedio": "Intermediate", "intermedia": "Intermediate",
    "difícil": "Advanced", "dificil": "Advanced", "difíciles": "Advanced",
    "dificiles": "Advanced", "avanzado": "Advanced", "avanzada": "Advanced",
}

# Ruido de la frase hablada. Se quita del texto sobrante para que «dame una
# canción de los 70» no acabe buscando literalmente «dame una canción de».
RELLENO = {
    "dame", "dime", "ponme", "busca", "buscame", "búscame", "buscar", "quiero",
    "necesito", "enseñame", "enséñame", "alguna", "algun", "algún", "algo",
    "una", "un", "unas", "unos", "cancion", "canción", "canciones", "tema",
    "temas", "de", "del", "la", "el", "los", "las", "con", "que", "para", "y",
    "en", "sobre", "sea", "sean", "tenga", "tengan", "por", "a", "al",
}

# Si el número de dos cifras es 00, 10 o 20 se entiende siglo XXI; de 30 en
# adelante, siglo XX. Es la lectura natural en 2026 y evita preguntar.
def _decada_de_dos_cifras(n):
    return 2000 + n if n <= 20 else 1900 + n


def interpretar_consulta(texto):
    """De una frase a `(filtros, chips, resto)`.

    - `filtros`: lo que entiende `Cancion.buscar()`.
    - `chips`: lista de `{"clave", "valor", "etiqueta"}` para pintar y poder quitar.
    - `resto`: lo que no ha reconocido, para búsqueda libre de texto.
    """
    if not texto or not texto.strip():
        return {}, [], ""

    restante = texto.lower()
    filtros = {}
    chips = []

    def consumir(patron, manejador):
        """Aplica el manejador a cada coincidencia y la borra del texto."""
        nonlocal restante

        def sustituir(m):
            manejador(m)
            return " "

        restante = re.sub(patron, sustituir, restante, flags=re.IGNORECASE)

    # --- Número de acordes. Va ANTES que la década para que «3 acordes» no se
    # lea como un año, y para que «los 70 con 4 acordes» no pierda el 4. ---
    palabras_num = "|".join(NUMEROS)
    comparadores = r"(menos\s+de|hasta|m[áa]ximo|como\s+mucho|m[áa]s\s+de|al\s+menos|m[íi]nimo)"

    def acordes(m):
        bruto = (m.group("n") or "").strip()
        n = NUMEROS.get(bruto, None)
        if n is None:
            n = int(bruto)
        comp = re.sub(r"\s+", " ", (m.group("comp") or "").strip())
        if comp in ("menos de",):
            filtros["num_acordes_max"] = n - 1
            chips.append({"clave": "num_acordes_max", "valor": n - 1, "etiqueta": f"≤ {n - 1} acordes"})
        elif comp in ("hasta", "maximo", "máximo", "como mucho"):
            filtros["num_acordes_max"] = n
            chips.append({"clave": "num_acordes_max", "valor": n, "etiqueta": f"≤ {n} acordes"})
        elif comp in ("mas de", "más de"):
            filtros["num_acordes_min"] = n + 1
            chips.append({"clave": "num_acordes_min", "valor": n + 1, "etiqueta": f"≥ {n + 1} acordes"})
        elif comp in ("al menos", "minimo", "mínimo"):
            filtros["num_acordes_min"] = n
            chips.append({"clave": "num_acordes_min", "valor": n, "etiqueta": f"≥ {n} acordes"})
        else:
            filtros.setdefault("num_acordes", []).append(n)
            chips.append({"clave": "num_acordes", "valor": n, "etiqueta": f"{n} acordes"})

    consumir(
        rf"(?:(?P<comp>{comparadores})\s+)?(?P<n>\d+|{palabras_num})\s+acordes?",
        acordes,
    )

    # --- Década: «los 70», «años 70», «70s», «1970», «1970s». ---
    def decada_cuatro(m):
        n = (int(m.group("a")) // 10) * 10
        filtros.setdefault("decada", []).append(n)
        chips.append({"clave": "decada", "valor": n, "etiqueta": f"años {n}"})

    def decada_dos(m):
        n = _decada_de_dos_cifras(int(m.group("a")))
        filtros.setdefault("decada", []).append(n)
        chips.append({"clave": "decada", "valor": n, "etiqueta": f"años {n}"})

    consumir(r"\b(?:a[ñn]os\s+|d[ée]cada\s+de\s+(?:los\s+)?|los\s+)?(?P<a>(?:19|20)\d{2})s?\b", decada_cuatro)
    consumir(r"\b(?:a[ñn]os\s+|d[ée]cada\s+de\s+(?:los\s+)?|los\s+)(?P<a>\d{2})\b", decada_dos)
    consumir(r"\b(?P<a>\d{2})s\b", decada_dos)

    # --- Instrumento, idioma, nivel: vocabularios cerrados. ---
    def vocabulario(diccionario, clave, formato):
        def manejador(m):
            valor = diccionario[m.group(0).lower()]
            filtros.setdefault(clave, [])
            if valor not in filtros[clave]:
                filtros[clave].append(valor)
                chips.append({"clave": clave, "valor": valor, "etiqueta": formato(m.group(0).lower())})

        return manejador

    consumir(
        r"\b(?:" + "|".join(sorted(INSTRUMENTOS, key=len, reverse=True)) + r")\b",
        vocabulario(INSTRUMENTOS, "instrumento", lambda p: p.capitalize()),
    )
    consumir(
        r"\b(?:" + "|".join(sorted(IDIOMAS, key=len, reverse=True)) + r")\b",
        vocabulario(IDIOMAS, "idioma", lambda p: f"en {p}"),
    )
    consumir(
        r"\b(?:" + "|".join(sorted(NIVELES, key=len, reverse=True)) + r")\b",
        vocabulario(NIVELES, "nivel", lambda p: p.capitalize()),
    )

    # --- Favoritas y curso. ---
    def favorito(m):
        filtros["favorito"] = True
        chips.append({"clave": "favorito", "valor": "1", "etiqueta": "Favoritas"})

    consumir(r"\bfavoritas?\b|\bfavoritos?\b", favorito)

    def curso(m):
        codigo = f"{m.group('c')}eso"
        filtros.setdefault("curso", []).append(codigo)
        chips.append({"clave": "curso", "valor": codigo, "etiqueta": f"{m.group('c')}º ESO"})

    consumir(r"\b(?P<c>[1234])\s*[ºo]?\s*(?:de\s+(?:la\s+)?)?eso\b", curso)

    # --- Lo que sobra, quitando el relleno. ---
    palabras = [p for p in re.split(r"[^\wáéíóúüñ]+", restante) if p]
    resto = " ".join(p for p in palabras if p not in RELLENO).strip()

    return filtros, chips, resto
