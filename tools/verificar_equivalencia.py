"""Verifica si dos versiones de un script Python tienen la misma lógica.

Compara los árboles sintácticos (AST) de dos versiones de un script después
de normalizarlos: se descartan los docstrings, las anotaciones de tipo y el
contenido de las cadenas de texto (los comentarios no forman parte del AST).
Sirve para demostrar que un cambio de formato (limpieza de docstrings,
emoticones o mensajes) no alteró la lógica, y para localizar los cambios de
lógica cuando sí los hay.

Como ignorar el contenido de todas las cadenas puede ocultar cambios con
efecto real (nombres de columnas, rutas de archivo, claves de diccionario),
la herramienta informa aparte, como [AVISO], las cadenas que difieren fuera
de llamadas a print(). Ese aviso no altera el veredicto de lógica; es para
revisión humana.

Entradas:
    Dos versiones, cada una como `REF:ruta` (Git), `:ruta` (staging),
    o una ruta del sistema de archivos. Alternativamente, `--commit SHA`
    compara cada .py modificado en el commit contra su padre.
Salidas:
    Informe en consola. Código de salida 0 si todo es equivalente,
    1 si hay diferencias de lógica, 2 si hubo errores.
"""

import argparse
import ast
import copy
import difflib
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

MARCADOR_CADENA = "<str>"
CAMPOS_BLOQUE = ("body", "handlers", "orelse", "finalbody", "cases")


# --- Paso 1: obtención del código fuente ---

def leer_fuente(especificacion):
    """Obtiene el código fuente de una versión de un script.

    Args:
        especificacion (str): `REF:ruta` para una versión registrada en Git,
            `:ruta` para la versión en staging, o una ruta de archivo.

    Returns:
        str | None: El código fuente, o None si el archivo no existe en esa
        versión (por ejemplo, un archivo nuevo en el commit).

    Raises:
        RuntimeError: Si Git falla por un motivo distinto a la ausencia del archivo.
    """
    # Una ruta existente tiene prioridad sobre la interpretación REF:ruta.
    if Path(especificacion).is_file():
        return Path(especificacion).read_text(encoding="utf-8")
    if ":" not in especificacion:
        raise RuntimeError(f"No existe el archivo ni es una referencia REF:ruta: {especificacion}")
    proceso = subprocess.run(["git", "show", especificacion], capture_output=True)
    if proceso.returncode != 0:
        error = proceso.stderr.decode("utf-8", "replace")
        if "does not exist" in error or "exists on disk, but not in" in error:
            return None
        raise RuntimeError(f"git show {especificacion} falló: {error.strip()}")
    return proceso.stdout.decode("utf-8")


# --- Paso 2: normalización del AST ---

def es_cadena_suelta(nodo):
    """Indica si un nodo es una sentencia formada solo por una cadena literal.

    Incluye los docstrings y las cadenas usadas como comentario. Ninguna tiene
    efecto en la ejecución, salvo poblar `__doc__`.

    Args:
        nodo (ast.AST): Sentencia a evaluar.

    Returns:
        bool: True si la sentencia es una cadena literal suelta.
    """
    return (isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Constant)
            and isinstance(nodo.value.value, (str, bytes)))


