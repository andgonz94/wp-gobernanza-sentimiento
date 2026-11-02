"""Ejecuta el plan de análisis multisemilla de BETO y BERTIN (sensibilidad a la semilla).

Implementa el plan fijado el 2026-10-08, antes de calcular cualquier
estadístico inferencial multisemilla. Es un análisis de sensibilidad
exploratorio, posterior a los resultados principales del script 14: evalúa si
la diferencia de F1-macro entre las condiciones B y A se sostiene al variar la
semilla de entrenamiento. Reutiliza sin cambios bootstrap_pareado() del script
14 para el análisis por semilla.

Secciones del plan:
    a) Bootstrap pareado por semilla (diferencia, IC 95 %, p bilateral, EMD).
    b) Agregado descriptivo por modelo y prueba de signos binomial exacta.
    c) Bootstrap de dos niveles (semillas y casos) sobre la media de Δ.
    d) Corrección de Holm, junto a los p sin corregir.
    e) Corrida principal como referencia, fuera del promedio.
    f) Log Loss y PR-AUC por semilla, solo descriptivos.
    g) Criterio de robustez a la semilla.

Entradas:
    <origen-colab>/{beto,roberta_es}/multisemilla/predicciones_s<semilla>_{A,B}.csv
    <origen-colab>/{beto,roberta_es}/multisemilla/detalle_multisemilla.csv
    outputs/bootstrap_resultados.csv (análisis principal, script 14).
Salidas (outputs/multisemilla/):
    bootstrap_por_semilla.csv, agregado_por_modelo.csv,
    holm_configuraciones_principales.csv, descriptivo_logloss_prauc.csv,
    manifiesto_insumos_multisemilla.csv.
    Con --por-entrevista y --excluir-fuga, las mismas tablas en
    outputs/multisemilla{_por_entrevista}{_sin_fuga}/, a partir de
    outputs/bootstrap_resultados{_por_entrevista}{_sin_fuga}.csv.

NOTA METODOLÓGICA (2026-11-02): con --por-entrevista, el bootstrap por semilla y el
segundo nivel del bootstrap de dos niveles remuestrean entrevistas únicas por contenido
(grupos_por_entrevista del script 14) en lugar de segmentos. Sin la opción, el script se
comporta exactamente como antes.
"""

import argparse
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest
from sklearn.metrics import f1_score

SEMILLAS = [42, 123, 2024, 7, 99]
MODELOS = {"beto": "beto", "bertin_roberta": "roberta_es"}
N_REPLICAS = 5000
SEMILLA_BOOTSTRAP = 42
ALFA = 0.05
MIN_SEMILLAS_MISMO_SIGNO = 4

OUT_DIR = Path("outputs/multisemilla")
RESULTADOS_PRINCIPALES = Path("outputs/bootstrap_resultados.csv")


