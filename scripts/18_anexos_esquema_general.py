"""Genera los anexos A a E del trabajo de grado en docs/anexos/.

Cada anexo se escribe como Markdown y CSV a partir de sus fuentes, sin transcribir cifras
a mano: el diccionario de datos, del esquema real de la BD (information_schema), del
respaldo previo al script 13 y de Fase2_Metadatos_Minimos.docx; los prompts, del código de
los scripts que llaman a la API; el catálogo de reglas, del código de 09a, de las consultas
de solo lectura a la BD y del borrador del working paper; el inventario de scripts, de la
guía operativa y de los docstrings; los resultados, de las matrices de confusión
registradas y de las salidas de los scripts 14, 14b y 15. Los juicios (correspondencia de
reglas, etapas, descripciones de columnas sin fuente documental) se declaran como datos
en este script.

Numeración de los anexos fijada el 2026-10-09 (sin cronograma); difiere de la del
Esquema General, que preveía B = cronograma, C = scripts y D = reglas.

Entradas:
    ../Borradores/{Fase2_Metadatos_Minimos,Working_Paper_Marco_Gobernado_v1}.docx,
    ../backup_antes_constraints_20260831_2324.sql (solo las sentencias CREATE TABLE),
    scripts/, docs/guia_operativa_scripts.md, docs/registro_entorno_colab.md,
    requirements-local*.txt, el historial de Git, la base de datos (solo lectura) y
    outputs/ (matrices de confusión y salidas de 14, 14b y 15).
Salidas:
    docs/anexos/anexo_{A,B,C,D,E}_*.md y sus CSV (borra antes los anexo_* anteriores).
"""

import ast
import html
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from config.db_connection import get_engine  # noqa: E402
from sqlalchemy import text  # noqa: E402

BORRADORES = RAIZ.parent / "Borradores"
RESPALDO_SQL = RAIZ.parent / "backup_antes_constraints_20260831_2324.sql"
SALIDA = RAIZ / "docs" / "anexos"
OUT = RAIZ / "outputs"
SCRIPT_09A = RAIZ / "scripts" / "09a_procesar_condicion_a.py"
VERSION_CITABLE = "v1.2-anexos-2026-10"

TITULOS = {
    "A": ("Anexo A — Diccionario de datos (versión liviana)",
          "Tablas retroalimentacion, segmento_retroalimentacion, segmento_condicion_a, "
          "ejecucion_pipeline y detalle_error: tipo, nulos, descripción, regla asociada y "
          "cambios del 2026-08-31."),
    "B": ("Anexo B — Prompts de la API de Claude",
          "Prompts literales, modelo y parámetros de los scripts 04, 07, 08 y "
          "09_reetiquetar_positivos."),
    "C": ("Anexo C — Reglas de calidad",
          "Catálogos implementado y de diseño, correspondencia, umbrales y matriz regla × corpus."),
    "D": ("Anexo D — Código y repositorio",
          "Inventario de scripts por etapa, orden de ejecución, versión citable y entorno."),
    "E": ("Anexo E — Resultados complementarios",
          "Métricas por clase de las 8 combinaciones de modelo y condición, bootstrap, "
          "multisemilla y sensibilidad a la fuga."),
}

# Corrección documentada en docs/cambios_agosto_2026.md, §20: 4 violaciones de canal "n/a"
# quedaron como RQ-04 por la lectura de pandas; corresponden a RQ-06.
CORRECCION_CONTEOS = {"RQ-04": -4, "RQ-06": +4}

# Juicio de correspondencia diseño → implementado (2026-10-09). Tipos: sin cambio, criterio
# modificado, acción modificada, renumerada, no implementada, agregada.
CORRESPONDENCIA = [
    ("RQ-01", "RQ-01", "sin cambio",
     "09a: texto vacío tras strip. Los cargadores de B (01, 02) la aplican como len(texto) < 5."),
    ("RQ-02", "RQ-02", "sin cambio", "09a valida num_sesion, que es el id de sesión en el CSV de A."),
    ("RQ-03", "RQ-03", "sin cambio", ""),
    ("RQ-04", "RQ-04", "acción modificada", "Diseño: corregir a 'desconocido'. 09a: rechazar."),
    ("RQ-05", "RQ-05", "criterio modificado",
     "09a solo verifica el formato %Y-%m-%d; no verifica fechas futuras."),
    ("RQ-06", "RQ-06", "acción y criterio modificados",
     "Diseño: corregir a 'desconocido'; catálogo sin 'desconocido'. 09a: rechazar; el catálogo "
     "incluye 'desconocido'."),
    ("RQ-07", "—", "no implementada",
     "Etiqueta fuera de {positivo, neutral, negativo}: el esquema final tiene 5 clases. No es "
     "una regla del 09a; 04_etiquetar_sentimiento.py asigna 'neutral' a etiquetas no "
     "reconocidas, sin registrarlo (sin casos en la ejecución: 0 errores en "
     "etiquetas_cargar_20260519_1752.csv). El código RQ-07 se reutilizó para duplicados."),
    ("RQ-08", "RQ-07", "renumerada y criterio modificado",
     "Diseño: hash MD5 del texto normalizado + id_sesion. 09a: primeros 200 caracteres en "
     "minúsculas, sin considerar la sesión. [VERIFICAR] emparejamiento."),
    ("RQ-09", "RQ-09", "criterio modificado", "Diseño: < 3 caracteres. 09a: < 20 caracteres."),
    ("RQ-10", "—", "no implementada",
     "Solo números o puntuación: ningún script lo verifica. [VERIFICAR] si RQ-08 o RQ-09 del "
     "09a cubren la intención."),
    ("RQ-11", "—", "no implementada como regla",
     "id_ejecucion obligatorio: 01, 02 y 09a siempre lo asignan al insertar (por "
     "construcción), pero ninguna regla lo valida y la columna admite NULL en el esquema."),
    ("—", "RQ-08", "agregada",
     "Texto no informativo (lista cerrada de expresiones). Sin equivalente en el diseño; "
     "[VERIFICAR] relación con RQ-10 de diseño."),
]


# --- Utilidades de lectura ---

def texto_docx(ruta):
    """Extrae el texto de un .docx, con un salto de línea por párrafo y por celda.

    Args:
        ruta (pathlib.Path): Archivo .docx.

    Returns:
        str: Texto del documento.
    """
    xml = zipfile.ZipFile(ruta).read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>|</w:tc>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def tablas_docx(ruta):
    """Extrae las tablas de un .docx como listas de filas de celdas de texto.

    Args:
        ruta (pathlib.Path): Archivo .docx.

    Returns:
        list[list[list[str]]]: Tablas, filas y celdas.
    """
    xml = zipfile.ZipFile(ruta).read("word/document.xml").decode("utf-8")
    tablas = []
    for tabla in re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.S):
        filas = []
        for fila in re.findall(r"<w:tr[ >].*?</w:tr>", tabla, re.S):
            celdas = []
            for celda in re.findall(r"<w:tc>.*?</w:tc>", fila, re.S):
                parrafos = re.findall(r"<w:p[ >].*?</w:p>", celda, re.S)
                celdas.append(" ".join(html.unescape(re.sub(r"<[^>]+>", "", p)).strip()
                                       for p in parrafos).strip())
            filas.append(celdas)
        tablas.append(filas)
    return tablas


def git(*args):
    """Ejecuta un comando de Git de solo lectura en la raíz del proyecto.

    Args:
        *args (str): Argumentos de git.

    Returns:
        str: Salida estándar sin espacios finales.
    """
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()


def a_markdown(df):
    """Convierte un DataFrame en una tabla Markdown.

    Args:
        df (pandas.DataFrame): Tabla a convertir.

    Returns:
        str: Tabla en Markdown.
    """
    limpiar = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
    cab = "| " + " | ".join(map(limpiar, df.columns)) + " |"
    sep = "|" + "---|" * len(df.columns)
    filas = ["| " + " | ".join(limpiar(v) for v in fila) + " |" for fila in df.itertuples(index=False)]
    return "\n".join([cab, sep] + filas)


def escribir(nombre, titulo, descripcion, secciones):
    """Escribe un anexo en Markdown y cada una de sus tablas en CSV.

    Args:
        nombre (str): Prefijo de archivo (por ejemplo, anexo_A_metadatos).
        titulo (str): Título del anexo.
        descripcion (str): Contenido del anexo en una frase.
        secciones (list): Tuplas (subtítulo, texto introductorio, DataFrame o None, sufijo CSV).
    """
    partes = [f"# {titulo}\n", f"> {descripcion}\n",
              f"> Generado por `scripts/18_anexos_esquema_general.py`. No editar a mano.\n"]
    for subtitulo, intro, df, sufijo in secciones:
        partes.append(f"\n## {subtitulo}\n")
        if intro:
            partes.append(intro + "\n")
        if df is not None:
            partes.append("\n" + a_markdown(df) + "\n")
            ruta_csv = SALIDA / f"{nombre}_{sufijo}.csv"
            df.to_csv(ruta_csv, index=False)
            partes.append(f"\nCSV: `{ruta_csv.name}`\n")
    (SALIDA / f"{nombre}.md").write_text("".join(partes), encoding="utf-8")
    print(f"[OK] {nombre}.md")