class Normalizador(ast.NodeTransformer):
    """Elimina del AST todo lo que no es lógica ejecutable comparable."""

    def _limpiar_bloques(self, nodo):
        # Al quitar docstrings o anotaciones un bloque puede quedar vacío;
        # se rellena con `pass` para que siga siendo un AST válido y para que
        # "solo docstring" y "docstring + pass" resulten equivalentes.
        for campo in ("body", "orelse", "finalbody"):
            bloque = getattr(nodo, campo, None)
            if isinstance(bloque, list):
                bloque[:] = [s for s in bloque if not es_cadena_suelta(s)]
                if campo == "body" and not bloque and not isinstance(nodo, ast.Module):
                    bloque.append(ast.Pass(lineno=nodo.lineno, col_offset=0))

    def generic_visit(self, nodo):
        resultado = super().generic_visit(nodo)
        if isinstance(resultado, ast.AST):
            self._limpiar_bloques(resultado)
        return resultado

    def visit_FunctionDef(self, nodo):
        nodo.returns = None
        nodo.type_comment = None
        if hasattr(nodo, "type_params"):
            nodo.type_params = []
        return self.generic_visit(nodo)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, nodo):
        if hasattr(nodo, "type_params"):
            nodo.type_params = []
        return self.generic_visit(nodo)

    def visit_arg(self, nodo):
        nodo.annotation = None
        nodo.type_comment = None
        return nodo

    def visit_AnnAssign(self, nodo):
        # `x: int = 5` equivale a `x = 5`; `x: int` sin valor no ejecuta nada.
        if nodo.value is None:
            return None
        asignacion = ast.Assign(targets=[nodo.target], value=nodo.value)
        ast.copy_location(asignacion, nodo)
        return self.generic_visit(asignacion)

    def visit_Constant(self, nodo):
        if isinstance(nodo.value, (str, bytes)):
            nodo.value = MARCADOR_CADENA
        return nodo

    def visit_JoinedStr(self, nodo):
        # En un f-string se conservan las expresiones interpoladas (son lógica)
        # y se descartan las partes literales y las especificaciones de formato.
        partes = []
        for parte in nodo.values:
            if isinstance(parte, ast.FormattedValue):
                parte.value = self.visit(parte.value)
                parte.format_spec = None
                partes.append(parte)
        nodo.values = partes
        return nodo


def normalizar(fuente):
    """Analiza y normaliza un código fuente.

    Args:
        fuente (str): Código fuente Python.

    Returns:
        ast.Module: AST sin docstrings, anotaciones ni contenido de cadenas.

    Raises:
        SyntaxError: Si el código no es Python válido.
    """
    arbol = ast.parse(fuente)
    return Normalizador().visit(arbol)


# --- Paso 3: segmentación por unidades (funciones, métodos, módulo) ---

