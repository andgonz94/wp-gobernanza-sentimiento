"""Procesa la condición cruda a través del pipeline de reglas de calidad.

Simula lo que ocurriría al aplicar el marco de gobernanza sobre los datos
crudos: valida cada registro contra las reglas de calidad (RQ-01 a RQ-09),
registra cada violación, carga solo los registros válidos y genera un reporte
comparativo contra la condición gobernada.

Entradas:
    outputs/condicion_A.csv y outputs/auditoria_inyeccion.csv.
Salidas:
    outputs/reporte_comparativo_condiciones.csv; registros válidos en
    retroalimentacion y violaciones en detalle_error.
"""

import sys, re, argparse
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_engine, get_connection

# --- CATÁLOGOS Y CONSTANTES ---

CANAL_CATALOGO = {"formulario", "papel", "app", "email", "desconocido"}

TEXTOS_NO_INFORMATIVOS = {
    "ok", "bien", ".", "bueno", "nada", "no sé", "regular",
    "así", "sí", "no", "todo bien", "bien gracias",
    "nada que decir", "nose", "no se"
}

# Mapeo de tipo de error de auditoría → codigo_regla
AUDITORIA_REGLA_MAP = {
    "nulo_id_sesion"      : "RQ-02",
    "nulo_texto"          : "RQ-01",
    "nulo_fecha"          : "RQ-03",
    "nulo_canal"          : "RQ-04",
    "duplicado_exacto"    : "RQ-07",
    "cuasi_duplicado"     : "RQ-07",
    "formato_fecha"       : "RQ-05",
    "canal_fuera_catalogo": "RQ-06",
    "texto_no_informativo": "RQ-08",
}

DESCRIPCION_REGLA = {
    "RQ-01": "Texto nulo o vacío",
    "RQ-02": "id_sesion nulo — registro no contextualizable",
    "RQ-03": "fecha_registro nula",
    "RQ-04": "canal_captura nulo",
    "RQ-05": "fecha_registro con formato inválido (no ISO 8601)",
    "RQ-06": "canal_captura fuera del catálogo definido",
    "RQ-07": "Duplicado exacto o cuasi-duplicado detectado",
    "RQ-08": "Texto no informativo sin valor analítico",
    "RQ-09": "Texto con longitud insuficiente (< 20 caracteres)",
}

# --- REGLAS DE CALIDAD ---

def validar_registro(row: dict, textos_vistos: set) -> list:
    """Aplica las reglas de calidad sobre un registro.

    Args:
        row (dict): Datos del registro a validar.
        textos_vistos (set): Conjunto de textos ya vistos, para detectar duplicados.

    Returns:
        list: Lista de tuplas (código de regla, valor recibido) por cada violación encontrada.
    """
    errores = []
    texto = str(row.get("text","")).strip() if pd.notna(row.get("text")) else ""

    # RQ-01: texto nulo
    if not texto:
        errores.append(("RQ-01", "NULL"))
        return errores  # sin texto no tiene sentido seguir

    # RQ-08: texto no informativo
    if texto.lower().strip() in TEXTOS_NO_INFORMATIVOS:
        errores.append(("RQ-08", texto[:100]))

    # RQ-09: texto muy corto
    if len(texto) < 20:
        errores.append(("RQ-09", texto[:100]))

    # RQ-02: id_sesion nulo
    id_sesion = row.get("num_sesion")
    if pd.isna(id_sesion) or id_sesion is None:
        errores.append(("RQ-02", "NULL"))

    # RQ-03: fecha nula
    fecha = row.get("fecha_real")
    if pd.isna(fecha) or fecha is None:
        errores.append(("RQ-03", "NULL"))
    else:
        # RQ-05: formato inválido
        try:
            pd.to_datetime(str(fecha), format="%Y-%m-%d")
        except Exception:
            errores.append(("RQ-05", str(fecha)[:50]))

    # RQ-04: canal nulo
    canal = row.get("canal_captura")
    if pd.isna(canal) or canal is None:
        errores.append(("RQ-04", "NULL"))
    else:
        # RQ-06: canal fuera de catálogo
        if str(canal).lower().strip() not in CANAL_CATALOGO:
            errores.append(("RQ-06", str(canal)[:50]))

    # RQ-07: duplicado
    texto_key = texto[:200].lower().strip()
    if texto_key in textos_vistos:
        errores.append(("RQ-07", texto[:100]))
    else:
        textos_vistos.add(texto_key)

    return errores

# --- REPORTE ---

