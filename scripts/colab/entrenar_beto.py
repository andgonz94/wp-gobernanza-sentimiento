"""Ajusta finamente BETO para clasificación de sentimiento en 5 clases.

Entrena y evalúa en ambas condiciones experimentales de forma secuencial. Usa
validación cruzada para decidir el número óptimo de épocas y aplica la misma
estrategia de evaluación que el baseline, para que los resultados sean
directamente comparables. Se ejecuta en Google Colab con GPU.

Entradas:
    Las 4 tablas exportadas por 12_exportar_tablas_para_colab.py.
Salidas:
    resultados_colab/beto/: resultado_{A,B}.csv, kfold_epocas_{A,B}.csv,
    matriz_confusion_{A,B}.csv, pr_auc_por_clase_{A,B}.csv,
    predicciones_{A,B}.csv, classification_report_{A,B}.txt y
    resumen_beto_A_vs_B.csv.
"""

# --- Solo en Colab: descomentar ---
# from google.colab import drive
# drive.mount('/content/drive')
# !pip install -q transformers datasets evaluate accelerate

import argparse
import inspect
import time
import numpy as np
import pandas as pd
import torch
from pathlib import Path
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold
from sklearn.metrics import (
    f1_score, classification_report, confusion_matrix,
    log_loss, average_precision_score,
)
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer, EarlyStoppingCallback,
)
from datasets import Dataset


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

# --- CONFIGURACIÓN ---

MODELO_CHECKPOINT = "dccuchile/bert-base-spanish-wwm-cased"
NOMBRE_MODELO     = "beto"

RUTA_DATOS  = Path("/content/drive/MyDrive/Working_Paper")
RUTA_SALIDA = Path("/content/drive/MyDrive/Working_Paper/resultados_colab") / NOMBRE_MODELO
RUTA_SALIDA.mkdir(parents=True, exist_ok=True)

MAX_LENGTH   = 128
SEMILLA      = 42
BATCH_SIZE   = 16
LR           = 2e-5
EPOCAS_MAX   = 4
WEIGHT_DECAY = 0.01
WARMUP_RATIO = 0.1

# K-fold para decidir el número óptimo de épocas (reemplaza el hold-out
# simple de validación como criterio de early stopping — ver justificación
# en la investigación sobre fiabilidad de F1-macro con validación pequeña
# y clases minoritarias de pocos ejemplos).
K_FOLDS = 5

# Parámetros del modo preview — reducidos para correr en minutos
PREVIEW_N_TRAIN = 40
PREVIEW_N_VAL   = 10
PREVIEW_N_TEST  = 10
PREVIEW_EPOCAS  = 1

ETIQUETAS = ["muy_positivo", "positivo", "levemente_positivo", "neutral", "negativo"]
ID2LABEL  = {i: e for i, e in enumerate(ETIQUETAS)}
LABEL2ID  = {e: i for i, e in enumerate(ETIQUETAS)}

torch.manual_seed(SEMILLA)
np.random.seed(SEMILLA)


# --- 1. CARGA Y CONSTRUCCIÓN DE CONJUNTOS (misma lógica que el baseline) ---

