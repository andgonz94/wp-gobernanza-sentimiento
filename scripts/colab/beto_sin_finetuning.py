"""Evalúa BETO como extractor de representaciones congelado (linear probing).

Sin ajustar ninguno de sus pesos, entrena un clasificador simple sobre sus
embeddings, igual que en el baseline TF-IDF. La diferencia de F1-macro frente al
ajuste fino completo cuantifica cuánto aporta ese ajuste frente a usar el modelo
preentrenado tal cual. Se ejecuta en Google Colab.

Entradas:
    Las 4 tablas exportadas por 12_exportar_tablas_para_colab.py; funciones de
    entrenar_beto.py.
Salidas:
    resultados_colab/beto_sin_finetuning/: resultado_{A,B}.csv,
    matriz_confusion_{A,B}.csv, pr_auc_por_clase_{A,B}.csv,
    predicciones_{A,B}.csv, classification_report_{A,B}.txt y
    resumen_beto_sinfinetuning_A_vs_B.csv.
"""

import sys
sys.path.insert(0, ".")

import time
import numpy as np
import pandas as pd
import torch
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    f1_score, classification_report, confusion_matrix,
    log_loss, average_precision_score,
)
from sklearn.preprocessing import label_binarize
from transformers import AutoTokenizer, AutoModel

import entrenar_beto as eb  # reutiliza cargar_todo, construir_conjunto,
                              # calcular_ids_nulo_texto_compartido, ETIQUETAS,
                              # LABEL2ID, RUTA_DATOS, MODELO_CHECKPOINT

RUTA_SALIDA = Path("/content/drive/MyDrive/working_paper/resultados_colab/beto_sin_finetuning")
RUTA_SALIDA.mkdir(parents=True, exist_ok=True)

BATCH_SIZE_EMB = 16
MAX_LENGTH = eb.MAX_LENGTH
SEMILLA = eb.SEMILLA


# --- 1. EXTRACCIÓN DE EMBEDDINGS CONGELADOS ---

def extraer_embeddings(textos, tokenizer, modelo, device):
    """Extrae embeddings de oración de un modelo congelado mediante mean pooling sobre su última capa oculta.

    Args:
        textos (list): Textos a codificar.
        tokenizer: Tokenizador del modelo.
        modelo: Modelo congelado usado como extractor de representaciones.
        device (str): Dispositivo de cómputo ("cuda" o "cpu").

    Returns:
        numpy.ndarray: Matriz de embeddings, una fila por texto.
    """
    modelo.eval()
    embeddings = []
    with torch.no_grad():
        for i in range(0, len(textos), BATCH_SIZE_EMB):
            batch = [str(t) if pd.notna(t) else "" for t in textos[i:i + BATCH_SIZE_EMB]]
            enc = tokenizer(batch, truncation=True, padding=True,
                             max_length=MAX_LENGTH, return_tensors="pt").to(device)
            salida = modelo(**enc)
            ultima_capa = salida.last_hidden_state  # (batch, seq_len, hidden)
            mascara = enc["attention_mask"].unsqueeze(-1).expand(ultima_capa.size()).float()
            suma = torch.sum(ultima_capa * mascara, dim=1)
            conteo = torch.clamp(mascara.sum(dim=1), min=1e-9)
            emb_promedio = suma / conteo
            embeddings.append(emb_promedio.cpu().numpy())
    return np.vstack(embeddings)


# --- 2. MÉTRICAS (mismo criterio que el resto del pipeline) ---

def reordenar_probs(clf, probs):
    """Reordena las columnas de probabilidades para que coincidan con el orden estándar de etiquetas.

    Args:
        clf: Clasificador entrenado, con su propio orden interno de clases.
        probs: Matriz de probabilidades predichas por el clasificador.

    Returns:
        numpy.ndarray: Matriz de probabilidades reordenada según ETIQUETAS.
    """
    idx = [list(clf.classes_).index(et) for et in eb.ETIQUETAS]
    return probs[:, idx]


def calcular_metricas(y_true_str, y_pred_str, probs_ordenadas):
    """Calcula F1-macro, Log Loss, PR-AUC, matriz de confusión y reporte de clasificación.

    Args:
        y_true_str: Etiquetas verdaderas, como texto.
        y_pred_str: Etiquetas predichas, como texto.
        probs_ordenadas: Probabilidades predichas, en el orden estándar de etiquetas.

    Returns:
        tuple: F1-macro, Log Loss, PR-AUC macro, PR-AUC por clase, reporte de clasificación y matriz de confusión.
    """
    y_true_idx = [eb.ETIQUETAS.index(e) for e in y_true_str]
    y_pred_idx = [eb.ETIQUETAS.index(e) for e in y_pred_str]

    f1_macro = f1_score(y_true_idx, y_pred_idx, average="macro")
    reporte = classification_report(y_true_idx, y_pred_idx,
                                     target_names=eb.ETIQUETAS, zero_division=0)
    matriz = confusion_matrix(y_true_idx, y_pred_idx, labels=list(range(len(eb.ETIQUETAS))))

    try:
        logloss = log_loss(y_true_idx, probs_ordenadas, labels=list(range(len(eb.ETIQUETAS))))
    except ValueError:
        logloss = np.nan

    try:
        y_bin = label_binarize(y_true_idx, classes=list(range(len(eb.ETIQUETAS))))
        pr_auc_por_clase = [
            average_precision_score(y_bin[:, c], probs_ordenadas[:, c])
            if y_bin[:, c].sum() > 0 else np.nan
            for c in range(len(eb.ETIQUETAS))
        ]
        pr_auc_macro = float(np.nanmean(pr_auc_por_clase))
    except Exception:
        pr_auc_por_clase, pr_auc_macro = [np.nan] * len(eb.ETIQUETAS), np.nan

    return f1_macro, logloss, pr_auc_macro, pr_auc_por_clase, reporte, matriz


