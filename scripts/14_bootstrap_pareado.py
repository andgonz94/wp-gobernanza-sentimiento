"""Estima por bootstrap pareado la diferencia de F1-macro entre las condiciones B y A.

Responde a la Pregunta 4 del análisis. Para cada configuración evaluada
(baseline, BETO, BERTIN/RoBERTa-es y BETO sin ajuste fino) remuestrea con
reemplazo los mismos id_segmento en ambas condiciones y obtiene la
distribución bootstrap de Δ = F1-macro(B) − F1-macro(A), su intervalo de
confianza del 95 % y un p-valor bilateral. La justificación del diseño
pareado y la estructura de carpetas esperada están en
docs/guia_operativa_scripts.md.

NOTA METODOLÓGICA (2026-08): se retiró la "lectura de una cola" que se
usaba antes para reportar un p-valor complementario sobre BETO. Esa
lectura no aportaba información nueva (era el mismo p bilateral dividido
entre 2) y su uso post-hoc, sin una hipótesis direccional registrada
formalmente antes del análisis en el Documento de Trabajo, es
indistinguible de HARKing (Hypothesizing After the Results are Known).
El resultado bilateral es ahora el único resultado inferencial reportado.

En su lugar se añaden dos elementos, ambos descriptivos o prospectivos,
que no requieren declarar direccionalidad a priori:

  1. `prop_b_mejor` — proporción de remuestras bootstrap en las que
     F1-macro(B) > F1-macro(A). Es una descripción de la distribución
     empírica, no una prueba de hipótesis.
  2. `potencia_retrospectiva` y `n_requerido_80pct` — con una
     aproximación normal (Fleiss et al., 1980; ver también el criterio
     de Takahashi et al. 2022 ya citado en el Reporte Metodológico para
     el umbral n≈500 en F1-macro bajo desbalance), se estima qué tan
     probable era detectar como significativo el efecto observado con
     el n actual, y qué n de prueba se necesitaría para 80% de potencia
     a un alfa bilateral de 0.05. Es una aproximación de primer orden
     (asume que la distribución bootstrap de la diferencia es
     aproximadamente normal, lo cual es razonable con 5.000 remuestreos)
     y debe reportarse como tal — no reemplaza un cálculo exacto vía
     simulación completa, pero es suficientemente rigurosa para
     justificar cuantitativamente la limitación de potencia en la
     sección de limitaciones y para motivar el tamaño de muestra
     recomendado en trabajo futuro.

Aclaración (2026-10): la lectura de una cola nunca estuvo implementada en
este script; ninguna versión registrada en Git la calcula. Era una
interpretación del reporte (el p bilateral dividido entre 2). Su retiro
afecta al reporte, no al código; ver docs/cambios_agosto_2026.md.

NOTA METODOLÓGICA (2026-10): se retiran `prop_b_mejor`,
`potencia_retrospectiva` y `n_requerido_80pct`, introducidas en 2026-08.
Las tres dependen del efecto observado o equivalen a una lectura
unilateral: `prop_b_mejor` es, en la práctica, el p de una cola expresado
como proporción; la potencia retrospectiva calculada con el efecto
observado es una función monótona del p-valor y no aporta información
nueva; el n requerido hereda esa dependencia. Se reemplazan por:

  1. `ee_bootstrap` — desviación estándar de la distribución bootstrap de
     Δ (con ddof=1), es decir, el error estándar bootstrap de la diferencia.
  2. `emd_80` — efecto mínimo detectable con 80 % de potencia y alfa
     bilateral de 0.05: (z_0.975 + z_0.80) × `ee_bootstrap`.

El EMD depende solo de la variabilidad del diseño (tamaño del conjunto de
prueba y dispersión de las predicciones), no del efecto observado. Se
calcula sobre la misma distribución bootstrap (misma semilla y número de
remuestreos), sin remuestreo adicional, de modo que la diferencia, el IC
y el p bilateral no cambian. Decisión del 2026-10-07.

Referencia sobre la potencia retrospectiva: Hoenig, J. M., & Heisey, D. M.
(2001). The abuse of power: The pervasive fallacy of power calculations for
data analysis. The American Statistician, 55(1), 19-24.

Entradas:
    outputs/bootstrap_input/: un CSV de predicciones por configuración y
    condición, con columnas id_segmento, y_true e y_pred.
Salidas:
    outputs/bootstrap_resultados.csv: resumen por configuración.
    outputs/bootstrap_distribuciones.png: distribuciones bootstrap con el IC.
    Con --excluir-fuga y --por-entrevista, los mismos archivos con sufijos _sin_fuga y
    _por_entrevista.

NOTA METODOLÓGICA (2026-11-02): con --por-entrevista el remuestreo se hace sobre
entrevistas únicas por contenido (los 17 pares de texto idéntico cuentan como una sola),
de modo que los segmentos de una misma entrevista entran o salen juntos. Es la inferencia
principal del plan del 2026-11-02; el remuestreo por segmento, que no tiene en cuenta la
dependencia entre segmentos de una entrevista, queda como comparación. Sin la opción, el
script se comporta exactamente como antes (mismos remuestreos y mismas salidas).
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import f1_score

Z_ALPHA_2 = norm.ppf(1 - 0.05 / 2)  # 1.959964 — alfa bilateral = 0.05
Z_BETA_80 = norm.ppf(0.80)          # 0.841621 — potencia objetivo = 80%

IN_DIR = Path("outputs/bootstrap_input")
OUT_DIR = Path("outputs")
OUT_DIR.mkdir(exist_ok=True)

N_BOOTSTRAP = 5000
SEMILLA = 42
NIVEL_CONFIANZA = 0.95

# Conjunto de exclusión del plan de sensibilidad a la fuga (2026-10-09): segmentos
# de prueba cuyo registro tiene un gemelo
# (entrevista con texto idéntico) con algún segmento o variante en entrenamiento.
# Solo se usa con --excluir-fuga; el análisis principal no lo aplica.
IDS_FUGA = frozenset([
    1654, 1655, 1656, 1657, 1658, 1659, 1723, 1724, 1725, 1726, 1727, 1728, 1729,
    1856, 1857, 1871, 1872, 1873, 2107, 2108, 2109, 2110,
])

# Orden y nombres de presentación de la figura, iguales a los de 01_metricas (script 16).
# No cambian el orden de cálculo ni el del CSV.
NOMBRES_FIGURA = {
    "baseline": "Baseline",
    "beto_sin_finetuning": "BETO sin ajuste",
    "beto": "BETO con ajuste fino",
    "bertin_roberta": "BERTIN",
}

MODELOS = {
    "baseline": ("baseline_predicciones_A.csv", "baseline_predicciones_B.csv"),
    "beto": ("beto_predicciones_A.csv", "beto_predicciones_B.csv"),
    "bertin_roberta": ("roberta_predicciones_A.csv", "roberta_predicciones_B.csv"),
    "beto_sin_finetuning": ("beto_probing_predicciones_A.csv", "beto_probing_predicciones_B.csv"),
}


def cargar_par(archivo_a, archivo_b):
    """Carga y alinea por identificador las predicciones de ambas condiciones para un modelo.

    Args:
        archivo_a (str): Nombre del archivo de predicciones de la condición cruda.
        archivo_b (str): Nombre del archivo de predicciones de la condición gobernada.

    Returns:
        tuple: DataFrames de predicciones de la condición cruda y gobernada, alineados por identificador común.
    """
    df_a = pd.read_csv(IN_DIR / archivo_a)
    df_b = pd.read_csv(IN_DIR / archivo_b)

    # Alinear por id_segmento — solo los presentes en AMBOS archivos
    # (deberían ser exactamente los mismos, dado el diseño ya validado,
    # pero se verifica explícitamente para no asumir nada)
    ids_comunes = sorted(set(df_a["id_segmento"]) & set(df_b["id_segmento"]))
    faltantes_a = set(df_b["id_segmento"]) - set(df_a["id_segmento"])
    faltantes_b = set(df_a["id_segmento"]) - set(df_b["id_segmento"])
    if faltantes_a or faltantes_b:
        print(f"  [AVISO] {len(faltantes_a)} ids solo en B, "
              f"{len(faltantes_b)} ids solo en A — se usan solo los {len(ids_comunes)} en común.")

    df_a = df_a.set_index("id_segmento").loc[ids_comunes].reset_index()
    df_b = df_b.set_index("id_segmento").loc[ids_comunes].reset_index()

    # Verificación de integridad: y_true debe ser idéntico para el mismo
    # id_segmento en A y B (es la misma etiqueta real, independiente de
    # la condición) — si no coincide, hay un problema de datos que hay
    # que resolver antes de continuar.
    discrepancias = (df_a["y_true"].astype(str).values != df_b["y_true"].astype(str).values).sum()
    if discrepancias > 0:
        print(f"  [ERROR] {discrepancias} casos con y_true distinto entre A y B para el mismo "
              f"id_segmento — revisar antes de confiar en este resultado.")

    return df_a, df_b


def grupos_por_entrevista(ids_segmento):
    """Asigna a cada segmento su entrevista única por contenido (plan del 2026-11-02).

    El grupo es el id_registro del segmento; los dos registros de cada par de texto
    idéntico (17 pares) forman un solo grupo, identificado por el id_registro menor.
    Solo lectura de la base de datos.

    Args:
        ids_segmento (array-like): id_segmento de los casos, en el orden del análisis.

    Returns:
        numpy.ndarray: Identificador de grupo de cada caso, en el mismo orden.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config.db_connection import get_engine
    engine = get_engine()
    registro = pd.read_sql("SELECT id_segmento, id_registro FROM segmento_retroalimentacion",
                           engine).set_index("id_segmento")["id_registro"]
    pares = pd.read_sql("""
        SELECT r1.id_registro AS primero, r2.id_registro AS segundo
        FROM retroalimentacion r1
        JOIN retroalimentacion r2
          ON r1.texto = r2.texto AND r1.id_registro < r2.id_registro
        WHERE r1.id_ejecucion = 2 AND r2.id_ejecucion = 2
    """, engine)
    gemelo = dict(zip(pares["segundo"], pares["primero"]))
    registros = registro.loc[list(ids_segmento)].to_numpy()
    return np.array([gemelo.get(r, r) for r in registros])


