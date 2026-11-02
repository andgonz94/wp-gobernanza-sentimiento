"""Deduplica las transcripciones crudas y las enriquece con metadatos de sesión.

Primer paso del pipeline de la condición gobernada. Infiere componente, zona,
bloque y número de sesión a partir de la ruta del archivo de audio o, como
respaldo, de la fecha de creación. Genera reportes de auditoría y,
opcionalmente, carga los registros válidos en la base de datos.

Entradas:
    CSV de transcripciones crudas (columnas id, created_at, audio_path,
    model_used, language, duration_s, text, segments).
Salidas:
    outputs/reporte_descartados.csv, outputs/corpus_deduplicado.csv y
    outputs/revision_manual_sesiones.csv; opcionalmente, tablas sesion y
    retroalimentacion.
"""

import sys, re, argparse
from pathlib import Path
from datetime import datetime, date
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_engine, get_connection

# --- CATÁLOGOS ---

MODELO_PRIORIDAD = {"tiny":0,"base":1,"small":2,"medium":3,"large":4}
CANAL_CAPTURA    = "formulario"

# Mapa fecha (MM-DD) → (bloque, numero_sesion)
FECHA_SESION_MAP = {
    "06-24": (1, 2),  "06-25": (1, 3),  "06-26": (1, 4),
    "06-27": (1, 5),  "06-28": (1, 6),  "07-19": (1, 7),
    "08-09": (1, 8),  "08-30": (1, 9),  "09-20": (1,10),
    "10-11": (1,11),  "11-01": (1,12),
    "07-01": (2, 1),  "07-02": (2, 2),  "07-03": (2, 3),
    "07-04": (2, 4),  "07-05": (2, 5),  "07-26": (2, 6),
    "08-16": (2, 7),  "09-06": (2, 8),  "09-27": (2, 9),
    "10-18": (2,10),  "11-08": (2,11),  "11-22": (2,12),
    "07-07": (3, 1),  "07-08": (3, 2),  "07-09": (3, 3),
    "07-10": (3, 4),  "07-11": (3, 5),  "07-12": (3, 6),
    "08-02": (3, 7),  "08-23": (3, 8),  "09-13": (3, 9),
    "10-04": (3,10),  "10-25": (3,11),  "11-15": (3,12),
    "12-06": (0, 13), # clausura — bloque 0 = todos
}

# --- EXTRACCIÓN DE METADATOS ---

def full_path(row) -> str:
    """Obtiene la ruta del archivo de audio asociado a un registro.

    Args:
        row: Fila de un DataFrame con información del registro.

    Returns:
        str: Ruta del archivo de audio en minúsculas.
    """
    return str(row.get("audio_path","")).lower()

def extraer_componente(path: str) -> str:
    """Clasifica el componente del programa a partir de la ruta del archivo.

    Args:
        path (str): Ruta del archivo de audio.

    Returns:
        str: Nombre del componente identificado.
    """
    if "c1" in path or "[programa_2]" in path:
        return "[PROGRAMA_2]"
    return "[PROGRAMA_1]"

def extraer_zona(path: str) -> str:
    """Clasifica la zona geográfica a partir de la ruta del archivo.

    Args:
        path (str): Ruta del archivo de audio.

    Returns:
        str: Nombre de la zona identificada.
    """
    if "rural" in path or "[LUGAR_O_NOMBRE] monta" in path:
        return "Rural"
    return "Urbano"