def dividir_en_unidades(arbol):
    """Agrupa las sentencias de nivel superior en unidades con nombre.

    Cada función y método es una unidad; el resto del código de módulo (o de
    cuerpo de clase) forma la unidad `<módulo>` (o el nombre de la clase).
    Las funciones anidadas permanecen dentro de su función contenedora.

    Args:
        arbol (ast.Module): AST normalizado.

    Returns:
        dict[str, list[ast.stmt]]: Sentencias de cada unidad, en orden.
    """
    unidades = {"<módulo>": []}
    for sentencia in arbol.body:
        if isinstance(sentencia, (ast.FunctionDef, ast.AsyncFunctionDef)):
            unidades[sentencia.name] = [sentencia]
        elif isinstance(sentencia, ast.ClassDef):
            cuerpo_clase = []
            for miembro in sentencia.body:
                if isinstance(miembro, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    unidades[f"{sentencia.name}.{miembro.name}"] = [miembro]
                else:
                    cuerpo_clase.append(miembro)
            cabecera = copy.copy(sentencia)
            cabecera.body = cuerpo_clase
            unidades[sentencia.name] = [cabecera]
        else:
            unidades["<módulo>"].append(sentencia)
    return unidades


def cabecera_de(sentencia):
    """Devuelve la línea de cabecera de una sentencia compuesta (sin su cuerpo).

    Args:
        sentencia (ast.AST): Sentencia compuesta (if, for, def, try, etc.).

    Returns:
        str: Cabecera desparseada, por ejemplo `if x > 0:`.
    """
    vacia = copy.copy(sentencia)
    for campo in CAMPOS_BLOQUE:
        if isinstance(getattr(vacia, campo, None), list):
            setattr(vacia, campo, [])
    texto = ast.unparse(vacia).strip()
    return " ".join(linea.strip() for linea in texto.splitlines())


def aplanar(sentencias, profundidad=0):
    """Convierte una lista de sentencias en líneas comparables con su número de línea.

    Args:
        sentencias (list[ast.AST]): Sentencias normalizadas.
        profundidad (int): Nivel de anidamiento, para reflejar la estructura.

    Returns:
        list[tuple[int, str]]: Pares (línea original, texto con sangría lógica).
    """
    lineas = []
    for s in sentencias:
        sangria = "    " * profundidad
        linea = getattr(s, "lineno", 0)
        campos = [c for c in CAMPOS_BLOQUE if isinstance(getattr(s, c, None), list)]
        if not campos:
            texto = " ".join(l.strip() for l in ast.unparse(s).splitlines())
            lineas.append((linea, sangria + texto))
            continue
        if isinstance(s, ast.match_case):
            cabecera = f"case {ast.unparse(s.pattern)}"
            cabecera += f" if {ast.unparse(s.guard)}:" if s.guard else ":"
        else:
            cabecera = cabecera_de(s)
        lineas.append((linea, sangria + cabecera))
        for campo in campos:
            hijos = getattr(s, campo)
            if not hijos:
                continue
            if campo in ("orelse", "finalbody"):
                etiqueta = "else:" if campo == "orelse" else "finally:"
                lineas.append((getattr(hijos[0], "lineno", linea), sangria + etiqueta))
            # Los `except` van al nivel del `try`; el resto de bloques, un nivel adentro.
            lineas.extend(aplanar(hijos, profundidad + (0 if campo == "handlers" else 1)))
    return lineas


# --- Paso 4: comparación ---

@dataclass
class Resultado:
    """Resultado de comparar dos versiones de un script."""

    etiqueta: str
    equivalente: bool = True
    diferencias: list = field(default_factory=list)
    avisos_cadenas: list = field(default_factory=list)
    nota: str = ""


def diferencias_de_unidad(nombre, sentencias_a, sentencias_b):
    """Describe las diferencias de lógica dentro de una unidad.

    Args:
        nombre (str): Nombre de la unidad (función, método o `<módulo>`).
        sentencias_a (list[ast.AST]): Sentencias de la versión A.
        sentencias_b (list[ast.AST]): Sentencias de la versión B.

    Returns:
        list[str]: Una descripción por bloque de cambio.
    """
    lineas_a, lineas_b = aplanar(sentencias_a), aplanar(sentencias_b)
    textos_a = [t for _, t in lineas_a]
    textos_b = [t for _, t in lineas_b]
    descripciones = []
    comparador = difflib.SequenceMatcher(a=textos_a, b=textos_b, autojunk=False)
    for operacion, i1, i2, j1, j2 in comparador.get_opcodes():
        if operacion == "equal":
            continue
        ubic_a = f"A:{lineas_a[i1][0]}" if i1 < i2 else f"A:(tras {lineas_a[i1 - 1][0] if i1 else 'inicio'})"
        ubic_b = f"B:{lineas_b[j1][0]}" if j1 < j2 else f"B:(tras {lineas_b[j1 - 1][0] if j1 else 'inicio'})"
        tipo = {"replace": "modificado", "delete": "eliminado", "insert": "agregado"}[operacion]
        bloque = [f"  [{nombre}] {tipo} ({ubic_a}, {ubic_b})"]
        bloque += [f"      - {t}" for t in textos_a[i1:i2]]
        bloque += [f"      + {t}" for t in textos_b[j1:j2]]
        descripciones.append("\n".join(bloque))
    return descripciones


class RecolectorCadenas(ast.NodeVisitor):
    """Recolecta las cadenas literales que no están dentro de una llamada a print()."""

    def __init__(self):
        self.cadenas = Counter()
        self.lineas = {}

    def visit_Call(self, nodo):
        if isinstance(nodo.func, ast.Name) and nodo.func.id == "print":
            return
        self.generic_visit(nodo)

    def _registrar(self, texto, nodo):
        self.cadenas[texto] += 1
        self.lineas.setdefault(texto, nodo.lineno)

    def visit_Constant(self, nodo):
        if isinstance(nodo.value, (str, bytes)):
            self._registrar(repr(nodo.value), nodo)

    def visit_JoinedStr(self, nodo):
        self._registrar(ast.unparse(nodo), nodo)


def cadenas_por_unidad(fuente):
    """Recolecta, por unidad, las cadenas fuera de print() y fuera de docstrings.

    Args:
        fuente (str): Código fuente sin normalizar.

    Returns:
        dict[str, RecolectorCadenas]: Recolector de cada unidad.
    """
    arbol = ast.parse(fuente)

    class SinDocstrings(ast.NodeTransformer):
        def generic_visit(self, nodo):
            super().generic_visit(nodo)
            for campo in ("body", "orelse", "finalbody"):
                bloque = getattr(nodo, campo, None)
                if isinstance(bloque, list):
                    bloque[:] = [s for s in bloque if not es_cadena_suelta(s)]
            return nodo

    arbol = SinDocstrings().visit(arbol)
    resultado = {}
    for nombre, sentencias in dividir_en_unidades(arbol).items():
        recolector = RecolectorCadenas()
        for s in sentencias:
            recolector.visit(s)
        resultado[nombre] = recolector
    return resultado


def comparar(espec_a, espec_b, etiqueta=None):
    """Compara la lógica de dos versiones de un script.

    Args:
        espec_a (str): Versión de referencia (ver `leer_fuente`).
        espec_b (str): Versión a comparar.
        etiqueta (str | None): Nombre a mostrar en el informe.

    Returns:
        Resultado: Veredicto, diferencias de lógica y avisos de cadenas.
    """
    resultado = Resultado(etiqueta or f"{espec_a}  vs  {espec_b}")
    fuente_a, fuente_b = leer_fuente(espec_a), leer_fuente(espec_b)
    if fuente_a is None or fuente_b is None:
        resultado.equivalente = None
        faltante = espec_a if fuente_a is None else espec_b
        resultado.nota = f"No existe {faltante}: no hay versión con la cual comparar."
        return resultado

    arbol_a, arbol_b = normalizar(fuente_a), normalizar(fuente_b)
    # El veredicto se basa en la igualdad estricta del AST completo; el
    # desglose por unidades solo sirve para explicar dónde está la diferencia.
    if ast.dump(arbol_a) == ast.dump(arbol_b):
        resultado.equivalente = True
    else:
        resultado.equivalente = False
        unidades_a, unidades_b = dividir_en_unidades(arbol_a), dividir_en_unidades(arbol_b)
        for nombre in sorted(unidades_a.keys() ^ unidades_b.keys()):
            if nombre not in unidades_b:
                resultado.diferencias.append(
                    f"  [{nombre}] función eliminada (A:{unidades_a[nombre][0].lineno})")
            elif nombre not in unidades_a:
                resultado.diferencias.append(
                    f"  [{nombre}] función agregada (B:{unidades_b[nombre][0].lineno})")
        for nombre in [n for n in unidades_a if n in unidades_b]:
            resultado.diferencias.extend(
                diferencias_de_unidad(nombre, unidades_a[nombre], unidades_b[nombre]))
        orden_a = [n for n in unidades_a if n in unidades_b]
        orden_b = [n for n in unidades_b if n in unidades_a]
        if orden_a != orden_b:
            resultado.diferencias.append("  Cambió el orden de definición de funciones o clases.")
        if not resultado.diferencias:
            resultado.diferencias.append(
                "  El AST difiere pero no se pudo localizar la diferencia por unidad; "
                "revisar manualmente.")

    cadenas_a, cadenas_b = cadenas_por_unidad(fuente_a), cadenas_por_unidad(fuente_b)
    for nombre in sorted(cadenas_a.keys() & cadenas_b.keys()):
        rec_a, rec_b = cadenas_a[nombre], cadenas_b[nombre]
        for texto in sorted((rec_a.cadenas - rec_b.cadenas).keys()):
            resultado.avisos_cadenas.append(f"  [{nombre}] - A:{rec_a.lineas[texto]}  {texto}")
        for texto in sorted((rec_b.cadenas - rec_a.cadenas).keys()):
            resultado.avisos_cadenas.append(f"  [{nombre}] + B:{rec_b.lineas[texto]}  {texto}")
    return resultado


def imprimir(resultado):
    """Imprime el informe de una comparación.

    Args:
        resultado (Resultado): Resultado a informar.
    """
    print(f"\n=== {resultado.etiqueta} ===")
    if resultado.equivalente is None:
        print(f"[INFO] {resultado.nota}")
        return
    if resultado.equivalente:
        print("[OK] SIN DIFERENCIAS DE LÓGICA (AST normalizado idéntico).")
    else:
        print(f"[AVISO] DIFERENCIAS DE LÓGICA: {len(resultado.diferencias)} bloque(s).")
        for d in resultado.diferencias:
            print(d)
    if resultado.avisos_cadenas:
        print(f"[AVISO] {len(resultado.avisos_cadenas)} cadena(s) distintas fuera de print() "
              f"(no cuentan como lógica; revisar si son columnas, rutas o claves):")
        for a in resultado.avisos_cadenas:
            print(a)
    else:
        print("[INFO] Sin diferencias en cadenas fuera de print().")


def archivos_py_del_commit(sha):
    """Lista los .py modificados en un commit.

    Args:
        sha (str): Referencia del commit.

    Returns:
        list[str]: Rutas de los .py modificados, agregados o eliminados.
    """
    salida = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", f"{sha}^", sha],
        capture_output=True, text=True, check=True).stdout
    return [r for r in salida.split() if r.endswith(".py")]