# --- Anexo A ---

TABLAS_DICCIONARIO = ["retroalimentacion", "segmento_retroalimentacion", "segmento_condicion_a",
                      "ejecucion_pipeline", "detalle_error"]

# Descripción de las columnas sin entrada en Fase2_Metadatos_Minimos.docx, declarada el
# 2026-10-09 a partir del código que las escribe (script entre paréntesis).
DESCRIPCIONES = {
    ("retroalimentacion", "duracion_segundos"): "Duración del audio de la entrevista, en segundos (02).",
    ("retroalimentacion", "etiqueta_sentimiento"): "Etiqueta a nivel de documento; sin uso (el etiquetado es por segmento).",
    ("retroalimentacion", "confianza_etiqueta"): "Confianza de la etiqueta de documento; sin uso.",
    ("retroalimentacion", "justificacion_etiqueta"): "Justificación de la etiqueta de documento; sin uso.",
    ("segmento_retroalimentacion", "id_segmento"): "Identificador del segmento (PK).",
    ("segmento_retroalimentacion", "id_registro"): "Entrevista de origen (FK a retroalimentacion).",
    ("segmento_retroalimentacion", "categoria"): "Categoría temática asignada al segmentar (07).",
    ("segmento_retroalimentacion", "texto_segmento"): "Texto del segmento devuelto por la API (07).",
    ("segmento_retroalimentacion", "inicio_seg"): "Inicio del segmento en el audio; sin uso con la segmentación por API.",
    ("segmento_retroalimentacion", "fin_seg"): "Fin del segmento en el audio; sin uso con la segmentación por API.",
    ("segmento_retroalimentacion", "etiqueta_sentimiento"): "Etiqueta de sentimiento de 5 clases: verdad de referencia (04, 09_reetiquetar_positivos, 09_cargar_revision_manual).",
    ("segmento_retroalimentacion", "confianza_etiqueta"): "Confianza declarada por el modelo de lenguaje al etiquetar (04).",
    ("segmento_retroalimentacion", "justificacion_etiqueta"): "Justificación del modelo de lenguaje al etiquetar (04).",
    ("segmento_retroalimentacion", "metodo_segmentacion"): "Método de segmentación (07).",
    ("segmento_retroalimentacion", "flag_excluir"): "1 si la revisión manual excluyó el segmento (09_cargar_revision_manual).",
    ("segmento_retroalimentacion", "naturaleza_negativo"): "Subtipo de los segmentos negativos, según la revisión manual.",
    ("segmento_retroalimentacion", "justificacion_revision_v2"): "Justificación del cambio en la revisión manual.",
    ("segmento_retroalimentacion", "fecha_revision_v2"): "Fecha del cambio en la revisión manual.",
    ("segmento_condicion_a", "id_segmento_a"): "Identificador del segmento de la Condición A (PK).",
    ("segmento_condicion_a", "id_segmento_origen"): "Segmento de B del que proviene (FK a segmento_retroalimentacion).",
    ("segmento_condicion_a", "id_registro"): "Entrevista de origen. El defecto nulo_id_sesion se inyecta anulando esta columna "
                                             "(la tabla no tiene id_sesion); las filas duplicado_exacto copian el valor nulo del original "
                                             "(09_construir_condicion_a_segmentos).",
    ("segmento_condicion_a", "categoria"): "Categoría temática copiada del segmento de origen.",
    ("segmento_condicion_a", "texto_segmento"): "Texto del segmento, alterado si el defecto es nulo_texto, texto_no_informativo o "
                                                "cuasi_duplicado; las filas duplicado_exacto copian el texto (o el nulo) del original.",
    ("segmento_condicion_a", "fecha_registro"): "Fecha como texto libre, con defectos de nulo o formato inyectados.",
    ("segmento_condicion_a", "canal_captura"): "Canal con defectos de nulo o fuera de catálogo inyectados.",
    ("segmento_condicion_a", "etiqueta_sentimiento"): "Etiqueta copiada del segmento de origen (idéntica en A y B).",
    ("segmento_condicion_a", "tipo_error_inyectado"): "Defectos inyectados, separados por coma; nulo si la fila no tiene defectos.",
    ("ejecucion_pipeline", "id_ejecucion"): "Identificador de la ejecución (PK).",
    ("ejecucion_pipeline", "inicio"): "Inicio de la ejecución.",
    ("ejecucion_pipeline", "fin"): "Fin de la ejecución; nulo si no terminó.",
    ("ejecucion_pipeline", "estado"): "en_proceso, completado o fallido (CHECK chk_estado).",
    ("ejecucion_pipeline", "registros_procesados"): "Registros leídos por la ejecución.",
    ("ejecucion_pipeline", "registros_rechazados"): "Registros rechazados por las reglas de calidad.",
    ("detalle_error", "id_error"): "Identificador de la violación (PK).",
    ("detalle_error", "id_registro"): "Registro afectado; nulo porque los rechazados no se insertan.",
    ("detalle_error", "id_ejecucion"): "Ejecución que detectó la violación (FK).",
    ("detalle_error", "codigo_regla"): "Código de la regla violada (catálogo implementado, Anexo C).",
    ("detalle_error", "descripcion"): "Descripción de la regla violada.",
    ("detalle_error", "valor_recibido"): "Valor que violó la regla.",
    ("detalle_error", "timestamp_error"): "Momento de la detección.",
}

# Reglas asociadas a cada columna (Anexo C). El catálogo implementado se aplicó a los
# documentos de la Condición A (09a); la carga de B solo aplicó el filtro de < 5 caracteres.
REGLAS_COLUMNA = {
    ("retroalimentacion", "texto"): "impl. RQ-01, RQ-07, RQ-08, RQ-09; diseño RQ-01, RQ-08, RQ-09, RQ-10",
    ("retroalimentacion", "id_sesion"): "impl. RQ-02; diseño RQ-02",
    ("retroalimentacion", "fecha_registro"): "impl. RQ-03, RQ-05; diseño RQ-03, RQ-05",
    ("retroalimentacion", "canal_captura"): "impl. RQ-04, RQ-06; diseño RQ-04, RQ-06",
    ("retroalimentacion", "id_ejecucion"): "diseño RQ-11 (no implementada)",
    ("retroalimentacion", "etiqueta_sentimiento"): "diseño RQ-07 (no implementada)",
    ("segmento_retroalimentacion", "etiqueta_sentimiento"): "diseño RQ-07 (no implementada)",
    ("segmento_condicion_a", "tipo_error_inyectado"): "defectos que las reglas impl. RQ-01 a RQ-09 detectarían en documentos",
    ("detalle_error", "codigo_regla"): "registra RQ-01 a RQ-09 (impl.)",
}


def columnas_ddl(ddl):
    """Separa una sentencia CREATE TABLE en definiciones de columna y restricciones CHECK.

    Args:
        ddl (str): Sentencia CREATE TABLE.

    Returns:
        tuple[dict, dict]: Columna → definición (sin intercalación) y nombre → cláusula CHECK.
    """
    columnas, checks = {}, {}
    for linea in ddl.split("\n"):
        linea = re.sub(r" COLLATE \w+", "", linea.strip().rstrip(","))
        m = re.match(r"`(\w+)` (.*)", linea)
        c = re.match(r"CONSTRAINT `(\w+)` CHECK (.*)", linea)
        if m:
            columnas[m.group(1)] = m.group(2)
        elif c:
            checks[c.group(1)] = c.group(2)
    return columnas, checks


def ddl_respaldo():
    """Lee del respaldo del 2026-08-31 solo las sentencias CREATE TABLE (no los datos).

    Returns:
        dict: Tabla → sentencia CREATE TABLE previa al script 13.
    """
    contenido = RESPALDO_SQL.read_text(encoding="utf-8", errors="replace")
    return {m.group(1): m.group(0) for m in re.finditer(r"CREATE TABLE `(\w+)` \(.*?\n\) ENGINE", contenido, re.S)}