def extraer_fecha_mmdd(path: str):
    """Extrae una fecha codificada en la ruta del archivo, probando distintos formatos conocidos.

    Args:
        path (str): Ruta del archivo de audio.

    Returns:
        tuple or None: Tupla (año, mes-día) si se reconoce una fecha válida, o None en caso contrario.
    """
    MESES = {
        "ene":1,"jan":1,"feb":2,"mar":3,"abr":4,"apr":4,
        "may":5,"jun":6,"jul":7,"ago":8,"aug":8,
        "sep":9,"oct":10,"nov":11,"dic":12,"dec":12,
        "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,
        "junio":6,"julio":7,"agosto":8,"septiembre":9,
        "octubre":10,"noviembre":11,"diciembre":12,
    }
    p = path.lower()

    # 1. YYYY_MM_DD o YYYY-MM-DD
    m = re.search(r"(202[0-9])[_\-](\d{2})[_\-](\d{2})", p)
    if m:
        y,mo,d = int(m.group(1)),int(m.group(2)),int(m.group(3))
        if y == 2025 and mo == 6 and d == 3: mo = 7  # corrección tipográfica
        try: date(y,mo,d); return y, f"{mo:02d}-{d:02d}"
        except ValueError: pass

    # 2. YYYYMMDD
    m = re.search(r"(202[0-9])(\d{2})(\d{2})", p)
    if m:
        y,mo,d = int(m.group(1)),int(m.group(2)),int(m.group(3))
        try: date(y,mo,d); return y, f"{mo:02d}-{d:02d}"
        except ValueError: pass

    # 3. DDMMYYYY
    m = re.search(r"(\d{2})(\d{2})(202[0-9])", p)
    if m:
        d,mo,y = int(m.group(1)),int(m.group(2)),int(m.group(3))
        try: date(y,mo,d); return y, f"{mo:02d}-{d:02d}"
        except ValueError: pass

    # 4. NombreMesDD YYYY → ej. Julio032025
    m = re.search(r"([a-záéíóúü]+)\s*(\d{1,2})\s*(202[0-9])", p)
    if m:
        nombre = m.group(1).rstrip("_- ")
        mes = MESES.get(nombre) or MESES.get(nombre[:3])
        if mes:
            d = int(m.group(2)); y = int(m.group(3))
            try: date(y,mes,d); return y, f"{mes:02d}-{d:02d}"
            except ValueError: pass

    # 5. Mes DD YYYY con separadores → ej. Dic 6 2025
    m = re.search(r"([a-z]{3})\w*[\s\-_]+(\d{1,2})[\s\-_]+(202[0-9])", p)
    if m:
        mes = MESES.get(m.group(1)[:3])
        if mes:
            d = int(m.group(2)); y = int(m.group(3))
            try: date(y,mes,d); return y, f"{mes:02d}-{d:02d}"
            except ValueError: pass

    return None

def asignar_sesion_por_fecha(mmdd: str):
    """Busca la sesión correspondiente a una fecha en el catálogo de sesiones.

    Args:
        mmdd (str): Fecha en formato mes-día.

    Returns:
        tuple or None: Tupla (bloque, número de sesión) si existe, o None.
    """
    return FECHA_SESION_MAP.get(mmdd)

def asignar_sesion_por_created_at(created_at_str: str):
    """Infiere la sesión a partir de la fecha de creación del registro, como respaldo cuando la ruta no la revela.

    Args:
        created_at_str (str): Fecha y hora de creación del registro.

    Returns:
        tuple: Tupla (bloque, número de sesión, método de asignación).
    """
    try:
        dt = pd.to_datetime(created_at_str)
        mmdd = f"{dt.month:02d}-{dt.day:02d}"
        result = FECHA_SESION_MAP.get(mmdd)
        if result:
            return result[0], result[1], "inferida"
    except Exception:
        pass
    return None, None, "sin_sesion"

def construir_nombre_sesion(componente, zona, bloque, num_sesion, metodo) -> str:
    """Construye un nombre identificador único para una sesión.

    Args:
        componente (str): Componente del programa.
        zona (str): Zona geográfica.
        bloque: Bloque al que pertenece la sesión.
        num_sesion: Número de la sesión.
        metodo (str): Método usado para asignar la sesión.

    Returns:
        str: Nombre identificador de la sesión.
    """
    if num_sesion == 13:
        base = "clausura"
    elif num_sesion:
        base = f"sesion_{num_sesion:02d}"
    else:
        base = "sesion_desconocida"

    bloque_str = f"bloque_{bloque}" if bloque and bloque > 0 else "bloque_general"
    metodo_str = f"[{metodo}]" if metodo == "inferida" else ""
    return f"{componente}_{zona}_{bloque_str}_{base}{metodo_str}"

# --- DEDUPLICACIÓN ---

def deduplicar(df: pd.DataFrame):
    """Elimina registros duplicados del mismo archivo de audio, conservando el de mejor calidad.

    Args:
        df (pandas.DataFrame): DataFrame con los registros originales.

    Returns:
        tuple: DataFrame de registros conservados y DataFrame de registros descartados.
    """
    df = df.copy()
    df["audio_filename"]   = df["audio_path"].apply(lambda p: Path(str(p)).name.strip())
    df["modelo_prioridad"] = df["model_used"].map(
        lambda m: MODELO_PRIORIDAD.get(str(m).lower(), -1)
    )
    df["created_at"] = pd.to_datetime(df["created_at"])
    df_s    = df.sort_values(
        ["audio_filename","modelo_prioridad","created_at"],
        ascending=[True,False,False]
    )
    limpio  = df_s.drop_duplicates(subset="audio_filename", keep="first").copy()
    desc    = df_s[~df_s.index.isin(set(limpio.index))].copy()
    desc["motivo_descarte"] = "duplicado_mismo_audio"
    return limpio.reset_index(drop=True), desc.reset_index(drop=True)

# --- ENRIQUECIMIENTO ---