def cargar_script_14():
    """Importa el script 14 como módulo, para reutilizar bootstrap_pareado sin copiarlo.

    Returns:
        module: Módulo del script 14_bootstrap_pareado.py.
    """
    ruta = Path(__file__).resolve().parent / "14_bootstrap_pareado.py"
    spec = importlib.util.spec_from_file_location("bootstrap_pareado_14", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def sha256(ruta):
    """Calcula la huella SHA-256 de un archivo.

    Args:
        ruta (pathlib.Path): Archivo a resumir.

    Returns:
        str: Huella hexadecimal.
    """
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def cargar_predicciones(origen_colab, carpeta, semilla, manifiesto, excluir=frozenset()):
    """Carga y alinea por id_segmento las predicciones A y B de una semilla.

    Args:
        origen_colab (pathlib.Path): Copia local de resultados_colab/.
        carpeta (str): Subcarpeta del modelo en resultados_colab/.
        semilla (int): Semilla de entrenamiento.
        manifiesto (list): Lista donde se registra cada insumo leído.
        excluir (frozenset): id_segmento a excluir (plan de sensibilidad a la fuga).

    Returns:
        tuple: DataFrames de A y B ordenados por id_segmento.

    Raises:
        ValueError: Si A y B no cubren los mismos id_segmento o difieren en y_true.
    """
    dfs = {}
    for condicion in ("A", "B"):
        ruta = origen_colab / carpeta / "multisemilla" / f"predicciones_s{semilla}_{condicion}.csv"
        df = pd.read_csv(ruta).sort_values("id_segmento").reset_index(drop=True)
        df = df[~df["id_segmento"].isin(excluir)].reset_index(drop=True)
        manifiesto.append({"archivo": str(ruta), "sha256": sha256(ruta), "filas": len(df)})
        dfs[condicion] = df
    if not dfs["A"]["id_segmento"].equals(dfs["B"]["id_segmento"]):
        raise ValueError(f"{carpeta} s{semilla}: A y B no cubren los mismos id_segmento")
    if not dfs["A"]["y_true"].equals(dfs["B"]["y_true"]):
        raise ValueError(f"{carpeta} s{semilla}: y_true difiere entre A y B")
    return dfs["A"], dfs["B"]


def p_bilateral(distribucion):
    """Calcula el p bilateral con la misma regla que el script 14.

    Args:
        distribucion (numpy.ndarray): Distribución bootstrap del estadístico.

    Returns:
        float: Doble de la menor proporción de colas respecto de cero, acotado en 1.
    """
    return min(2 * min((distribucion <= 0).mean(), (distribucion >= 0).mean()), 1.0)


def holm(p_valores):
    """Aplica la corrección de Holm-Bonferroni.

    Args:
        p_valores (list[float]): p sin corregir.

    Returns:
        list[float]: p ajustados, en el mismo orden de entrada.
    """
    m = len(p_valores)
    orden = np.argsort(p_valores)
    ajustados = np.empty(m)
    acumulado = 0.0
    for rango, i in enumerate(orden):
        acumulado = max(acumulado, min((m - rango) * p_valores[i], 1.0))
        ajustados[i] = acumulado
    return ajustados.tolist()


def bootstrap_dos_niveles(y_true, preds_a, preds_b, n_replicas=N_REPLICAS, semilla=SEMILLA_BOOTSTRAP,
                          grupos=None):
    """Estima la distribución de la media de Δ remuestreando semillas y casos.

    En cada réplica se sortean primero las semillas (con reemplazo) y después los
    casos (con reemplazo); los mismos índices de casos se aplican a A, B y a todas
    las semillas sorteadas en esa réplica.

    Args:
        y_true (numpy.ndarray): Etiquetas reales, comunes a todas las semillas.
        preds_a (numpy.ndarray): Predicciones de A, forma (n_semillas, n_casos).
        preds_b (numpy.ndarray): Predicciones de B, forma (n_semillas, n_casos).
        n_replicas (int): Número de réplicas bootstrap.
        semilla (int): Semilla del generador aleatorio.
        grupos (numpy.ndarray | None): Si se indica, en el segundo nivel se sortean grupos
            (entrevistas) y sus casos entran juntos; si es None, se sortean casos, como antes.

    Returns:
        numpy.ndarray: Media de Δ F1-macro en cada réplica.
    """
    rng = np.random.default_rng(semilla)
    n_semillas, n_casos = preds_a.shape
    if grupos is not None:
        _, codigos = np.unique(grupos, return_inverse=True)
        miembros = [np.flatnonzero(codigos == g) for g in range(codigos.max() + 1)]
    medias = np.empty(n_replicas)
    for r in range(n_replicas):
        idx_semillas = rng.integers(0, n_semillas, size=n_semillas)
        if grupos is None:
            idx_casos = rng.integers(0, n_casos, size=n_casos)
        else:
            idx_casos = np.concatenate([miembros[g] for g in rng.integers(0, len(miembros), size=len(miembros))])
        yt = y_true[idx_casos]
        # Se calcula una vez por semilla distinta y se pondera por su frecuencia
        # en el sorteo: equivale a promediar sobre las 5 semillas sorteadas.
        unicas, conteos = np.unique(idx_semillas, return_counts=True)
        difs = [
            f1_score(yt, preds_b[s, idx_casos], average="macro", zero_division=0)
            - f1_score(yt, preds_a[s, idx_casos], average="macro", zero_division=0)
            for s in unicas
        ]
        medias[r] = np.dot(difs, conteos) / n_semillas
    return medias


def main():
    """Ejecuta las secciones a) a g) del plan multisemilla y guarda las tablas."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--origen-colab", required=True, type=Path,
                        help="copia local de MyDrive/working_paper/resultados_colab/")
    parser.add_argument("--excluir-fuga", action="store_true",
                        help="excluye el conjunto de fuga (plan del 2026-10-09); salidas en "
                             "outputs/multisemilla_sin_fuga/")
    parser.add_argument("--por-entrevista", action="store_true",
                        help="remuestrea entrevistas únicas por contenido en lugar de segmentos "
                             "(plan del 2026-11-02); salidas en outputs/multisemilla_por_entrevista*/")
    args = parser.parse_args()
    origen = args.origen_colab.expanduser().resolve()

    s14 = cargar_script_14()
    # Con --excluir-fuga se usan el conjunto de exclusión del 14, sus resultados sin fuga
    # y una carpeta de salida separada; sin la opción, todo queda como en el plan original.
    # --por-entrevista agrega el sufijo _por_entrevista a la carpeta y a los resultados del 14.
    excluir = s14.IDS_FUGA if args.excluir_fuga else frozenset()
    sufijo = ("_por_entrevista" if args.por_entrevista else "") + ("_sin_fuga" if args.excluir_fuga else "")
    out_dir = Path(f"outputs/multisemilla{sufijo}")
    resultados_principales = Path(f"outputs/bootstrap_resultados{sufijo}.csv")
    out_dir.mkdir(parents=True, exist_ok=True)
    if (s14.N_BOOTSTRAP, s14.SEMILLA) != (N_REPLICAS, SEMILLA_BOOTSTRAP):
        print(f"[AVISO] El script 14 usa {s14.N_BOOTSTRAP} remuestreos y semilla {s14.SEMILLA}; "
              f"el plan fija {N_REPLICAS} y {SEMILLA_BOOTSTRAP}.")

    manifiesto, filas_semilla, filas_agregado, descriptivos = [], [], [], []

    for modelo, carpeta in MODELOS.items():
        print(f"\n{'=' * 60}\n  {modelo.upper()}\n{'=' * 60}")
        y_true_ref, preds_a, preds_b = None, [], []

        # --- Paso a: bootstrap pareado por semilla (script 14 sin cambios) ---
        for semilla in SEMILLAS:
            df_a, df_b = cargar_predicciones(origen, carpeta, semilla, manifiesto, excluir)
            if y_true_ref is None:
                y_true_ref, ids_ref = df_a["y_true"].to_numpy(), df_a["id_segmento"]
                grupos = s14.grupos_por_entrevista(ids_ref) if args.por_entrevista else None
                if grupos is not None:
                    print(f"  [INFO] Remuestreo por entrevista: {len(np.unique(grupos))} entrevistas "
                          f"únicas para {len(ids_ref)} segmentos.")
            elif not (df_a["id_segmento"].equals(ids_ref) and np.array_equal(df_a["y_true"], y_true_ref)):
                raise ValueError(f"{modelo} s{semilla}: el conjunto de prueba difiere entre semillas")
            preds_a.append(df_a["y_pred"].to_numpy())
            preds_b.append(df_b["y_pred"].to_numpy())

            resultado, _ = s14.bootstrap_pareado(df_a, df_b, grupos=grupos)
            resultado.update({"modelo": modelo, "semilla": semilla})
            filas_semilla.append(resultado)
            print(f"  s{semilla:<5} Δ {resultado['diferencia_B_menos_A']:+.4f}  "
                  f"IC [{resultado['ci95_low']:+.4f}, {resultado['ci95_high']:+.4f}]  "
                  f"p {resultado['p_valor_aprox']:.4f}  EMD {resultado['emd_80']:.4f}")

        # --- Paso b: agregado descriptivo y prueba de signos ---
        difs = np.array([f["diferencia_B_menos_A"] for f in filas_semilla if f["modelo"] == modelo])
        n_b = int((difs > 0).sum())
        n_a = int((difs < 0).sum())
        p_signos = binomtest(n_b, n_b + n_a, 0.5, alternative="two-sided").pvalue if n_b + n_a else np.nan

        # --- Paso c: bootstrap de dos niveles ---
        print(f"  [INFO] Bootstrap de dos niveles: {N_REPLICAS} réplicas...")
        medias = bootstrap_dos_niveles(y_true_ref, np.vstack(preds_a), np.vstack(preds_b), grupos=grupos)
        ic_low, ic_high = np.percentile(medias, [100 * ALFA / 2, 100 * (1 - ALFA / 2)])

        filas_agregado.append({
            "modelo": modelo, "n_semillas": len(difs),
            "media_dif": difs.mean(), "de_dif": difs.std(ddof=1),
            "min_dif": difs.min(), "max_dif": difs.max(),
            "semillas_B_mayor": n_b, "semillas_A_mayor": n_a,
            "p_signos_binomial": p_signos,
            "ic95_low_2niveles": ic_low, "ic95_high_2niveles": ic_high,
            "p_2niveles": p_bilateral(medias),
        })

        # --- Paso f: Log Loss y PR-AUC, solo descriptivos ---
        ruta_detalle = origen / carpeta / "multisemilla" / "detalle_multisemilla.csv"
        manifiesto.append({"archivo": str(ruta_detalle), "sha256": sha256(ruta_detalle),
                           "filas": len(pd.read_csv(ruta_detalle))})
        detalle = pd.read_csv(ruta_detalle)
        detalle = detalle[detalle["semilla"].isin(SEMILLAS)]
        for condicion, grupo in detalle.groupby("condicion"):
            descriptivos.append({
                "modelo": modelo, "condicion": condicion, "n_semillas": len(grupo),
                "log_loss_media": grupo["log_loss"].mean(), "log_loss_de": grupo["log_loss"].std(ddof=1),
                "pr_auc_media": grupo["pr_auc_macro"].mean(), "pr_auc_de": grupo["pr_auc_macro"].std(ddof=1),
            })

    # --- Paso d: Holm sobre los 2 modelos (inferencia agregada) ---
    agregado = pd.DataFrame(filas_agregado)
    agregado["p_2niveles_holm"] = holm(agregado["p_2niveles"].tolist())

    # --- Paso e: corrida principal como referencia (no entra en el promedio) ---
    principal = pd.read_csv(resultados_principales).set_index("modelo")
    manifiesto.append({"archivo": str(resultados_principales.resolve()),
                       "sha256": sha256(resultados_principales), "filas": len(principal)})
    agregado["dif_corrida_principal"] = agregado["modelo"].map(principal["diferencia_B_menos_A"])

    # --- Paso g: criterio de robustez a la semilla ---
    # Con el p bilateral definido como en el script 14, p ajustado < alfa equivale a
    # que el IC percentil al nivel ajustado excluya cero.
    agregado["signo_consistente"] = agregado[["semillas_B_mayor", "semillas_A_mayor"]].max(axis=1) >= MIN_SEMILLAS_MISMO_SIGNO
    agregado["robusto_a_semilla"] = (agregado["p_2niveles_holm"] < ALFA) & agregado["signo_consistente"]

    # --- Paso d: Holm sobre las 4 configuraciones del análisis principal ---
    holm_principal = principal.reset_index()[["modelo", "diferencia_B_menos_A", "ci95_low",
                                               "ci95_high", "p_valor_aprox"]].copy()
    holm_principal["p_holm"] = holm(holm_principal["p_valor_aprox"].tolist())

    por_semilla = pd.DataFrame(filas_semilla)[
        ["modelo", "semilla", "f1_macro_A", "f1_macro_B", "diferencia_B_menos_A",
         "ci95_low", "ci95_high", "p_valor_aprox", "ee_bootstrap", "emd_80", "n_pares"]]
    por_semilla.to_csv(out_dir / "bootstrap_por_semilla.csv", index=False)
    agregado.to_csv(out_dir / "agregado_por_modelo.csv", index=False)
    holm_principal.to_csv(out_dir / "holm_configuraciones_principales.csv", index=False)
    pd.DataFrame(descriptivos).to_csv(out_dir / "descriptivo_logloss_prauc.csv", index=False)
    pd.DataFrame(manifiesto).to_csv(out_dir / "manifiesto_insumos_multisemilla.csv", index=False)

    print(f"\n{'=' * 60}\n  AGREGADO POR MODELO\n{'=' * 60}")
    print(agregado.to_string(index=False))
    print(f"\n{'=' * 60}\n  HOLM — CONFIGURACIONES PRINCIPALES\n{'=' * 60}")
    print(holm_principal.to_string(index=False))
    print("\n[INFO] Con 5 semillas, el menor p posible de la prueba de signos es 0.0625.")
    print("[INFO] Con 5 semillas, el remuestreo de nivel semilla es grueso.")
    print(f"[OK] Tablas guardadas en {out_dir}/")


if __name__ == "__main__":
    main()