# --- Paso 5: punto de entrada ---

def main():
    """Interpreta los argumentos y ejecuta las comparaciones solicitadas.

    Returns:
        int: Código de salida (0 equivalente, 1 diferencias, 2 errores).
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version_a", nargs="?", help="REF:ruta, :ruta (staging) o ruta de archivo")
    parser.add_argument("version_b", nargs="?", help="REF:ruta, :ruta (staging) o ruta de archivo")
    parser.add_argument("--commit", nargs="+", metavar="SHA",
                        help="compara cada .py modificado en el commit contra su padre")
    args = parser.parse_args()

    comparaciones = []
    if args.commit:
        for sha in args.commit:
            archivos = archivos_py_del_commit(sha)
            if not archivos:
                comparaciones.append((None, None, f"commit {sha}"))
            for ruta in archivos:
                comparaciones.append((f"{sha}^:{ruta}", f"{sha}:{ruta}", f"commit {sha}: {ruta}"))
    elif args.version_a and args.version_b:
        comparaciones.append((args.version_a, args.version_b, None))
    else:
        parser.error("indica dos versiones o --commit SHA")

    hubo_diferencias = hubo_errores = False
    for espec_a, espec_b, etiqueta in comparaciones:
        if espec_a is None:
            print(f"\n=== {etiqueta} ===\n[INFO] El commit no modifica archivos .py.")
            continue
        try:
            resultado = comparar(espec_a, espec_b, etiqueta)
        except (RuntimeError, SyntaxError) as error:
            print(f"\n=== {etiqueta or espec_a + '  vs  ' + espec_b} ===\n[ERROR] {error}")
            hubo_errores = True
            continue
        imprimir(resultado)
        hubo_diferencias |= resultado.equivalente is False

    return 2 if hubo_errores else (1 if hubo_diferencias else 0)


if __name__ == "__main__":
    sys.exit(main())