def imprimir_reporte(n_total, n_validos, n_rechazados,
                     errores_por_regla: dict,
                     metricas_b: dict = None):
    """Imprime un resumen del procesamiento, con errores por regla y comparación opcional.

    Args:
        n_total (int): Número total de registros procesados.
        n_validos (int): Número de registros válidos.
        n_rechazados (int): Número de registros rechazados.
        errores_por_regla (dict): Conteo de errores agrupados por código de regla.
        metricas_b (dict, optional): Métricas de la condición gobernada, para comparar.

    Returns:
        None
    """
    sep = "─"*65
    print(f"\n{sep}")
    print("  REPORTE — Procesamiento Condición A")
    print(sep)
    print(f"  Registros procesados          : {n_total:>6}")
    print(f"  Registros válidos (pasaron)   : {n_validos:>6}  "
          f"({n_validos/n_total*100:.1f}%)")
    print(f"  Registros rechazados          : {n_rechazados:>6}  "
          f"({n_rechazados/n_total*100:.1f}%)")

    print(f"\n  Errores detectados por regla:")
    total_errores = sum(errores_por_regla.values())
    for regla, n in sorted(errores_por_regla.items(), key=lambda x: -x[1]):
        desc = DESCRIPCION_REGLA.get(regla, regla)
        print(f"    {regla} — {desc:<45} {n:>4}")
    print(f"    {'TOTAL':<50} {total_errores:>4}")

    if metricas_b:
        print(f"\n  COMPARACIÓN Condición B vs Condición A:")
        print(f"    {'Métrica':<30} {'Cond. B':>12} {'Cond. A':>12}")
        print(f"    {'':─<30} {'':─>12} {'':─>12}")
        print(f"    {'Registros procesados':<30} "
              f"{metricas_b['n_total']:>12} {n_total:>12}")
        print(f"    {'Registros válidos':<30} "
              f"{metricas_b['n_validos']:>12} {n_validos:>12}")
        print(f"    {'Tasa de rechazo':<30} "
              f"{metricas_b['tasa_rechazo']:>11.1f}% "
              f"{n_rechazados/n_total*100:>11.1f}%")
        print(f"    {'Total errores detectados':<30} "
              f"{metricas_b['total_errores']:>12} {total_errores:>12}")
    print(sep)

# --- CARGA A MYSQL ---

def procesar_y_cargar(df: pd.DataFrame, df_auditoria: pd.DataFrame):
    """Valida y carga los registros de la condición cruda, registrando cada violación de calidad.

    Args:
        df (pandas.DataFrame): Registros de la condición cruda a procesar.
        df_auditoria (pandas.DataFrame): Auditoría de errores inyectados, para trazabilidad.

    Returns:
        tuple: Número de registros válidos, número de rechazados y conteo de errores por regla.
    """
    conn = get_connection()
    inicio = datetime.now()
    n_validos = n_rechazados = 0
    errores_por_regla = {}
    id_ejecucion = None

    try:
        with conn.cursor() as cur:

            # Abrir ejecucion_pipeline para Condición A
            cur.execute("""
                INSERT INTO ejecucion_pipeline
                    (inicio, estado, registros_procesados, registros_rechazados)
                VALUES (%s, 'en_proceso', 0, 0)
            """, (inicio,))
            conn.commit()
            id_ejecucion = cur.lastrowid
            print(f"\n  Ejecución Condición A iniciada → id_ejecucion = {id_ejecucion}")

            # Obtener sesiones existentes para FK
            cur.execute("SELECT id_sesion, nombre_sesion FROM sesion")
            sesiones = {r["nombre_sesion"]: r["id_sesion"]
                       for r in cur.fetchall()}

            # Construir mapa de errores desde auditoría
            errores_por_indice = {}
            for _, row in df_auditoria.iterrows():
                idx = int(row["indice_original"])
                tipo = row["tipo_error"]
                regla = AUDITORIA_REGLA_MAP.get(tipo, "RQ-00")
                if idx not in errores_por_indice:
                    errores_por_indice[idx] = []
                errores_por_indice[idx].append(regla)

            # Procesar cada registro
            textos_vistos = set()
            id_registros_cargados = []

            for idx, (_, row) in enumerate(df.iterrows()):
                errores = validar_registro(row.to_dict(), textos_vistos)

                if errores:
                    n_rechazados += 1
                    # Registrar cada error en detalle_error
                    for codigo, valor in errores:
                        cur.execute("""
                            INSERT INTO detalle_error
                                (id_ejecucion, codigo_regla,
                                 descripcion, valor_recibido)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            id_ejecucion,
                            codigo,
                            DESCRIPCION_REGLA.get(codigo, ""),
                            str(valor)[:500],
                        ))
                        errores_por_regla[codigo] = \
                            errores_por_regla.get(codigo, 0) + 1
                else:
                    # Registro válido — insertar en retroalimentacion
                    texto = str(row.get("text","")).strip()
                    fecha_reg = None
                    try:
                        if pd.notna(row.get("fecha_real")):
                            fecha_reg = pd.to_datetime(
                                str(row["fecha_real"]),
                                format="%Y-%m-%d"
                            ).date()
                    except Exception:
                        pass

                    nombre_sesion = row.get("nombre_sesion")
                    id_sesion = sesiones.get(str(nombre_sesion)) \
                        if pd.notna(nombre_sesion) else None
                    duracion = int(row["duration_s"]) \
                        if pd.notna(row.get("duration_s")) else None

                    cur.execute("""
                        INSERT INTO retroalimentacion
                            (texto, id_sesion, fecha_registro,
                             canal_captura, ingesta_timestamp,
                             id_ejecucion, duracion_segundos)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        texto, id_sesion, fecha_reg,
                        str(row.get("canal_captura","desconocido"))[:50]
                            if pd.notna(row.get("canal_captura")) else "desconocido",
                        datetime.now(), id_ejecucion, duracion,
                    ))
                    id_registros_cargados.append(cur.lastrowid)
                    n_validos += 1

            conn.commit()

            # Cerrar ejecucion_pipeline
            estado_final = "completado"
            cur.execute("""
                UPDATE ejecucion_pipeline
                SET fin                  = %s,
                    estado               = %s,
                    registros_procesados = %s,
                    registros_rechazados = %s
                WHERE id_ejecucion = %s
            """, (datetime.now(), estado_final,
                  len(df), n_rechazados, id_ejecucion))
            conn.commit()

        print(f"\n  Procesamiento Condición A completado:")
        print(f"      Registros válidos insertados : {n_validos}")
        print(f"      Registros rechazados         : {n_rechazados}")
        print(f"      Errores en detalle_error      : "
              f"{sum(errores_por_regla.values())}")
        print(f"      id_ejecucion                 : {id_ejecucion}")

        return n_validos, n_rechazados, errores_por_regla

    except Exception as e:
        conn.rollback()
        if id_ejecucion:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE ejecucion_pipeline SET estado='fallido' "
                        "WHERE id_ejecucion=%s", (id_ejecucion,))
                conn.commit()
            except Exception:
                pass
        print(f"\n  [ERROR] {e}"); raise
    finally:
        conn.close()

