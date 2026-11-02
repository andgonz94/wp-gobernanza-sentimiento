"""Entrena y evalúa el baseline TF-IDF con regresión logística en ambas condiciones.

Usa la partición agrupada ya construida y una estrategia explícita para el texto
totalmente perdido en la condición cruda, de forma que la comparación de
F1-macro entre condiciones sea sobre exactamente el mismo conjunto de casos.

Entradas:
    Tablas split_asignacion, segmento_retroalimentacion, segmento_condicion_a y
    augmentation_segmentos.
Salidas:
    outputs/resultados_baseline.csv, outputs/matriz_confusion_{A,B}.csv,
    outputs/pr_auc_por_clase_{A,B}.csv y outputs/predicciones_{A,B}_baseline.csv.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    f1_score, classification_report, confusion_matrix,
    log_loss, average_precision_score,
)
from sklearn.preprocessing import label_binarize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_engine

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)

# Mismo orden de clases usado en entrenar_beto.py / entrenar_roberta.py,
# para que matrices de confusión y métricas por clase sean directamente
# comparables entre los 3 modelos (LogisticRegression ordena sus clases
# alfabéticamente por defecto, que NO coincide con este orden).
ETIQUETAS = ["muy_positivo", "positivo", "levemente_positivo", "neutral", "negativo"]

# --- 1. CARGA DE DATOS ---

def cargar_datos():
    """Carga desde la base de datos el split de asignación y los datos de ambas condiciones.

    Returns:
        tuple: Asignación de split, segmentos reales, segmentos primarios y duplicados de la condición cruda, y segmentos de augmentation.
    """
    engine = get_engine()

    split = pd.read_sql("SELECT * FROM split_asignacion", engine)

    real_b = pd.read_sql("""
        SELECT id_segmento, texto_segmento, etiqueta_sentimiento
        FROM segmento_retroalimentacion
        WHERE flag_excluir = 0
    """, engine)

    # Condición A: nos quedamos con la PRIMERA fila por id_segmento_origen
    # (las filas adicionales de 'duplicado_exacto' se tratan aparte, como
    # refuerzo de entrenamiento, no como registros de evaluación)
    cond_a_full = pd.read_sql("""
        SELECT id_segmento_a, id_segmento_origen, texto_segmento, tipo_error_inyectado
        FROM segmento_condicion_a
        ORDER BY id_segmento_a
    """, engine)
    cond_a_primaria = cond_a_full.drop_duplicates(subset="id_segmento_origen", keep="first")
    cond_a_duplicados_extra = cond_a_full[
        cond_a_full.duplicated(subset="id_segmento_origen", keep="first")
    ]

    aug = pd.read_sql("""
        SELECT id_aug, id_segmento_origen, condicion, texto_segmento,
               etiqueta_sentimiento, tipo_error_inyectado
        FROM augmentation_segmentos
    """, engine)

    return split, real_b, cond_a_primaria, cond_a_duplicados_extra, aug


# --- 2. CONSTRUCCIÓN DE CONJUNTOS TRAIN/TEST POR CONDICIÓN ---

def construir_conjunto(split, real_b, cond_a_primaria, cond_a_dup_extra, aug, condicion):
    """Construye el conjunto de datos de entrenamiento y prueba para una condición experimental.

    Args:
        split (pandas.DataFrame): Asignación de train/test por segmento u observación sintética.
        real_b (pandas.DataFrame): Segmentos reales de la condición gobernada.
        cond_a_primaria (pandas.DataFrame): Segmentos primarios de la condición cruda.
        cond_a_dup_extra (pandas.DataFrame): Filas duplicadas adicionales de la condición cruda.
        aug (pandas.DataFrame): Segmentos de augmentation.
        condicion (str): Condición experimental a construir ("A" o "B").

    Returns:
        pandas.DataFrame: Conjunto de datos con texto, etiqueta y partición para la condición dada.
    """
    idx_a = cond_a_primaria.set_index("id_segmento_origen")
    idx_b = real_b.set_index("id_segmento")

    filas = []
    sub_split = split[(split["condicion"] == condicion) & (split["origen"] == "real")]

    for _, r in sub_split.iterrows():
        sid = int(r["id_referencia"])
        if condicion == "B":
            texto = idx_b.loc[sid, "texto_segmento"]
            tipo_error = None
        else:
            row_a = idx_a.loc[sid]
            texto = row_a["texto_segmento"]
            tipo_error = row_a["tipo_error_inyectado"]

        filas.append({
            "id_segmento": sid, "texto": texto, "tipo_error": tipo_error,
            "etiqueta": r["etiqueta_sentimiento"], "split": r["split"],
        })

    df = pd.DataFrame(filas)

    # --- Añadir augmentation (solo train, ya filtrado sin fuga en split_asignacion) ---
    sub_aug = split[(split["condicion"] == condicion) & (split["origen"] == "sintetico")]
    aug_idx = aug.set_index("id_aug")
    for _, r in sub_aug.iterrows():
        aid = int(r["id_referencia"])
        row_aug = aug_idx.loc[aid]
        df = pd.concat([df, pd.DataFrame([{
            "id_segmento": f"aug_{aid}", "texto": row_aug["texto_segmento"],
            "tipo_error": row_aug["tipo_error_inyectado"],
            "etiqueta": row_aug["etiqueta_sentimiento"], "split": "train",
        }])], ignore_index=True)

    # --- Añadir duplicados exactos de Condición A como refuerzo SOLO en train ---
    if condicion == "A":
        ids_train_real = set(sub_split[sub_split["split"] == "train"]["id_referencia"])
        dup_train = cond_a_dup_extra[cond_a_dup_extra["id_segmento_origen"].isin(ids_train_real)]
        for _, r in dup_train.iterrows():
            etiqueta_origen = idx_b.loc[r["id_segmento_origen"], "etiqueta_sentimiento"]
            df = pd.concat([df, pd.DataFrame([{
                "id_segmento": f"dupA_{r['id_segmento_a']}", "texto": r["texto_segmento"],
                "tipo_error": r["tipo_error_inyectado"], "etiqueta": etiqueta_origen,
                "split": "train",
            }])], ignore_index=True)

    return df


# --- 3. ENTRENAMIENTO Y EVALUACIÓN HÍBRIDA (Opción 3) ---

def es_nulo_texto(tipo_error):
    """Determina si un tipo de error inyectado corresponde a texto totalmente perdido.

    Args:
        tipo_error: Tipo o tipos de error inyectado sobre el registro.

    Returns:
        bool: True si el error incluye pérdida total del texto.
    """
    return isinstance(tipo_error, str) and "nulo_texto" in tipo_error


def reordenar_probs(clf, probs):
    """Reordena las columnas de probabilidades para que coincidan con el orden estándar de etiquetas.

    Args:
        clf: Clasificador entrenado, con su propio orden interno de clases.
        probs: Matriz de probabilidades predichas por el clasificador.

    Returns:
        numpy.ndarray: Matriz de probabilidades reordenada según ETIQUETAS.
    """
    idx = [list(clf.classes_).index(et) for et in ETIQUETAS]
    return probs[:, idx]


def calcular_metricas_extra(y_true, probs_ordenadas):
    """Calcula Log Loss y PR-AUC (macro y por clase) para un conjunto de predicciones.

    Args:
        y_true: Etiquetas verdaderas.
        probs_ordenadas: Probabilidades predichas, en el orden estándar de etiquetas.

    Returns:
        tuple: Log Loss, PR-AUC macro y PR-AUC por clase.
    """
    y_true_idx = [ETIQUETAS.index(e) for e in y_true]

    try:
        logloss = log_loss(y_true_idx, probs_ordenadas, labels=list(range(len(ETIQUETAS))))
    except ValueError as e:
        print(f"  Log Loss no calculable: {e}")
        logloss = np.nan

    try:
        y_bin = label_binarize(y_true_idx, classes=list(range(len(ETIQUETAS))))
        pr_auc_por_clase = []
        for c in range(len(ETIQUETAS)):
            if y_bin[:, c].sum() == 0:
                pr_auc_por_clase.append(np.nan)
            else:
                pr_auc_por_clase.append(
                    average_precision_score(y_bin[:, c], probs_ordenadas[:, c]))
        pr_auc_macro = float(np.nanmean(pr_auc_por_clase))
    except Exception as e:
        print(f"  PR-AUC no calculable: {e}")
        pr_auc_por_clase = [np.nan] * len(ETIQUETAS)
        pr_auc_macro = np.nan

    return logloss, pr_auc_macro, pr_auc_por_clase


def entrenar_y_evaluar(df_b, df_a):
    """Entrena un clasificador por condición y evalúa ambos sobre un conjunto de test comparable.

    Args:
        df_b (pandas.DataFrame): Conjunto de datos de la condición gobernada.
        df_a (pandas.DataFrame): Conjunto de datos de la condición cruda.

    Returns:
        dict: Métricas de evaluación y predicciones detalladas para ambas condiciones.
    """
    # --- Vectorizador único, ajustado sobre TRAIN de B (contenido de referencia) ---
    train_b = df_b[df_b["split"] == "train"].copy()
    train_b["texto"] = train_b["texto"].fillna("")
    vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), min_df=2)
    Xtr_b = vectorizer.fit_transform(train_b["texto"])
    ytr_b = train_b["etiqueta"]

    clf_b = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    clf_b.fit(Xtr_b, ytr_b)

    # --- Entrenar un clasificador separado para A, mismo vectorizador ---
    train_a = df_a[df_a["split"] == "train"].copy()
    train_a["texto"] = train_a["texto"].fillna("")  # nulo_texto -> "" en train también
    Xtr_a = vectorizer.transform(train_a["texto"])
    ytr_a = train_a["etiqueta"]

    clf_a = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    clf_a.fit(Xtr_a, ytr_a)

    # --- TEST — aplicar estrategia híbrida ---
    test_a_full = df_a[df_a["split"] == "test"].copy()
    ids_nulo_texto = set(
        test_a_full[test_a_full["tipo_error"].apply(es_nulo_texto)]["id_segmento"]
    )
    n_test_a_total = len(test_a_full)
    n_perdidos = len(ids_nulo_texto)
    tasa_perdida = n_perdidos / n_test_a_total if n_test_a_total else 0

    # Subconjunto "comparable": excluye nulo_texto, en AMBAS condiciones,
    # sobre el MISMO conjunto de id_segmento para comparación justa.
    test_a_comparable = test_a_full[~test_a_full["id_segmento"].isin(ids_nulo_texto)].copy()
    ids_comparables = set(test_a_comparable["id_segmento"])

    test_b_full = df_b[df_b["split"] == "test"].copy()
    test_b_comparable = test_b_full[test_b_full["id_segmento"].isin(ids_comparables)].copy()

    test_a_comparable["texto"] = test_a_comparable["texto"].fillna("")
    test_b_comparable["texto"] = test_b_comparable["texto"].fillna("")

    Xte_a = vectorizer.transform(test_a_comparable["texto"])
    Xte_b = vectorizer.transform(test_b_comparable["texto"])

    pred_a = clf_a.predict(Xte_a)
    pred_b = clf_b.predict(Xte_b)

    # --- Probabilidades (necesarias para Log Loss y PR-AUC) ---
    probs_a = reordenar_probs(clf_a, clf_a.predict_proba(Xte_a))
    probs_b = reordenar_probs(clf_b, clf_b.predict_proba(Xte_b))

    f1_a = f1_score(test_a_comparable["etiqueta"], pred_a, average="macro")
    f1_b = f1_score(test_b_comparable["etiqueta"], pred_b, average="macro")

    logloss_a, pr_auc_a, pr_auc_por_clase_a = calcular_metricas_extra(
        test_a_comparable["etiqueta"].values, probs_a)
    logloss_b, pr_auc_b, pr_auc_por_clase_b = calcular_metricas_extra(
        test_b_comparable["etiqueta"].values, probs_b)

    # --- Matrices de confusión, mismo orden de clases que BETO/RoBERTa ---
    matriz_a = confusion_matrix(test_a_comparable["etiqueta"], pred_a, labels=ETIQUETAS)
    matriz_b = confusion_matrix(test_b_comparable["etiqueta"], pred_b, labels=ETIQUETAS)
    df_matriz_a = pd.DataFrame(matriz_a, index=ETIQUETAS, columns=ETIQUETAS)
    df_matriz_b = pd.DataFrame(matriz_b, index=ETIQUETAS, columns=ETIQUETAS)

    print("\n" + "═" * 60)
    print("  RESULTADOS — BASELINE (TF-IDF + Regresión Logística)")
    print("═" * 60)
    print(f"\n  Tamaño test Condición B (comparable): {len(test_b_comparable)}")
    print(f"  Tamaño test Condición A (comparable): {len(test_a_comparable)}")
    print(f"  Registros de Condición A EXCLUIDOS del F1 por nulo_texto: {n_perdidos}")
    print(f"  Tasa de pérdida de información en test A: {tasa_perdida*100:.1f}%")

    print(f"\n  F1-macro   Condición B: {f1_b:.4f}  |  Condición A: {f1_a:.4f}"
          f"  (diferencia B-A: {f1_b - f1_a:.4f})")
    print(f"  Log Loss   Condición B: {logloss_b:.4f}  |  Condición A: {logloss_a:.4f}")
    print(f"  PR-AUC     Condición B: {pr_auc_b:.4f}  |  Condición A: {pr_auc_a:.4f}")

    print("\n  Classification report — Condición B:")
    print(classification_report(test_b_comparable["etiqueta"], pred_b, zero_division=0))
    print("\n  Classification report — Condición A:")
    print(classification_report(test_a_comparable["etiqueta"], pred_a, zero_division=0))

    print("\n  Matriz de confusión — Condición B:")
    print(df_matriz_b)
    print("\n  Matriz de confusión — Condición A:")
    print(df_matriz_a)

    # --- Guardar resultados detallados ---
    # --- Métrica complementaria: costo operativo total de A ---
    # Sobre el TEST COMPLETO de A (183, incluyendo los nulo_texto),
    # los casos nulo_texto se cuentan como fallo garantizado (predicción
    # forzada a incorrecta). Esto captura el costo real de "no poder
    # clasificar" en vez de simplemente excluirlo de la métrica.
    correctas_a = (pred_a == test_a_comparable["etiqueta"].values).sum()
    total_a_operativo = len(test_a_comparable) + n_perdidos
    accuracy_operativa_a = correctas_a / total_a_operativo
    print(f"\n  Accuracy operativa de A (nulo_texto contado como fallo): "
          f"{accuracy_operativa_a:.4f}  (sobre {total_a_operativo} casos, "
          f"vs. accuracy estándar {(pred_a==test_a_comparable['etiqueta'].values).mean():.4f} "
          f"sobre {len(test_a_comparable)} comparables)")

    resumen = pd.DataFrame([{
        "modelo": "baseline_tfidf_logreg",
        "f1_macro_B": f1_b, "f1_macro_A": f1_a,
        "diferencia_B_menos_A": f1_b - f1_a,
        "log_loss_B": logloss_b, "log_loss_A": logloss_a,
        "pr_auc_macro_B": pr_auc_b, "pr_auc_macro_A": pr_auc_a,
        "n_test_comparable": len(test_b_comparable),
        "n_perdidos_A_nulo_texto": n_perdidos,
        "tasa_perdida_A": tasa_perdida,
        "accuracy_operativa_A": accuracy_operativa_a,
    }])
    resumen.to_csv(OUT / "resultados_baseline.csv", index=False)

    # --- Archivos auxiliares, mismo naming que entrenar_beto.py / entrenar_roberta.py ---
    df_matriz_b.to_csv(OUT / "matriz_confusion_B.csv")
    df_matriz_a.to_csv(OUT / "matriz_confusion_A.csv")
    pd.DataFrame({"clase": ETIQUETAS, "pr_auc": pr_auc_por_clase_b}).to_csv(
        OUT / "pr_auc_por_clase_B.csv", index=False)
    pd.DataFrame({"clase": ETIQUETAS, "pr_auc": pr_auc_por_clase_a}).to_csv(
        OUT / "pr_auc_por_clase_A.csv", index=False)

    # Predicciones + probabilidades por caso — mismo formato que los
    # scripts de transformers, insumo para el bootstrap pareado (Pregunta 4)
    df_pred_b = test_b_comparable[["id_segmento"]].copy()
    df_pred_b["y_true"] = test_b_comparable["etiqueta"].values
    df_pred_b["y_pred"] = pred_b
    for i, et in enumerate(ETIQUETAS):
        df_pred_b[f"prob_{et}"] = probs_b[:, i]
    df_pred_b.to_csv(OUT / "predicciones_B_baseline.csv", index=False)

    df_pred_a = test_a_comparable[["id_segmento"]].copy()
    df_pred_a["y_true"] = test_a_comparable["etiqueta"].values
    df_pred_a["y_pred"] = pred_a
    for i, et in enumerate(ETIQUETAS):
        df_pred_a[f"prob_{et}"] = probs_a[:, i]
    df_pred_a.to_csv(OUT / "predicciones_A_baseline.csv", index=False)

    print(f"\n  [OK] CSVs guardados en outputs/: resultados_baseline.csv, "
          f"matriz_confusion_{{A,B}}.csv, pr_auc_por_clase_{{A,B}}.csv, "
          f"predicciones_{{A,B}}_baseline.csv")

    return {
        "f1_b": f1_b, "f1_a": f1_a, "tasa_perdida_a": tasa_perdida,
        "logloss_b": logloss_b, "logloss_a": logloss_a,
        "pr_auc_b": pr_auc_b, "pr_auc_a": pr_auc_a,
        "test_a_comparable": test_a_comparable, "pred_a": pred_a,
        "test_b_comparable": test_b_comparable, "pred_b": pred_b,
    }


if __name__ == "__main__":
    split, real_b, cond_a_primaria, cond_a_dup_extra, aug = cargar_datos()

    print(f"Filas en split_asignacion: {len(split)}")
    print(f"Segmentos reales B: {len(real_b)}")
    print(f"Segmentos únicos Condición A (primaria): {len(cond_a_primaria)}")
    print(f"Filas duplicadas extra de Condición A: {len(cond_a_dup_extra)}")
    print(f"Filas de augmentation: {len(aug)}")

    df_b = construir_conjunto(split, real_b, cond_a_primaria, cond_a_dup_extra, aug, "B")
    df_a = construir_conjunto(split, real_b, cond_a_primaria, cond_a_dup_extra, aug, "A")

    print(f"\nConjunto B — train: {len(df_b[df_b['split']=='train'])}, "
          f"test: {len(df_b[df_b['split']=='test'])}")
    print(f"Conjunto A — train: {len(df_a[df_a['split']=='train'])}, "
          f"test: {len(df_a[df_a['split']=='test'])}")

    resultados = entrenar_y_evaluar(df_b, df_a)