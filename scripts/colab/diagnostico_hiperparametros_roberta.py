"""Compara dos configuraciones de hiperparámetros de RoBERTa-es en un mismo fold.

Diagnostica si un ajuste al learning rate y al recorte de gradiente reduce la
inestabilidad de entrenamiento observada. Imprime grad_norm y F1-macro por época
de ambas configuraciones, lado a lado. Se ejecuta en Google Colab.

Entradas:
    Las tablas exportadas por 12_exportar_tablas_para_colab.py; funciones de
    entrenar_roberta.py.
Salidas:
    Solo salida en consola.
"""

import sys
sys.path.insert(0, ".")  # asume que entrenar_roberta.py está en el mismo directorio

import numpy as np
import torch
from sklearn.model_selection import StratifiedGroupKFold
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments,
)

# Reutiliza funciones y datos ya definidos en entrenar_roberta.py
import entrenar_roberta as er

MODELO_CHECKPOINT = "bertin-project/bertin-roberta-base-spanish"
EPOCAS_PRUEBA = 4


def correr_config(df_tr, df_val, lr, max_grad_norm, etiqueta_config):
    """Entrena una configuración de hiperparámetros sobre un fold y registra F1-macro y grad_norm por época.

    Args:
        df_tr (pandas.DataFrame): Conjunto de entrenamiento del fold.
        df_val (pandas.DataFrame): Conjunto de validación del fold.
        lr (float): Tasa de aprendizaje a usar.
        max_grad_norm (float): Valor máximo de recorte de gradiente.
        etiqueta_config (str): Nombre descriptivo de la configuración, para el reporte.

    Returns:
        tuple: Historial de F1-macro por época y lista de valores de grad_norm registrados.
    """
    print(f"\n{'─'*55}\n  Configuración: {etiqueta_config} "
          f"(LR={lr}, max_grad_norm={max_grad_norm})\n{'─'*55}")

    tokenizer = AutoTokenizer.from_pretrained(MODELO_CHECKPOINT)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODELO_CHECKPOINT, num_labels=len(er.ETIQUETAS),
        id2label=er.ID2LABEL, label2id=er.LABEL2ID)

    ds_tr = er.a_hf_dataset(df_tr, tokenizer)
    ds_val = er.a_hf_dataset(df_val, tokenizer)
    pesos = er.calcular_pesos_clase(df_tr)

    args = TrainingArguments(
        output_dir="/tmp/diagnostico_roberta",
        eval_strategy="epoch", save_strategy="no",
        learning_rate=lr, per_device_train_batch_size=er.BATCH_SIZE,
        per_device_eval_batch_size=er.BATCH_SIZE, num_train_epochs=EPOCAS_PRUEBA,
        weight_decay=er.WEIGHT_DECAY, warmup_ratio=er.WARMUP_RATIO,
        max_grad_norm=max_grad_norm,
        logging_steps=5,  # frecuente, para tener suficientes puntos de grad_norm
        report_to="none", seed=er.SEMILLA, disable_tqdm=True,
    )

    historial_f1 = []

    class RegistrarF1(er.TrainerConPesos):
        def evaluate(self, *a, **kw):
            """Evalúa con el Trainer base y guarda el F1-macro de la época en el historial.

            Args:
                *a: Argumentos posicionales de Trainer.evaluate.
                **kw: Argumentos con nombre de Trainer.evaluate.

            Returns:
                dict: Métricas de evaluación devueltas por Trainer.evaluate.
            """
            m = super().evaluate(*a, **kw)
            historial_f1.append(m.get("eval_f1_macro", np.nan))
            return m

    trainer = RegistrarF1(
        class_weights=pesos, model=model, args=args,
        train_dataset=ds_tr, eval_dataset=ds_val,
        compute_metrics=er.compute_metrics,
    )
    trainer.train()

    # grad_norm ya viene en el log_history nativo del Trainer (el mismo
    # valor que se ve impreso en los logs de entrenamiento normales) —
    # más fiable que intentar recalcularlo manualmente.
    grad_norms = [
        entry["grad_norm"] for entry in trainer.state.log_history
        if "grad_norm" in entry
    ]

    print(f"\n  F1-macro por época: {[round(v, 3) for v in historial_f1]}")
    if grad_norms:
        print(f"  grad_norm — media: {np.mean(grad_norms):.2f}  "
              f"máx: {np.max(grad_norms):.2f}  "
              f"p90: {np.percentile(grad_norms, 90):.2f}  "
              f"(n={len(grad_norms)} mediciones)")
    return historial_f1, grad_norms


if __name__ == "__main__":
    split, real_b, cond_a_primaria, cond_a_dup_extra, aug = er.cargar_todo()
    df = er.construir_conjunto(split, real_b, cond_a_primaria, cond_a_dup_extra, aug, "B")
    df_train_full = df[df["split"] == "train"].reset_index(drop=True)

    grupo = er.columna_grupo(df_train_full)
    y = df_train_full["etiqueta"].map(er.LABEL2ID).values
    sgkf = StratifiedGroupKFold(n_splits=er.K_FOLDS, shuffle=True, random_state=er.SEMILLA)
    idx_tr, idx_val = next(sgkf.split(df_train_full, y, groups=grupo))
    df_tr = df_train_full.iloc[idx_tr].reset_index(drop=True)
    df_val = df_train_full.iloc[idx_val].reset_index(drop=True)

    print(f"Fold 1 aislado — Train: {len(df_tr)} | Val: {len(df_val)}")

    f1_original, gn_original = correr_config(df_tr, df_val, lr=2e-5, max_grad_norm=1.0,
                                               etiqueta_config="ORIGINAL")
    f1_ajustada, gn_ajustada = correr_config(df_tr, df_val, lr=1e-5, max_grad_norm=0.5,
                                               etiqueta_config="AJUSTADA")

    print(f"\n{'='*55}\n  COMPARACIÓN\n{'='*55}")
    print(f"  F1 época 1 — Original: {f1_original[0]:.3f}  |  Ajustada: {f1_ajustada[0]:.3f}")
    print(f"  F1 época final — Original: {f1_original[-1]:.3f}  |  Ajustada: {f1_ajustada[-1]:.3f}")
    print(f"  grad_norm medio — Original: {np.mean(gn_original):.2f}  |  "
          f"Ajustada: {np.mean(gn_ajustada):.2f}")
    print(f"  grad_norm máximo — Original: {np.max(gn_original):.2f}  |  "
          f"Ajustada: {np.max(gn_ajustada):.2f}")