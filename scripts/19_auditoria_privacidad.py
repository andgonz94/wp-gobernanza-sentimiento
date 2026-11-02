"""Audita el historial de Git en busca de datos identificables, sin modificar nada.

Revisa cada versión de cada archivo de todas las ramas y etiquetas (locales y remotas),
las rutas, los mensajes de commit y de etiqueta, y los objetos inalcanzables que solo
existen en el equipo. Busca nombres propios, nombres de archivo de audio, nombres de
institución educativa, nombres de sesión y de programa, y texto de estudiantes. Los
términos se derivan en tiempo de ejecución (tools/terminos_privacidad.py) y nunca se
escriben: el reporte indica archivo, commit, tipo de hallazgo y cuántos términos
distintos aparecen, sin reproducirlos.

Entradas:
    El repositorio Git, outputs/corpus_{deduplicado,final}.csv y la base de datos (solo lectura).
Salidas:
    docs/auditoria_privacidad.md y docs/auditoria_privacidad.csv.
"""

import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tools"))
from config.db_connection import get_engine  # noqa: E402
from terminos_privacidad import (archivos_audio, instituciones, nombres_propios,  # noqa: E402
                                 sesiones_y_programas, textos_estudiantes)

SALIDA_MD = RAIZ / "docs" / "auditoria_privacidad.md"
SALIDA_CSV = RAIZ / "docs" / "auditoria_privacidad.csv"
# Decisiones de la autora sobre los hallazgos (se declaran aquí para que el reporte, que
# no se edita a mano, las incluya).
DECISIONES = [
    ("2026-10-09", "Nombre propio en `scripts/01_deduplicar_y_cargar.py`",
     "Se deja como está. No se reescribe el historial, porque rompería las etiquetas "
     "publicadas (v1.0, v1.1) y las referencias a commits citadas en la documentación; "
     "tampoco se modifica en HEAD, porque cambiaría la lógica de un script que es evidencia "
     "de los resultados reportados. El repositorio permanece privado, con acceso bajo solicitud."),
]
VENTANA = 50  # caracteres normalizados que deben coincidir para contar texto de estudiante
LETRA = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"


def git(*args, entrada=None):
    """Ejecuta un comando de Git de solo lectura.

    Args:
        *args (str): Argumentos de git.
        entrada (bytes, optional): Entrada estándar.

    Returns:
        bytes: Salida estándar.
    """
    return subprocess.run(["git", *args], cwd=RAIZ, input=entrada, capture_output=True, check=True).stdout


def leer_objetos(shas):
    """Lee el contenido de varios objetos con una sola llamada a git cat-file --batch.

    Args:
        shas (list[str]): Identificadores de objeto.

    Returns:
        dict: sha → contenido en bytes.
    """
    salida = git("cat-file", "--batch", entrada=("\n".join(shas) + "\n").encode())
    contenido, i = {}, 0
    while i < len(salida):
        fin = salida.index(b"\n", i)
        sha, _, tam = salida[i:fin].split()
        contenido[sha.decode()] = salida[fin + 1:fin + 1 + int(tam)]
        i = fin + 1 + int(tam) + 1
    return contenido


def normalizar(cadena):
    """Minúsculas, escapes de JSON y CSV como espacio y solo letras y dígitos separados por un espacio.

    Args:
        cadena (str): Texto.

    Returns:
        str: Texto normalizado.
    """
    cadena = re.sub(r"\\[ntr]", " ", cadena.lower())
    return re.sub(r"[^0-9a-záéíóúüñ]+", " ", cadena).strip()


def ventanas(cadena):
    """Fragmentos de VENTANA caracteres que empiezan en inicio de palabra.

    Args:
        cadena (str): Texto normalizado.

    Returns:
        list[str]: Fragmentos.
    """
    inicios = [0] + [m.end() for m in re.finditer(" ", cadena)]
    return [cadena[i:i + VENTANA] for i in inicios if i + VENTANA <= len(cadena)]


