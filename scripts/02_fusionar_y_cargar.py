"""Fusiona el corpus deduplicado con las correcciones manuales de sesión.

Segundo paso del pipeline de la condición gobernada. Recalcula los metadatos
derivados con los valores corregidos y, opcionalmente, carga los registros
resultantes en la base de datos.

Entradas:
    outputs/corpus_deduplicado.csv y outputs/revision_manual_sesiones.csv
    (con num_sesion completado en la revisión manual).
Salidas:
    outputs/corpus_final.csv; opcionalmente, tablas sesion y retroalimentacion.
"""

import sys, re, argparse
from pathlib import Path
from datetime import datetime, date
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_connection

CANAL_CAPTURA = "formulario"

# Mapa (bloque, num_sesion) → fecha real del calendario
SESION_FECHA_MAP = {
    (1, 2): date(2025, 6, 24),  (1, 3): date(2025, 6, 25),
    (1, 4): date(2025, 6, 26),  (1, 5): date(2025, 6, 27),
    (1, 6): date(2025, 6, 28),  (1, 7): date(2025, 7, 19),
    (1, 8): date(2025, 8,  9),  (1, 9): date(2025, 8, 30),
    (1,10): date(2025, 9, 20),  (1,11): date(2025,10, 11),
    (1,12): date(2025,11,  1),
    (2, 1): date(2025, 7,  1),  (2, 2): date(2025, 7,  2),
    (2, 3): date(2025, 7,  3),  (2, 4): date(2025, 7,  4),
    (2, 5): date(2025, 7,  5),  (2, 6): date(2025, 7, 26),
    (2, 7): date(2025, 8, 16),  (2, 8): date(2025, 9,  6),
    (2, 9): date(2025, 9, 27),  (2,10): date(2025,10, 18),
    (2,11): date(2025,11,  8),  (2,12): date(2025,11, 22),
    (3, 1): date(2025, 7,  7),  (3, 2): date(2025, 7,  8),
    (3, 3): date(2025, 7,  9),  (3, 4): date(2025, 7, 10),
    (3, 5): date(2025, 7, 11),  (3, 6): date(2025, 7, 12),
    (3, 7): date(2025, 8,  2),  (3, 8): date(2025, 8, 23),
    (3, 9): date(2025, 9, 13),  (3,10): date(2025,10,  4),
    (3,11): date(2025,10, 25),  (3,12): date(2025,11, 15),
    (0,13): date(2025,12,  6),  # clausura
}

def recalcular_nombre_sesion(row) -> str:
    """Reconstruye el nombre identificador de una sesión con sus valores actuales.

    Args:
        row: Fila de un DataFrame con los metadatos de la sesión.

    Returns:
        str: Nombre identificador de la sesión.
    """
    componente = row.get("componente", "[PROGRAMA]")
    zona       = row.get("zona", "Urbano")
    bloque     = row.get("bloque")
    num        = row.get("num_sesion")
    metodo     = row.get("metodo_sesion", "")

    if pd.isna(num) or num is None:
        base = "sesion_desconocida"
    elif int(num) == 13:
        base = "clausura"
    else:
        base = f"sesion_{int(num):02d}"

    if pd.isna(bloque) or bloque is None or int(bloque) == 0:
        bloque_str = "bloque_general"
    else:
        bloque_str = f"bloque_{int(bloque)}"

    sufijo = "[manual]" if metodo == "manual" else ""
    return f"{componente}_{zona}_{bloque_str}_{base}{sufijo}"

def recalcular_fecha(row):
    """Determina la fecha real de una sesión a partir de su bloque y número, con respaldo a la fecha original.

    Args:
        row: Fila de un DataFrame con los metadatos de la sesión.

    Returns:
        datetime.date or None: Fecha de la sesión si se pudo determinar, o None.
    """
    try:
        bloque = int(row["bloque"]) if pd.notna(row.get("bloque")) else None
        num    = int(row["num_sesion"]) if pd.notna(row.get("num_sesion")) else None
        if bloque is not None and num is not None:
            return SESION_FECHA_MAP.get((bloque, num))
    except (ValueError, TypeError):
        pass
    # Intentar recuperar fecha_real original si existe
    if pd.notna(row.get("fecha_real")) and row.get("fecha_real"):
        try:
            return pd.to_datetime(row["fecha_real"]).date()
        except Exception:
            pass
    return None