def bootstrap_pareado(df_a, df_b, n_bootstrap=N_BOOTSTRAP, semilla=SEMILLA, grupos=None):
    """Estima por bootstrap pareado la diferencia de F1-macro entre dos condiciones.

    Args:
        df_a (pandas.DataFrame): Predicciones de la condición cruda.
        df_b (pandas.DataFrame): Predicciones de la condición gobernada.
        n_bootstrap (int): Número de remuestreos a realizar.
        semilla (int): Semilla del generador de números aleatorios, para reproducibilidad.
        grupos (numpy.ndarray | None): Si se indica, se remuestrean grupos (entrevistas) con
            reemplazo y sus casos entran juntos; si es None, se remuestrean casos, como antes.

    Returns:
        tuple: Diccionario de métricas resumen y arreglo con la distribución bootstrap de diferencias.
    """
    rng = np.random.default_rng(semilla)
    n = len(df_a)
    if grupos is not None:
        _, codigos = np.unique(grupos, return_inverse=True)
        miembros = [np.flatnonzero(codigos == g) for g in range(codigos.max() + 1)]

    y_true_a = df_a["y_true"].values
    y_pred_a = df_a["y_pred"].values
    y_true_b = df_b["y_true"].values
    y_pred_b = df_b["y_pred"].values

    f1_obs_a = f1_score(y_true_a, y_pred_a, average="macro")
    f1_obs_b = f1_score(y_true_b, y_pred_b, average="macro")
    diff_obs = f1_obs_b - f1_obs_a

    diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        if grupos is None:
            idx = rng.integers(0, n, size=n)  # remuestreo CON reemplazo, MISMOS índices para A y B
        else:  # remuestreo de entrevistas: los casos de cada entrevista sorteada entran juntos
            idx = np.concatenate([miembros[g] for g in rng.integers(0, len(miembros), size=len(miembros))])
        f1_a_boot = f1_score(y_true_a[idx], y_pred_a[idx], average="macro", zero_division=0)
        f1_b_boot = f1_score(y_true_b[idx], y_pred_b[idx], average="macro", zero_division=0)
        diffs[i] = f1_b_boot - f1_a_boot

    alpha = 1 - NIVEL_CONFIANZA
    ci_low, ci_high = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    # p-valor de dos colas: proporción de la distribución bootstrap que
    # cae del lado opuesto a la diferencia observada, doblado.
    # (Se reporta ÚNICAMENTE el bilateral; la lectura de una cola era una
    # interpretación del reporte, no código: ver la nota metodológica.)
    p_valor = 2 * min((diffs <= 0).mean(), (diffs >= 0).mean())
    p_valor = min(p_valor, 1.0)
    significativo = not (ci_low <= 0 <= ci_high)

    # Error estándar bootstrap y efecto mínimo detectable (80 % de potencia,
    # alfa bilateral 0.05). Se calculan sobre la misma distribución ya
    # remuestreada: no consumen el generador aleatorio, así que no alteran
    # la diferencia, el IC ni el p-valor.
    ee_bootstrap = float(np.std(diffs, ddof=1))
    emd_80 = float((Z_ALPHA_2 + Z_BETA_80) * ee_bootstrap)

    return {
        "f1_macro_B": f1_obs_b, "f1_macro_A": f1_obs_a,
        "diferencia_B_menos_A": diff_obs,
        "ci95_low": ci_low, "ci95_high": ci_high,
        "p_valor_aprox": p_valor,
        "significativo_95": significativo,
        "ee_bootstrap": ee_bootstrap,
        "emd_80": emd_80,
        "n_pares": n,
    }, diffs


