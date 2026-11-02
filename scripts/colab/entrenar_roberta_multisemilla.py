"""Reentrena BERTIN con 5 semillas por condición para evaluar la estabilidad de la ordenación B frente a A.

Prueba dirigida a la anomalia de BERTIN (Reporte Metodologico, seccion 11.1
y 16): la reversion F1-macro(B) < F1-macro(A) observada con una unica
semilla (42) puede ser una propiedad estable de la arquitectura frente a
la gobernanza de datos, o puede ser un artefacto de esa inicializacion
especifica, dado el regimen de alta varianza ya documentado (norma de
gradiente 17-33 en la primera epoca, ausencia de pooler preentrenado).

Con una sola corrida por condicion no se puede distinguir entre esas dos
hipotesis. Este script reentrena BERTIN N veces por condicion, variando
UNICAMENTE la semilla, y deja fijo todo lo demas (arquitectura,
hiperparametros originales -- NO los que causaron el colapso de clase en
la seccion 11.1 --, y el numero de epocas ya determinado por el k-fold
original).

Decisiones de diseno respecto al script original (entrenar_roberta.py):

  1. NO se repite el k-fold de seleccion de epocas en cada semilla. Ya
     esta decidido (4 epocas para BERTIN, ver seccion 10.2 del Reporte).
     Repetirlo por semilla multiplicaria el costo de computo sin aportar
     a la pregunta de interes (estabilidad de la ORDENACION final B vs A).
     Si prefieren repetirlo de todas formas, hay un flag mas abajo
     (REPETIR_KFOLD_POR_SEMILLA) que lo activa a costo de mucho mas tiempo
     de Colab.

  2. La semilla se resetea (transformers.set_seed) INMEDIATAMENTE antes
     de cada from_pretrained() -- una vez por condicion, dentro del loop
     de semillas. Fijarla solo una vez al importar el modulo mezclaria
     el efecto de la semilla con el orden en que se entrenan B y A.

  3. Se reutilizan sin modificar, importandolas del script original:
     cargar_todo, construir_conjunto, columna_grupo, a_hf_dataset,
     compute_metrics, TrainerConPesos, calcular_pesos_clase,
     calcular_ids_nulo_texto_compartido. Esto minimiza el riesgo de que
     la variante multisemilla difiera silenciosamente del pipeline oficial
     en la carga o construccion de datos.

Entradas:
    Las tablas exportadas por 12_exportar_tablas_para_colab.py; funciones de
    entrenar_roberta.py (misma carpeta).
Salidas:
    resultados_colab/roberta_es/multisemilla/: predicciones_s<semilla>_{A,B}.csv,
    detalle_multisemilla.csv, detalle_multisemilla_parcial.csv y
    resumen_multisemilla.csv.
"""

import argparse
import inspect
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score, log_loss, average_precision_score
from sklearn.preprocessing import label_binarize
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, set_seed,
)

import entrenar_roberta as er  # script original, misma carpeta


def _kwarg_warmup(valor):
    """Elige el argumento de warmup que acepta la versión instalada de transformers.

    La v4.x usa warmup_ratio; la v5.0+ lo eliminó y fusionó su función en
    warmup_steps, que ahora acepta también un float < 1 con la misma semántica
    (guía oficial de migración a v5 de Hugging Face). Se detecta en tiempo de
    ejecución qué parámetro acepta TrainingArguments.

    Args:
        valor (float): Proporción de pasos de warmup.

    Returns:
        dict: {"warmup_ratio": valor} o {"warmup_steps": valor}, para desempaquetar
        en TrainingArguments.
    """
    parametros = inspect.signature(TrainingArguments.__init__).parameters
    if "warmup_ratio" in parametros:
        return {"warmup_ratio": valor}
    return {"warmup_steps": valor}

# --- CONFIGURACION ---

SEMILLAS_DEFAULT = [42, 123, 2024, 7, 99]

# Epocas ya determinadas por el k-fold original (seccion 10.2 del Reporte
# Metodologico: "para BERTIN se seleccionaron igualmente 4 epocas").
# Si cambia la epoca optima en su reporte, actualicen esta constante.
EPOCAS_FIJAS = 4