def cargar_todo():
    """Carga desde Drive las tablas exportadas necesarias para construir los conjuntos de entrenamiento.

    Returns:
        tuple: Asignación de split, segmentos reales, segmentos primarios y duplicados de la condición cruda, y segmentos de augmentation.
    """
    split   = pd.read_csv(RUTA_DATOS / "split_asignacion.csv")
    real_b  = pd.read_csv(RUTA_DATOS / "segmento_retroalimentacion.csv")
    cond_a  = pd.read_csv(RUTA_DATOS / "segmento_condicion_a.csv")
    aug     = pd.read_csv(RUTA_DATOS / "augmentation_segmentos.csv")

    cond_a_primaria = cond_a.drop_duplicates(subset="id_segmento_origen", keep="first")
    cond_a_dup_extra = cond_a[cond_a.duplicated(subset="id_segmento_origen", keep="first")]
    return split, real_b, cond_a_primaria, cond_a_dup_extra, aug


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
            row = idx_b.loc[sid]
            texto, id_reg, tipo_error = row["texto_segmento"], row["id_registro"], None
        else:
            row = idx_a.loc[sid]
            texto, id_reg, tipo_error = row["texto_segmento"], row["id_registro"], row["tipo_error_inyectado"]
        filas.append({"id_segmento": sid, "id_registro": id_reg, "texto": texto,
                       "tipo_error": tipo_error, "etiqueta": r["etiqueta_sentimiento"],
                       "split": r["split"]})
    df = pd.DataFrame(filas)

    sub_aug = split[(split["condicion"] == condicion) & (split["origen"] == "sintetico")]
    aug_idx = aug.set_index("id_aug")
    extra = []
    for _, r in sub_aug.iterrows():
        row_aug = aug_idx.loc[int(r["id_referencia"])]
        extra.append({"id_segmento": f"aug_{int(r['id_referencia'])}", "id_registro": row_aug["id_registro"],
                       "texto": row_aug["texto_segmento"], "tipo_error": row_aug["tipo_error_inyectado"],
                       "etiqueta": row_aug["etiqueta_sentimiento"], "split": "train"})
    if extra:
        df = pd.concat([df, pd.DataFrame(extra)], ignore_index=True)

    if condicion == "A":
        ids_train_real = set(sub_split[sub_split["split"] == "train"]["id_referencia"])
        dup_train = cond_a_dup_extra[cond_a_dup_extra["id_segmento_origen"].isin(ids_train_real)]
        extra_dup = []
        for _, r in dup_train.iterrows():
            etiqueta_origen = idx_b.loc[r["id_segmento_origen"], "etiqueta_sentimiento"]
            extra_dup.append({"id_segmento": f"dupA_{r['id_segmento_a']}", "id_registro": r["id_registro"],
                               "texto": r["texto_segmento"], "tipo_error": r["tipo_error_inyectado"],
                               "etiqueta": etiqueta_origen, "split": "train"})
        if extra_dup:
            df = pd.concat([df, pd.DataFrame(extra_dup)], ignore_index=True)

    return df


def columna_grupo(df):
    """Construye la columna de agrupación para splits agrupados por entrevista de origen.

    Args:
        df (pandas.DataFrame): Conjunto de datos con columnas id_registro e id_segmento.

    Returns:
        pandas.Series: Identificador de grupo por fila, como texto.
    """
    # Se usa id_segmento como grupo propio cuando no hay id_registro (p. ej.
    # filas sintéticas degradadas a nulo_id_sesion). Toda la columna se
    # fuerza a texto de forma consistente: mezclar floats (id_registro) con
    # strings (fallback) rompe el ordenamiento interno de scikit-learn
    # (TypeError: '<' not supported between 'str' and 'float').
    id_reg_str = df["id_registro"].apply(lambda x: str(int(x)) if pd.notna(x) else None)
    return id_reg_str.fillna(df["id_segmento"].astype(str))


def separar_validacion(df, frac_val=0.1, semilla=SEMILLA):
    """Extrae un conjunto de validación de train, agrupado por entrevista de origen.

    Método anterior, ya no se usa para BETO/RoBERTa (reemplazado por el
    k-fold de determinar_epocas_optimas_kfold); se mantiene por si se
    necesita un hold-out simple para comparación o depuración.

    Args:
        df (pandas.DataFrame): Conjunto de datos con columna split.
        frac_val (float): Fracción de train a reservar para validación.
        semilla (int): Semilla del generador de números aleatorios, para reproducibilidad.

    Returns:
        tuple: Conjuntos de train, validación y test.
    """
    train = df[df["split"] == "train"].copy()
    test  = df[df["split"] == "test"].copy()
    train["grupo"] = columna_grupo(train)

    gss = GroupShuffleSplit(n_splits=1, test_size=frac_val, random_state=semilla)
    idx_tr, idx_val = next(gss.split(train, groups=train["grupo"]))
    return train.iloc[idx_tr].reset_index(drop=True), train.iloc[idx_val].reset_index(drop=True), test


# --- 2. TOKENIZACIÓN Y DATASET DE HUGGING FACE ---

def a_hf_dataset(df, tokenizer):
    """Convierte un conjunto de datos en un Dataset de Hugging Face tokenizado.

    Args:
        df (pandas.DataFrame): Conjunto de datos con columnas texto y etiqueta.
        tokenizer: Tokenizador del modelo a utilizar.

    Returns:
        datasets.Dataset: Dataset tokenizado, listo para entrenamiento o evaluación.
    """
    textos = df["texto"].fillna("").tolist()
    etiquetas = [LABEL2ID[e] for e in df["etiqueta"]]
    enc = tokenizer(textos, truncation=True, padding="max_length", max_length=MAX_LENGTH)
    ds = Dataset.from_dict({**enc, "labels": etiquetas})
    return ds