def main():
    """Ejecuta el bootstrap pareado para cada modelo disponible y consolida los resultados.

    Con --excluir-fuga aplica el plan de sensibilidad a la fuga: excluye IDS_FUGA del
    conjunto de prueba y escribe en archivos con sufijo _sin_fuga, sin tocar las salidas
    principales.
    """
    parser = argparse.ArgumentParser(description="Bootstrap pareado de la diferencia de F1-macro B − A.")
    parser.add_argument("--excluir-fuga", action="store_true",
                        help="excluye el conjunto de fuga (plan del 2026-10-09); salidas *_sin_fuga")
    parser.add_argument("--por-entrevista", action="store_true",
                        help="remuestrea entrevistas únicas por contenido en lugar de segmentos "
                             "(plan del 2026-11-02); salidas *_por_entrevista")
    args = parser.parse_args()
    sufijo = ("_por_entrevista" if args.por_entrevista else "") + ("_sin_fuga" if args.excluir_fuga else "")
    if not IN_DIR.exists():
        print(f"[ERROR] No existe la carpeta {IN_DIR}. Consulta docs/guia_operativa_scripts.md "
              f"para la estructura y los nombres de archivo esperados.")
        return

    resultados = []
    distribuciones = {}

    for nombre_modelo, (archivo_a, archivo_b) in MODELOS.items():
        ruta_a, ruta_b = IN_DIR / archivo_a, IN_DIR / archivo_b
        if not ruta_a.exists() or not ruta_b.exists():
            print(f"[AVISO] Saltando {nombre_modelo}: faltan {archivo_a} o {archivo_b} en {IN_DIR}")
            continue

        print(f"\n{'='*60}\n  {nombre_modelo.upper()}\n{'='*60}")
        df_a, df_b = cargar_par(archivo_a, archivo_b)
        if args.excluir_fuga:
            conservar = ~df_a["id_segmento"].isin(IDS_FUGA).to_numpy()
            print(f"  [INFO] Sensibilidad a la fuga: se excluyen {int((~conservar).sum())} "
                  f"segmentos; quedan {int(conservar.sum())}.")
            df_a = df_a[conservar].reset_index(drop=True)
            df_b = df_b[conservar].reset_index(drop=True)
        grupos = grupos_por_entrevista(df_a["id_segmento"]) if args.por_entrevista else None
        if grupos is not None:
            print(f"  [INFO] Remuestreo por entrevista: {len(np.unique(grupos))} entrevistas "
                  f"únicas para {len(df_a)} segmentos.")
        resultado, diffs = bootstrap_pareado(df_a, df_b, grupos=grupos)
        resultado["modelo"] = nombre_modelo
        if grupos is not None:
            resultado["n_entrevistas"] = len(np.unique(grupos))
        resultados.append(resultado)
        distribuciones[nombre_modelo] = diffs

        print(f"  F1-macro B: {resultado['f1_macro_B']:.4f}  |  "
              f"F1-macro A: {resultado['f1_macro_A']:.4f}")
        print(f"  Diferencia observada (B - A): {resultado['diferencia_B_menos_A']:.4f}")
        print(f"  IC 95% (bootstrap, {N_BOOTSTRAP} remuestreos): "
              f"[{resultado['ci95_low']:.4f}, {resultado['ci95_high']:.4f}]")
        print(f"  p-valor (dos colas, único reportado como inferencial): "
              f"{resultado['p_valor_aprox']:.4f}")
        print(f"  ¿Significativo al 95%? "
              f"{'SÍ' if resultado['significativo_95'] else 'NO'} "
              f"({'el IC no cruza 0' if resultado['significativo_95'] else 'el IC cruza 0'})")
        print(f"  Error estándar bootstrap de Δ: {resultado['ee_bootstrap']:.4f}")
        print(f"  Efecto mínimo detectable (80 % de potencia, alfa bilateral 0.05, "
              f"n={resultado['n_pares']}): {resultado['emd_80']:.4f}")

    if not resultados:
        print("\n[ERROR] No se procesó ningún modelo — verifica los archivos de entrada.")
        return

    df_resultados = pd.DataFrame(resultados)[
        ["modelo", "f1_macro_B", "f1_macro_A", "diferencia_B_menos_A",
         "ci95_low", "ci95_high", "p_valor_aprox", "significativo_95",
         "ee_bootstrap", "emd_80", "n_pares"] + (["n_entrevistas"] if args.por_entrevista else [])
    ]
    ruta_csv = OUT_DIR / f"bootstrap_resultados{sufijo}.csv"
    df_resultados.to_csv(ruta_csv, index=False)

    print(f"\n{'='*60}\n  RESUMEN CONSOLIDADO — TODAS LAS CONFIGURACIONES\n{'='*60}")
    print(df_resultados.to_string(index=False))
    print(f"\n[OK] CSV guardado: {ruta_csv}")

    # --- Gráfico de las distribuciones bootstrap, con el IC marcado ---
    try:
        import matplotlib.pyplot as plt

        orden = [m for m in NOMBRES_FIGURA if m in distribuciones]
        fig, axes = plt.subplots(1, len(orden), figsize=(5 * len(orden), 4.5), sharex=True)
        if len(orden) == 1:
            axes = [axes]

        for ax, nombre in zip(axes, orden):
            diffs = distribuciones[nombre]
            row = df_resultados[df_resultados["modelo"] == nombre].iloc[0]
            ax.hist(diffs, bins=50, color="#4C72B0", alpha=0.75)
            ax.axvline(0, color="black", linestyle="--", linewidth=1, label="0 (sin diferencia)")
            ax.axvline(row["diferencia_B_menos_A"], color="red", linewidth=1.5,
                       label=f"Observado: {row['diferencia_B_menos_A']:.3f}")
            ax.axvspan(row["ci95_low"], row["ci95_high"], color="orange", alpha=0.15,
                       label="IC 95%")
            # El panel informa Δ, IC 95 % y p bilateral; no etiqueta "significativo"
            # para no convertir un umbral en conclusión (decisión del 2026-10-08).
            ax.set_title(f"{NOMBRES_FIGURA[nombre]}\nΔ = {row['diferencia_B_menos_A']:+.3f}  "
                         f"IC 95 % [{row['ci95_low']:+.3f}, {row['ci95_high']:+.3f}]  "
                         f"p = {row['p_valor_aprox']:.3f}", fontsize=9)
            ax.set_xlabel("Diferencia F1-macro (B - A)")
            ax.legend(fontsize=8)

        plt.tight_layout()
        ruta_fig = OUT_DIR / f"bootstrap_distribuciones{sufijo}.png"
        plt.savefig(ruta_fig, dpi=150)
        print(f"[OK] Gráfico guardado: {ruta_fig}")
    except ImportError:
        print("[AVISO] matplotlib no disponible: se omite el gráfico; el CSV ya tiene todo el detalle.")


if __name__ == "__main__":
    main()