# Poner en True solo si quieren repetir el k-fold completo de seleccion
# de epocas en CADA semilla (mucho mas caro en tiempo de Colab).
REPETIR_KFOLD_POR_SEMILLA = False

RUTA_SALIDA_MULTI = er.RUTA_SALIDA / "multisemilla"
RUTA_SALIDA_MULTI.mkdir(parents=True, exist_ok=True)

PREVIEW_N_TRAIN = er.PREVIEW_N_TRAIN
PREVIEW_N_TEST = er.PREVIEW_N_TEST


# --- ENTRENAMIENTO DE UNA (SEMILLA, CONDICION) ---

def entrenar_una_semilla_condicion(condicion, semilla, split, real_b, cond_a_primaria,
                                    cond_a_dup_extra, aug, ids_nulo_texto_compartido,
                                    modo="completo"):
    """Entrena BERTIN para una condicion y una semilla especificas.

    Reutiliza construir_conjunto del script original tal cual; solo cambia
    la semilla de inicializacion del modelo y del Trainer, y fija el
    numero de epocas (sin repetir el k-fold), salvo que
    REPETIR_KFOLD_POR_SEMILLA este activo.

    Args:
        condicion (str): Condición experimental ("A" o "B").
        semilla (int): Semilla de inicialización del modelo y del Trainer.
        split (pandas.DataFrame): Asignación de train/test por segmento.
        real_b (pandas.DataFrame): Segmentos reales de la condición gobernada.
        cond_a_primaria (pandas.DataFrame): Segmentos primarios de la condición cruda.
        cond_a_dup_extra (pandas.DataFrame): Filas duplicadas adicionales de la condición cruda.
        aug (pandas.DataFrame): Segmentos sintéticos de augmentation.
        ids_nulo_texto_compartido (set): Ids de test excluidos por nulo_texto en ambas condiciones.
        modo (str): "completo" o "preview" (submuestra y 1 época).

    Returns:
        dict: metricas resumen de esta (semilla, condicion), mas la ruta
        del CSV de predicciones guardado (insumo directo para el bootstrap
        pareado de 14_bootstrap_pareado.py).
    """
    _t0 = time.time()
    print(f"\n{'-'*60}\n  Semilla {semilla} — Condicion {condicion}"
          f"{'  [PREVIEW]' if modo == 'preview' else ''}\n{'-'*60}")

    df = er.construir_conjunto(split, real_b, cond_a_primaria, cond_a_dup_extra, aug, condicion)
    df_train_full = df[df["split"] == "train"].reset_index(drop=True)
    df_test = df[df["split"] == "test"].reset_index(drop=True)

    if modo == "preview":
        df_train_full = df_train_full.sample(
            min(PREVIEW_N_TRAIN, len(df_train_full)), random_state=semilla
        ).reset_index(drop=True)
        df_test = df_test.sample(
            min(PREVIEW_N_TEST, len(df_test)), random_state=semilla
        ).reset_index(drop=True)

    epocas = 1 if modo == "preview" else EPOCAS_FIJAS
    if REPETIR_KFOLD_POR_SEMILLA and modo != "preview":
        # Camino caro: repetir tambien la seleccion de epocas por semilla.
        # Reutiliza la funcion original, pero esta usa SEMILLA global del
        # script importado para el StratifiedGroupKFold -- se sobreescribe
        # temporalmente para que el k-fold tambien varie con la semilla.
        er.SEMILLA = semilla
        epocas, _ = er.determinar_epocas_optimas_kfold(df_train_full, modo=modo)

    # --- Reset de semilla INMEDIATAMENTE antes de instanciar el modelo:
    #    aqui es donde se decide la inicializacion aleatoria de la cabeza
    #    de clasificacion (la parte con mas parametros aleatorios en
    #    BERTIN, seccion 2.6 del Reporte)
    set_seed(semilla)

    tokenizer = AutoTokenizer.from_pretrained(er.MODELO_CHECKPOINT)
    model = AutoModelForSequenceClassification.from_pretrained(
        er.MODELO_CHECKPOINT, num_labels=len(er.ETIQUETAS),
        id2label=er.ID2LABEL, label2id=er.LABEL2ID,
    )

    ds_train_full = er.a_hf_dataset(df_train_full, tokenizer)
    pesos = er.calcular_pesos_clase(df_train_full)

    args = TrainingArguments(
        output_dir=str(RUTA_SALIDA_MULTI / f"checkpoints_s{semilla}_{condicion}"),
        eval_strategy="no", save_strategy="no",
        learning_rate=er.LR, per_device_train_batch_size=er.BATCH_SIZE,
        per_device_eval_batch_size=er.BATCH_SIZE, num_train_epochs=epocas,
        weight_decay=er.WEIGHT_DECAY, **_kwarg_warmup(er.WARMUP_RATIO),
        logging_steps=9999, report_to="none", seed=semilla, disable_tqdm=True,
    )

    trainer = er.TrainerConPesos(
        class_weights=pesos, model=model, args=args,
        train_dataset=ds_train_full, compute_metrics=er.compute_metrics,
    )
    trainer.train()

    # --- Evaluacion, identica en criterio al script original: excluir
    #    nulo_texto, mismo N comparable entre A y B
    ids_nulo = ids_nulo_texto_compartido
    df_test_comparable = df_test[~df_test["id_segmento"].isin(ids_nulo)].copy()

    ds_test = er.a_hf_dataset(df_test_comparable, tokenizer)
    pred_logits = trainer.predict(ds_test).predictions
    preds = np.argmax(pred_logits, axis=1)
    y_true = df_test_comparable["etiqueta"].map(er.LABEL2ID).values
    probs = torch.softmax(torch.tensor(pred_logits), dim=1).numpy()

    f1_macro = f1_score(y_true, preds, average="macro")
    try:
        logloss = log_loss(y_true, probs, labels=list(range(len(er.ETIQUETAS))))
    except ValueError:
        logloss = np.nan
    try:
        y_bin = label_binarize(y_true, classes=list(range(len(er.ETIQUETAS))))
        pr_auc_por_clase = [
            average_precision_score(y_bin[:, c], probs[:, c]) if y_bin[:, c].sum() > 0 else np.nan
            for c in range(len(er.ETIQUETAS))
        ]
        pr_auc_macro = float(np.nanmean(pr_auc_por_clase))
    except Exception:
        pr_auc_macro = np.nan

    tiempo_min = (time.time() - _t0) / 60
    print(f"  F1-macro: {f1_macro:.4f}  |  Log Loss: {logloss:.4f}  |  "
          f"PR-AUC: {pr_auc_macro:.4f}  |  {tiempo_min:.1f} min")

    # --- Guardar predicciones -- mismo formato que espera
    #    14_bootstrap_pareado.py (id_segmento, y_true, y_pred)
    sufijo = "_preview" if modo == "preview" else ""
    ruta_pred = RUTA_SALIDA_MULTI / f"predicciones_s{semilla}_{condicion}{sufijo}.csv"
    df_predicciones = df_test_comparable[["id_segmento"]].copy()
    df_predicciones["y_true"] = y_true
    df_predicciones["y_pred"] = preds
    df_predicciones.to_csv(ruta_pred, index=False)

    return {
        "semilla": semilla, "condicion": condicion, "modo": modo,
        "f1_macro": f1_macro, "log_loss": logloss, "pr_auc_macro": pr_auc_macro,
        "epocas_usadas": epocas, "n_test_comparable": len(df_test_comparable),
        "tiempo_minutos": round(tiempo_min, 2), "ruta_predicciones": str(ruta_pred),
    }


