"""Leer las listas de la aplicación de gestión del centro.

Llegan como volcados de phpMyAdmin (`INSERT INTO ... VALUES (...), (...);`) de
tres tablas: `DepartamentosInstituto`, `DepartamentosProfesorado` y
`CuentasGoogle`. No se importan a una base de datos: solo se leen las filas.

Dos cosas que no son obvias y que costaron medirlas (2026-09-16):

- **El profesor se casa con su cuenta por Id, no por nombre.**
  `DepartamentosProfesorado.IdProfesorado` es `CuentasGoogle.Id` en 107 de 107
  filas; por nombre solo casan 104, porque la misma persona aparece como
  «M. ROSA LOPEZ» en una tabla y «María Rosa López» en la otra
  (ejemplo inventado; el caso real tiene esta misma forma).
- **El jefe solo viene por nombre** (`DepartamentosInstituto.JefeDpto`), así que
  ahí no queda otra que comparar nombres normalizados, y exigir que casen con
  UNA cuenta. Si casan con dos, no se elige: se avisa.
"""

import re
import unicodedata

# Nombre del departamento en la gestión del centro → título del blog.
#
# Explícito a propósito: los nombres no se parecen lo bastante como para
# adivinarlos («LATÍN» es «Cultura clásica», «CIENCIAS NATURALES» es «Biología y
# Geología»). Un departamento que no esté aquí no se reparte a ningún blog: se
# avisa y se deja fuera, en vez de meter a sus profesores donde no toca.
SIGAD_A_BLOG = {
    "ALEMÁN": "Alemán",
    "ARTES PLÁSTICAS": "Educación Plástica y Visual",
    "CIENCIAS NATURALES": "Biología y Geología",
    "DEPARTAMENTO DE ORIENTACIÓN": "Orientación",
    "ECONOMÍA": "Economía",
    "EDUCACIÓN FÍSICA Y DEPORTIVA": "Educación Física",
    "FILOSOFÍA": "Filosofía",
    "FÍSICA Y QUÍMICA": "Física y Química",
    "FRANCÉS": "Francés",
    "GEOGRAFÍA E HISTORIA": "Geografía e Historia",
    "INGLÉS": "Inglés",
    "INSTALACIONES ELECTROTÉCNICAS": "Instalaciones Electrotécnicas",
    "LATÍN": "Cultura clásica",
    "LENGUA CASTELLANA Y LITERATURA": "Lengua y Literatura",
    "MATEMÁTICAS": "Matemáticas",
    "MÚSICA": "Música",
    "TECNOLOGÍA": "Tecnología",
}


def normalizar(texto):
    """Minúsculas, sin acentos y con los espacios colapsados."""
    sin_acentos = "".join(
        c
        for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_acentos.lower()).strip()


def leer_tabla(texto, tabla):
    """Filas de `tabla` en un volcado de phpMyAdmin, como diccionarios.

    Recorre carácter a carácter en vez de partir por comas o paréntesis, porque
    los valores traen las dos cosas dentro de las comillas («Pérez, M. (tutor)»)
    y un nombre como «O'Donnell» llega como `'O\\'Donnell'` o `'O''Donnell'`.
    `NULL` se devuelve como `None`; los números, como texto.
    """
    filas = []
    patron = re.compile(
        r"INSERT INTO `%s` \(([^)]*)\) VALUES\s*" % re.escape(tabla), re.S
    )
    for cabecera in patron.finditer(texto):
        columnas = [c.strip(" `") for c in cabecera.group(1).split(",")]
        i = cabecera.end()
        fila = None
        valor = []
        citado = False
        en_comillas = False
        while i < len(texto):
            ch = texto[i]
            if en_comillas:
                if ch == "\\" and i + 1 < len(texto):
                    valor.append(texto[i + 1])
                    i += 2
                    continue
                if ch == "'":
                    if texto[i + 1 : i + 2] == "'":
                        valor.append("'")
                        i += 2
                        continue
                    en_comillas = False
                else:
                    valor.append(ch)
                i += 1
                continue

            if ch == "'" and fila is not None:
                # Lo que hubiera antes de la comilla es el espacio tras la coma.
                valor = []
                en_comillas = citado = True
            elif ch == "(" and fila is None:
                fila, valor, citado = [], [], False
            elif ch in ",)" and fila is not None:
                crudo = "".join(valor) if citado else "".join(valor).strip()
                fila.append(None if not citado and crudo.upper() == "NULL" else crudo)
                valor, citado = [], False
                if ch == ")":
                    filas.append(dict(zip(columnas, fila)))
                    fila = None
            elif ch == ";" and fila is None:
                break
            elif fila is not None:
                valor.append(ch)
            i += 1
    return filas