class Detector:
    """Busca cada tipo de término identificable en un texto, sin exponer los términos."""

    def __init__(self, engine):
        """Deriva los términos de la BD y de los CSV del corpus.

        Args:
            engine (sqlalchemy.engine.Engine): Motor de conexión (solo lectura).
        """
        sesiones, programas = sesiones_y_programas(engine)
        variantes = lambda ts: {v for t in ts for v in (t, t.title(), t.upper())}
        palabra = lambda ts: re.compile(rf"(?<![\w{LETRA}])(?:" + "|".join(sorted(map(re.escape, ts), key=len, reverse=True))
                                        + rf")(?![\w{LETRA}])")
        for nombre, conjunto in (("nombres propios", nombres_propios()), ("archivos de audio", archivos_audio()),
                                 ("instituciones", instituciones()), ("sesiones", sesiones), ("programas", programas)):
            if not conjunto:
                raise RuntimeError(f"No se derivó ningún término de {nombre}: revisar las fuentes")
        self.patrones = {
            "nombre propio": palabra(variantes(nombres_propios())),
            "nombre de archivo de audio": re.compile("|".join(map(re.escape, sorted(archivos_audio(), key=len, reverse=True)))),
            "institución educativa": re.compile(
                rf"(?<![\w{LETRA}])(?:" + "|".join(sorted(instituciones(), key=len, reverse=True))
                + rf")(?![\w{LETRA}])|Instituci[oó]n Educativa\s+[A-ZÁÉÍÓÚ]|(?<![{LETRA}])I\.E\.\s+[A-ZÁÉÍÓÚ]"),
            "nombre de sesión": re.compile("|".join(map(re.escape, sorted(sesiones, key=len, reverse=True)))),
            "nombre de programa": palabra(variantes(programas)),
        }
        self.indice = {}
        for k, t in enumerate(textos_estudiantes(engine)):
            for v in ventanas(normalizar(t)):
                self.indice.setdefault(v, k)

    def buscar(self, contenido):
        """Cuenta coincidencias y términos distintos por tipo.

        Args:
            contenido (str): Texto a revisar.

        Returns:
            dict: tipo → (coincidencias, términos o textos de origen distintos).
        """
        hallazgos = {}
        for tipo, patron in self.patrones.items():
            coincidencias = patron.findall(contenido)
            if coincidencias:
                hallazgos[tipo] = (len(coincidencias), len(set(coincidencias)))
        origenes = [self.indice[v] for v in ventanas(normalizar(contenido)) if v in self.indice]
        if origenes:
            hallazgos["texto de estudiante"] = (len(origenes), len(set(origenes)))
        return hallazgos