# --- ORQUESTACION: TODAS LAS SEMILLAS ---

def main():
    """Entrena todas las semillas en ambas condiciones y consolida los resultados."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--semillas", type=str,
                         default=",".join(str(s) for s in SEMILLAS_DEFAULT),
                         help="Lista de semillas separadas por coma, ej: 42,123,2024,7,99")
    parser.add_argument("--modo", choices=["preview", "completo"], default="completo")
    args_cli, _ = parser.parse_known_args()
    semillas = [int(s.strip()) for s in args_cli.semillas.split(",")]

    print(f"Semillas a correr: {semillas}")
    print(f"Epocas fijas: {EPOCAS_FIJAS} "
          f"(k-fold {'SE REPITE' if REPETIR_KFOLD_POR_SEMILLA else 'NO se repite'} por semilla)")

    split, real_b, cond_a_primaria, cond_a_dup_extra, aug = er.cargar_todo()
    ids_nulo_compartido = er.calcular_ids_nulo_texto_compartido(split, cond_a_primaria)
    print(f"Ids de test excluidos por nulo_texto (compartido A/B): {len(ids_nulo_compartido)}")

    resultados = []
    ruta_parcial = RUTA_SALIDA_MULTI / f"detalle_multisemilla_parcial{'_preview' if args_cli.modo == 'preview' else ''}.csv"
    for semilla in semillas:
        for condicion in ["B", "A"]:
            r = entrenar_una_semilla_condicion(
                condicion, semilla, split, real_b, cond_a_primaria, cond_a_dup_extra, aug,
                ids_nulo_texto_compartido=ids_nulo_compartido, modo=args_cli.modo,
            )
            resultados.append(r)
        # --- Guardado incremental: si el script se corta en una semilla
        #    posterior, no se pierde el trabajo ya hecho en las anteriores
        pd.DataFrame(resultados).to_csv(ruta_parcial, index=False)
        print(f"  [checkpoint] Progreso guardado en {ruta_parcial} "
              f"({len(resultados)} corridas completadas)")

    df_detalle = pd.DataFrame(resultados)
    sufijo = "_preview" if args_cli.modo == "preview" else ""
    df_detalle.to_csv(RUTA_SALIDA_MULTI / f"detalle_multisemilla{sufijo}.csv", index=False)

    # --- Resumen consolidado: una fila por semilla ---
    resumen = (
        df_detalle.pivot(index="semilla", columns="condicion", values="f1_macro")
        .rename(columns={"A": "f1_macro_A", "B": "f1_macro_B"})
        .reset_index()
    )
    resumen["diferencia_B_menos_A"] = resumen["f1_macro_B"] - resumen["f1_macro_A"]
    resumen["favorece"] = np.where(resumen["diferencia_B_menos_A"] > 0, "B", "A")
    resumen.to_csv(RUTA_SALIDA_MULTI / f"resumen_multisemilla{sufijo}.csv", index=False)

    n_favorece_b = (resumen["favorece"] == "B").sum()
    n_total = len(resumen)

    print(f"\n{'='*60}\n  RESUMEN — {n_total} SEMILLAS\n{'='*60}")
    print(resumen.to_string(index=False))
    print(f"\n  Diferencia B-A -- media: {resumen['diferencia_B_menos_A'].mean():.4f}  "
          f"desv.est.: {resumen['diferencia_B_menos_A'].std():.4f}")
    print(f"  Semillas donde favorece B: {n_favorece_b}/{n_total}  |  "
          f"favorece A: {n_total - n_favorece_b}/{n_total}")

    if n_favorece_b == n_total or n_favorece_b == 0:
        print(f"\n  DIAGNOSTICO: la ordenacion B vs A fue ESTABLE en las {n_total} semillas.")
        print(f"  Esto respalda tratar el resultado de BERTIN como un hallazgo")
        print(f"  arquitectonico legitimo, no como varianza de entrenamiento.")
    else:
        print(f"\n  DIAGNOSTICO: la ordenacion B vs A CAMBIO de signo entre semillas.")
        print(f"  Esto respalda reportar BERTIN como resultado NO CONCLUYENTE por")
        print(f"  alta varianza de entrenamiento (Dodge et al., 2020), y excluirlo")
        print(f"  de las conclusiones direccionales generales del estudio.")

    print(f"\n  [OK] CSVs guardados en {RUTA_SALIDA_MULTI}/:")
    print(f"    detalle_multisemilla{sufijo}.csv")
    print(f"    resumen_multisemilla{sufijo}.csv")
    print(f"    predicciones_s<semilla>_<condicion>{sufijo}.csv (uno por semilla y condicion)")


if __name__ == "__main__":
    main()