def compute_metrics(eval_pred):
    """Calcula el F1-macro a partir de las predicciones de evaluación del Trainer.

    Args:
        eval_pred: Tupla (logits, etiquetas verdaderas) provista por el Trainer.

    Returns:
        dict: F1-macro de la evaluación.
    """
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    return {"f1_macro": f1_score(labels, preds, average="macro")}


class TrainerConPesos(Trainer):
    """Trainer con pérdida ponderada por clase, equivalente a class_weight='balanced' del baseline.

    Args:
        class_weights (torch.Tensor): Peso a aplicar a cada clase en la función de pérdida.
    """
    def __init__(self, class_weights, *args, **kwargs):
        """Inicializa el Trainer guardando los pesos de clase de la pérdida.

        Args:
            class_weights (torch.Tensor): Peso de cada clase en la entropía cruzada.
            *args: Argumentos posicionales de transformers.Trainer.
            **kwargs: Argumentos con nombre de transformers.Trainer.
        """
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        """Calcula la entropía cruzada ponderada por clase.

        Args:
            model (transformers.PreTrainedModel): Modelo en entrenamiento.
            inputs (dict): Lote tokenizado, con la clave labels.
            return_outputs (bool): Si es True, devuelve también las salidas del modelo.
            **kwargs: Argumentos adicionales que pasa el Trainer; no se usan.

        Returns:
            torch.Tensor | tuple: La pérdida, o (pérdida, salidas) si return_outputs es True.
        """
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        loss_fct = torch.nn.CrossEntropyLoss(
            weight=self.class_weights.to(logits.device))
        loss = loss_fct(logits, labels)
        return (loss, outputs) if return_outputs else loss


def calcular_pesos_clase(df_train):
    """Calcula el peso balanceado de cada clase para compensar el desbalance en el conjunto de entrenamiento.

    Args:
        df_train (pandas.DataFrame): Conjunto de entrenamiento con columna etiqueta.

    Returns:
        torch.Tensor: Peso por clase, en el orden de ETIQUETAS.
    """
    from sklearn.utils.class_weight import compute_class_weight
    y = df_train["etiqueta"].map(LABEL2ID).values
    clases_presentes = np.unique(y)
    # compute_class_weight exige que toda clase solicitada tenga al menos
    # 1 ejemplo en y. En muestras chicas (p. ej. modo preview) puede faltar
    # alguna clase por azar — se calculan pesos solo para las presentes y
    # se rellena con peso neutro (1.0) el resto, que de todas formas no
    # participa en el entrenamiento de este batch.
    pesos_presentes = compute_class_weight("balanced", classes=clases_presentes, y=y)
    pesos_completos = np.ones(len(ETIQUETAS), dtype=float)
    for c, p in zip(clases_presentes, pesos_presentes):
        pesos_completos[c] = p
    return torch.tensor(pesos_completos, dtype=torch.float)


# --- 2b. K-FOLD PARA DECIDIR EL NÚMERO ÓPTIMO DE ÉPOCAS ---
#
# Reemplaza el early stopping sobre un hold-out único de validación
# (80-112 ejemplos, con solo 3-4 casos de la clase minoritaria — ver
# justificación en la investigación de fiabilidad de F1-macro con
# validación pequeña). En su lugar:
#   1. Se parte TODO el train (sin apartar validación) en k=5 folds,
#      agrupados por id_registro y estratificados por etiqueta.
#   2. Por cada fold, se entrena un modelo desde cero hasta EPOCAS_MAX,
#      registrando el F1-macro de validación en CADA época (sin early
#      stopping dentro del fold, para observar la curva completa).
#   3. Se promedia el F1-macro por época a través de los 5 folds, y se
#      elige la época con mejor promedio como número de épocas final.
#   4. El modelo definitivo se reentrena UNA vez sobre el train COMPLETO
#      (sin apartar nada), con ese número fijo de épocas — así el modelo
#      final aprovecha el 100% de los datos disponibles, y el k-fold solo
#      se usó para decidir CUÁNDO detenerse, no para producir el modelo.
#
# Esto es más caro en tiempo (k entrenamientos cortos adicionales) pero
# resuelve la fragilidad de decidir el punto de parada con muy pocos
# ejemplos de la clase minoritaria en un único hold-out.