def main():
    """Recorre el historial, agrega los hallazgos por archivo y escribe el reporte."""
    detector = Detector(get_engine())
    commits = git("rev-list", "--all", "--reverse", "--topo-order").decode().split()
    orden = {c: i for i, c in enumerate(commits)}
    remotos = set(git("rev-list", "--remotes").decode().split())
    cabeza = git("rev-parse", "HEAD").decode().strip()
    cortos = {c: git("show", "--no-patch", "--format=%h %ad", "--date=short", c).decode().strip() for c in commits}

    # Versiones (blob, ruta) y commits que las contienen.
    apariciones = defaultdict(list)
    for c in commits:
        for linea in git("ls-tree", "-r", c).decode().split("\n"):
            if linea and " blob " in linea:
                meta, ruta = linea.split("\t", 1)
                apariciones[(meta.split()[2], ruta)].append(c)
    blobs = sorted({b for b, _ in apariciones})
    contenido = leer_objetos(blobs)
    binarios = {b for b in blobs if b"\0" in contenido[b][:8000]}
    resultados = {b: detector.buscar(contenido[b].decode("utf-8", "replace")) for b in blobs if b not in binarios}

    filas = []
    por_ruta = defaultdict(lambda: defaultdict(list))
    for (blob, ruta), cs in apariciones.items():
        for tipo, (n, distintos) in resultados.get(blob, {}).items():
            por_ruta[(tipo, ruta)]["commits"] += cs
            por_ruta[(tipo, ruta)]["n"].append((n, distintos))
            if cabeza in cs:
                por_ruta[(tipo, ruta)]["head"].append(True)
    for (tipo, ruta), d in por_ruta.items():
        cs = sorted(set(d["commits"]), key=orden.get)
        ruta_reporte = "[ruta con término identificable]" if detector.buscar(ruta) else ruta
        filas.append({
            "ambito": "archivo", "tipo": tipo, "archivo": ruta_reporte,
            "primer_commit": cortos[cs[0]], "ultimo_commit": cortos[cs[-1]], "n_commits": len(cs),
            "en_HEAD": "sí" if d["head"] else "no",
            "publicado_en_origin": "sí" if any(c in remotos for c in cs) else "no",
            "max_coincidencias": max(n for n, _ in d["n"]), "max_terminos_distintos": max(k for _, k in d["n"]),
        })
    commits_ruta = defaultdict(set)
    for (_, ruta), cs in apariciones.items():
        commits_ruta[ruta].update(cs)
    for ruta, cs in commits_ruta.items():
        for tipo, (n, k) in detector.buscar(ruta).items():
            filas.append({"ambito": "ruta del archivo", "tipo": tipo, "archivo": "[ruta con término identificable]",
                          "primer_commit": cortos[min(cs, key=orden.get)], "ultimo_commit": cortos[max(cs, key=orden.get)],
                          "n_commits": len(cs), "en_HEAD": "sí" if cabeza in cs else "no",
                          "publicado_en_origin": "sí" if any(c in remotos for c in cs) else "no",
                          "max_coincidencias": n, "max_terminos_distintos": k})

    for c in commits:
        mensaje = git("show", "--no-patch", "--format=%B", c).decode("utf-8", "replace")
        for tipo, (n, k) in detector.buscar(mensaje).items():
            filas.append({"ambito": "mensaje de commit", "tipo": tipo, "archivo": "—",
                          "primer_commit": cortos[c], "ultimo_commit": cortos[c], "n_commits": 1,
                          "en_HEAD": "—", "publicado_en_origin": "sí" if c in remotos else "no",
                          "max_coincidencias": n, "max_terminos_distintos": k})
    for linea in git("for-each-ref", "--format=%(refname:short)", "refs/tags").decode().split():
        mensaje = git("for-each-ref", "--format=%(contents)", f"refs/tags/{linea}").decode("utf-8", "replace")
        for tipo, (n, k) in detector.buscar(mensaje).items():
            filas.append({"ambito": "mensaje de etiqueta", "tipo": tipo, "archivo": linea,
                          "primer_commit": "—", "ultimo_commit": "—", "n_commits": 0, "en_HEAD": "—",
                          "publicado_en_origin": "sí" if git("ls-remote", "--tags", "origin", linea) else "no",
                          "max_coincidencias": n, "max_terminos_distintos": k})

    # Objetos inalcanzables: existen solo en este equipo (no están en ninguna rama ni etiqueta).
    inalcanzables = [l.split()[2] for l in git("fsck", "--unreachable", "--no-reflogs").decode().split("\n")
                     if l.startswith("unreachable blob")]
    resumen_inal = defaultdict(lambda: [0, 0])
    for i in range(0, len(inalcanzables), 500):
        lote = leer_objetos(inalcanzables[i:i + 500])
        for sha, datos in lote.items():
            if b"\0" in datos[:8000]:
                continue
            for tipo in detector.buscar(datos.decode("utf-8", "replace")):
                resumen_inal[tipo][0] += 1
                resumen_inal[tipo][1] += len(datos)

    df = pd.DataFrame(filas).sort_values(["ambito", "tipo", "archivo"]) if filas else pd.DataFrame()
    df.to_csv(SALIDA_CSV, index=False)
    escribir_reporte(df, len(commits), len(blobs), len(binarios), len(inalcanzables), resumen_inal, len(detector.indice))
    print(f"[OK] {len(df)} hallazgos en {SALIDA_MD.relative_to(RAIZ)} (sin reproducir términos)")


def visibilidad_remoto():
    """Consulta con la CLI de GitHub si el repositorio remoto es privado.

    Returns:
        str: Visibilidad informada por GitHub, o el motivo por el que no se pudo consultar.
    """
    try:
        url = git("remote", "get-url", "origin").decode().strip()
        repo = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url).group(1)
        r = subprocess.run(["gh", "repo", "view", repo, "--json", "visibility", "-q", ".visibility"],
                           capture_output=True, text=True, check=True)
        return f"{r.stdout.strip()} (consultada con `gh repo view`)"
    except (subprocess.CalledProcessError, FileNotFoundError, AttributeError):
        return "no verificada (sin acceso a la CLI de GitHub)"