# --- 3. MAIN ---

def main():
    """Ejecuta la evaluación por linear probing en ambas condiciones experimentales.

    Returns:
        None
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Dispositivo: {device}")

    tokenizer = AutoTokenizer.from_pretrained(eb.MODELO_CHECKPOINT)
    modelo = AutoModel.from_pretrained(eb.MODELO_CHECKPOINT).to(device)
    for p in modelo.parameters():
        p.requires_grad = False  # congelado: ningún parámetro se actualiza

    split, real_b, cond_a_primaria, cond_a_dup_extra, aug = eb.cargar_todo()
    ids_nulo_compartido = eb.calcular_ids_nulo_texto_compartido(split, cond_a_primaria)
    print(f"Ids excluidos por nulo_texto (compartido A/B): {len(ids_nulo_compartido)}")

    resultados = []

    for condicion in ["B", "A"]:
        print(f"\n{'='*60}\n  BETO SIN FINE-TUNING (linear probing) — Condición {condicion}\n{'='*60}")
        _t0 = time.time()

        df = eb.construir_conjunto(split, real_b, cond_a_primaria, cond_a_dup_extra, aug, condicion)
        df_train = df[df["split"] == "train"].reset_index(drop=True)
        df_test = df[df["split"] == "test"].reset_index(drop=True)
        df_test_comparable = df_test[~df_test["id_segmento"].isin(ids_nulo_compartido)].reset_index(drop=True)

        print(f"Train: {len(df_train)} | Test comparable: {len(df_test_comparable)}")

        print("Extrayendo embeddings de train...")
        X_train = extraer_embeddings(df_train["texto"].tolist(), tokenizer, modelo, device)
        print("Extrayendo embeddings de test...")
        X_test = extraer_embeddings(df_test_comparable["texto"].tolist(), tokenizer, modelo, device)

        y_train = df_train["etiqueta"].values
        y_test = df_test_comparable["etiqueta"].values

        clf = LogisticRegression(class_weight="balanced", max_iter=2000, random_state=SEMILLA)
        clf.fit(X_train, y_train)

        preds = clf.predict(X_test)
        probs = reordenar_probs(clf, clf.predict_proba(X_test))

        f1_macro, logloss, pr_auc, pr_auc_por_clase, reporte, matriz = calcular_metricas(
            y_test, preds, probs)

        tiempo_min = (time.time() - _t0) / 60
        print(f"\nF1-macro (linear probing) Condición {condicion}: {f1_macro:.4f}")
        print(f"Log Loss: {logloss:.4f}  |  PR-AUC macro: {pr_auc:.4f}")
        print(reporte)
        print(f"Tiempo: {tiempo_min:.1f} minutos")

        resumen = {
            "modelo": "beto_sin_finetuning", "condicion": condicion,
            "f1_macro": f1_macro, "log_loss": logloss, "pr_auc_macro": pr_auc,
            "n_test_comparable": len(df_test_comparable), "n_train": len(df_train),
            "tiempo_minutos": round(tiempo_min, 2),
        }
        resultados.append(resumen)

        pd.DataFrame([resumen]).to_csv(RUTA_SALIDA / f"resultado_{condicion}.csv", index=False)
        with open(RUTA_SALIDA / f"classification_report_{condicion}.txt", "w") as f:
            f.write(reporte)
        pd.DataFrame(matriz, index=eb.ETIQUETAS, columns=eb.ETIQUETAS).to_csv(
            RUTA_SALIDA / f"matriz_confusion_{condicion}.csv")
        pd.DataFrame({"clase": eb.ETIQUETAS, "pr_auc": pr_auc_por_clase}).to_csv(
            RUTA_SALIDA / f"pr_auc_por_clase_{condicion}.csv", index=False)

        df_pred = df_test_comparable[["id_segmento"]].copy()
        df_pred["y_true"] = y_test
        df_pred["y_pred"] = preds
        for i, et in enumerate(eb.ETIQUETAS):
            df_pred[f"prob_{et}"] = probs[:, i]
        df_pred.to_csv(RUTA_SALIDA / f"predicciones_{condicion}.csv", index=False)

        print(f"[OK] Guardado en {RUTA_SALIDA} (condición {condicion})")

    df_final = pd.DataFrame(resultados)
    df_final.to_csv(RUTA_SALIDA / "resumen_beto_sinfinetuning_A_vs_B.csv", index=False)
    print("\n" + "=" * 60)
    print("RESUMEN FINAL — BETO SIN FINE-TUNING (linear probing)")
    print(df_final[["condicion", "f1_macro", "log_loss", "pr_auc_macro"]])
    print("\nCompara contra entrenar_beto.py (fine-tuning completo) para "
          "cuantificar el aporte del ajuste fino (Fase 7 vs Fase 6).")


if __name__ == "__main__":
    main()