def determinar_epocas_optimas_kfold(df_train_full, k=K_FOLDS, epocas_max=EPOCAS_MAX,
                                     modo="completo"):
    """Determina el número óptimo de épocas de entrenamiento mediante validación cruzada agrupada.

    Args:
        df_train_full (pandas.DataFrame): Conjunto de entrenamiento completo, sin apartar validación.
        k (int): Número de folds de la validación cruzada.
        epocas_max (int): Número máximo de épocas a evaluar por fold.
        modo (str): "preview" para omitir el k-fold y usar un número fijo de épocas reducido, o "completo".

    Returns:
        tuple: Número óptimo de épocas y reporte de F1-macro promedio por época (o None en modo preview).
    """
    if modo == "preview":
        # En preview, el k-fold completo tomaría más tiempo que el resto
        # del pipeline junto — se omite y se usa 1 época fija, coherente
        # con el resto de los parámetros reducidos del modo preview.
        print("  [PREVIEW] K-fold de épocas omitido — se usa "
              f"{PREVIEW_EPOCAS} época(s) fija(s).")
        return PREVIEW_EPOCAS, None

    df_train_full = df_train_full.reset_index(drop=True)
    grupo = columna_grupo(df_train_full)
    y = df_train_full["etiqueta"].map(LABEL2ID).values

    sgkf = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=SEMILLA)

    matriz_f1 = np.full((k, epocas_max), np.nan)  # filas=fold, cols=época

    for fold_i, (idx_tr, idx_val) in enumerate(sgkf.split(df_train_full, y, groups=grupo)):
        print(f"\n  ── K-fold {fold_i + 1}/{k} ──")
        df_tr  = df_train_full.iloc[idx_tr].reset_index(drop=True)
        df_val = df_train_full.iloc[idx_val].reset_index(drop=True)

        tokenizer = AutoTokenizer.from_pretrained(MODELO_CHECKPOINT)
        model = AutoModelForSequenceClassification.from_pretrained(
            MODELO_CHECKPOINT, num_labels=len(ETIQUETAS), id2label=ID2LABEL, label2id=LABEL2ID)

        ds_tr  = a_hf_dataset(df_tr, tokenizer)
        ds_val = a_hf_dataset(df_val, tokenizer)
        pesos = calcular_pesos_clase(df_tr)

        args = TrainingArguments(
            output_dir=str(RUTA_SALIDA / f"kfold_tmp_{fold_i}"),
            eval_strategy="epoch", save_strategy="no",  # no guardar checkpoints de folds
            learning_rate=LR, per_device_train_batch_size=BATCH_SIZE,
            per_device_eval_batch_size=BATCH_SIZE, num_train_epochs=epocas_max,
            weight_decay=WEIGHT_DECAY, **_kwarg_warmup(WARMUP_RATIO),
            load_best_model_at_end=False,  # queremos la curva completa, no solo la mejor
            logging_steps=9999, report_to="none", seed=SEMILLA, disable_tqdm=True,
        )

        historial = []

        class RegistrarF1(TrainerConPesos):
            def evaluate(self, *a, **kw):
                """Evalúa con el Trainer base y guarda el F1-macro de la época en el historial.

                Args:
                    *a: Argumentos posicionales de Trainer.evaluate.
                    **kw: Argumentos con nombre de Trainer.evaluate.

                Returns:
                    dict: Métricas de evaluación devueltas por Trainer.evaluate.
                """
                m = super().evaluate(*a, **kw)
                historial.append(m.get("eval_f1_macro", np.nan))
                return m

        trainer = RegistrarF1(
            class_weights=pesos, model=model, args=args,
            train_dataset=ds_tr, eval_dataset=ds_val,
            compute_metrics=compute_metrics,
        )
        trainer.train()

        for e, f1 in enumerate(historial[:epocas_max]):
            matriz_f1[fold_i, e] = f1
        print(f"  Fold {fold_i + 1} — F1-macro por época: "
              f"{[round(v, 3) for v in historial[:epocas_max]]}")

    media_por_epoca = np.nanmean(matriz_f1, axis=0)
    std_por_epoca = np.nanstd(matriz_f1, axis=0)
    epoca_optima = int(np.nanargmax(media_por_epoca)) + 1  # 1-indexado

    print(f"\n  F1-macro promedio por época (across {k} folds):")
    for i, (m, s) in enumerate(zip(media_por_epoca, std_por_epoca), start=1):
        marca = "  ← elegida" if i == epoca_optima else ""
        print(f"    Época {i}: {m:.4f} ± {s:.4f}{marca}")

    reporte_kfold = pd.DataFrame({
        "epoca": range(1, epocas_max + 1),
        "f1_macro_promedio": media_por_epoca,
        "f1_macro_std": std_por_epoca,
    })
    return epoca_optima, reporte_kfold