# --- MAIN ---

def main():
    """Ejecuta el flujo de validación y carga de la condición cruda a partir de argumentos de línea de comandos.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["preview","cargar"],
                        default="preview")
    args = parser.parse_args()

    condicion_a_path = Path("outputs/condicion_A.csv")
    auditoria_path   = Path("outputs/auditoria_inyeccion.csv")

    for p in [condicion_a_path, auditoria_path]:
        if not p.exists():
            print(f"No encontrado: {p}"); sys.exit(1)

    print("\nLeyendo Condición A...")
    df = pd.read_csv(condicion_a_path)
    df_auditoria = pd.read_csv(auditoria_path)
    print(f"  Registros en Condición A : {len(df)}")
    print(f"  Errores en auditoría     : {len(df_auditoria)}")

    # Preview: simular sin tocar BD
    if args.modo == "preview":
        print("\nSimulando pipeline de gobernanza (sin cambios en BD)...")
        textos_vistos = set()
        n_val = n_rech = 0
        errores_sim = {}

        for _, row in df.iterrows():
            errores = validar_registro(row.to_dict(), textos_vistos)
            if errores:
                n_rech += 1
                for codigo, _ in errores:
                    errores_sim[codigo] = errores_sim.get(codigo, 0) + 1
            else:
                n_val += 1

        # Métricas Condición B para comparación
        metricas_b = {
            "n_total"      : 152,
            "n_validos"    : 152,
            "tasa_rechazo" : 0.0,
            "total_errores": 0,
        }
        imprimir_reporte(len(df), n_val, n_rech, errores_sim, metricas_b)
        print("\nModo PREVIEW — sin cambios en BD.")
        print("Ejecuta con --modo cargar cuando estés lista.")
        return

    # Modo cargar
    print("\nProcesando Condición A y cargando a MySQL...")
    n_val, n_rech, errores_por_regla = procesar_y_cargar(df, df_auditoria)

    # Métricas Condición B para comparación
    metricas_b = {
        "n_total"      : 152,
        "n_validos"    : 152,
        "tasa_rechazo" : 0.0,
        "total_errores": 0,
    }
    imprimir_reporte(len(df), n_val, n_rech, errores_por_regla, metricas_b)

    # Guardar reporte comparativo
    out = Path("outputs")
    reporte = pd.DataFrame([
        {"condicion": "B_gobernada", "n_total": 152, "n_validos": 152,
         "n_rechazados": 0, "tasa_rechazo_pct": 0.0,
         "total_errores": 0},
        {"condicion": "A_cruda", "n_total": len(df), "n_validos": n_val,
         "n_rechazados": n_rech,
         "tasa_rechazo_pct": round(n_rech/len(df)*100, 1),
         "total_errores": sum(errores_por_regla.values())},
    ])
    reporte.to_csv(out/"reporte_comparativo_condiciones.csv", index=False)
    print(f"\n  Reporte guardado: outputs/reporte_comparativo_condiciones.csv")
    print(f"\n  Siguiente paso: data augmentation")
    print(f"  python scripts/08_data_augmentation.py --modo preview")

if __name__ == "__main__":
    main()