def enriquecer(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega metadatos de sesión (componente, zona, bloque, número y fecha) a cada registro.

    Args:
        df (pandas.DataFrame): DataFrame con los registros a enriquecer.

    Returns:
        pandas.DataFrame: DataFrame con las columnas de metadatos agregadas.
    """
    df = df.copy()
    rows = []
    for _, row in df.iterrows():
        path = full_path(row)

        componente = extraer_componente(path)
        zona       = extraer_zona(path)

        # Intentar fecha desde path
        fecha_result = extraer_fecha_mmdd(path)
        if fecha_result:
            anio, mmdd = fecha_result
            sesion_result = asignar_sesion_por_fecha(mmdd)
            if sesion_result:
                bloque, num_sesion = sesion_result
                metodo = "directa"
                fecha_real = date(anio, int(mmdd[:2]), int(mmdd[3:]))
            else:
                bloque, num_sesion, metodo = None, None, "fecha_sin_mapa"
                fecha_real = date(anio, int(mmdd[:2]), int(mmdd[3:]))
        else:
            # Fallback: created_at
            bloque, num_sesion, metodo = asignar_sesion_por_created_at(row["created_at"])
            fecha_real = None

        nombre = construir_nombre_sesion(componente, zona, bloque, num_sesion, metodo)

        rows.append({
            **row.to_dict(),
            "componente"   : componente,
            "zona"         : zona,
            "bloque"       : bloque,
            "num_sesion"   : num_sesion,
            "metodo_sesion": metodo,
            "fecha_real"   : fecha_real,
            "nombre_sesion": nombre,
        })
    return pd.DataFrame(rows)

# --- REPORTE ---

def imprimir_reporte(orig, limpio, desc):
    """Imprime un resumen de la deduplicación y el enriquecimiento de metadatos.

    Args:
        orig (pandas.DataFrame): DataFrame con los registros originales.
        limpio (pandas.DataFrame): DataFrame con los registros conservados y enriquecidos.
        desc (pandas.DataFrame): DataFrame con los registros descartados.

    Returns:
        None
    """
    sep = "─"*60
    print(f"\n{sep}")
    print("  REPORTE DE DEDUPLICACIÓN Y ENRIQUECIMIENTO — Paso 1")
    print(sep)
    print(f"  Registros CSV original          : {len(orig):>6}")
    print(f"  Registros conservados (únicos)  : {len(limpio):>6}")
    print(f"  Registros descartados           : {len(desc):>6}")
    print(f"  Tasa de duplicación             : {len(desc)/len(orig)*100:>5.1f} %")

    print(f"\n  Distribución por Componente:")
    for v, n in limpio["componente"].value_counts().items():
        print(f"    {v:<30} {n:>4}")

    print(f"\n  Distribución por Zona:")
    for v, n in limpio["zona"].value_counts().items():
        print(f"    {v:<30} {n:>4}")

    print(f"\n  Distribución por Método de asignación de sesión:")
    for v, n in limpio["metodo_sesion"].value_counts().items():
        print(f"    {v:<30} {n:>4}")

    print(f"\n  Distribución por Sesión (número):")
    sesiones = limpio["num_sesion"].value_counts().sort_index()
    for v, n in sesiones.items():
        label = "clausura" if v == 13 else f"Sesión {v}"
        print(f"    {label:<30} {n:>4}")
    sin = limpio["num_sesion"].isna().sum()
    if sin:
        print(f"    {'Sin sesión asignada':<30} {sin:>4}  ← requieren revisión manual")

    print(f"\n  Registros que requieren revisión manual:")
    revision = limpio[
        (limpio["metodo_sesion"].isin(["inferida","sin_sesion","fecha_sin_mapa"]))
    ][["audio_filename","componente","zona","metodo_sesion","num_sesion"]]
    print(f"    Total: {len(revision)}")
    print(sep)

# --- CARGA A MYSQL ---

def cargar_a_mysql(df: pd.DataFrame):
    """Carga los registros enriquecidos a la base de datos, registrando la ejecución del pipeline.

    Args:
        df (pandas.DataFrame): DataFrame con los registros a cargar.

    Returns:
        None
    """
    conn = get_connection()
    inicio = datetime.now()
    insertados = rechazados = 0
    id_ejecucion = None

    try:
        with conn.cursor() as cur:

            # Abrir ejecucion_pipeline
            cur.execute(
                "INSERT INTO ejecucion_pipeline (inicio,estado,registros_procesados,registros_rechazados) VALUES (%s,'en_proceso',0,0)",
                (inicio,)
            )
            conn.commit()
            id_ejecucion = cur.lastrowid
            print(f"\n  Ejecución iniciada → id_ejecucion = {id_ejecucion}")

            # Insertar sesiones únicas
            sesion_id_map = {}
            sesiones_unicas = df[["nombre_sesion","fecha_real","componente","zona","bloque","num_sesion"]]\
                .drop_duplicates("nombre_sesion")

            for _, row in sesiones_unicas.iterrows():
                cur.execute("SELECT id_sesion FROM sesion WHERE nombre_sesion=%s",(row["nombre_sesion"],))
                ex = cur.fetchone()
                if ex:
                    sesion_id_map[row["nombre_sesion"]] = ex["id_sesion"]
                else:
                    fecha_s = row["fecha_real"] if pd.notna(row["fecha_real"]) and row["fecha_real"] else None
                    cur.execute(
                        "INSERT INTO sesion (nombre_sesion,fecha_sesion,docente,materia) VALUES (%s,%s,%s,%s)",
                        (row["nombre_sesion"], fecha_s, None, None)
                    )
                    sesion_id_map[row["nombre_sesion"]] = cur.lastrowid
            conn.commit()
            print(f"  Sesiones registradas: {len(sesion_id_map)}")

            # Insertar registros
            for _, row in df.iterrows():
                texto = str(row["text"]).strip() if pd.notna(row["text"]) else ""

                if not texto or len(texto) < 5:
                    rechazados += 1
                    cur.execute(
                        "INSERT INTO detalle_error (id_ejecucion,codigo_regla,descripcion,valor_recibido) VALUES (%s,%s,%s,%s)",
                        (id_ejecucion,"RQ-01","Texto vacío o insuficiente",texto[:200])
                    )
                    continue

                fecha_reg = row["fecha_real"] if pd.notna(row.get("fecha_real")) and row.get("fecha_real") else None
                duracion  = int(row["duration_s"]) if pd.notna(row.get("duration_s")) else None

                cur.execute("""
                    INSERT INTO retroalimentacion
                        (texto,id_sesion,fecha_registro,canal_captura,
                         ingesta_timestamp,id_ejecucion,duracion_segundos)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (
                    texto,
                    sesion_id_map.get(row["nombre_sesion"]),
                    fecha_reg,
                    CANAL_CAPTURA,
                    datetime.now(),
                    id_ejecucion,
                    duracion,
                ))
                insertados += 1

            conn.commit()

            # Cerrar ejecucion_pipeline
            cur.execute(
                "UPDATE ejecucion_pipeline SET fin=%s,estado='completado',registros_procesados=%s,registros_rechazados=%s WHERE id_ejecucion=%s",
                (datetime.now(), len(df), rechazados, id_ejecucion)
            )
            conn.commit()

        print(f"\n  Carga completada:")
        print(f"      Registros insertados : {insertados}")
        print(f"      Registros rechazados : {rechazados}")
        print(f"      id_ejecucion         : {id_ejecucion}")

    except Exception as e:
        conn.rollback()
        if id_ejecucion:
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE ejecucion_pipeline SET estado='fallido' WHERE id_ejecucion=%s",(id_ejecucion,))
                conn.commit()
            except: pass
        print(f"\n  [ERROR] {e}")
        raise
    finally:
        conn.close()