def escribir_reporte(df, n_commits, n_blobs, n_binarios, n_inalcanzables, resumen_inal, n_ventanas):
    """Escribe el reporte Markdown.

    Args:
        df (pandas.DataFrame): Hallazgos.
        n_commits (int): Commits revisados.
        n_blobs (int): Versiones de archivo revisadas.
        n_binarios (int): Versiones binarias omitidas.
        n_inalcanzables (int): Objetos inalcanzables revisados.
        resumen_inal (dict): tipo → [objetos con hallazgo, bytes].
        n_ventanas (int): Fragmentos de texto de estudiante indexados.
    """
    limpiar = lambda v: str(v).replace("|", "\\|")
    tabla = lambda d: "\n".join(["| " + " | ".join(d.columns) + " |", "|" + "---|" * len(d.columns)]
                                + ["| " + " | ".join(limpiar(v) for v in f) + " |" for f in d.itertuples(index=False)])
    resumen = df.groupby(["ambito", "tipo"]).agg(
        archivos=("archivo", "nunique"), en_HEAD=("en_HEAD", lambda s: int((s == "sí").sum())),
        publicados=("publicado_en_origin", lambda s: int((s == "sí").sum()))).reset_index() if len(df) else pd.DataFrame()
    inal = pd.DataFrame([(t, n, round(b / 1e6, 1)) for t, (n, b) in sorted(resumen_inal.items())],
                        columns=["tipo", "objetos", "MB"])
    partes = [
        "# Auditoría de privacidad del historial de Git\n",
        f"> Generado por `scripts/19_auditoria_privacidad.py` el {datetime.now():%Y-%m-%d %H:%M}. "
        "Solo lectura; no reproduce ningún término encontrado. No editar a mano.\n",
        "\n## Método\n",
        f"Se revisaron {n_commits} commits de todas las ramas y etiquetas (locales y remotas), "
        f"{n_blobs} versiones distintas de archivo ({n_binarios} binarias, omitidas), las rutas, los "
        "mensajes de commit y de etiqueta y, aparte, los objetos inalcanzables. Los términos se "
        "derivan en tiempo de ejecución (`tools/terminos_privacidad.py`):\n\n"
        "- **nombre propio:** palabras de los nombres y rutas de los audios que no aparecen en minúscula "
        "en el corpus (búsqueda por palabra completa, sensible a mayúsculas). Puede incluir falsos "
        "positivos (palabras comunes escritas con mayúscula en un nombre de archivo).\n"
        "- **nombre de archivo de audio:** nombre completo del archivo, sin extensión.\n"
        "- **institución educativa:** palabras que acompañan a la sigla IE en los nombres de audio, y "
        "las expresiones \"Institución Educativa\" o \"I.E.\" seguidas de un nombre.\n"
        "- **nombre de sesión** y **nombre de programa:** valores de la tabla `sesion` y su primer componente.\n"
        f"- **texto de estudiante:** fragmentos de {VENTANA} caracteres normalizados de las entrevistas y "
        f"segmentos ({n_ventanas} fragmentos indexados) que aparecen en el archivo.\n\n"
        "Columnas: `max_coincidencias` y `max_terminos_distintos` son el máximo sobre las versiones del "
        "archivo con hallazgo (para texto de estudiante, fragmentos y documentos de origen distintos). "
        "`publicado_en_origin`: alguna versión con hallazgo está en una rama o etiqueta remota.\n",
        "\n## Resumen\n\n" + (tabla(resumen) if len(resumen) else "Sin hallazgos.") + "\n",
        "\n## Hallazgos por archivo, ruta y mensaje\n\n" + (tabla(df) if len(df) else "Sin hallazgos.") + "\n",
        "\n## Decisiones sobre los hallazgos\n\n" + "\n".join(f"- **{f} · {h}.** {d}" for f, h, d in DECISIONES)
        + f"\n\nVisibilidad del repositorio remoto al generar el reporte: {visibilidad_remoto()}.\n",
        f"\n## Objetos inalcanzables (solo en este equipo)\n\n{n_inalcanzables} objetos que no pertenecen a "
        "ningún commit alcanzable (por ejemplo, archivos agregados al área de preparación y nunca "
        "confirmados). No están publicados; desaparecen con `git gc --prune`. Objetos con hallazgo:\n\n"
        + (tabla(inal) if len(inal) else "Ninguno.") + "\n",
    ]
    SALIDA_MD.write_text("".join(partes), encoding="utf-8")


if __name__ == "__main__":
    main()