# --- 3. ENTRENAMIENTO + EVALUACIÓN HÍBRIDA (misma estrategia del baseline) ---

def entrenar_condicion(condicion, split, real_b, cond_a_primaria, cond_a_dup_extra, aug,
                        ids_nulo_texto_compartido, modo="completo"):
    """Entrena y evalúa el modelo para una condición experimental, guardando resultados y checkpoints.

    Args:
        condicion (str): Condición experimental a entrenar ("A" o "B").
        split (pandas.DataFrame): Asignación de train/test por segmento u observación sintética.
        real_b (pandas.DataFrame): Segmentos reales de la condición gobernada.
        cond_a_primaria (pandas.DataFrame): Segmentos primarios de la condición cruda.
        cond_a_dup_extra (pandas.DataFrame): Filas duplicadas adicionales de la condición cruda.
        aug (pandas.DataFrame): Segmentos de augmentation.
        ids_nulo_texto_compartido (set): Identificadores a excluir del test comparable en ambas condiciones.
        modo (str): "preview" para una corrida reducida, o "completo".

    Returns:
        dict: Métricas resumen de la condición entrenada.
    """
    print(f"\n{'='*60}\n  {NOMBRE_MODELO.upper()} — Condición {condicion}"
          f"{'  [PREVIEW]' if modo == 'preview' else ''}\n{'='*60}")
    _t0 = time.time()

    df = construir_conjunto(split, real_b, cond_a_primaria, cond_a_dup_extra, aug, condicion)
    df_train_full = df[df["split"] == "train"].reset_index(drop=True)
    df_test = df[df["split"] == "test"].reset_index(drop=True)

    if modo == "preview":
        df_train_full = df_train_full.sample(min(PREVIEW_N_TRAIN, len(df_train_full)),
                                               random_state=SEMILLA).reset_index(drop=True)
        df_test = df_test.sample(min(PREVIEW_N_TEST, len(df_test)),
                                  random_state=SEMILLA).reset_index(drop=True)

    print(f"Train completo: {len(df_train_full)} | Test: {len(df_test)}")

    # --- Paso 1: k-fold para decidir el número óptimo de épocas ---
    epoca_optima, reporte_kfold = determinar_epocas_optimas_kfold(
        df_train_full, modo=modo)
    print(f"\n  → Épocas elegidas para el entrenamiento final: {epoca_optima}")
    if reporte_kfold is not None:
        reporte_kfold.to_csv(
            RUTA_SALIDA / f"kfold_epocas_{condicion}.csv", index=False)

    # --- Paso 2: reentrenar UNA VEZ sobre el train COMPLETO, sin apartar
    #    validación, con el número de épocas ya decidido (sin early
    #    stopping — el punto de parada ya se decidió por k-fold)
    tokenizer = AutoTokenizer.from_pretrained(MODELO_CHECKPOINT)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODELO_CHECKPOINT, num_labels=len(ETIQUETAS), id2label=ID2LABEL, label2id=LABEL2ID)

    ds_train_full = a_hf_dataset(df_train_full, tokenizer)
    pesos = calcular_pesos_clase(df_train_full)

    args = TrainingArguments(
        output_dir=str(RUTA_SALIDA / f"checkpoints_{condicion}"),
        eval_strategy="no", save_strategy="no",
        learning_rate=LR, per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE, num_train_epochs=epoca_optima,
        weight_decay=WEIGHT_DECAY, **_kwarg_warmup(WARMUP_RATIO),
        logging_steps=20, report_to="none", seed=SEMILLA,
    )

    trainer = TrainerConPesos(
        class_weights=pesos, model=model, args=args,
        train_dataset=ds_train_full, compute_metrics=compute_metrics,
    )
    trainer.train()

    # --- Evaluación híbrida (Opción 3): excluir nulo_texto del F1 comparable ---
    # IMPORTANTE: el conjunto de ids excluidos se calcula UNA SOLA VEZ fuera
    # de esta función (a partir de Condición A, la única que puede tener
    # nulo_texto) y se aplica IGUAL a ambas condiciones — así B y A se
    # evalúan siempre sobre el mismo N, sea cual sea el orden en que se
    # llame a esta función.
    ids_nulo = ids_nulo_texto_compartido
    df_test_comparable = df_test[~df_test["id_segmento"].isin(ids_nulo)].copy()

    ds_test = a_hf_dataset(df_test_comparable, tokenizer)
    pred_logits = trainer.predict(ds_test).predictions
    preds = np.argmax(pred_logits, axis=1)
    y_true = df_test_comparable["etiqueta"].map(LABEL2ID).values

    # --- Probabilidades (softmax) — necesarias para Log Loss y PR-AUC ---
    probs = torch.softmax(torch.tensor(pred_logits), dim=1).numpy()

    f1_macro = f1_score(y_true, preds, average="macro")
    reporte = classification_report(y_true, preds, target_names=ETIQUETAS, zero_division=0)

    # --- Matriz de confusión ---
    matriz_confusion = confusion_matrix(y_true, preds, labels=list(range(len(ETIQUETAS))))
    df_confusion = pd.DataFrame(matriz_confusion, index=ETIQUETAS, columns=ETIQUETAS)

    # --- Log Loss (calibración/confianza) — requiere que 'labels' cubra
    #    las 5 clases aunque alguna no aparezca en y_true, para que las
    #    columnas de 'probs' se interpreten correctamente
    try:
        logloss = log_loss(y_true, probs, labels=list(range(len(ETIQUETAS))))
    except ValueError as e:
        print(f"  Log Loss no calculable: {e}")
        logloss = np.nan

    # --- PR-AUC macro (one-vs-rest) ---
    try:
        from sklearn.preprocessing import label_binarize
        y_bin = label_binarize(y_true, classes=list(range(len(ETIQUETAS))))
        pr_auc_por_clase = []
        for c in range(len(ETIQUETAS)):
            if y_bin[:, c].sum() == 0:
                pr_auc_por_clase.append(np.nan)  # clase ausente en test comparable
            else:
                pr_auc_por_clase.append(average_precision_score(y_bin[:, c], probs[:, c]))
        pr_auc_macro = float(np.nanmean(pr_auc_por_clase))
    except Exception as e:
        print(f"  PR-AUC no calculable: {e}")
        pr_auc_por_clase = [np.nan] * len(ETIQUETAS)
        pr_auc_macro = np.nan

    print(f"\nF1-macro {NOMBRE_MODELO} Condición {condicion} (comparable): {f1_macro:.4f}")
    print(f"Log Loss: {logloss:.4f}" if not np.isnan(logloss) else "Log Loss: N/D")
    print(f"PR-AUC macro: {pr_auc_macro:.4f}")
    print(f"Casos excluidos por nulo_texto: {len(ids_nulo)} / {len(df_test)} "
          f"({len(ids_nulo)/len(df_test)*100:.1f}%)")
    print(reporte)
    print("\nMatriz de confusión:")
    print(df_confusion)

    # --- Guardar en Drive inmediatamente (checkpoint de progreso) ---
    tiempo_min = (time.time() - _t0) / 60
    resumen = {
        "modelo": NOMBRE_MODELO, "condicion": condicion, "modo": modo,
        "f1_macro": f1_macro, "log_loss": logloss, "pr_auc_macro": pr_auc_macro,
        "epocas_usadas": epoca_optima,
        "n_test_comparable": len(df_test_comparable), "n_excluidos_nulo_texto": len(ids_nulo),
        "n_train_full": len(df_train_full),
        "tiempo_minutos": round(tiempo_min, 2),
    }
    print(f"\nTiempo de esta condición (incluye k-fold + entrenamiento final): "
          f"{tiempo_min:.1f} minutos")
    sufijo = "_preview" if modo == "preview" else ""
    pd.DataFrame([resumen]).to_csv(RUTA_SALIDA / f"resultado_{condicion}{sufijo}.csv", index=False)
    with open(RUTA_SALIDA / f"classification_report_{condicion}{sufijo}.txt", "w") as f:
        f.write(reporte)
    df_confusion.to_csv(RUTA_SALIDA / f"matriz_confusion_{condicion}{sufijo}.csv")
    pd.DataFrame({"clase": ETIQUETAS, "pr_auc": pr_auc_por_clase}).to_csv(
        RUTA_SALIDA / f"pr_auc_por_clase_{condicion}{sufijo}.csv", index=False)
    # Probabilidades y predicciones crudas — insumo para el bootstrap
    # pareado de la Pregunta 4 (comparación A vs. B caso a caso)
    df_predicciones = df_test_comparable[["id_segmento"]].copy()
    df_predicciones["y_true"] = y_true
    df_predicciones["y_pred"] = preds
    for i, et in enumerate(ETIQUETAS):
        df_predicciones[f"prob_{et}"] = probs[:, i]
    df_predicciones.to_csv(RUTA_SALIDA / f"predicciones_{condicion}{sufijo}.csv", index=False)

    if modo != "preview":
        trainer.save_model(str(RUTA_SALIDA / f"modelo_final_{condicion}"))
    print(f"[OK] Guardado en {RUTA_SALIDA} (condición {condicion}{sufijo})")

    return resumen