def anexo_a(engine):
    """Diccionario de datos liviano: esquema real, descripción, regla y cambio del 2026-08-31."""
    fase2 = tablas_docx(BORRADORES / "Fase2_Metadatos_Minimos.docx")[0]
    metadatos = {f[1]: f"{f[0]} {f[2]}: {f[6]}" for f in fase2[1:]}
    antes = ddl_respaldo()
    filas, conteos = [], {}
    with engine.connect() as c:
        for tabla in TABLAS_DICCIONARIO:
            conteos[tabla] = c.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()
            ahora = c.execute(text(f"SHOW CREATE TABLE {tabla}")).fetchone()[1]
            cols_ahora, checks_ahora = columnas_ddl(ahora)
            cols_antes, checks_antes = columnas_ddl(antes[tabla]) if tabla in antes else ({}, {})
            info = pd.read_sql(text(
                "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t ORDER BY ORDINAL_POSITION"), c, params={"t": tabla})
            for _, r in info.iterrows():
                col = r.COLUMN_NAME
                nulos = c.execute(text(f"SELECT SUM({col} IS NULL) FROM {tabla}")).scalar()
                cambios = []
                if tabla not in antes:
                    cambios.append("sin respaldo")
                elif cols_antes.get(col) != cols_ahora[col]:
                    cambios.append(f"{cols_antes.get(col)} → {cols_ahora[col]}")
                cambios += [f"CHECK nuevo {n}" for n, cl in checks_ahora.items()
                            if n not in checks_antes and f"`{col}`" in cl]
                if col in metadatos and tabla == "retroalimentacion":
                    descripcion, fuente = metadatos[col], "Fase2_Metadatos_Minimos.docx"
                else:
                    descripcion, fuente = DESCRIPCIONES.get((tabla, col), ""), "script 18"
                filas.append({
                    "tabla": tabla, "columna": col, "tipo": r.COLUMN_TYPE,
                    "admite_nulos": "sí" if r.IS_NULLABLE == "YES" else "no",
                    "clave": r.COLUMN_KEY or "", "nulos_observados": int(nulos or 0),
                    "descripcion": descripcion, "fuente_descripcion": fuente,
                    "regla_calidad": REGLAS_COLUMNA.get((tabla, col), "—"),
                    "cambio_2026_08_31": "sí: " + "; ".join(cambios) if cambios else "no",
                })
    linea_filas = "Filas el " + datetime.now().strftime("%Y-%m-%d") + ": " + \
        ", ".join(f"`{t}` {n}" for t, n in conteos.items()) + "."
    intro = (linea_filas + "\n\nTipo, nulos y clave de `information_schema`; nulos observados por "
             "consulta. Descripción de `Fase2_Metadatos_Minimos.docx` (metadatos M-01 a M-07) "
             "cuando existe; si no, declarada en el script 18. Cambio del 2026-08-31: "
             "comparación de cada columna con la sentencia CREATE TABLE del respaldo "
             "`backup_antes_constraints_20260831_2324.sql` (script 13); se leen solo las "
             "sentencias de esquema, no los datos. Regla de calidad: \"impl.\" es el catálogo "
             "implementado en 09a y \"diseño\" el catálogo de 11 reglas (Anexo C). El 09a "
             "validó los documentos de la Condición A; la carga de B solo aplicó el filtro de "
             "menos de 5 caracteres (matriz regla × corpus del Anexo C).")
    escribir("anexo_A_diccionario_datos", *TITULOS["A"], [
        ("Columnas", intro, pd.DataFrame(filas), "columnas"),
    ])


# --- Anexo B ---

# Scripts que llaman a la API: función que construye la llamada, evidencia de ejecución
# (archivo de salida) y parámetros adicionales del módulo que definen la entrada.
SCRIPTS_API = [
    ("scripts/04_etiquetar_sentimiento.py", "etiquetar_segmento", "etiquetas_cargar_20260519_1752.csv",
     ["CATEGORIAS_EXCLUIR", "ETIQUETAS"]),
    ("scripts/07_resegmentar_corpus_completo.py", "segmentar_con_claude", "segmentos_claude_api_completo.csv",
     ["CATEGORIAS"]),
    ("scripts/08_data_augmentation.py", "generar_variantes", "augmentation_variantes.csv",
     ["VARIANTES_POR_CLASE", "SEMILLA"]),
    ("scripts/09_reetiquetar_positivos.py", "reclasificar_segmento", "reetiquetado_positivos_20260519_2049.csv", []),
]

# Tratamiento de la respuesta, ubicado en el código con una expresión regular.
POSPROCESO = {
    "04": [("etiqueta no reconocida → 'neutral'", r"ETIQUETAS\.get\(etiqueta_num"),
           ("error de JSON → 'neutral', confianza 'baja'", r"except json\.JSONDecodeError"),
           ("justificación truncada a 300 caracteres", r"\[:300\]")],
    "07": [("solo categorías del catálogo y fragmentos de 30 caracteres o más", r"if cat in CATEGORIAS and len\(texto_s\) >= 30"),
           ("error de JSON o de API → ningún segmento para la entrevista", r"^\s*return \[\]\s*$"),
           ("el máximo de 10 segmentos solo se pide en el prompt; el código no lo verifica", None)],
    "08": [("se descartan variantes de menos de 20 caracteres", r"len\(v\.strip\(\)\) >= 20"),
           ("error → ninguna variante", r"^\s*return \[\]\s*$")],
    "09": [("etiqueta fuera de {positivo, levemente_positivo} → 'positivo'", r"if etiqueta not in"),
           ("error → 'positivo', confianza 'baja'", r"except Exception"),
           ("solo las reclasificaciones de confianza alta se escriben en la BD", r'\(df_resultados\["confianza"\] == "alta"\)')],
}


def plantilla(nodo, asignaciones):
    """Reconstruye el texto de una f-string, con cada expresión entre llaves.

    Args:
        nodo (ast.JoinedStr): f-string.
        asignaciones (dict): Nombre → expresión asignada en la función.

    Returns:
        tuple[str, list[str]]: Plantilla y expresiones de preprocesamiento de la entrada.
    """
    partes, preproceso = [], []
    for v in nodo.values:
        if isinstance(v, ast.Constant):
            partes.append(v.value)
        else:
            expr = ast.unparse(v.value)
            partes.append("{" + expr + "}")
            if isinstance(v.value, ast.Name) and v.value.id in asignaciones:
                preproceso.append(f"{expr} = {ast.unparse(asignaciones[v.value.id])}")
            elif isinstance(v.value, ast.Subscript):
                preproceso.append(expr)
    return "".join(partes), preproceso


def extraer_llamada(ruta, nombre_funcion):
    """Extrae del código la llamada a la API: prompts, parámetros y preprocesamiento.

    Args:
        ruta (pathlib.Path): Script.
        nombre_funcion (str): Función que llama a cliente.messages.create.

    Returns:
        dict: Constantes del módulo, argumentos de la llamada, plantilla del mensaje de
        usuario, preprocesamiento y línea de la llamada.
    """
    modulo = ast.parse(ruta.read_text(encoding="utf-8"))
    constantes = {}
    for n in modulo.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id.isupper():
            try:
                constantes[n.targets[0].id] = ast.literal_eval(n.value)
            except ValueError:
                pass
    funcion = next(n for n in modulo.body if isinstance(n, ast.FunctionDef) and n.name == nombre_funcion)
    asignaciones = {n.targets[0].id: n.value for n in ast.walk(funcion)
                    if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    llamada = next(n for n in ast.walk(funcion) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute) and n.func.attr == "create")
    argumentos = {k.arg: ast.unparse(k.value) for k in llamada.keywords}
    mensajes = next(k.value for k in llamada.keywords if k.arg == "messages")
    contenido = next(v for d in ast.walk(mensajes) if isinstance(d, ast.Dict)
                     for k, v in zip(d.keys, d.values) if getattr(k, "value", None) == "content")
    if isinstance(contenido, ast.Name):
        contenido = asignaciones[contenido.id]
    usuario, preproceso = plantilla(contenido, asignaciones)
    seleccion = ""
    for n in ast.walk(modulo):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "read_sql" and n.args:
            consulta = n.args[0]
            sql = consulta.value if isinstance(consulta, ast.Constant) else \
                plantilla(consulta, {})[0] if isinstance(consulta, ast.JoinedStr) else ""
            if "texto" in sql:
                seleccion = f"{' '.join(sql.split())} (línea {n.lineno})"
                break
    return {"constantes": constantes, "argumentos": argumentos, "usuario": usuario,
            "preproceso": preproceso, "seleccion": seleccion, "linea": llamada.lineno}


