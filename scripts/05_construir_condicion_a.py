"""Construye la condición cruda a nivel de documento inyectando errores controlados.

Genera la condición de datos no gobernados a partir del corpus base gobernado,
con errores reproducibles (nulos, duplicados, formatos inválidos, valores fuera
de catálogo y texto no informativo). Calcula y compara las métricas de calidad
estructural de ambas condiciones.

Entradas:
    outputs/corpus_final.csv (corpus base gobernado).
Salidas:
    outputs/condicion_A.csv, outputs/auditoria_inyeccion.csv y
    outputs/comparativa_calidad.csv (solo en modo generar).
"""

import sys, re, argparse, hashlib
from pathlib import Path
from datetime import date, timedelta
import random
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# --- CONFIGURACIÓN ---

RANDOM_SEED = 42  # reproducibilidad garantizada

# Tasas de inyección por tipo de error
TASAS = {
    "nulo_id_sesion"      : 0.15,
    "nulo_texto"          : 0.05,
    "nulo_fecha"          : 0.10,
    "nulo_canal"          : 0.12,
    "duplicado_exacto"    : 0.08,
    "cuasi_duplicado"     : 0.05,
    "formato_fecha"       : 0.08,
    "canal_fuera_catalogo": 0.10,
    "texto_no_informativo": 0.07,
}

# Valores fuera de catálogo para canal_captura
CANALES_INVALIDOS = [
    "WhatsApp", "Teams", "presencial", "No sé",
    "verbal", "otro", "zoom", "telefono", "n/a"
]

# Textos no informativos
TEXTOS_NO_INFORMATIVOS = [
    "ok", "bien", ".", "bueno", "nada",
    "no sé", "regular", "así", "sí", "no",
    "todo bien", "bien gracias", "nada que decir"
]

# Formatos de fecha inválidos
def fecha_formato_invalido(fecha_original):
    """Genera una representación de fecha con un formato inválido o incorrecto.

    Args:
        fecha_original: Fecha original a partir de la cual generar la variante inválida.

    Returns:
        str: Fecha representada en un formato incorrecto o no parseable.
    """
    formatos_invalidos = [
        lambda f: f.strftime("%d/%m/%Y"),        # separador incorrecto
        lambda f: f.strftime("%d-%m-%Y"),        # orden incorrecto
        lambda f: f.strftime("%m/%d/%Y"),        # orden anglosajón
        lambda f: "N/A",                          # cadena no parseable
        lambda f: str(f.year + 5) + f.strftime("-%m-%d"),  # año futuro
        lambda f: f.strftime("%Y-%d-%m"),        # día y mes invertidos
    ]
    if pd.isna(fecha_original) or fecha_original is None:
        return "31/13/2025"  # fecha imposible
    try:
        if isinstance(fecha_original, str):
            fecha_original = pd.to_datetime(fecha_original).date()
        return random.choice(formatos_invalidos)(fecha_original)
    except Exception:
        return "N/A"

# --- PIPELINE DE INYECCIÓN ---