# --- MAIN ---

def main():
    """Ejecuta el flujo de deduplicación, enriquecimiento y carga a partir de argumentos de línea de comandos.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv",  required=True)
    parser.add_argument("--modo", choices=["preview","cargar"], default="preview")
    args = parser.parse_args()

    p = Path(args.csv)
    if not p.exists():
        print(f"No encontrado: {p}"); sys.exit(1)

    print(f"\nLeyendo: {p.name}")
    orig = pd.read_csv(p)
    print(f"Registros: {len(orig)}")

    print("Deduplicando...")
    limpio, desc = deduplicar(orig)

    print("Enriqueciendo metadatos...")
    limpio = enriquecer(limpio)

    imprimir_reporte(orig, limpio, desc)

    # Guardar siempre los CSVs de auditoría
    out = Path("outputs")
    out.mkdir(exist_ok=True)

    desc[["id","audio_filename","model_used","created_at","motivo_descarte"]]\
        .to_csv(out/"reporte_descartados.csv", index=False)

    limpio.to_csv(out/"corpus_deduplicado.csv", index=False)

    # CSV especial para revisión manual de sesiones inferidas
    revision = limpio[limpio["metodo_sesion"].isin(["inferida","sin_sesion","fecha_sin_mapa"])]\
        [["id","audio_filename","audio_path","componente","zona",
          "bloque","num_sesion","metodo_sesion","fecha_real"]]
    if len(revision) > 0:
        revision.to_csv(out/"revision_manual_sesiones.csv", index=False)
        print(f"\n  {len(revision)} registros requieren revisión manual.")
        print(f"      Archivo generado: outputs/revision_manual_sesiones.csv")
        print(f"      Abre ese CSV, revisa la columna num_sesion y corrige donde sea necesario.")

    print(f"\n  Archivos guardados en outputs/")

    if args.modo == "cargar":
        print("\nCargando en MySQL...")
        cargar_a_mysql(limpio)
    else:
        print("\nModo PREVIEW — sin cambios en BD.")
        print("Ejecuta con --modo cargar cuando estés lista.")

if __name__ == "__main__":
    main()