def historial_prompt(ruta):
    """Verifica en el historial de Git si cambió el texto del prompt o los parámetros.

    El verificador de equivalencia ignora el contenido de las cadenas, así que este control
    compara directamente SYSTEM_PROMPT, MODELO y MAX_TOKENS en cada versión del archivo.

    Args:
        ruta (str): Ruta del script relativa a Code/.

    Returns:
        str: Versiones revisadas, primera versión en Git y si hubo cambios.
    """
    commits = git("log", "--follow", "--format=%h %ad", "--date=short", "--", ruta).split("\n")
    valores = []
    for c in commits:
        h = c.split()[0]
        archivos = git("show", "--name-only", "--format=", h).split("\n")
        ruta_h = next((a for a in archivos if a.endswith(Path(ruta).name)), ruta)
        modulo = ast.parse(git("show", f"{h}:{ruta_h}"))
        valores.append(repr({n.targets[0].id: ast.literal_eval(n.value) for n in modulo.body
                             if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                             and n.targets[0].id in ("SYSTEM_PROMPT", "MODELO", "MAX_TOKENS")}))
    estado = "sin cambios" if len(set(valores)) == 1 else "CON CAMBIOS"
    return f"{estado} en {len(commits)} versiones (primera en Git: {commits[-1]})"