def calcular_ids_nulo_texto_compartido(split, cond_a_primaria):
    """Identifica los segmentos de test cuyo texto quedó vacío en la condición cruda por el defecto nulo_texto.

    Este conjunto se excluye tanto de A como de B al evaluar, para que la
    comparación sea sobre el mismo N.

    Args:
        split (pandas.DataFrame): Asignación de train/test por segmento.
        cond_a_primaria (pandas.DataFrame): Segmentos primarios de la condición cruda.

    Returns:
        set: Identificadores de segmento a excluir del test comparable.
    """
    def es_nulo_texto(t):
        """Indica si el tipo de error inyectado incluye nulo_texto.

        Args:
            t (str | None): Valor de tipo_error_inyectado (tipos separados por coma).

        Returns:
            bool: True si t es una cadena que contiene nulo_texto.
        """
        return isinstance(t, str) and "nulo_texto" in t

    idx_a = cond_a_primaria.set_index("id_segmento_origen")
    test_ids_reales = split[
        (split["condicion"] == "A") & (split["origen"] == "real") & (split["split"] == "test")
    ]["id_referencia"].astype(int)

    ids_nulo = set()
    for sid in test_ids_reales:
        if sid in idx_a.index and es_nulo_texto(idx_a.loc[sid, "tipo_error_inyectado"]):
            ids_nulo.add(sid)
    return ids_nulo


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["preview", "completo"], default="completo")
    # parse_known_args() en vez de parse_args(): ignora argumentos que no
    # reconoce (como los que Jupyter/Colab inyecta automáticamente, p. ej.
    # "-f /root/.../kernel-....json") en vez de fallar con SystemExit.
    args_cli, _ = parser.parse_known_args()

    split, real_b, cond_a_primaria, cond_a_dup_extra, aug = cargar_todo()
    ids_nulo_compartido = calcular_ids_nulo_texto_compartido(split, cond_a_primaria)
    print(f"\nIds de test excluidos por nulo_texto (compartido entre A y B): "
          f"{len(ids_nulo_compartido)} → {sorted(ids_nulo_compartido)}")

    resultados = []
    for condicion in ["B", "A"]:  # B primero: es la referencia "limpia"
        r = entrenar_condicion(condicion, split, real_b, cond_a_primaria, cond_a_dup_extra, aug,
                                ids_nulo_texto_compartido=ids_nulo_compartido, modo=args_cli.modo)
        resultados.append(r)

    df_final = pd.DataFrame(resultados)
    sufijo = "_preview" if args_cli.modo == "preview" else ""
    df_final.to_csv(RUTA_SALIDA / f"resumen_beto_A_vs_B{sufijo}.csv", index=False)
    print("\n" + "="*60)
    print(f"RESUMEN FINAL — BETO{'  [PREVIEW]' if args_cli.modo == 'preview' else ''}")
    print(df_final[["condicion", "f1_macro", "n_excluidos_nulo_texto"]])
    if args_cli.modo == "preview":
        print("\nSi todo corrió sin errores, ejecuta con --modo completo (o sin argumento) "
              "para la corrida real.")