def inyectar_errores(df_base: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Inyecta errores controlados y reproducibles sobre el corpus base.

    Args:
        df_base (pandas.DataFrame): Corpus base gobernado.

    Returns:
        tuple: DataFrame con los errores inyectados y diccionario de auditoría por tipo de error.
    """
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    df = df_base.copy()
    n = len(df)
    auditoria = {tipo: [] for tipo in TASAS}

    # --- 1. Nulos bloqueantes en id_sesion ---
    idx = df.sample(frac=TASAS["nulo_id_sesion"],
                    random_state=RANDOM_SEED).index
    df.loc[idx, "num_sesion"] = np.nan
    df.loc[idx, "nombre_sesion"] = np.nan
    auditoria["nulo_id_sesion"] = list(idx)

    # --- 2. Nulos bloqueantes en texto ---
    idx = df.sample(frac=TASAS["nulo_texto"],
                    random_state=RANDOM_SEED+1).index
    df.loc[idx, "text"] = np.nan
    auditoria["nulo_texto"] = list(idx)

    # --- 3. Nulos degradantes en fecha_registro ---
    idx = df.sample(frac=TASAS["nulo_fecha"],
                    random_state=RANDOM_SEED+2).index
    df.loc[idx, "fecha_real"] = np.nan
    auditoria["nulo_fecha"] = list(idx)

    # --- 4. Nulos degradantes en canal_captura ---
    # En Condición A el canal no existe como campo estandarizado
    if "canal_captura" not in df.columns:
        df["canal_captura"] = "formulario"
    idx = df.sample(frac=TASAS["nulo_canal"],
                    random_state=RANDOM_SEED+3).index
    df.loc[idx, "canal_captura"] = np.nan
    auditoria["nulo_canal"] = list(idx)

    # --- 5. Duplicados exactos ---
    n_dup = max(1, int(n * TASAS["duplicado_exacto"]))
    duplicados = df.sample(n=n_dup, random_state=RANDOM_SEED+4)
    df = pd.concat([df, duplicados], ignore_index=True)
    auditoria["duplicado_exacto"] = list(duplicados.index)

    # --- 6. Cuasi-duplicados (mismo texto, distinta sesión) ---
    n_quasi = max(1, int(n * TASAS["cuasi_duplicado"]))
    quasi = df.sample(n=n_quasi, random_state=RANDOM_SEED+5).copy()
    # Cambiar id_sesion para que parezca diferente
    quasi["num_sesion"] = quasi["num_sesion"].apply(
        lambda x: (x + 1) % 12 + 1 if pd.notna(x) else x
    )
    quasi["nombre_sesion"] = quasi["nombre_sesion"].apply(
        lambda x: str(x) + "_duplicado" if pd.notna(x) else x
    )
    df = pd.concat([df, quasi], ignore_index=True)
    auditoria["cuasi_duplicado"] = list(quasi.index)

    # --- 7. Formato de fecha inválido ---
    idx = df.sample(frac=TASAS["formato_fecha"],
                    random_state=RANDOM_SEED+6).index
    df.loc[idx, "fecha_real"] = df.loc[idx, "fecha_real"].apply(
        fecha_formato_invalido
    )
    auditoria["formato_fecha"] = list(idx)

    # --- 8. Canal fuera de catálogo ---
    idx = df.sample(frac=TASAS["canal_fuera_catalogo"],
                    random_state=RANDOM_SEED+7).index
    df.loc[idx, "canal_captura"] = [
        random.choice(CANALES_INVALIDOS) for _ in range(len(idx))
    ]
    auditoria["canal_fuera_catalogo"] = list(idx)

    # --- 9. Texto no informativo ---
    idx = df.sample(frac=TASAS["texto_no_informativo"],
                    random_state=RANDOM_SEED+8).index
    df.loc[idx, "text"] = [
        random.choice(TEXTOS_NO_INFORMATIVOS) for _ in range(len(idx))
    ]
    auditoria["texto_no_informativo"] = list(idx)

    # Eliminar metadatos gobernados que no existirían en Condición A
    cols_a_eliminar = [
        "ingesta_timestamp", "id_ejecucion", "metodo_sesion",
        "[programa]", "tematica"
    ]
    df.drop(columns=[c for c in cols_a_eliminar if c in df.columns],
            inplace=True)

    return df, auditoria

# --- MÉTRICAS DE CALIDAD ---

def calcular_metricas(df, nombre, es_condicion_b=False):
    """Calcula las dimensiones de calidad del dato de un conjunto de registros.

    Args:
        df (pandas.DataFrame): Conjunto de registros a evaluar.
        nombre (str): Nombre descriptivo del conjunto de datos.
        es_condicion_b (bool): Indica si el conjunto corresponde a la condición gobernada.

    Returns:
        dict: Métricas de completitud, unicidad, validez y trazabilidad, en porcentaje.
    """
    n = len(df)

    # Completitud
    campos = ["text", "num_sesion", "fecha_real"]
    if "canal_captura" in df.columns:
        campos.append("canal_captura")
    campos_presentes = [c for c in campos if c in df.columns]
    completitud = sum(df[c].notna().sum() for c in campos_presentes) / (n * len(campos_presentes)) if campos_presentes else 0.0

    # Unicidad
    unicidad = 1 - (df["text"].duplicated().sum() / n) if "text" in df.columns else 1.0

    # Validez fecha — solo sobre fechas presentes
    def es_fecha_valida(v):
        """Indica si una fecha presente tiene formato YYYY-MM-DD.

        Args:
            v: Valor de fecha_real.

        Returns:
            bool | None: True si es válida, False si no, y None si falta (las fechas
            ausentes no cuentan para la validez).
        """
        if pd.isna(v): return None
        try:
            pd.to_datetime(str(v), format="%Y-%m-%d")
            return True
        except Exception:
            return False

    if "fecha_real" in df.columns:
        fechas = df["fecha_real"].dropna()
        validez_fecha = fechas.apply(es_fecha_valida).mean() if len(fechas) > 0 else 0.0
    else:
        validez_fecha = 0.0

    # Validez canal
    catalogo = {"formulario","papel","app","email","desconocido"}
    if "canal_captura" in df.columns:
        canal = df["canal_captura"].dropna()
        validez_canal = canal.apply(lambda x: str(x).lower() in catalogo).mean() if len(canal) > 0 else 0.0
    else:
        validez_canal = 1.0 if es_condicion_b else 0.0

    # Trazabilidad
    if es_condicion_b:
        tiene_traz = all(c in df.columns for c in ["metodo_sesion","nombre_sesion"])
        trazabilidad = 1.0 if tiene_traz else 0.5
    else:
        trazabilidad = 0.0

    return {
        "dataset"      : nombre,
        "n_registros"  : n,
        "completitud"  : round(completitud * 100, 1),
        "unicidad"     : round(unicidad * 100, 1),
        "validez_fecha": round(validez_fecha * 100, 1),
        "validez_canal": round(validez_canal * 100, 1),
        "trazabilidad" : round(trazabilidad * 100, 1),
    }

def imprimir_comparacion(metricas_b: dict, metricas_a: dict):
    """Imprime una tabla comparativa de métricas de calidad entre ambas condiciones.

    Args:
        metricas_b (dict): Métricas de la condición gobernada.
        metricas_a (dict): Métricas de la condición cruda.

    Returns:
        None
    """
    sep = "─"*70
    print(f"\n{sep}")
    print("  TABLA COMPARATIVA DE CALIDAD — Condición B vs Condición A")
    print(sep)
    print(f"  {'Métrica':<25} {'Cond. B (gobernado)':>20} "
          f"{'Cond. A (crudo)':>18} {'Diferencia':>12}")
    print(f"  {'':─<25} {'':─>20} {'':─>18} {'':─>12}")

    for campo in ["n_registros","completitud","unicidad",
                  "validez_fecha","validez_canal","trazabilidad"]:
        vb = metricas_b[campo]
        va = metricas_a[campo]
        if isinstance(vb, float):
            diff = vb - va
            signo = "▲" if diff > 0 else "▼" if diff < 0 else "="
            print(f"  {campo:<25} {vb:>19.1f}% {va:>17.1f}% "
                  f"  {signo}{abs(diff):>7.1f}%")
        else:
            print(f"  {campo:<25} {vb:>20} {va:>18}")
    print(sep)

def imprimir_reporte_inyeccion(auditoria: dict, n_base: int, n_final: int):
    """Imprime un resumen de los errores inyectados por tipo.

    Args:
        auditoria (dict): Registros afectados agrupados por tipo de error.
        n_base (int): Número de registros del corpus base.
        n_final (int): Número de registros resultantes tras la inyección.

    Returns:
        None
    """
    sep = "─"*60
    print(f"\n{sep}")
    print("  REPORTE DE INYECCIÓN DE ERRORES")
    print(sep)
    print(f"  Registros base              : {n_base:>6}")
    print(f"  Registros en Condición A    : {n_final:>6}")
    print(f"  Registros añadidos (dup)    : {n_final-n_base:>6}")
    print(f"\n  Errores inyectados por tipo:")
    for tipo, indices in auditoria.items():
        tasa = TASAS[tipo]*100
        print(f"    {tipo:<30} {len(indices):>5} registros  "
              f"(tasa objetivo: {tasa:.0f}%)")
    print(sep)

# --- MAIN ---

def main():
    """Ejecuta el flujo de construcción de la condición cruda a partir de argumentos de línea de comandos.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["preview","generar"], default="preview")
    args = parser.parse_args()

    corpus_path = Path("outputs/corpus_final.csv")
    if not corpus_path.exists():
        print(f"No encontrado: {corpus_path}"); sys.exit(1)

    print("\nLeyendo corpus base (Condición B)...")
    df_base = pd.read_csv(corpus_path)
    print(f"  Registros base: {len(df_base)}")

    # Métricas de Condición B
    metricas_b = calcular_metricas(df_base, "Condición B (gobernado)", es_condicion_b=True)

    print("\nInyectando errores controlados...")
    df_cond_a, auditoria = inyectar_errores(df_base)

    # Métricas de Condición A
    metricas_a = calcular_metricas(df_cond_a, "Condición A (crudo)")

    imprimir_reporte_inyeccion(auditoria, len(df_base), len(df_cond_a))
    imprimir_comparacion(metricas_b, metricas_a)

    if args.modo == "generar":
        out = Path("outputs")

        # Guardar Condición A
        path_a = out / "condicion_A.csv"
        df_cond_a.to_csv(path_a, index=False)

        # Guardar registro de auditoría
        audit_rows = []
        for tipo, indices in auditoria.items():
            for idx in indices:
                audit_rows.append({"tipo_error": tipo, "indice_original": idx})
        pd.DataFrame(audit_rows).to_csv(out/"auditoria_inyeccion.csv", index=False)

        # Guardar tabla comparativa de métricas
        pd.DataFrame([metricas_b, metricas_a]).to_csv(
            out/"comparativa_calidad.csv", index=False)

        print(f"\n  Archivos generados:")
        print(f"      outputs/condicion_A.csv")
        print(f"      outputs/auditoria_inyeccion.csv")
        print(f"      outputs/comparativa_calidad.csv")
    else:
        print("\nModo PREVIEW — sin archivos generados.")
        print("Ejecuta con --modo generar cuando estés lista.")

if __name__ == "__main__":
    main()