def fusionar(corpus_path: Path, revision_path: Path) -> pd.DataFrame:
    """Combina el corpus deduplicado con las correcciones manuales de sesión.

    Args:
        corpus_path (pathlib.Path): Ruta al CSV del corpus deduplicado.
        revision_path (pathlib.Path): Ruta al CSV de correcciones manuales.

    Returns:
        pandas.DataFrame: Corpus fusionado con los metadatos recalculados.
    """
    df = pd.read_csv(corpus_path)
    rev = pd.read_csv(revision_path)

    # Normalizar tipos en revisión
    rev["num_sesion"] = pd.to_numeric(rev["num_sesion"], errors="coerce")
    rev["bloque"]     = pd.to_numeric(rev["bloque"],     errors="coerce")

    # Solo tomar registros donde num_sesion fue efectivamente corregido
    rev_validos = rev[rev["num_sesion"].notna()][["audio_filename","num_sesion","bloque"]].copy()
    rev_validos["metodo_sesion"] = "manual"

    print(f"  Correcciones manuales con sesión asignada : {len(rev_validos)}")
    sin_asignar = len(rev) - len(rev_validos)
    print(f"  Correcciones manuales sin sesión (vacías) : {sin_asignar}")

    # Fusionar: las correcciones manuales sobrescriben
    df = df.merge(
        rev_validos,
        on="audio_filename",
        how="left",
        suffixes=("", "_manual")
    )

    # Aplicar correcciones donde existen
    mask = df["num_sesion_manual"].notna()
    df.loc[mask, "num_sesion"]    = df.loc[mask, "num_sesion_manual"]
    df.loc[mask, "bloque"]        = df.loc[mask, "bloque_manual"]
    df.loc[mask, "metodo_sesion"] = df.loc[mask, "metodo_sesion_manual"]
    df.drop(columns=["num_sesion_manual","bloque_manual","metodo_sesion_manual"],
            inplace=True, errors="ignore")

    # Recalcular nombre_sesion y fecha_real para todos
    df["nombre_sesion"] = df.apply(recalcular_nombre_sesion, axis=1)
    df["fecha_real"]    = df.apply(recalcular_fecha, axis=1)

    return df

def imprimir_reporte_final(df):
    """Imprime un resumen del corpus fusionado antes de cargarlo a la base de datos.

    Args:
        df (pandas.DataFrame): Corpus fusionado.

    Returns:
        None
    """
    sep = "─"*60
    print(f"\n{sep}")
    print("  REPORTE FINAL ANTES DE CARGA — Paso 2")
    print(sep)
    print(f"  Total registros a cargar        : {len(df):>6}")

    print(f"\n  Método de asignación de sesión:")
    for v,n in df["metodo_sesion"].value_counts().items():
        print(f"    {str(v):<35} {n:>4}")

    print(f"\n  Distribución final por Sesión:")
    for v,n in df["num_sesion"].value_counts().sort_index().items():
        label = "clausura" if v == 13 else f"Sesión {int(v)}"
        print(f"    {label:<35} {n:>4}")
    sin = df["num_sesion"].isna().sum()
    if sin:
        print(f"    {'Sin sesión (se cargan como nulo)':<35} {sin:>4}")

    print(f"\n  Por Componente:")
    for v,n in df["componente"].value_counts().items():
        print(f"    {str(v):<35} {n:>4}")

    print(f"\n  Por Zona:")
    for v,n in df["zona"].value_counts().items():
        print(f"    {str(v):<35} {n:>4}")

    print(sep)

def cargar_a_mysql(df: pd.DataFrame):
    """Carga el corpus fusionado a la base de datos, registrando la ejecución del pipeline.

    Args:
        df (pandas.DataFrame): Corpus fusionado a cargar.

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
            for _, row in df[["nombre_sesion","fecha_real"]].drop_duplicates("nombre_sesion").iterrows():
                cur.execute("SELECT id_sesion FROM sesion WHERE nombre_sesion=%s",(row["nombre_sesion"],))
                ex = cur.fetchone()
                if ex:
                    sesion_id_map[row["nombre_sesion"]] = ex["id_sesion"]
                else:
                    fecha_s = None
                    if pd.notna(row.get("fecha_real")) and row.get("fecha_real"):
                        try:
                            fecha_s = pd.to_datetime(row["fecha_real"]).date()
                        except Exception:
                            pass
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

                fecha_reg = None
                if pd.notna(row.get("fecha_real")) and row.get("fecha_real"):
                    try:
                        fecha_reg = pd.to_datetime(row["fecha_real"]).date()
                    except Exception:
                        pass

                duracion = int(row["duration_s"]) if pd.notna(row.get("duration_s")) else None

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
                    cur.execute(
                        "UPDATE ejecucion_pipeline SET estado='fallido' WHERE id_ejecucion=%s",
                        (id_ejecucion,)
                    )
                conn.commit()
            except Exception:
                pass
        print(f"\n  [ERROR] {e}")
        raise
    finally:
        conn.close()

def main():
    """Ejecuta el flujo de fusión, reporte y carga a partir de argumentos de línea de comandos.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["preview","cargar"], default="preview")
    args = parser.parse_args()

    corpus_path   = Path("outputs/corpus_deduplicado.csv")
    revision_path = Path("outputs/revision_manual_sesiones.csv")

    for p in [corpus_path, revision_path]:
        if not p.exists():
            print(f"No encontrado: {p}")
            sys.exit(1)

    print("\nFusionando corpus con correcciones manuales...")
    df = fusionar(corpus_path, revision_path)

    imprimir_reporte_final(df)

    # Guardar corpus final para auditoría
    df.to_csv("outputs/corpus_final.csv", index=False)
    print(f"\n  Corpus final guardado en: outputs/corpus_final.csv")

    if args.modo == "cargar":
        print("\nCargando en MySQL...")
        cargar_a_mysql(df)
    else:
        print("\nModo PREVIEW — sin cambios en BD.")
        print("Ejecuta con --modo cargar cuando estés lista.")

if __name__ == "__main__":
    main()