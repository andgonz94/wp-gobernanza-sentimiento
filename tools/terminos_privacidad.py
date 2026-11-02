"""Deriva en tiempo de ejecución los términos identificables del corpus, sin escribirlos en el código.

Los términos se leen de los nombres y rutas de los archivos de audio
(outputs/corpus_deduplicado.csv y outputs/corpus_final.csv), de la tabla sesion y de los
textos de las entrevistas. Ningún término queda en el repositorio: los scripts que usan
este módulo (18 y 19) solo reportan si aparecen y dónde, nunca cuáles son.

Entradas:
    outputs/corpus_deduplicado.csv, outputs/corpus_final.csv y la base de datos (solo lectura).
Salidas:
    Ninguna (funciones de apoyo).
"""

import re
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd
from sqlalchemy import text

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "outputs"
LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"


def _tokens_camel(cadena):
    """Divide una cadena en palabras, separando también las uniones en CamelCase.

    Args:
        cadena (str): Nombre de archivo o componente de ruta.

    Returns:
        list[str]: Palabras encontradas.
    """
    palabras = []
    for parte in re.split(f"[^{LETRAS}]+", cadena):
        palabras += re.findall(r"[A-ZÁÉÍÓÚÜÑ]+(?![a-záéíóúüñ])|[A-ZÁÉÍÓÚÜÑ]?[a-záéíóúüñ]+", parte)
    return [p for p in palabras if p]


def _sin_tildes(palabra):
    """Quita tildes y diéresis para comparar palabras sin depender de la ortografía.

    Args:
        palabra (str): Palabra.

    Returns:
        str: Palabra sin tildes.
    """
    return unicodedata.normalize("NFKD", palabra).encode("ascii", "ignore").decode()


def _corpus_audio():
    """Lee los nombres y rutas de audio de los CSV del corpus.

    Returns:
        pandas.DataFrame: Columnas audio_filename, audio_path y text.
    """
    marcos = [pd.read_csv(OUT / f, usecols=["audio_filename", "audio_path", "text"])
              for f in ("corpus_deduplicado.csv", "corpus_final.csv") if (OUT / f).exists()]
    return pd.concat(marcos, ignore_index=True)


def archivos_audio(min_largo=8):
    """Nombres de archivo de audio sin extensión (contienen nombres de estudiantes).

    Args:
        min_largo (int): Longitud mínima del nombre.

    Returns:
        set[str]: Nombres de archivo.
    """
    nombres = (re.sub(r"\.\w+$", "", str(v)) for v in _corpus_audio()["audio_filename"].dropna())
    return {n for n in nombres if len(n) >= min_largo}


def textos_estudiantes(engine):
    """Textos de las entrevistas y de los segmentos (solo lectura; no se imprimen).

    Args:
        engine (sqlalchemy.engine.Engine): Motor de conexión.

    Returns:
        list[str]: Textos.
    """
    with engine.connect() as c:
        textos = [r[0] for r in c.execute(text("SELECT texto FROM retroalimentacion"))]
        textos += [r[0] for r in c.execute(text("SELECT texto_segmento FROM segmento_retroalimentacion"))]
    return [t for t in textos if t]


def nombres_propios(min_largo=4):
    """Candidatos a nombre propio: palabras de los nombres y rutas de audio que no son de uso común.

    Una palabra se considera de uso común si aparece al menos dos veces en minúscula como
    palabra completa en los textos de las entrevistas (los nombres propios aparecen con
    mayúscula inicial en las transcripciones).

    Args:
        min_largo (int): Longitud mínima de la palabra.

    Returns:
        set[str]: Candidatos, en su forma original.
    """
    corpus = _corpus_audio()
    candidatos = set()
    for valor in pd.concat([corpus["audio_filename"], corpus["audio_path"]]).dropna():
        partes = [re.sub(r"\.\w+$", "", c) for c in str(valor).split("/") if c not in ("", "..", ".")]
        for parte in partes:
            candidatos.update(t for t in _tokens_camel(parte) if len(t) >= min_largo)
    minusculas = Counter(_sin_tildes(w) for w in re.findall(f"[{LETRAS}]+", " ".join(corpus["text"].dropna())))
    return {t for t in candidatos if minusculas[_sin_tildes(t.lower())] < 2}


def instituciones():
    """Patrones de nombres de institución educativa tomados de los nombres de archivo de audio.

    Toma las palabras unidas a la sigla IE (sin separador) dentro de un mismo nombre de
    archivo, por ejemplo IE seguida de un nombre en CamelCase.

    Returns:
        set[str]: Expresiones regulares (palabras unidas con espacio o guion bajo opcionales).
    """
    patrones = set()
    for valor in _corpus_audio()["audio_filename"].dropna():
        for parte in re.split(f"[^{LETRAS}]+", re.sub(r"\.\w+$", "", str(valor))):
            palabras = _tokens_camel(parte)
            for i, p in enumerate(palabras):
                siguientes = palabras[i + 1:i + 4]
                if p in ("IE", "IEL") and siguientes and all(w[0].isupper() for w in siguientes):
                    patrones.add(r"[\s_]*".join(map(re.escape, siguientes)))
    return patrones


def sesiones_y_programas(engine):
    """Nombres de sesión de la tabla sesion y nombres de programa (su primer componente).

    Args:
        engine (sqlalchemy.engine.Engine): Motor de conexión (solo lectura).

    Returns:
        tuple[set[str], set[str]]: Nombres de sesión completos y nombres de programa.
    """
    with engine.connect() as c:
        nombres = [r[0] for r in c.execute(text("SELECT nombre_sesion FROM sesion"))]
    sesiones = {re.sub(r"\[manual\]$", "", n) for n in nombres}
    programas = {n.split("_")[0] for n in nombres}
    return sesiones, programas