def anexo_b(engine):
    """Prompts literales y parámetros de las llamadas a la API, con datos identificables marcados."""
    sys.path.insert(0, str(RAIZ / "tools"))
    from terminos_privacidad import nombres_propios, sesiones_y_programas
    _, programas = sesiones_y_programas(engine)
    nombres = nombres_propios()

    def enmascarar(texto_prompt):
        marcas = []
        for p in sorted(programas):
            if re.search(rf"\b{re.escape(p)}\b", texto_prompt):
                texto_prompt = re.sub(rf"\b{re.escape(p)}\b", "[nombre del programa]", texto_prompt)
                marcas.append("nombre del programa")
        for n in sorted(nombres):
            if re.search(rf"\b{re.escape(n)}\b", texto_prompt):
                texto_prompt = re.sub(rf"\b{re.escape(n)}\b", "[nombre propio]", texto_prompt)
                marcas.append("nombre propio")
        return texto_prompt, sorted(set(marcas))

    parametros, secciones = [], []
    for ruta, funcion, evidencia, extras in SCRIPTS_API:
        d = extraer_llamada(RAIZ / ruta, funcion)
        k = d["constantes"]
        clave = Path(ruta).name[:2]
        sistema, marcas_s = enmascarar(k["SYSTEM_PROMPT"])
        usuario, marcas_u = enmascarar(d["usuario"])
        marcas = sorted(set(marcas_s + marcas_u))
        fecha = datetime.fromtimestamp((OUT / evidencia).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        no_fijados = [p for p in ("temperature", "top_p", "top_k", "stop_sequences") if p not in d["argumentos"]]
        posproceso = [f"{desc} ({ubicar(ruta, patron)})" if patron else desc for desc, patron in POSPROCESO[clave]]
        posproceso = [f"se eliminan las cercas ```json ({ubicar(ruta, r'replace\(\"```json\"')}) y se lee con "
                      f"json.loads ({ubicar(ruta, r'json\.loads\(raw\)')})"] + posproceso
        parametros.append({
            "script": ruta, "modelo": k["MODELO"], "max_tokens": k["MAX_TOKENS"],
            "parametros_fijados": ", ".join(f"{a}={v}" for a, v in d["argumentos"].items() if a != "messages"),
            "no_fijados": ", ".join(no_fijados) + " (valor por defecto de la API)" if no_fijados else "—",
            "pausa_entre_llamadas_s": k.get("PAUSA_SEG", ""),
            "seleccion_entrada": d["seleccion"],
            "preprocesamiento_entrada": "; ".join(d["preproceso"]),
            "llamada": f"{ruta}:{d['linea']}",
            "evidencia_ejecucion": f"outputs/{evidencia} ({fecha})",
            "historial_prompt": historial_prompt(ruta),
            "marcas_privacidad": ", ".join(marcas) if marcas else "ninguna",
        })
        otros = "\n".join(f"- `{e}` = `{k[e]!r}`" for e in extras)
        cuerpo = (
            f"Modelo `{k['MODELO']}`, `max_tokens` = {k['MAX_TOKENS']}, llamada en `{ruta}:{d['linea']}`. "
            f"No se fijan {', '.join(f'`{p}`' for p in no_fijados)}: rigen los valores por defecto de la "
            "API (temperatura 1,0), así que la respuesta no es determinista.\n\n"
            f"**Selección de la entrada:** `{d['seleccion']}`.\n\n"
            f"**Preprocesamiento de la entrada:** {'; '.join(f'`{p}`' for p in d['preproceso'])}.\n\n"
            + (f"**Parámetros del módulo:**\n{otros}\n\n" if otros else "")
            + "**Prompt de sistema** (literal):\n\n```text\n" + sistema + "\n```\n\n"
            + "**Mensaje de usuario** (plantilla literal; entre llaves, la expresión de Python que se "
              "sustituye):\n\n```text\n" + usuario + "\n```\n\n"
            + "**Formato de respuesta esperado:** el JSON que pide el prompt de sistema. "
            + "**Tratamiento de la respuesta:** " + "; ".join(posproceso) + ".\n\n"
            + f"**Marcas de privacidad:** {', '.join(marcas) if marcas else 'ninguna'}."
        )
        secciones.append((f"B.{len(secciones) + 2} {Path(ruta).name}", cuerpo, None, None))
    intro = ("Extraído del código con `ast` (no transcrito). La API key no aparece en el código: "
             "se lee de `.env` con `os.getenv`, y este anexo no la incluye. Los nombres de programa "
             "y los nombres propios se reemplazan por una marca entre corchetes; los términos se "
             "obtienen en tiempo de ejecución de la tabla `sesion` y de los nombres de archivo de "
             "audio (`tools/terminos_privacidad.py`). Las frases de ejemplo del prompt de "
             "09_reetiquetar_positivos son expresiones genéricas escritas en el prompt, sin "
             "identificadores. Historial: el texto del prompt, el modelo y `max_tokens` se "
             "comparan en todas las versiones de Git (columna `historial_prompt`).\n\n"
             "**Nota sobre la versión ejecutada:** los prompts entraron al repositorio el 21 de "
             "agosto de 2026, después de su ejecución (mayo-junio de 2026; columna "
             "`evidencia_ejecucion`). No cambiaron en ninguna versión registrada, pero no hay "
             "registro del texto exacto usado en la ejecución.")
    escribir("anexo_B_prompts_api", *TITULOS["B"],
             [("B.1 Parámetros de las llamadas", intro, pd.DataFrame(parametros), "parametros")] + secciones)


# --- Anexo C (reglas de calidad) ---

def catalogo_implementado(engine):
    """Construye el catálogo implementado en 09a con líneas, criterios y conteos.

    Args:
        engine (sqlalchemy.engine.Engine): Motor de conexión (solo lectura).

    Returns:
        pandas.DataFrame: Una fila por regla RQ-01 a RQ-09.
    """
    lineas = SCRIPT_09A.read_text(encoding="utf-8").split("\n")
    modulo = ast.parse(SCRIPT_09A.read_text(encoding="utf-8"))
    descripciones = {}
    for nodo in modulo.body:
        if isinstance(nodo, ast.Assign) and getattr(nodo.targets[0], "id", "") == "DESCRIPCION_REGLA":
            descripciones = ast.literal_eval(nodo.value)
    campos = {"RQ-01": "texto", "RQ-02": "num_sesion (id_sesion)", "RQ-03": "fecha_real (fecha_registro)",
              "RQ-04": "canal_captura", "RQ-05": "fecha_real (fecha_registro)", "RQ-06": "canal_captura",
              "RQ-07": "texto", "RQ-08": "texto", "RQ-09": "texto"}
    esquema = {"RQ-01": "texto NOT NULL; CHECK (CHAR_LENGTH(texto) >= 5) (script 13, retroalimentacion)",
               "RQ-02": "id_sesion NOT NULL (script 13)", "RQ-03": "fecha_registro NOT NULL (script 13)",
               "RQ-04": "canal_captura NOT NULL (script 13)", "RQ-05": "tipo DATE de fecha_registro (parcial)",
               "RQ-06": "CHECK canal_captura IN catálogo (script 13)", "RQ-07": "—", "RQ-08": "—",
               "RQ-09": "— (el CHECK de 5 caracteres no coincide con el umbral de 20)"}
    with engine.connect() as c:
        conteos = pd.read_sql(text("SELECT codigo_regla, COUNT(*) n FROM detalle_error GROUP BY 1"), c) \
            .set_index("codigo_regla")["n"]
    filas = []
    for codigo in sorted(descripciones):
        i = next(k for k, l in enumerate(lineas) if l.strip().startswith(f"# {codigo}"))
        criterio = next(lineas[k].strip() for k in range(i + 1, len(lineas))
                        if lineas[k].strip().startswith(("if ", "texto_key")) or "errores.append" in lineas[k])
        linea_criterio = next(k for k in range(i + 1, len(lineas)) if lineas[k].strip() == criterio) + 1
        if codigo == "RQ-07":
            criterio = "texto_key = texto[:200].lower().strip(); if texto_key in textos_vistos"
        if codigo == "RQ-05":
            criterio = 'pd.to_datetime(str(fecha), format="%Y-%m-%d") falla'
            linea_criterio = next(k for k in range(i + 1, len(lineas))
                                  if "pd.to_datetime(str(fecha)" in lineas[k]) + 1
        registradas = int(conteos.get(codigo, 0))
        filas.append({
            "codigo": codigo, "campo": campos[codigo], "descripcion_09a": descripciones[codigo],
            "criterio_literal": criterio, "accion": "rechazar el registro",
            "linea_09a": linea_criterio, "restriccion_esquema": esquema[codigo],
            "violaciones_registradas": registradas,
            "violaciones_corregidas": registradas + CORRECCION_CONTEOS.get(codigo, 0),
        })
    return pd.DataFrame(filas)


def catalogo_diseno():
    """Extrae textualmente la tabla de 11 reglas del borrador del working paper.

    Returns:
        pandas.DataFrame: Tabla de diseño, columnas y contenido literales.
    """
    for tabla in tablas_docx(BORRADORES / "Working_Paper_Marco_Gobernado_v1.docx"):
        if tabla and tabla[0] and tabla[0][0] == "RQ":
            return pd.DataFrame(tabla[1:], columns=tabla[0])
    raise RuntimeError("No se encontró la tabla de reglas en Working_Paper_Marco_Gobernado_v1.docx")


def umbrales_longitud(diseno):
    """Localiza los umbrales de longitud de texto en diseño, código, esquema y segmentación.

    Args:
        diseno (pandas.DataFrame): Catálogo de diseño.

    Returns:
        pandas.DataFrame: Umbral, alcance y ubicación de cada criterio.
    """
    filas = [{"etapa": "diseño", "criterio": diseno.loc[diseno["RQ"] == "RQ-09", "Condición de fallo"].iloc[0],
              "unidad": "registro", "efecto": "rechazar (RQ-09 de diseño)",
              "ubicacion": "Borradores/Working_Paper_Marco_Gobernado_v1.docx, tabla de reglas"}]
    patrones = [
        ("scripts/01_deduplicar_y_cargar.py", r"len\(texto\) < 5", "registro (carga de B)", "rechazar; RQ-01 en detalle_error"),
        ("scripts/02_fusionar_y_cargar.py", r"len\(texto\) < 5", "registro (carga de B)", "rechazar; RQ-01 en detalle_error"),
        ("scripts/09a_procesar_condicion_a.py", r"len\(texto\) < 20", "registro (Condición A)", "rechazar; RQ-09"),
        ("scripts/09a_procesar_condicion_a.py", r"texto\[:200\]", "registro (Condición A)", "clave de duplicado RQ-07"),
        ("scripts/07_resegmentar_corpus_completo.py", r"LENGTH\(texto\) > 50", "registro", "solo se segmentan registros de más de 50 caracteres"),
        ("scripts/07_resegmentar_corpus_completo.py", r"texto\[:4000\]", "registro", "solo los primeros 4.000 caracteres se envían a segmentar"),
        ("scripts/07_resegmentar_corpus_completo.py", r"len\(texto_s\) >= 30", "segmento", "se descartan fragmentos de menos de 30 caracteres"),
        ("scripts/09_cargar_revision_manual.py", r"len\(texto\.strip\(\)\) < 20", "segmento", "excluir (flag_excluir)"),
        ("scripts/09_cargar_revision_manual.py", r"len\(texto\.split\(\)\) < 8", "segmento", "excluir (menos de 8 palabras)"),
        ("scripts/08_data_augmentation.py", r"len\(v\.strip\(\)\) >= 20", "variante sintética", "se descartan variantes de menos de 20 caracteres"),
        ("scripts/colab/entrenar_beto.py", r"^MAX_LENGTH\s*=", "secuencia de tokens", "truncamiento al tokenizar (BETO, BERTIN)"),
    ]
    for archivo, patron, unidad, efecto in patrones:
        lineas = (RAIZ / archivo).read_text(encoding="utf-8").split("\n")
        for k, linea in enumerate(lineas, 1):
            if re.search(patron, linea.strip()):
                filas.append({"etapa": "código", "criterio": linea.strip(), "unidad": unidad,
                              "efecto": efecto, "ubicacion": f"{archivo}:{k}"})
                break
        else:
            filas.append({"etapa": "código", "criterio": f"[no encontrado: {patron}]", "unidad": unidad,
                          "efecto": efecto, "ubicacion": archivo})
    with get_engine().connect() as c:
        checks = pd.read_sql(text("SELECT CONSTRAINT_NAME, CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS "
                                  "WHERE CONSTRAINT_SCHEMA = DATABASE() AND CHECK_CLAUSE LIKE '%char_length%'"), c)
    for _, r in checks.iterrows():
        filas.append({"etapa": "esquema", "criterio": r.CHECK_CLAUSE, "unidad": "registro",
                      "efecto": "MySQL rechaza la inserción", "ubicacion": f"retroalimentacion.{r.CONSTRAINT_NAME} (script 13)"})
    return pd.DataFrame(filas)


def ubicar(archivo, patron):
    """Devuelve 'archivo:línea' de la primera línea que coincide con un patrón.

    Args:
        archivo (str): Ruta relativa a Code/.
        patron (str): Expresión regular.

    Returns:
        str: Ubicación, o un aviso si el patrón no aparece.

    Raises:
        RuntimeError: Si el patrón no aparece (evita citar una línea inexistente).
    """
    for k, linea in enumerate((RAIZ / archivo).read_text(encoding="utf-8").split("\n"), 1):
        if re.search(patron, linea):
            return f"{archivo}:{k}"
    raise RuntimeError(f"Patrón no encontrado en {archivo}: {patron}")


def cifras_condicion_b(engine):
    """Obtiene de la BD y de corpus_final.csv las cifras que cita la matriz (solo lectura).

    Args:
        engine (sqlalchemy.engine.Engine): Motor de conexión.

    Returns:
        dict: rechazos de la ejecución 2, registros con sesión comodín, pares de texto
        idéntico en B y fechas nulas en la carga.
    """
    with engine.connect() as c:
        rechazos = c.execute(text("SELECT registros_rechazados FROM ejecucion_pipeline WHERE id_ejecucion = 2")).scalar()
        comodin = c.execute(text(
            "SELECT COUNT(*) FROM retroalimentacion r JOIN sesion s USING (id_sesion) "
            "WHERE r.id_ejecucion = 2 AND s.nombre_sesion LIKE '%sesion_desconocida'")).scalar()
        pares = c.execute(text(
            "SELECT COUNT(*) FROM (SELECT texto FROM retroalimentacion WHERE id_ejecucion = 2 "
            "GROUP BY texto HAVING COUNT(*) > 1) t")).scalar()
    fechas_nulas = int(pd.read_csv(OUT / "corpus_final.csv")["fecha_real"].isna().sum())
    return {"rechazos": int(rechazos), "comodin": int(comodin), "pares": int(pares), "fechas_nulas": fechas_nulas}


def matriz_regla_corpus(engine):
    """Construye la matriz regla × corpus: dónde se aplicó cada regla y con qué criterio.

    Condición B: carga con 02_fusionar_y_cargar.py (ejecución 2; 01 tiene el mismo bloque
    de carga) y deduplicación previa en 01. Condición A: 09a sobre condicion_A.csv
    (documentos). Las ubicaciones se localizan en el código; los criterios se citan literales.

    Args:
        engine (sqlalchemy.engine.Engine): Motor de conexión (solo lectura).

    Returns:
        pandas.DataFrame: Una fila por regla (9 implementadas, 11 de diseño) y por control de B.
    """
    k = cifras_condicion_b(engine)
    A, B1, B2 = "scripts/09a_procesar_condicion_a.py", "scripts/01_deduplicar_y_cargar.py", "scripts/02_fusionar_y_cargar.py"
    u = ubicar
    l5 = f"{u(B2, r'len\(texto\) < 5')} (y {u(B1, r'len\(texto\) < 5')})"
    sesion = (f"no se valida; se asigna la sesión por nombre ({u(B2, r'sesion_id_map\.get')}). Los {k['comodin']} "
              "registros sin sesión recibieron una sesión comodín (nombre terminado en 'sesion_desconocida')")
    fecha_b = f"no se valida; si falta, se carga NULL ({u(B2, r'fecha_reg = None')}); {k['fechas_nulas']} NULL, imputados después (2026-08-31)"
    coercion = f"no se rechaza: si pd.to_datetime falla, se carga NULL ({u(B2, r'fecha_reg = pd.to_datetime')})"
    canal = f"por construcción: canal constante CANAL_CAPTURA = \"formulario\" ({u(B2, r'^CANAL_CAPTURA')})"
    audio = f"solo por nombre de archivo de audio ({u(B1, r'drop_duplicates\(subset=\"audio_filename\"')}); {k['pares']} pares de texto idéntico pasaron"
    ejec = f"por construcción: id_ejecucion de la ejecución en curso ({u(B2, r'INSERT INTO ejecucion_pipeline')}); sin validación"
    esquema = "retroalimentacion, desde 2026-08-31 (script 13)"
    filas = [
        # catálogo implementado
        ("implementado", "RQ-01", "texto nulo o vacío", f"sí, con otro criterio: `if not texto or len(texto) < 5` — {l5}",
         f"sí: `if not texto` — {u(A, r'^\s*if not texto:')}", f"NOT NULL y CHECK ≥ 5 ({esquema})"),
        ("implementado", "RQ-02", "id_sesion nulo", sesion, f"sí — {u(A, r'if pd\.isna\(id_sesion\)')}", f"NOT NULL ({esquema})"),
        ("implementado", "RQ-03", "fecha_registro nula", fecha_b, f"sí — {u(A, r'if pd\.isna\(fecha\)')}", f"NOT NULL ({esquema})"),
        ("implementado", "RQ-04", "canal_captura nulo", canal, f"sí — {u(A, r'if pd\.isna\(canal\)')}", f"NOT NULL ({esquema})"),
        ("implementado", "RQ-05", "formato de fecha inválido", coercion, f"sí — {u(A, r'pd\.to_datetime\(str\(fecha\)')}", "tipo DATE (parcial)"),
        ("implementado", "RQ-06", "canal fuera del catálogo", canal, f"sí — {u(A, r'not in CANAL_CATALOGO')}", f"CHECK catálogo ({esquema})"),
        ("implementado", "RQ-07", "duplicado (primeros 200 caracteres)", f"no por texto; control distinto: {audio}",
         f"sí — {u(A, r'texto_key = texto\[:200\]')}", "—"),
        ("implementado", "RQ-08", "texto no informativo", "no en la carga de documentos", f"sí — {u(A, r'in TEXTOS_NO_INFORMATIVOS')}", "—"),
        ("implementado", "RQ-09", "texto < 20 caracteres", "no en la carga de documentos (solo < 5)", f"sí — {u(A, r'len\(texto\) < 20')}", "—"),
        # catálogo de diseño
        ("diseño", "RQ-01", "texto nulo o vacío → rechazar", f"sí, con otro criterio (< 5) — {l5}", f"sí — {u(A, r'^\s*if not texto:')}", "NOT NULL"),
        ("diseño", "RQ-02", "id_sesion nulo → rechazar", sesion, f"sí — {u(A, r'if pd\.isna\(id_sesion\)')}", "NOT NULL"),
        ("diseño", "RQ-03", "fecha nula → rechazar", fecha_b, f"sí — {u(A, r'if pd\.isna\(fecha\)')}", "NOT NULL"),
        ("diseño", "RQ-04", "canal nulo → corregir a 'desconocido'", canal + "; no se corrige a 'desconocido'",
         f"con acción distinta (rechaza) — {u(A, r'if pd\.isna\(canal\)')}", "NOT NULL"),
        ("diseño", "RQ-05", "formato ≠ YYYY-MM-DD o fecha futura → rechazar", coercion + "; no verifica fechas futuras",
         f"solo formato; no verifica futuras — {u(A, r'pd\.to_datetime\(str\(fecha\)')}", "tipo DATE (parcial)"),
        ("diseño", "RQ-06", "canal fuera del catálogo → corregir a 'desconocido'", canal,
         f"con acción distinta (rechaza) — {u(A, r'not in CANAL_CATALOGO')}", "CHECK catálogo"),
        ("diseño", "RQ-07", "etiqueta fuera de {positivo, neutral, negativo} → rechazar",
         f"ninguna regla; el etiquetado asigna 'neutral' a etiquetas no reconocidas ({u('scripts/04_etiquetar_sentimiento.py', r'ETIQUETAS\.get\(etiqueta_num')})",
         "ninguna", "—"),
        ("diseño", "RQ-08", "duplicado por hash + id_sesion → rechazar", f"criterio distinto: {audio}",
         f"criterio distinto (texto, sin sesión) — {u(A, r'texto_key = texto\[:200\]')}", "—"),
        ("diseño", "RQ-09", "texto < 3 caracteres → rechazar", f"cubierta por el filtro < 5 — {l5}",
         f"cubierta por < 20 — {u(A, r'len\(texto\) < 20')}", "CHECK ≥ 5"),
        ("diseño", "RQ-10", "solo números o puntuación → rechazar", "ninguna", "ninguna", "—"),
        ("diseño", "RQ-11", "id_ejecucion ausente → rechazar", ejec,
         f"por construcción, sin validación — {u(A, r'INSERT INTO ejecucion_pipeline')}", "admite NULL"),
        # controles propios de B
        ("control de B", "—", "deduplicación por nombre de archivo de audio", f"sí — {u(B1, r'drop_duplicates\(subset=\"audio_filename\"')}",
         "no aplica (A se construye después, desde el corpus deduplicado)", "—"),
        ("control de B", "—", "filtro de texto vacío o < 5 caracteres (registrado como RQ-01)", f"sí — {l5}; {k['rechazos']} rechazos en la ejecución 2",
         "no aplica", "CHECK ≥ 5 (script 13)"),
    ]
    return pd.DataFrame(filas, columns=["catalogo", "regla", "criterio", "condicion_B_carga_documentos",
                                        "condicion_A_09a_documentos", "esquema"])


NOTA_MATRIZ = """Alcance: la matriz describe la validación de **documentos** (registros de entrevista).
Condición B: deduplicación en 01 y carga con 02 (ejecución 2, 2026-05-14; 01 contiene el
mismo bloque de carga). Condición A: validación del 09a sobre `condicion_A.csv`
(ejecución 4); los 59 documentos válidos se cargaron en `retroalimentacion`, pero **el
corpus de A que usan los modelos es `segmento_condicion_a`, que no pasa por ninguna
regla** (es la condición no gobernada, por diseño).

A nivel de segmento, ambas condiciones comparten los controles de B, porque A se
construye a partir de los segmentos de B con `flag_excluir = 0`: solo se segmentan los
primeros 4.000 caracteres de cada entrevista y se descartan fragmentos de menos de 30
caracteres (script 07), y se excluyen segmentos de menos de 20 caracteres o de 8 palabras
o sin valor analítico (script 09_cargar_revision_manual). Ver el apartado d) de umbrales.

En la Condición B, el script 13 (2026-08-31) añadió después restricciones de esquema
sobre `retroalimentacion`, columna "esquema"."""


NOTA_DEDUPLICACION = """El corpus de la Condición B tiene 17 pares de registros con texto idéntico
(`docs/cambios_agosto_2026.md`, §18-19). No los detectó ninguna regla, por dos razones:

1. **El script 01 deduplica por nombre de archivo de audio** (`deduplicar()`,
   `drop_duplicates(subset="audio_filename")`), no por texto. Los 17 pares tienen nombres de
   archivo distintos, aunque la misma duración y el mismo modelo de transcripción: casi con
   seguridad es el mismo audio guardado con dos nombres.
2. **RQ-07 solo se aplica a la Condición A.** El 09a valida `condicion_A.csv`; los
   registros de B se cargaron con 01 y 02, que solo aplican RQ-01 (`len(texto) < 5`).
   Reproduciendo la validación del 09a en memoria (2026-10-09), RQ-07 marca 34 registros
   en A: 17 en las filas que agrega la inyección de duplicados, 14 que son la segunda
   aparición de un par natural de B, y 3 textos no informativos inyectados que se repiten
   ("." y "nada que decir"). Los otros 3 pares naturales no se detectan porque la
   inyección alteró el texto de uno de sus gemelos. Es decir, la regla de duplicados
   habría detectado la mayoría de estos pares, pero no se aplicó al corpus gobernado.

Consecuencia: fuga entre entrenamiento y prueba en 5 pares (20 de los 177 segmentos
evaluados). El análisis de sensibilidad del 2026-10-09 no cambia las conclusiones según
su criterio (Anexo E)."""


def anexo_c(engine):
    """Catálogo de reglas: implementado, diseño, correspondencia, umbrales, deduplicación y matriz."""
    implementado = catalogo_implementado(engine)
    diseno = catalogo_diseno()
    corr = pd.DataFrame(CORRESPONDENCIA, columns=["regla_diseno", "regla_implementada", "tipo_de_cambio", "observacion"])
    escribir("anexo_C_reglas_calidad", *TITULOS["C"], [
        ("a) Catálogo implementado (09a_procesar_condicion_a.py)",
         "Criterio literal y línea del código; acción de 09a: toda violación rechaza el "
         "registro. Violaciones de `detalle_error` (ejecución 4, Condición A); las corregidas "
         "reasignan 4 casos de canal \"n/a\" de RQ-04 a RQ-06 (`cambios_agosto_2026.md`, §20).",
         implementado, "catalogo_implementado"),
        ("b) Catálogo de diseño (11 reglas)",
         "Transcripción literal de la tabla de `Borradores/Working_Paper_Marco_Gobernado_v1.docx` "
         "(2026-08-09).", diseno, "catalogo_diseno"),
        ("c) Correspondencia diseño → implementado", "", corr, "correspondencia"),
        ("d) Umbrales de longitud en el pipeline", "Ubicación exacta de cada criterio de longitud.",
         umbrales_longitud(diseno), "umbrales_longitud"),
        ("e) Nota sobre la deduplicación", NOTA_DEDUPLICACION, None, None),
        ("f) Matriz regla × corpus", NOTA_MATRIZ, matriz_regla_corpus(engine), "matriz_regla_corpus"),
    ])


# --- Anexo D ---

# Etapa y fase de CRISP-DM de cada paso del orden de ejecución de la guía operativa
# (juicio declarado el 2026-10-09).
ETAPA_PASO = {
    0: ("Entorno y conexión", "—"),
    1: ("Carga del corpus gobernado (B)", "Preparación de los datos"),
    2: ("Carga del corpus gobernado (B)", "Preparación de los datos"),
    3: ("Segmentación", "Preparación de los datos"),
    4: ("Etiquetado y revisión", "Preparación de los datos"),
    5: ("Condición A", "Preparación de los datos"),
    6: ("Etiquetado y revisión", "Preparación de los datos"),
    7: ("Condición A", "Preparación de los datos"),
    8: ("Etiquetado y revisión", "Preparación de los datos"),
    9: ("Condición A", "Preparación de los datos"),
    10: ("Aumento de datos", "Preparación de los datos"),
    11: ("Partición", "Preparación de los datos"),
    12: ("Modelado", "Modelado"),
    13: ("Modelado", "Modelado"),
    14: ("Restricciones de esquema", "Gobernanza"),
    15: ("Evaluación", "Evaluación"),
    16: ("Evaluación", "Evaluación"),
    17: ("Evaluación", "Evaluación"),
    18: ("Evaluación", "Evaluación"),
    19: ("Anexos", "Evaluación"),
    20: ("Auditoría de privacidad", "—"),
}


def tabla_markdown(ruta, encabezado):
    """Lee una tabla Markdown de un documento a partir de su primera celda de encabezado.

    Args:
        ruta (pathlib.Path): Documento Markdown.
        encabezado (str): Texto de la primera celda del encabezado.

    Returns:
        list[list[str]]: Filas de datos (sin encabezado ni separador), celdas sin espacios.
    """
    lineas = ruta.read_text(encoding="utf-8").split("\n")
    i = next(k for k, l in enumerate(lineas) if re.match(rf"\|\s*{re.escape(encabezado)}\s*\|", l))
    filas = []
    for linea in lineas[i + 2:]:
        if not linea.startswith("|"):
            break
        filas.append([c.strip() for c in linea.strip().strip("|").split("|")])
    return filas


def docstring_script(ruta):
    """Resumen, entradas y salidas del docstring de un script.

    Args:
        ruta (pathlib.Path): Script.

    Returns:
        dict: funcion, entradas y salidas.
    """
    doc = ast.get_docstring(ast.parse(ruta.read_text(encoding="utf-8"))) or ""
    entradas = re.search(r"Entradas:\n(.*?)(?:\nSalidas:|\Z)", doc, re.S)
    salidas = re.search(r"Salidas:\n(.*?)(?:\n\n|\Z)", doc, re.S)
    compactar = lambda m: " ".join(m.group(1).split()) if m else ""
    return {"funcion": " ".join(doc.strip().split("\n\n")[0].split()) if doc else "",
            "entradas": compactar(entradas), "salidas": compactar(salidas)}


def inventario_scripts():
    """Inventario por etapa: el orden de ejecución de la guía más los scripts fuera de él.

    Returns:
        pandas.DataFrame: Paso, etapa, fase, script, función, entradas y salidas.
    """
    guia = RAIZ / "docs" / "guia_operativa_scripts.md"
    filas, vistos = [], set()
    for paso, scripts, _, _ in tabla_markdown(guia, "Paso"):
        for nombre in re.findall(r"`([\w/]+\.py)`", scripts):
            ruta = next(r for r in (RAIZ / "scripts" / nombre, RAIZ / "scripts" / "colab" / nombre) if r.exists())
            etapa, fase = ETAPA_PASO[int(paso)]
            filas.append({"paso": int(paso), "etapa": etapa, "fase_crisp_dm": fase,
                          "script": str(ruta.relative_to(RAIZ)), **docstring_script(ruta)})
            vistos.add(ruta)
    otros = [("—", "Sin paso en la guía", "—", r) for r in sorted((RAIZ / "scripts").glob("*.py"))] \
        + [(13, "Modelado (Colab)", "Modelado", r) for r in sorted((RAIZ / "scripts" / "colab").glob("*.py"))] \
        + [("—", "Histórico (fuera del flujo)", "—", r) for r in sorted((RAIZ / "scripts" / "historico").glob("*.py"))] \
        + [("—", "Herramienta", "—", r) for r in sorted((RAIZ / "tools").glob("*.py"))]
    for paso, etapa, fase, ruta in otros:
        if ruta not in vistos:
            filas.append({"paso": paso, "etapa": etapa, "fase_crisp_dm": fase,
                          "script": str(ruta.relative_to(RAIZ)), **docstring_script(ruta)})
    return pd.DataFrame(filas)


def version_citable():
    """Datos de la etiqueta citable y archivos de código que cambiaron después de ella.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Etiqueta y cambios posteriores.
    """
    ref = f"refs/tags/{VERSION_CITABLE}"
    objeto, commit, fecha, asunto = git("for-each-ref", "--format=%(objectname)|%(*objectname)|%(taggerdate:iso)|%(subject)", ref).split("|")
    etiqueta = pd.DataFrame([
        ("Etiqueta", VERSION_CITABLE), ("Objeto de la etiqueta (anotada)", objeto),
        ("Commit", commit), ("Fecha de la etiqueta", fecha), ("Mensaje", asunto),
        ("Commit (fecha y asunto)", git("show", "--no-patch", "--format=%ci · %s", commit)),
        ("Repositorio", git("remote", "get-url", "origin")),
        ("Etiqueta en el remoto", "sí" if git("ls-remote", "--tags", "origin", ref) else "no"),
    ], columns=["dato", "valor"])
    rutas = ["scripts", "tools", "config"]
    cambios = [(l.split("\t")[-1], {"M": "modificado", "A": "agregado", "D": "eliminado"}.get(l[0], l.split("\t")[0]))
               for l in git("diff", "--name-status", VERSION_CITABLE, "--", *rutas).split("\n") if l]
    cambios += [(a, "agregado")
                for a in git("ls-files", "--others", "--exclude-standard", "--", *rutas).split("\n") if a]
    return etiqueta, pd.DataFrame(cambios, columns=["archivo", "cambio_desde_la_etiqueta"])


def requisitos_entorno():
    """Requisitos local (rangos y versiones congeladas) y de Colab (registro de entorno).

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Entorno local y entorno de Colab.
    """
    leer = lambda r: [l.split("#")[0].strip() for l in (RAIZ / r).read_text(encoding="utf-8").split("\n")
                      if l.split("#")[0].strip()]
    congeladas = dict(l.split("==") for l in leer("requirements-local.lock.txt") if "==" in l)
    verificado = (OUT / "entorno_verificado.txt").read_text(encoding="utf-8")
    local = [("Python", "—", re.search(r"Versión\s*:\s*(.+)", verificado).group(1).strip(), "outputs/entorno_verificado.txt"),
             ("MySQL", "—", re.search(r"MySQL ([\d.]+)", verificado).group(1), "outputs/entorno_verificado.txt")]
    for linea in leer("requirements-local.txt"):
        paquete = re.match(r"[A-Za-z0-9_.-]+", linea).group(0)
        version = next((v for k, v in congeladas.items() if k.lower().replace("_", "-") == paquete.lower().replace("_", "-")), "")
        local.append((paquete, linea[len(paquete):], version, "requirements-local.txt y .lock.txt"))
    colab_md = RAIZ / "docs" / "registro_entorno_colab.md"
    colab = [(f[0], f[1], f[2]) for f in tabla_markdown(colab_md, "Dato")]
    colab += [(f[0], f"primera corrida: {f[1]}; segunda: {f[2]}", "tabla de corridas")
              for f in tabla_markdown(colab_md, "Aspecto") if f[0] in ("Python", "transformers")]
    return (pd.DataFrame(local, columns=["componente", "rango_declarado", "version", "fuente"]),
            pd.DataFrame(colab, columns=["componente", "valor", "fuente"]))


def anexo_d():
    """Código y repositorio: inventario por etapa, orden, versión citable y entorno."""
    etiqueta, cambios = version_citable()
    local, colab = requisitos_entorno()
    escribir("anexo_D_codigo_repositorio", *TITULOS["D"], [
        ("D.1 Inventario de scripts por etapa y orden de ejecución",
         "Paso y orden: tabla \"Orden de ejecución\" de `docs/guia_operativa_scripts.md`; "
         "etapa y fase de CRISP-DM declaradas en el script 18; función, entradas y salidas, "
         "del docstring de cada script. Los scripts de `colab/` se ejecutan en el paso 13.",
         inventario_scripts(), "inventario"),
        ("D.2 Versión citable",
         "Etiqueta anotada que congela el código y los anexos regenerados. Este anexo se "
         "actualizó para citarla en un commit posterior a la etiqueta (un archivo no puede "
         "contener el identificador del commit que lo incluye); D.3 lista los archivos de "
         "código que cambiaron desde la etiqueta. Etiquetas anteriores, sin modificar: "
         "v1.0-auditoria-2026-10 y v1.1-auditoria-2026-10.", etiqueta, "version_citable"),
        ("D.3 Cambios en el código posteriores a la versión citable", "", cambios, "cambios_posteriores"),
        ("D.4 Requisitos del entorno local", "Python y MySQL de la última verificación de "
         "`00c_verificar_entorno.py`; rangos de `requirements-local.txt` y versiones de "
         "`requirements-local.lock.txt` (registro oficial).", local, "entorno_local"),
        ("D.5 Entorno de Colab (GPU)", "Tomado de `docs/registro_entorno_colab.md`; no hay archivo "
         "de requisitos de Colab.", colab, "entorno_colab"),
    ])


# --- Anexo E ---

# Configuración (nombre del bootstrap) → carpeta de graficos_input.
CONFIGURACIONES = [("baseline", "baseline"), ("beto_sin_finetuning", "beto_sin_finetuning"),
                   ("beto", "beto"), ("bertin_roberta", "roberta_es")]
CLASES = ["muy_positivo", "positivo", "levemente_positivo", "neutral", "negativo"]


def metricas_por_clase():
    """Precisión, cobertura y F1 por clase desde las matrices de confusión registradas.

    Las matrices tienen la etiqueta real en filas y la predicha en columnas
    (sklearn.metrics.confusion_matrix). Se verifica que el F1-macro recalculado coincida
    con el registrado por cada modelo.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Métricas por clase y verificación.
    """
    gi = OUT / "graficos_input"
    filas, control = [], []
    for config, carpeta in CONFIGURACIONES:
        for cond in ("A", "B"):
            m = pd.read_csv(gi / carpeta / f"matriz_confusion_{cond}.csv", index_col=0).loc[CLASES, CLASES].values
            tp = np.diag(m)
            precision = np.divide(tp, m.sum(axis=0), out=np.zeros(5), where=m.sum(axis=0) > 0)
            cobertura = np.divide(tp, m.sum(axis=1), out=np.zeros(5), where=m.sum(axis=1) > 0)
            f1 = np.divide(2 * precision * cobertura, precision + cobertura, out=np.zeros(5),
                           where=(precision + cobertura) > 0)
            for k, clase in enumerate(CLASES):
                filas.append({"configuracion": config, "condicion": cond, "clase": clase,
                              "precision": round(precision[k], 4), "cobertura": round(cobertura[k], 4),
                              "f1": round(f1[k], 4), "soporte": int(m[k].sum())})
            if carpeta == "baseline":
                registrado = pd.read_csv(gi / carpeta / "resultados_baseline.csv")[f"f1_macro_{cond}"].iloc[0]
            else:
                registrado = pd.read_csv(gi / carpeta / f"resultado_{cond}.csv")["f1_macro"].iloc[0]
            control.append({"configuracion": config, "condicion": cond, "n": int(m.sum()),
                            "f1_macro_recalculado": round(f1.mean(), 6), "f1_macro_registrado": round(registrado, 6),
                            "coincide": bool(abs(f1.mean() - registrado) < 1e-9)})
    return pd.DataFrame(filas), pd.DataFrame(control)


def anexo_e():
    """Resultados complementarios: métricas por clase, bootstrap, multisemilla y sensibilidad."""
    leer = lambda r: pd.read_csv(OUT / r)
    redondear = lambda df: df.round(4)
    por_clase, control = metricas_por_clase()
    if not control["coincide"].all():
        raise RuntimeError("El F1-macro recalculado no coincide con el registrado:\n" + control.to_string())
    secciones = [
        ("E.1 Precisión, cobertura y F1 por clase (8 combinaciones de modelo y condición)",
         "Calculadas desde las matrices de confusión registradas "
         "(`outputs/graficos_input/<modelo>/matriz_confusion_{A,B}.csv`, n = 177). Cobertura = "
         "recall. BERTIN = `roberta_es`.", por_clase, "metricas_por_clase"),
        ("E.2 Verificación: F1-macro recalculado frente al registrado", "", control, "verificacion_f1_macro"),
        ("E.3 Bootstrap pareado, análisis principal (n = 177)", "Salida de `14_bootstrap_pareado.py`.",
         redondear(leer("bootstrap_resultados.csv")), "bootstrap_principal"),
        ("E.4 Corrección de Holm sobre las 4 configuraciones", "Salida de `14b_bootstrap_multisemilla.py`.",
         redondear(leer("multisemilla/holm_configuraciones_principales.csv")), "holm_principal"),
        ("E.5 Multisemilla: bootstrap pareado por semilla", "Los p por semilla son descriptivos.",
         redondear(leer("multisemilla/bootstrap_por_semilla.csv")), "multisemilla_por_semilla"),
        ("E.6 Multisemilla: agregado por modelo", "Incluye F1-macro A y B por semilla en E.5 "
         "(equivalente a resumen_multisemilla.csv de Colab).",
         redondear(leer("multisemilla/agregado_por_modelo.csv")), "multisemilla_agregado"),
        ("E.7 Multisemilla: Log Loss y PR-AUC (descriptivo)", "",
         redondear(leer("multisemilla/descriptivo_logloss_prauc.csv")), "multisemilla_descriptivo"),
        ("E.8 Flips por clase de defecto (sección d del script 15)", "Texto idéntico determinado por "
         "comparación directa (versión corregida).", leer("flips_por_clase_defecto.csv"), "flips_por_clase_defecto"),
        ("E.9 Análisis de sensibilidad a la fuga: bootstrap pareado (n = 157)",
         "**Análisis de sensibilidad**, no principal: excluye los 20 segmentos evaluados expuestos "
         "a la fuga (plan del 2026-10-09).", redondear(leer("bootstrap_resultados_sin_fuga.csv")), "sensibilidad_bootstrap"),
        ("E.10 Análisis de sensibilidad a la fuga: Holm", "**Análisis de sensibilidad.**",
         redondear(leer("multisemilla_sin_fuga/holm_configuraciones_principales.csv")), "sensibilidad_holm"),
        ("E.11 Análisis de sensibilidad a la fuga: multisemilla por semilla", "**Análisis de sensibilidad.**",
         redondear(leer("multisemilla_sin_fuga/bootstrap_por_semilla.csv")), "sensibilidad_multisemilla_por_semilla"),
        ("E.12 Análisis de sensibilidad a la fuga: multisemilla agregado", "**Análisis de sensibilidad.**",
         redondear(leer("multisemilla_sin_fuga/agregado_por_modelo.csv")), "sensibilidad_multisemilla_agregado"),
    ]
    escribir("anexo_E_resultados", *TITULOS["E"], secciones)


def main():
    """Borra los anexos anteriores y genera los cinco anexos."""
    SALIDA.mkdir(parents=True, exist_ok=True)
    for viejo in list(SALIDA.glob("anexo_*.md")) + list(SALIDA.glob("anexo_*.csv")):
        viejo.unlink()
    engine = get_engine()
    anexo_a(engine)
    anexo_b(engine)
    anexo_c(engine)
    anexo_d()
    anexo_e()
    print(f"[OK] Anexos en {SALIDA}")


if __name__ == "__main__":
    main()
