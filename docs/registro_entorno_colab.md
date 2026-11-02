# Registro del entorno y de las ejecuciones en Colab

Elaborado el 2026-10-08 a partir de las salidas de `scripts/test_colab.ipynb` antes de
limpiarlas, de las fechas de los archivos en `MyDrive/Working_Paper/` y de los `.pyc` de
`MyDrive/Working_Paper/__pycache__/`. Las horas de `nvidia-smi` están en UTC (Colab); las
de los archivos de Drive, en hora de Colombia (UTC−5). Lo inferido se marca `[VERIFICAR]`.

## 1. Fuentes

| Fuente | Contenido |
|---|---|
| `test_colab.ipynb` en `788f4ff` (commit inicial, 2026-08-21) | 12 celdas; 8 con salida |
| `test_colab.ipynb` en `0c8b4cb` (versión en staging, incluida por error) | 17 celdas; 10 con salida |
| `test_colab.ipynb` en `5cc821d` (copia de trabajo, registrada el 2026-10-08) | 24 celdas; 5 con salida |
| `__pycache__/*.pyc` en Drive | Tamaño y fecha del código fuente que importó cada sesión |
| Archivos de `resultados_colab/` | Fechas de escritura de cada salida |

Un notebook guarda la última salida de cada celda; las celdas de una misma versión pueden
venir de **sesiones distintas** (los contadores de ejecución se reinician en cada sesión
y aparecen repetidos). Las salidas completas siguen disponibles en el historial de Git
en esos tres commits.

## 2. Entorno común a todas las sesiones con salida

| Dato | Valor | Fuente |
|---|---|---|
| GPU | Tesla T4 | `nvidia-smi` (las tres versiones) |
| Driver NVIDIA | 580.82.07 | `nvidia-smi` |
| CUDA | 13.0 | `nvidia-smi` |
| sentencepiece | 0.2.2 | `pip show sentencepiece` (`788f4ff`, `0c8b4cb`) |

## 3. Sesiones identificadas

| Sesión | Fecha | Evidencia | Qué se ejecutó | Datos de entorno |
|---|---|---|---|---|
| 1 | 2026-08-12 y 13 | `.pyc` de Python 3.12: `entrenar_beto.py` de 25.213 bytes (2026-08-12 14:31) y `entrenar_roberta.py` de 25.264 bytes (15:09); `resultado_{A,B}.csv` de BETO (12 de agosto, 14:48-14:57) y de RoBERTa (13 de agosto, 21:22-21:29), conservados en `Working_paper/outputs/graficos_input/` | **Primera corrida principal** de BETO y RoBERTa | Python 3.12. Versión de transformers no registrada `[VERIFICAR]`. Sus salidas de consola no se conservaron |
| 2 | 2026-08-18/19 | `nvidia-smi` 2026-08-19 02:22 UTC (18 de agosto, 21:22 en Colombia), versión `788f4ff` | `beto_sin_finetuning.py` (salidas en Drive a las 21:37), `diagnostico_tokenizacion.py`; en la misma versión del notebook, RoBERTa preview y completo (posiblemente de otra sesión) | Aviso "warmup_ratio is deprecated and will be removed in v5.2" en la corrida de RoBERTa: transformers 5.0 o 5.1 en ese momento |
| 3 | 2026-08-26/27 | Versión `0c8b4cb`; contadores consecutivos 9, 10, 14, 17 y 19; salidas de RoBERTa en Drive del 27 de agosto, 00:32-00:41 (principal) y 01:19-01:31 (multisemilla) | `pip install -U transformers ...` (contador 9), `print(transformers.__version__)` (10), `entrenar_roberta.py --modo completo` (17), `entrenar_roberta_multisemilla.py` (19). Antes, en una sesión con transformers ≥ 5.2, `entrenar_beto.py --modo preview` falló con "unexpected keyword argument 'warmup_ratio'" (contador 3) | **transformers 5.16.1**, impreso justo antes de las corridas de RoBERTa. Python 3.13 (`.pyc` de `entrenar_roberta.py`, 29.085 bytes, 27 de agosto 00:27). El `nvidia-smi` de esta versión (2026-08-27 16:32 UTC) es de una sesión posterior |
| 4 | 2026-08-28 | `nvidia-smi` 2026-08-28 17:18 UTC (12:18 en Colombia), contadores 7, 9, 10, 12 y 13; salidas de BETO en Drive 12:24-12:44 (principal) y 12:49-13:20 (multisemilla) | `entrenar_beto.py` preview y completo; `entrenar_beto_multisemilla.py` preview y completo | Python 3.13 (`.pyc` de `entrenar_beto.py`, 29.041 bytes, 2026-08-28 12:21). La versión de transformers no se imprimió en esta sesión; `entrenar_beto.py` se corrigió a las 12:21 con `_kwarg_warmup`, después del fallo con transformers ≥ 5.2 `[VERIFICAR]` |

## 4. Las dos corridas principales de BETO y BERTIN

### Qué cambió entre ellas

| Aspecto | Primera corrida (12-13 de agosto) | Segunda corrida (BERTIN 27 de agosto; BETO 28 de agosto) |
|---|---|---|
| Código | Versión equivalente a `files/entrenar_*.py` y a Git `1a97748` (`verificar_equivalencia`: sin diferencias de lógica). El fuente compilado mide 12 bytes menos que la copia local `files/` en ambos scripts: diferencia no identificada, probablemente una ruta `[VERIFICAR]` | Versión de Drive registrada en `0c8b4cb` |
| Rutas | `/content/drive/MyDrive/working_paper/datos_colab` y `.../working_paper/resultados_colab` (versión de Git) | `/content/drive/MyDrive/Working_Paper` y `.../Working_Paper/resultados_colab` |
| Warmup | `warmup_ratio=WARMUP_RATIO` | `_kwarg_warmup(WARMUP_RATIO)`: `warmup_ratio` si la versión lo acepta y, si no, `warmup_steps` con el mismo valor (transformers ≥ 5.2) |
| Python | 3.12 | 3.13 |
| transformers | No registrada (5.0 o 5.1 el 18-19 de agosto, por el aviso de obsolescencia) | 5.16.1 en la sesión de BERTIN; no impresa en la de BETO |
| Semilla, datos, épocas | `SEMILLA = 42`, mismas tablas exportadas, 4 épocas elegidas por k-fold | Iguales |

### Comparación de métricas

| Modelo | Condición | F1-macro | Log Loss | PR-AUC | Primera frente a segunda |
|---|---|---|---|---|---|
| BETO | A | 0.46484085770567934 | 1.1478759181352411 | 0.517126073554859 | Idénticas en todos los decimales |
| BETO | B | 0.5218982258648497 | 1.0614188647713907 | 0.5891459847865579 | Idénticas |
| BERTIN | A | 0.510251578956615 | 1.1644337374008595 | 0.5428291155579561 | Idénticas |
| BERTIN | B | 0.45162544167819635 | 1.140906328249765 | 0.541155783799062 | Idénticas |

Solo difiere `tiempo_minutos`. Además, los archivos `matriz_confusion_{A,B}.csv` y
`kfold_epocas_{A,B}.csv` de ambos modelos tienen la misma huella SHA-256 en las dos
corridas, y las salidas de RoBERTa de las sesiones 2 y 3 muestran las mismas F1 por
época en los 5 folds y las mismas métricas finales. RoBERTa se ejecutó, por tanto, al
menos tres veces con resultados idénticos.

### Comparación caso a caso

**No es posible.** Las predicciones de la primera corrida no se conservaron: en Drive,
`predicciones_{A,B}.csv` se sobrescribió con cada ejecución, y la búsqueda en
`Working_paper/`, Descargas y Drive (incluida la copia "Otras computadoras") solo encontró
las de la segunda corrida y las de la semilla 2024 del multisemilla. Evidencia indirecta
de que las predicciones son idénticas: matrices de confusión idénticas y Log Loss
idéntico hasta el último decimal, que depende de todas las probabilidades predichas.

### De qué corrida salen los archivos que usa el análisis

Según `outputs/manifiesto_insumos.csv` (13b):

| Archivo | Origen | Fecha | Corrida |
|---|---|---|---|
| `beto_predicciones_{A,B}.csv` | `resultados_colab/beto/predicciones_{A,B}.csv` | 2026-08-28 12:37 y 12:44 | Segunda (sesión 4) |
| `roberta_predicciones_{A,B}.csv` | `resultados_colab/roberta_es/roberta_predicciones_{A,B}.csv` | 2026-08-30 22:46 | Copia renombrada a mano; la última escritura de predicciones de RoBERTa es la de la sesión 3 (27 de agosto), así que lo más probable es que provenga de la segunda corrida `[VERIFICAR]`. Su contenido es coherente con las métricas de ambas corridas |

## 5. Anexo: salidas sustantivas del notebook

Todas las líneas de las salidas, sin barras de progreso, informes de carga de pesos ni
avisos de autenticación de Hugging Face (993 de 2.680 líneas). Revisadas: no contienen
texto de estudiantes ni credenciales.

### `788f4ff`, celda 0 (contador 1)

`!nvidia-smi`

```
Wed Aug 19 02:22:46 2026
| NVIDIA-SMI 580.82.07              Driver Version: 580.82.07      CUDA Version: 13.0     |
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|   0  Tesla T4                       Off |   00000000:00:04.0 Off |                    0 |
| N/A   40C    P8              9W /   70W |       0MiB /  15360MiB |      0%      Default |
|                                         |                        |                  N/A |
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|  No running processes found                                                             |
```

### `788f4ff`, celda 1 (contador 2)

`from google.colab import drive`

```
Mounted at /content/drive
```

### `788f4ff`, celda 2 (contador 4)

`!pip install -q transformers datasets evaluate accelerate`

```
[?25h
```

### `788f4ff`, celda 4 (contador 6)

`!pip show sentencepiece`

```
Name: sentencepiece
Version: 0.2.2
Summary: Unsupervised text tokenizer and detokenizer.
Home-page: https://github.com/google/sentencepiece
Author:
Author-email: Taku Kudo <taku@google.com>
License:
Location: /usr/local/lib/python3.12/dist-packages
Requires:
Required-by: torchtune
```

### `788f4ff`, celda 7 (contador 7)

`!python "/content/drive/MyDrive/Working_Paper/entrenar_roberta.py" --modo preview`

```
Ids de test excluidos por nulo_texto (compartido entre A y B): 6 → [1685, 1784, 1857, 1901, 2045, 2110]
  ROBERTA_ES — Condición B  [PREVIEW]
Train completo: 40 | Test: 10
  [PREVIEW] K-fold de épocas omitido — se usa 1 época(s) fija(s).
  → Épocas elegidas para el entrenamiento final: 1
config.json: 100% 674/674 [00:00<00:00, 1.57MB/s]
tokenizer_config.json: 100% 1.12k/1.12k [00:00<00:00, 3.64MB/s]
vocab.json: 100% 851k/851k [00:00<00:00, 14.4MB/s]
merges.txt: 100% 509k/509k [00:00<00:00, 58.0MB/s]
tokenizer.json: 100% 2.21M/2.21M [00:00<00:00, 73.1MB/s]
special_tokens_map.json: 100% 772/772 [00:00<00:00, 1.16MB/s]
model.safetensors: downloading bytes:  30% 152M/499M [00:01<00:01, 210MB/s, 10.6MB/s  ]
model.safetensors: downloading bytes:  70% 347M/499M [00:03<00:01, 120MB/s, 28.2MB/s  ]
model.safetensors: downloading bytes:  90% 447M/499M [00:04<00:00, 122MB/s, 34.9MB/s  ]  ]
model.safetensors: reconstructing file:  67% 335M/499M [00:04<00:01, 81.9MB/s, 23.8MB/s  ]
model.safetensors: downloading bytes:  93% 462M/499M [00:04<00:00, 107MB/s, 36.4MB/s  ] ]
model.safetensors: downloading bytes: 100% 465M/465M [00:04<00:00, 97.0MB/s, 36.2MB/s  ]]
model.safetensors: reconstructing file: 100% 499M/499M [00:04<00:00, 104MB/s, 42.2MB/s  ]
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'train_runtime': '1.747', 'train_samples_per_second': '22.9', 'train_steps_per_second': '1.718', 'train_loss': '1.616', 'epoch': '1'}
F1-macro roberta_es Condición B (comparable): 0.0364
Log Loss: 1.6326
PR-AUC macro: 0.5902
Casos excluidos por nulo_texto: 6 / 10 (60.0%)
                    precision    recall  f1-score   support
      muy_positivo       0.00      0.00      0.00         1
          positivo       0.10      1.00      0.18         1
levemente_positivo       0.00      0.00      0.00         2
           neutral       0.00      0.00      0.00         4
          negativo       0.00      0.00      0.00         2
          accuracy                           0.10        10
         macro avg       0.02      0.20      0.04        10
      weighted avg       0.01      0.10      0.02        10
Matriz de confusión:
                    muy_positivo  positivo  ...  neutral  negativo
muy_positivo                   0         1  ...        0         0
positivo                       0         1  ...        0         0
levemente_positivo             0         2  ...        0         0
neutral                        0         4  ...        0         0
negativo                       0         2  ...        0         0
[5 rows x 5 columns]
⏱️  Tiempo de esta condición (incluye k-fold + entrenamiento final): 0.2 minutos
✅  Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es (condición B_preview)
  ROBERTA_ES — Condición A  [PREVIEW]
Train completo: 40 | Test: 10
  [PREVIEW] K-fold de épocas omitido — se usa 1 época(s) fija(s).
  → Épocas elegidas para el entrenamiento final: 1
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'train_runtime': '0.8007', 'train_samples_per_second': '49.96', 'train_steps_per_second': '3.747', 'train_loss': '1.614', 'epoch': '1'}
F1-macro roberta_es Condición A (comparable): 0.0364
Log Loss: 1.6417
PR-AUC macro: 0.3881
Casos excluidos por nulo_texto: 6 / 10 (60.0%)
                    precision    recall  f1-score   support
      muy_positivo       0.10      1.00      0.18         1
          positivo       0.00      0.00      0.00         1
levemente_positivo       0.00      0.00      0.00         2
           neutral       0.00      0.00      0.00         4
          negativo       0.00      0.00      0.00         2
          accuracy                           0.10        10
         macro avg       0.02      0.20      0.04        10
      weighted avg       0.01      0.10      0.02        10
Matriz de confusión:
                    muy_positivo  positivo  ...  neutral  negativo
muy_positivo                   1         0  ...        0         0
positivo                       1         0  ...        0         0
levemente_positivo             2         0  ...        0         0
neutral                        4         0  ...        0         0
negativo                       2         0  ...        0         0
[5 rows x 5 columns]
⏱️  Tiempo de esta condición (incluye k-fold + entrenamiento final): 0.1 minutos
✅  Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es (condición A_preview)
RESUMEN FINAL — RoBERTa-es (BERTIN)  [PREVIEW]
  condicion  f1_macro  n_excluidos_nulo_texto
0         B  0.036364                       6
1         A  0.036364                       6
Si todo corrió sin errores, ejecuta con --modo completo (o sin argumento) para la corrida real.
```

### `788f4ff`, celda 8 (contador 9)

`!python "/content/drive/MyDrive/Working_Paper/entrenar_roberta.py" --modo completo`

```
Ids de test excluidos por nulo_texto (compartido entre A y B): 6 → [1685, 1784, 1857, 1901, 2045, 2110]
  ROBERTA_ES — Condición B
Train completo: 864 | Test: 183
  ── K-fold 1/5 ──
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'eval_loss': '1.58', 'eval_f1_macro': '0.1017', 'eval_runtime': '0.8981', 'eval_samples_per_second': '162.6', 'eval_steps_per_second': '11.13', 'epoch': '1'}
{'eval_loss': '1.515', 'eval_f1_macro': '0.3769', 'eval_runtime': '0.9084', 'eval_samples_per_second': '160.7', 'eval_steps_per_second': '11.01', 'epoch': '2'}
{'eval_loss': '1.217', 'eval_f1_macro': '0.5278', 'eval_runtime': '0.92', 'eval_samples_per_second': '158.7', 'eval_steps_per_second': '10.87', 'epoch': '3'}
{'eval_loss': '1.19', 'eval_f1_macro': '0.5228', 'eval_runtime': '0.9462', 'eval_samples_per_second': '154.3', 'eval_steps_per_second': '10.57', 'epoch': '4'}
{'train_runtime': '57.39', 'train_samples_per_second': '50.05', 'train_steps_per_second': '3.137', 'train_loss': '1.261', 'epoch': '4'}
  Fold 1 — F1-macro por época: [0.102, 0.377, 0.528, 0.523]
  ── K-fold 2/5 ──
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'eval_loss': '1.613', 'eval_f1_macro': '0.08328', 'eval_runtime': '1.403', 'eval_samples_per_second': '151.1', 'eval_steps_per_second': '9.979', 'epoch': '1'}
{'eval_loss': '1.414', 'eval_f1_macro': '0.2782', 'eval_runtime': '1.417', 'eval_samples_per_second': '149.7', 'eval_steps_per_second': '9.884', 'epoch': '2'}
{'eval_loss': '1.182', 'eval_f1_macro': '0.4966', 'eval_runtime': '1.439', 'eval_samples_per_second': '147.3', 'eval_steps_per_second': '9.727', 'epoch': '3'}
{'eval_loss': '1.186', 'eval_f1_macro': '0.4353', 'eval_runtime': '1.446', 'eval_samples_per_second': '146.6', 'eval_steps_per_second': '9.683', 'epoch': '4'}
{'train_runtime': '56.77', 'train_samples_per_second': '45.94', 'train_steps_per_second': '2.889', 'train_loss': '1.145', 'epoch': '4'}
  Fold 2 — F1-macro por época: [0.083, 0.278, 0.497, 0.435]
  ── K-fold 3/5 ──
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'eval_loss': '1.524', 'eval_f1_macro': '0.3263', 'eval_runtime': '1.102', 'eval_samples_per_second': '151.6', 'eval_steps_per_second': '9.986', 'epoch': '1'}
{'eval_loss': '1.45', 'eval_f1_macro': '0.3001', 'eval_runtime': '1.097', 'eval_samples_per_second': '152.3', 'eval_steps_per_second': '10.03', 'epoch': '2'}
{'eval_loss': '1.406', 'eval_f1_macro': '0.3938', 'eval_runtime': '1.097', 'eval_samples_per_second': '152.2', 'eval_steps_per_second': '10.03', 'epoch': '3'}
{'eval_loss': '1.331', 'eval_f1_macro': '0.4455', 'eval_runtime': '1.094', 'eval_samples_per_second': '152.7', 'eval_steps_per_second': '10.06', 'epoch': '4'}
{'train_runtime': '59.38', 'train_samples_per_second': '46.95', 'train_steps_per_second': '2.964', 'train_loss': '1.188', 'epoch': '4'}
  Fold 3 — F1-macro por época: [0.326, 0.3, 0.394, 0.446]
  ── K-fold 4/5 ──
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'eval_loss': '1.518', 'eval_f1_macro': '0.3277', 'eval_runtime': '0.9703', 'eval_samples_per_second': '150.5', 'eval_steps_per_second': '10.31', 'epoch': '1'}
{'eval_loss': '1.172', 'eval_f1_macro': '0.4506', 'eval_runtime': '0.9801', 'eval_samples_per_second': '149', 'eval_steps_per_second': '10.2', 'epoch': '2'}
{'eval_loss': '1.077', 'eval_f1_macro': '0.5051', 'eval_runtime': '0.9771', 'eval_samples_per_second': '149.4', 'eval_steps_per_second': '10.23', 'epoch': '3'}
{'eval_loss': '1.144', 'eval_f1_macro': '0.5676', 'eval_runtime': '0.9592', 'eval_samples_per_second': '152.2', 'eval_steps_per_second': '10.43', 'epoch': '4'}
{'train_runtime': '60.58', 'train_samples_per_second': '47.41', 'train_steps_per_second': '2.971', 'train_loss': '1.036', 'epoch': '4'}
  Fold 4 — F1-macro por época: [0.328, 0.451, 0.505, 0.568]
  ── K-fold 5/5 ──
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'eval_loss': '1.563', 'eval_f1_macro': '0.07967', 'eval_runtime': '1.279', 'eval_samples_per_second': '150.9', 'eval_steps_per_second': '10.17', 'epoch': '1'}
{'eval_loss': '1.424', 'eval_f1_macro': '0.4575', 'eval_runtime': '1.272', 'eval_samples_per_second': '151.7', 'eval_steps_per_second': '10.22', 'epoch': '2'}
{'eval_loss': '1.259', 'eval_f1_macro': '0.4705', 'eval_runtime': '1.284', 'eval_samples_per_second': '150.3', 'eval_steps_per_second': '10.12', 'epoch': '3'}
{'eval_loss': '1.295', 'eval_f1_macro': '0.4662', 'eval_runtime': '1.269', 'eval_samples_per_second': '152.1', 'eval_steps_per_second': '10.24', 'epoch': '4'}
{'train_runtime': '57.92', 'train_samples_per_second': '46.34', 'train_steps_per_second': '2.9', 'train_loss': '1.228', 'epoch': '4'}
  Fold 5 — F1-macro por época: [0.08, 0.457, 0.47, 0.466]
  F1-macro promedio por época (across 5 folds):
    Época 1: 0.1837 ± 0.1172
    Época 2: 0.3727 ± 0.0741
    Época 3: 0.4787 ± 0.0463
    Época 4: 0.4875 ± 0.0502  ← elegida
  → Épocas elegidas para el entrenamiento final: 4
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'loss': '1.608', 'grad_norm': '1.714', 'learning_rate': '1.727e-05', 'epoch': '0.3704'}
{'loss': '1.602', 'grad_norm': '3.444', 'learning_rate': '1.825e-05', 'epoch': '0.7407'}
{'loss': '1.557', 'grad_norm': '33.08', 'learning_rate': '1.619e-05', 'epoch': '1.111'}
{'loss': '1.547', 'grad_norm': '8.354', 'learning_rate': '1.412e-05', 'epoch': '1.481'}
{'loss': '1.368', 'grad_norm': '20.14', 'learning_rate': '1.206e-05', 'epoch': '1.852'}
{'loss': '1.158', 'grad_norm': '19.98', 'learning_rate': '1e-05', 'epoch': '2.222'}
{'loss': '0.9937', 'grad_norm': '19.25', 'learning_rate': '7.938e-06', 'epoch': '2.593'}
{'loss': '0.9334', 'grad_norm': '12.25', 'learning_rate': '5.876e-06', 'epoch': '2.963'}
{'loss': '0.6782', 'grad_norm': '15.89', 'learning_rate': '3.814e-06', 'epoch': '3.333'}
{'loss': '0.6463', 'grad_norm': '12.69', 'learning_rate': '1.753e-06', 'epoch': '3.704'}
{'train_runtime': '68.13', 'train_samples_per_second': '50.73', 'train_steps_per_second': '3.17', 'train_loss': '1.165', 'epoch': '4'}
F1-macro roberta_es Condición B (comparable): 0.4516
Log Loss: 1.1409
PR-AUC macro: 0.5412
Casos excluidos por nulo_texto: 6 / 183 (3.3%)
                    precision    recall  f1-score   support
      muy_positivo       0.50      0.47      0.48        30
          positivo       0.55      0.43      0.48        75
levemente_positivo       0.37      0.60      0.46        45
           neutral       0.50      0.30      0.38        20
          negativo       0.50      0.43      0.46         7
          accuracy                           0.46       177
         macro avg       0.48      0.44      0.45       177
      weighted avg       0.49      0.46      0.46       177
Matriz de confusión:
                    muy_positivo  positivo  ...  neutral  negativo
muy_positivo                  14        10  ...        1         2
positivo                      13        32  ...        0         0
levemente_positivo             1        13  ...        4         0
neutral                        0         2  ...        6         1
negativo                       0         1  ...        1         3
[5 rows x 5 columns]
⏱️  Tiempo de esta condición (incluye k-fold + entrenamiento final): 6.2 minutos
✅  Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es (condición B)
  ROBERTA_ES — Condición A
Train completo: 911 | Test: 183
  ── K-fold 1/5 ──
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'eval_loss': '1.519', 'eval_f1_macro': '0.2437', 'eval_runtime': '1.162', 'eval_samples_per_second': '150.6', 'eval_steps_per_second': '9.466', 'epoch': '1'}
{'eval_loss': '1.565', 'eval_f1_macro': '0.2169', 'eval_runtime': '1.158', 'eval_samples_per_second': '151.1', 'eval_steps_per_second': '9.497', 'epoch': '2'}
{'eval_loss': '1.485', 'eval_f1_macro': '0.3427', 'eval_runtime': '1.15', 'eval_samples_per_second': '152.2', 'eval_steps_per_second': '9.564', 'epoch': '3'}
{'eval_loss': '1.438', 'eval_f1_macro': '0.394', 'eval_runtime': '1.143', 'eval_samples_per_second': '153.1', 'eval_steps_per_second': '9.623', 'epoch': '4'}
{'train_runtime': '63.14', 'train_samples_per_second': '46.62', 'train_steps_per_second': '2.914', 'train_loss': '1.237', 'epoch': '4'}
  Fold 1 — F1-macro por época: [0.244, 0.217, 0.343, 0.394]
  ── K-fold 2/5 ──
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'eval_loss': '1.606', 'eval_f1_macro': '0.1679', 'eval_runtime': '1.266', 'eval_samples_per_second': '150.1', 'eval_steps_per_second': '9.479', 'epoch': '1'}
{'eval_loss': '1.454', 'eval_f1_macro': '0.4313', 'eval_runtime': '1.264', 'eval_samples_per_second': '150.3', 'eval_steps_per_second': '9.493', 'epoch': '2'}
{'eval_loss': '1.217', 'eval_f1_macro': '0.4633', 'eval_runtime': '1.255', 'eval_samples_per_second': '151.4', 'eval_steps_per_second': '9.56', 'epoch': '3'}
{'eval_loss': '1.149', 'eval_f1_macro': '0.5772', 'eval_runtime': '1.245', 'eval_samples_per_second': '152.6', 'eval_steps_per_second': '9.637', 'epoch': '4'}
{'train_runtime': '61.75', 'train_samples_per_second': '46.7', 'train_steps_per_second': '2.98', 'train_loss': '1.19', 'epoch': '4'}
  Fold 2 — F1-macro por época: [0.168, 0.431, 0.463, 0.577]
  ── K-fold 3/5 ──
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'eval_loss': '1.615', 'eval_f1_macro': '0.08687', 'eval_runtime': '1.217', 'eval_samples_per_second': '151.2', 'eval_steps_per_second': '9.861', 'epoch': '1'}
{'eval_loss': '1.432', 'eval_f1_macro': '0.359', 'eval_runtime': '1.214', 'eval_samples_per_second': '151.5', 'eval_steps_per_second': '9.882', 'epoch': '2'}
{'eval_loss': '1.283', 'eval_f1_macro': '0.4335', 'eval_runtime': '1.224', 'eval_samples_per_second': '150.4', 'eval_steps_per_second': '9.808', 'epoch': '3'}
{'eval_loss': '1.284', 'eval_f1_macro': '0.4715', 'eval_runtime': '1.229', 'eval_samples_per_second': '149.7', 'eval_steps_per_second': '9.765', 'epoch': '4'}
{'train_runtime': '62.06', 'train_samples_per_second': '46.86', 'train_steps_per_second': '2.965', 'train_loss': '1.16', 'epoch': '4'}
  Fold 3 — F1-macro por época: [0.087, 0.359, 0.434, 0.472]
  ── K-fold 4/5 ──
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'eval_loss': '1.596', 'eval_f1_macro': '0.247', 'eval_runtime': '1.013', 'eval_samples_per_second': '151', 'eval_steps_per_second': '9.872', 'epoch': '1'}
{'eval_loss': '1.475', 'eval_f1_macro': '0.3898', 'eval_runtime': '1.014', 'eval_samples_per_second': '150.9', 'eval_steps_per_second': '9.863', 'epoch': '2'}
{'eval_loss': '1.233', 'eval_f1_macro': '0.4818', 'eval_runtime': '1.009', 'eval_samples_per_second': '151.7', 'eval_steps_per_second': '9.912', 'epoch': '3'}
{'eval_loss': '1.171', 'eval_f1_macro': '0.4827', 'eval_runtime': '1.016', 'eval_samples_per_second': '150.6', 'eval_steps_per_second': '9.846', 'epoch': '4'}
{'train_runtime': '63.67', 'train_samples_per_second': '47.62', 'train_steps_per_second': '3.016', 'train_loss': '1.317', 'epoch': '4'}
  Fold 4 — F1-macro por época: [0.247, 0.39, 0.482, 0.483]
  ── K-fold 5/5 ──
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'eval_loss': '1.585', 'eval_f1_macro': '0.1575', 'eval_runtime': '1.391', 'eval_samples_per_second': '150.2', 'eval_steps_per_second': '10.06', 'epoch': '1'}
{'eval_loss': '1.321', 'eval_f1_macro': '0.3704', 'eval_runtime': '1.377', 'eval_samples_per_second': '151.8', 'eval_steps_per_second': '10.17', 'epoch': '2'}
{'eval_loss': '1.156', 'eval_f1_macro': '0.4805', 'eval_runtime': '1.377', 'eval_samples_per_second': '151.8', 'eval_steps_per_second': '10.17', 'epoch': '3'}
{'eval_loss': '1.127', 'eval_f1_macro': '0.5216', 'eval_runtime': '1.373', 'eval_samples_per_second': '152.2', 'eval_steps_per_second': '10.19', 'epoch': '4'}
{'train_runtime': '60.69', 'train_samples_per_second': '46.27', 'train_steps_per_second': '2.9', 'train_loss': '1.106', 'epoch': '4'}
  Fold 5 — F1-macro por época: [0.158, 0.37, 0.48, 0.522]
  F1-macro promedio por época (across 5 folds):
    Época 1: 0.1806 ± 0.0598
    Época 2: 0.3535 ± 0.0726
    Época 3: 0.4404 ± 0.0519
    Época 4: 0.4894 ± 0.0604  ← elegida
  → Épocas elegidas para el entrenamiento final: 4
[transformers] warmup_ratio is deprecated and will be removed in v5.2. Use `warmup_steps` instead.
{'loss': '1.607', 'grad_norm': '1.772', 'learning_rate': '1.652e-05', 'epoch': '0.3509'}
{'loss': '1.596', 'grad_norm': '3.691', 'learning_rate': '1.844e-05', 'epoch': '0.7018'}
{'loss': '1.599', 'grad_norm': '6.162', 'learning_rate': '1.649e-05', 'epoch': '1.053'}
{'loss': '1.483', 'grad_norm': '17.62', 'learning_rate': '1.454e-05', 'epoch': '1.404'}
{'loss': '1.235', 'grad_norm': '14.33', 'learning_rate': '1.259e-05', 'epoch': '1.754'}
{'loss': '1.215', 'grad_norm': '13.81', 'learning_rate': '1.063e-05', 'epoch': '2.105'}
{'loss': '0.9415', 'grad_norm': '14.81', 'learning_rate': '8.683e-06', 'epoch': '2.456'}
{'loss': '0.8625', 'grad_norm': '13.72', 'learning_rate': '6.732e-06', 'epoch': '2.807'}
{'loss': '0.7042', 'grad_norm': '17.22', 'learning_rate': '4.78e-06', 'epoch': '3.158'}
{'loss': '0.6125', 'grad_norm': '8.849', 'learning_rate': '2.829e-06', 'epoch': '3.509'}
{'loss': '0.5734', 'grad_norm': '12.35', 'learning_rate': '8.78e-07', 'epoch': '3.86'}
{'train_runtime': '71.57', 'train_samples_per_second': '50.91', 'train_steps_per_second': '3.186', 'train_loss': '1.109', 'epoch': '4'}
F1-macro roberta_es Condición A (comparable): 0.5103
Log Loss: 1.1644
PR-AUC macro: 0.5428
Casos excluidos por nulo_texto: 6 / 183 (3.3%)
                    precision    recall  f1-score   support
      muy_positivo       0.52      0.57      0.54        30
          positivo       0.56      0.48      0.52        75
levemente_positivo       0.46      0.47      0.46        45
           neutral       0.36      0.50      0.42        20
          negativo       0.67      0.57      0.62         7
          accuracy                           0.50       177
         macro avg       0.51      0.52      0.51       177
      weighted avg       0.51      0.50      0.50       177
Matriz de confusión:
                    muy_positivo  positivo  ...  neutral  negativo
muy_positivo                  17         8  ...        3         0
positivo                      15        36  ...        6         0
levemente_positivo             0        16  ...        7         1
neutral                        0         4  ...       10         1
negativo                       1         0  ...        2         4
[5 rows x 5 columns]
⏱️  Tiempo de esta condición (incluye k-fold + entrenamiento final): 6.6 minutos
✅  Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es (condición A)
RESUMEN FINAL — RoBERTa-es (BERTIN)
  condicion  f1_macro  n_excluidos_nulo_texto
0         B  0.451625                       6
1         A  0.510252                       6
```

### `788f4ff`, celda 10 (contador 6)

`!python "/content/drive/MyDrive/Working_Paper/diagnostico_tokenizacion.py"`

```
Corpus: 799 segmentos reales (Condición B)
───────────────────────────────────────────────────────
  BETO  (dccuchile/bert-base-spanish-wwm-cased)
───────────────────────────────────────────────────────
config.json: 100% 648/648 [00:00<00:00, 4.01MB/s]
tokenizer_config.json: 100% 364/364 [00:00<00:00, 1.75MB/s]
vocab.txt: 100% 242k/242k [00:00<00:00, 24.0MB/s]
tokenizer.json: 100% 480k/480k [00:00<00:00, 60.7MB/s]
special_tokens_map.json: 100% 134/134 [00:00<00:00, 976kB/s]
  Palabras por ejemplo (split simple)     — media: 34.6
  Tokens por ejemplo (sin truncar)         — media: 42.7  mediana: 41  p95: 75  máx: 131
  Fertilidad (tokens / palabra)            — media: 1.26
  Ejemplos que exceden MAX_LENGTH=128      : 1 (0.1%)
  Tokens UNK                               : 2 / 34139 (0.006%)
───────────────────────────────────────────────────────
  BERTIN  (bertin-project/bertin-roberta-base-spanish)
───────────────────────────────────────────────────────
config.json: 100% 674/674 [00:00<00:00, 5.08MB/s]
tokenizer_config.json: 100% 1.12k/1.12k [00:00<00:00, 5.42MB/s]
vocab.json: 100% 851k/851k [00:00<00:00, 93.3MB/s]
merges.txt: 100% 509k/509k [00:00<00:00, 86.5MB/s]
tokenizer.json: 100% 2.21M/2.21M [00:00<00:00, 119MB/s]
special_tokens_map.json: 100% 772/772 [00:00<00:00, 5.10MB/s]
  Palabras por ejemplo (split simple)     — media: 34.6
  Tokens por ejemplo (sin truncar)         — media: 42.2  mediana: 41  p95: 75  máx: 128
  Fertilidad (tokens / palabra)            — media: 1.25
  Ejemplos que exceden MAX_LENGTH=128      : 0 (0.0%)
  Tokens UNK                               : 0 / 33738 (0.000%)
  COMPARACIÓN
modelo  tokens_media  tokens_p95  fertilidad_media  pct_truncados  pct_unk
  BETO     42.727159        75.1          1.259422       0.125156 0.005858
BERTIN     42.225282        75.0          1.245546       0.000000 0.000000
  BERTIN fragmenta -1.1% más que BETO (fertilidad relativa)
  ✅  Proporción de truncamiento similar entre ambos tokenizers — MAX_LENGTH=128 no parece ser un problema diferencial.
```

### `788f4ff`, celda 11 (contador 3)

`!python "/content/drive/MyDrive/Working_Paper/beto_sin_finetuning.py"`

```
Dispositivo: cuda
config.json: 100% 648/648 [00:00<00:00, 3.66MB/s]
tokenizer_config.json: 100% 364/364 [00:00<00:00, 2.11MB/s]
vocab.txt: 100% 242k/242k [00:00<00:00, 59.9MB/s]
tokenizer.json: 100% 480k/480k [00:00<00:00, 104MB/s]
special_tokens_map.json: 100% 134/134 [00:00<00:00, 723kB/s]
pytorch_model.bin: downloading bytes:  49% 215M/440M [00:02<00:01, 209MB/s, 15.8MB/s  ]
pytorch_model.bin: downloading bytes:  61% 267M/440M [00:02<00:00, 193MB/s, 23.5MB/s  ]
pytorch_model.bin: downloading bytes:  95% 417M/440M [00:04<00:00, 55.4MB/s, 31.7MB/s  ]]
pytorch_model.bin: downloading bytes: 100% 417M/417M [00:05<00:00, 81.5MB/s, 31.5MB/s  ] ]
pytorch_model.bin: reconstructing file: 100% 440M/440M [00:05<00:00, 86.0MB/s, 35.7MB/s  ]
model.safetensors: downloading bytes:  89% 393M/440M [00:03<00:00, 240MB/s, 33.1MB/s  ]
model.safetensors: reconstructing file:  31% 134M/440M [00:03<00:07, 39.7MB/s]
model.safetensors: reconstructing file:  61% 268M/440M [00:03<00:02, 85.5MB/s, 12.4MB/s  ]Ids excluidos por nulo_texto (compartido A/B): 6
  BETO SIN FINE-TUNING (linear probing) — Condición B
Train: 864 | Test comparable: 177
Extrayendo embeddings de train...
model.safetensors: downloading bytes: 100% 417M/417M [00:04<00:00, 101MB/s, 35.8MB/s  ] ]
model.safetensors: reconstructing file: 100% 440M/440M [00:04<00:00, 106MB/s, 38.9MB/s  ]
Extrayendo embeddings de test...
F1-macro (linear probing) Condición B: 0.4464
Log Loss: 1.3358  |  PR-AUC macro: 0.4760
                    precision    recall  f1-score   support
      muy_positivo       0.60      0.60      0.60        30
          positivo       0.56      0.51      0.53        75
levemente_positivo       0.40      0.49      0.44        45
           neutral       0.33      0.25      0.29        20
          negativo       0.33      0.43      0.38         7
          accuracy                           0.49       177
         macro avg       0.45      0.45      0.45       177
      weighted avg       0.49      0.49      0.49       177
⏱️  Tiempo: 0.1 minutos
✅  Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto_sin_finetuning (condición B)
  BETO SIN FINE-TUNING (linear probing) — Condición A
Train: 911 | Test comparable: 177
Extrayendo embeddings de train...
Extrayendo embeddings de test...
F1-macro (linear probing) Condición A: 0.4304
Log Loss: 1.3991  |  PR-AUC macro: 0.4532
                    precision    recall  f1-score   support
      muy_positivo       0.53      0.53      0.53        30
          positivo       0.51      0.47      0.49        75
levemente_positivo       0.38      0.44      0.41        45
           neutral       0.35      0.30      0.32        20
          negativo       0.38      0.43      0.40         7
          accuracy                           0.45       177
         macro avg       0.43      0.43      0.43       177
      weighted avg       0.46      0.45      0.45       177
⏱️  Tiempo: 0.2 minutos
✅  Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto_sin_finetuning (condición A)
RESUMEN FINAL — BETO SIN FINE-TUNING (linear probing)
  condicion  f1_macro  log_loss  pr_auc_macro
0         B  0.446437  1.335765      0.476028
1         A  0.430386  1.399144      0.453240
Compara contra entrenar_beto.py (fine-tuning completo) para cuantificar el aporte del ajuste fino (Fase 7 vs Fase 6).
```

### `0c8b4cb`, celda 0 (contador 1)

`!nvidia-smi`

```
Thu Aug 27 16:32:10 2026
| NVIDIA-SMI 580.82.07              Driver Version: 580.82.07      CUDA Version: 13.0     |
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|   0  Tesla T4                       Off |   00000000:00:04.0 Off |                    0 |
| N/A   51C    P8             10W /   70W |       0MiB /  15360MiB |      0%      Default |
|                                         |                        |                  N/A |
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|  No running processes found                                                             |
```

### `0c8b4cb`, celda 1 (contador 2)

`from google.colab import drive`

```
Mounted at /content/drive
```

### `0c8b4cb`, celda 2 (contador 4)

`!pip install -q transformers datasets evaluate accelerate`

```
[?25h
```

### `0c8b4cb`, celda 4 (contador 6)

`!pip show sentencepiece`

```
Name: sentencepiece
Version: 0.2.2
Summary: Unsupervised text tokenizer and detokenizer.
Home-page: https://github.com/google/sentencepiece
Author:
Author-email: Taku Kudo <taku@google.com>
License:
Location: /usr/local/lib/python3.13/dist-packages
Requires:
Required-by: torchtune
```

### `0c8b4cb`, celda 5 (contador 3)

`!python "/content/drive/MyDrive/Working_Paper/entrenar_beto.py" --modo preview`

```
Ids de test excluidos por nulo_texto (compartido entre A y B): 6 → [1685, 1784, 1857, 1901, 2045, 2110]
  BETO — Condición B  [PREVIEW]
Train completo: 40 | Test: 10
  [PREVIEW] K-fold de épocas omitido — se usa 1 época(s) fija(s).
  → Épocas elegidas para el entrenamiento final: 1
config.json: 100% 648/648 [00:00<00:00, 3.93MB/s]
tokenizer_config.json: 100% 364/364 [00:00<00:00, 2.42MB/s]
vocab.txt: 100% 242k/242k [00:00<00:00, 87.2MB/s]
tokenizer.json: 100% 480k/480k [00:00<00:00, 112MB/s]
special_tokens_map.json: 100% 134/134 [00:00<00:00, 861kB/s]
pytorch_model.bin: downloading bytes:  76% 336M/440M [00:02<00:00, 210MB/s, 29.1MB/s  ]
pytorch_model.bin: downloading bytes:  88% 389M/440M [00:03<00:00, 227MB/s, 32.6MB/s  ]
pytorch_model.bin: reconstructing file:  76% 335M/440M [00:03<00:00, 111MB/s, 25.0MB/s  ]
pytorch_model.bin: downloading bytes: 100% 417M/417M [00:03<00:00, 123MB/s, 36.4MB/s  ] ]
pytorch_model.bin: reconstructing file: 100% 440M/440M [00:03<00:00, 129MB/s, 39.9MB/s  ]
Traceback (most recent call last):
  File "/content/drive/MyDrive/Working_Paper/entrenar_beto.py", line 515, in <module>
    r = entrenar_condicion(condicion, split, real_b, cond_a_primaria, cond_a_dup_extra, aug,
                            ids_nulo_texto_compartido=ids_nulo_compartido, modo=args_cli.modo)
  File "/content/drive/MyDrive/Working_Paper/entrenar_beto.py", line 372, in entrenar_condicion
    args = TrainingArguments(
        output_dir=str(RUTA_SALIDA / f"checkpoints_{condicion}"),
    ...<4 lines>...
        logging_steps=20, report_to="none", seed=SEMILLA,
    )
TypeError: TrainingArguments.__init__() got an unexpected keyword argument 'warmup_ratio'
model.safetensors: downloading bytes:  75% 329M/440M [00:02<00:00, 343MB/s, 26.2MB/s  ]
model.safetensors: downloading bytes:  93% 408M/440M [00:02<00:00, 364MB/s, 33.5MB/s  ]
model.safetensors: reconstructing file:  31% 134M/440M [00:02<00:05, 58.9MB/s, 6.32MB/s  ]
model.safetensors: reconstructing file:  61% 268M/440M [00:02<00:01, 137MB/s, 12.5MB/s  ]
model.safetensors: downloading bytes: 100% 417M/417M [00:03<00:00, 124MB/s, 37.7MB/s  ] ]
model.safetensors: reconstructing file: 100% 440M/440M [00:03<00:00, 130MB/s, 39.5MB/s  ]
```

### `0c8b4cb`, celda 12 (contador 9)

`!pip install -q -U transformers accelerate datasets evaluate`

```
[?25h
```

### `0c8b4cb`, celda 13 (contador 10)

`import transformers`

```
5.16.1
```

### `0c8b4cb`, celda 14 (contador 14)

`import os`

```
La carpeta NO existe: /content/drive/MyDrive/Working_Paper/datos_colab
Contenido de Working_Paper/:
 - entrenar_roberta_multisemilla.py
 - augmentation_segmentos.csv
 - segmento_condicion_a.csv
 - segmento_retroalimentacion.csv
 - split_asignacion.csv
 - resultados_colab
 - entrenar_beto.py
 - diagnostico_hiperparametros_roberta.py
 - __pycache__
 - diagnostico_tokenizacion.py
 - entrenar_roberta.py
 - beto_sin_finetuning.py
```

### `0c8b4cb`, celda 15 (contador 17)

`!python "/content/drive/MyDrive/Working_Paper/entrenar_roberta.py" --modo completo`

```
Ids de test excluidos por nulo_texto (compartido entre A y B): 6 → [1685, 1784, 1857, 1901, 2045, 2110]
  ROBERTA_ES — Condición B
Train completo: 864 | Test: 183
  ── K-fold 1/5 ──
{'eval_loss': '1.58', 'eval_f1_macro': '0.1017', 'eval_runtime': '0.9265', 'eval_samples_per_second': '157.6', 'eval_steps_per_second': '10.79', 'epoch': '1'}
{'eval_loss': '1.515', 'eval_f1_macro': '0.3769', 'eval_runtime': '0.9339', 'eval_samples_per_second': '156.3', 'eval_steps_per_second': '10.71', 'epoch': '2'}
{'eval_loss': '1.217', 'eval_f1_macro': '0.5278', 'eval_runtime': '0.953', 'eval_samples_per_second': '153.2', 'eval_steps_per_second': '10.49', 'epoch': '3'}
{'eval_loss': '1.19', 'eval_f1_macro': '0.5228', 'eval_runtime': '0.9938', 'eval_samples_per_second': '146.9', 'eval_steps_per_second': '10.06', 'epoch': '4'}
{'train_runtime': '58.85', 'train_samples_per_second': '48.8', 'train_steps_per_second': '3.059', 'train_loss': '1.261', 'epoch': '4'}
  Fold 1 — F1-macro por época: [0.102, 0.377, 0.528, 0.523]
  ── K-fold 2/5 ──
{'eval_loss': '1.613', 'eval_f1_macro': '0.08328', 'eval_runtime': '1.539', 'eval_samples_per_second': '137.7', 'eval_steps_per_second': '9.095', 'epoch': '1'}
{'eval_loss': '1.414', 'eval_f1_macro': '0.2782', 'eval_runtime': '1.621', 'eval_samples_per_second': '130.8', 'eval_steps_per_second': '8.639', 'epoch': '2'}
{'eval_loss': '1.182', 'eval_f1_macro': '0.4966', 'eval_runtime': '1.725', 'eval_samples_per_second': '122.9', 'eval_steps_per_second': '8.117', 'epoch': '3'}
{'eval_loss': '1.186', 'eval_f1_macro': '0.4353', 'eval_runtime': '1.693', 'eval_samples_per_second': '125.2', 'eval_steps_per_second': '8.268', 'epoch': '4'}
{'train_runtime': '62.1', 'train_samples_per_second': '42', 'train_steps_per_second': '2.641', 'train_loss': '1.145', 'epoch': '4'}
  Fold 2 — F1-macro por época: [0.083, 0.278, 0.497, 0.435]
  ── K-fold 3/5 ──
{'eval_loss': '1.524', 'eval_f1_macro': '0.3263', 'eval_runtime': '1.242', 'eval_samples_per_second': '134.5', 'eval_steps_per_second': '8.857', 'epoch': '1'}
{'eval_loss': '1.45', 'eval_f1_macro': '0.3001', 'eval_runtime': '1.242', 'eval_samples_per_second': '134.5', 'eval_steps_per_second': '8.858', 'epoch': '2'}
{'eval_loss': '1.406', 'eval_f1_macro': '0.3938', 'eval_runtime': '1.267', 'eval_samples_per_second': '131.8', 'eval_steps_per_second': '8.68', 'epoch': '3'}
{'eval_loss': '1.331', 'eval_f1_macro': '0.4455', 'eval_runtime': '1.283', 'eval_samples_per_second': '130.2', 'eval_steps_per_second': '8.575', 'epoch': '4'}
{'train_runtime': '64.5', 'train_samples_per_second': '43.23', 'train_steps_per_second': '2.729', 'train_loss': '1.188', 'epoch': '4'}
  Fold 3 — F1-macro por época: [0.326, 0.3, 0.394, 0.446]
  ── K-fold 4/5 ──
{'eval_loss': '1.518', 'eval_f1_macro': '0.3277', 'eval_runtime': '1.128', 'eval_samples_per_second': '129.5', 'eval_steps_per_second': '8.869', 'epoch': '1'}
{'eval_loss': '1.172', 'eval_f1_macro': '0.4506', 'eval_runtime': '1.137', 'eval_samples_per_second': '128.5', 'eval_steps_per_second': '8.798', 'epoch': '2'}
{'eval_loss': '1.077', 'eval_f1_macro': '0.5051', 'eval_runtime': '1.111', 'eval_samples_per_second': '131.4', 'eval_steps_per_second': '8.999', 'epoch': '3'}
{'eval_loss': '1.144', 'eval_f1_macro': '0.5676', 'eval_runtime': '1.116', 'eval_samples_per_second': '130.8', 'eval_steps_per_second': '8.96', 'epoch': '4'}
{'train_runtime': '66.17', 'train_samples_per_second': '43.4', 'train_steps_per_second': '2.72', 'train_loss': '1.036', 'epoch': '4'}
  Fold 4 — F1-macro por época: [0.328, 0.451, 0.505, 0.568]
  ── K-fold 5/5 ──
{'eval_loss': '1.563', 'eval_f1_macro': '0.07967', 'eval_runtime': '1.494', 'eval_samples_per_second': '129.2', 'eval_steps_per_second': '8.7', 'epoch': '1'}
{'eval_loss': '1.424', 'eval_f1_macro': '0.4575', 'eval_runtime': '1.483', 'eval_samples_per_second': '130.2', 'eval_steps_per_second': '8.768', 'epoch': '2'}
{'eval_loss': '1.259', 'eval_f1_macro': '0.4705', 'eval_runtime': '1.486', 'eval_samples_per_second': '129.9', 'eval_steps_per_second': '8.75', 'epoch': '3'}
{'eval_loss': '1.295', 'eval_f1_macro': '0.4662', 'eval_runtime': '1.472', 'eval_samples_per_second': '131.1', 'eval_steps_per_second': '8.83', 'epoch': '4'}
{'train_runtime': '63.41', 'train_samples_per_second': '42.33', 'train_steps_per_second': '2.649', 'train_loss': '1.228', 'epoch': '4'}
  Fold 5 — F1-macro por época: [0.08, 0.457, 0.47, 0.466]
  F1-macro promedio por época (across 5 folds):
    Época 1: 0.1837 ± 0.1172
    Época 2: 0.3727 ± 0.0741
    Época 3: 0.4787 ± 0.0463
    Época 4: 0.4875 ± 0.0502  ← elegida
  → Épocas elegidas para el entrenamiento final: 4
{'loss': '1.608', 'grad_norm': '1.714', 'learning_rate': '1.727e-05', 'epoch': '0.3704'}
{'loss': '1.602', 'grad_norm': '3.444', 'learning_rate': '1.825e-05', 'epoch': '0.7407'}
{'loss': '1.557', 'grad_norm': '33.08', 'learning_rate': '1.619e-05', 'epoch': '1.111'}
{'loss': '1.547', 'grad_norm': '8.354', 'learning_rate': '1.412e-05', 'epoch': '1.481'}
{'loss': '1.368', 'grad_norm': '20.14', 'learning_rate': '1.206e-05', 'epoch': '1.852'}
{'loss': '1.158', 'grad_norm': '19.98', 'learning_rate': '1e-05', 'epoch': '2.222'}
{'loss': '0.9937', 'grad_norm': '19.25', 'learning_rate': '7.938e-06', 'epoch': '2.593'}
{'loss': '0.9334', 'grad_norm': '12.25', 'learning_rate': '5.876e-06', 'epoch': '2.963'}
{'loss': '0.6782', 'grad_norm': '15.89', 'learning_rate': '3.814e-06', 'epoch': '3.333'}
{'loss': '0.6463', 'grad_norm': '12.69', 'learning_rate': '1.753e-06', 'epoch': '3.704'}
{'train_runtime': '74.04', 'train_samples_per_second': '46.68', 'train_steps_per_second': '2.917', 'train_loss': '1.165', 'epoch': '4'}
F1-macro roberta_es Condición B (comparable): 0.4516
Log Loss: 1.1409
PR-AUC macro: 0.5412
Casos excluidos por nulo_texto: 6 / 183 (3.3%)
                    precision    recall  f1-score   support
      muy_positivo       0.50      0.47      0.48        30
          positivo       0.55      0.43      0.48        75
levemente_positivo       0.37      0.60      0.46        45
           neutral       0.50      0.30      0.38        20
          negativo       0.50      0.43      0.46         7
          accuracy                           0.46       177
         macro avg       0.48      0.44      0.45       177
      weighted avg       0.49      0.46      0.46       177
Matriz de confusión:
                    muy_positivo  positivo  ...  neutral  negativo
muy_positivo                  14        10  ...        1         2
positivo                      13        32  ...        0         0
levemente_positivo             1        13  ...        4         0
neutral                        0         2  ...        6         1
negativo                       0         1  ...        1         3
[5 rows x 5 columns]
Tiempo de esta condición (incluye k-fold + entrenamiento final): 6.8 minutos
Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es (condición B)
  ROBERTA_ES — Condición A
Train completo: 911 | Test: 183
  ── K-fold 1/5 ──
{'eval_loss': '1.519', 'eval_f1_macro': '0.2437', 'eval_runtime': '1.361', 'eval_samples_per_second': '128.6', 'eval_steps_per_second': '8.084', 'epoch': '1'}
{'eval_loss': '1.565', 'eval_f1_macro': '0.2169', 'eval_runtime': '1.437', 'eval_samples_per_second': '121.8', 'eval_steps_per_second': '7.658', 'epoch': '2'}
{'eval_loss': '1.485', 'eval_f1_macro': '0.3427', 'eval_runtime': '1.307', 'eval_samples_per_second': '133.9', 'eval_steps_per_second': '8.419', 'epoch': '3'}
{'eval_loss': '1.438', 'eval_f1_macro': '0.394', 'eval_runtime': '1.26', 'eval_samples_per_second': '138.8', 'eval_steps_per_second': '8.727', 'epoch': '4'}
{'train_runtime': '69.12', 'train_samples_per_second': '42.59', 'train_steps_per_second': '2.662', 'train_loss': '1.237', 'epoch': '4'}
  Fold 1 — F1-macro por época: [0.244, 0.217, 0.343, 0.394]
  ── K-fold 2/5 ──
{'eval_loss': '1.606', 'eval_f1_macro': '0.1679', 'eval_runtime': '1.432', 'eval_samples_per_second': '132.7', 'eval_steps_per_second': '8.381', 'epoch': '1'}
{'eval_loss': '1.454', 'eval_f1_macro': '0.4313', 'eval_runtime': '1.564', 'eval_samples_per_second': '121.5', 'eval_steps_per_second': '7.674', 'epoch': '2'}
{'eval_loss': '1.217', 'eval_f1_macro': '0.4633', 'eval_runtime': '1.457', 'eval_samples_per_second': '130.4', 'eval_steps_per_second': '8.237', 'epoch': '3'}
{'eval_loss': '1.149', 'eval_f1_macro': '0.5772', 'eval_runtime': '1.414', 'eval_samples_per_second': '134.4', 'eval_steps_per_second': '8.487', 'epoch': '4'}
{'train_runtime': '67.66', 'train_samples_per_second': '42.62', 'train_steps_per_second': '2.719', 'train_loss': '1.19', 'epoch': '4'}
  Fold 2 — F1-macro por época: [0.168, 0.431, 0.463, 0.577]
  ── K-fold 3/5 ──
{'eval_loss': '1.615', 'eval_f1_macro': '0.08687', 'eval_runtime': '1.381', 'eval_samples_per_second': '133.2', 'eval_steps_per_second': '8.689', 'epoch': '1'}
{'eval_loss': '1.432', 'eval_f1_macro': '0.359', 'eval_runtime': '1.448', 'eval_samples_per_second': '127.1', 'eval_steps_per_second': '8.288', 'epoch': '2'}
{'eval_loss': '1.283', 'eval_f1_macro': '0.4335', 'eval_runtime': '1.414', 'eval_samples_per_second': '130.1', 'eval_steps_per_second': '8.484', 'epoch': '3'}
{'eval_loss': '1.284', 'eval_f1_macro': '0.4715', 'eval_runtime': '1.386', 'eval_samples_per_second': '132.8', 'eval_steps_per_second': '8.658', 'epoch': '4'}
{'train_runtime': '67.78', 'train_samples_per_second': '42.91', 'train_steps_per_second': '2.715', 'train_loss': '1.16', 'epoch': '4'}
  Fold 3 — F1-macro por época: [0.087, 0.359, 0.434, 0.472]
  ── K-fold 4/5 ──
{'eval_loss': '1.596', 'eval_f1_macro': '0.247', 'eval_runtime': '1.16', 'eval_samples_per_second': '131.9', 'eval_steps_per_second': '8.618', 'epoch': '1'}
{'eval_loss': '1.475', 'eval_f1_macro': '0.3898', 'eval_runtime': '1.174', 'eval_samples_per_second': '130.3', 'eval_steps_per_second': '8.518', 'epoch': '2'}
{'eval_loss': '1.233', 'eval_f1_macro': '0.4818', 'eval_runtime': '1.175', 'eval_samples_per_second': '130.2', 'eval_steps_per_second': '8.507', 'epoch': '3'}
{'eval_loss': '1.171', 'eval_f1_macro': '0.4827', 'eval_runtime': '1.161', 'eval_samples_per_second': '131.8', 'eval_steps_per_second': '8.614', 'epoch': '4'}
{'train_runtime': '69.35', 'train_samples_per_second': '43.72', 'train_steps_per_second': '2.768', 'train_loss': '1.317', 'epoch': '4'}
  Fold 4 — F1-macro por época: [0.247, 0.39, 0.482, 0.483]
  ── K-fold 5/5 ──
{'eval_loss': '1.585', 'eval_f1_macro': '0.1575', 'eval_runtime': '1.594', 'eval_samples_per_second': '131.1', 'eval_steps_per_second': '8.781', 'epoch': '1'}
{'eval_loss': '1.321', 'eval_f1_macro': '0.3704', 'eval_runtime': '1.605', 'eval_samples_per_second': '130.2', 'eval_steps_per_second': '8.72', 'epoch': '2'}
{'eval_loss': '1.156', 'eval_f1_macro': '0.4805', 'eval_runtime': '1.594', 'eval_samples_per_second': '131.1', 'eval_steps_per_second': '8.784', 'epoch': '3'}
{'eval_loss': '1.127', 'eval_f1_macro': '0.5216', 'eval_runtime': '1.597', 'eval_samples_per_second': '130.9', 'eval_steps_per_second': '8.766', 'epoch': '4'}
{'train_runtime': '66.34', 'train_samples_per_second': '42.33', 'train_steps_per_second': '2.653', 'train_loss': '1.106', 'epoch': '4'}
  Fold 5 — F1-macro por época: [0.158, 0.37, 0.48, 0.522]
  F1-macro promedio por época (across 5 folds):
    Época 1: 0.1806 ± 0.0598
    Época 2: 0.3535 ± 0.0726
    Época 3: 0.4404 ± 0.0519
    Época 4: 0.4894 ± 0.0604  ← elegida
  → Épocas elegidas para el entrenamiento final: 4
{'loss': '1.607', 'grad_norm': '1.772', 'learning_rate': '1.652e-05', 'epoch': '0.3509'}
{'loss': '1.596', 'grad_norm': '3.691', 'learning_rate': '1.844e-05', 'epoch': '0.7018'}
{'loss': '1.599', 'grad_norm': '6.162', 'learning_rate': '1.649e-05', 'epoch': '1.053'}
{'loss': '1.483', 'grad_norm': '17.62', 'learning_rate': '1.454e-05', 'epoch': '1.404'}
{'loss': '1.235', 'grad_norm': '14.33', 'learning_rate': '1.259e-05', 'epoch': '1.754'}
{'loss': '1.215', 'grad_norm': '13.81', 'learning_rate': '1.063e-05', 'epoch': '2.105'}
{'loss': '0.9415', 'grad_norm': '14.81', 'learning_rate': '8.683e-06', 'epoch': '2.456'}
{'loss': '0.8625', 'grad_norm': '13.72', 'learning_rate': '6.732e-06', 'epoch': '2.807'}
{'loss': '0.7042', 'grad_norm': '17.22', 'learning_rate': '4.78e-06', 'epoch': '3.158'}
{'loss': '0.6125', 'grad_norm': '8.849', 'learning_rate': '2.829e-06', 'epoch': '3.509'}
{'loss': '0.5734', 'grad_norm': '12.35', 'learning_rate': '8.78e-07', 'epoch': '3.86'}
{'train_runtime': '77.8', 'train_samples_per_second': '46.84', 'train_steps_per_second': '2.931', 'train_loss': '1.109', 'epoch': '4'}
F1-macro roberta_es Condición A (comparable): 0.5103
Log Loss: 1.1644
PR-AUC macro: 0.5428
Casos excluidos por nulo_texto: 6 / 183 (3.3%)
                    precision    recall  f1-score   support
      muy_positivo       0.52      0.57      0.54        30
          positivo       0.56      0.48      0.52        75
levemente_positivo       0.46      0.47      0.46        45
           neutral       0.36      0.50      0.42        20
          negativo       0.67      0.57      0.62         7
          accuracy                           0.50       177
         macro avg       0.51      0.52      0.51       177
      weighted avg       0.51      0.50      0.50       177
Matriz de confusión:
                    muy_positivo  positivo  ...  neutral  negativo
muy_positivo                  17         8  ...        3         0
positivo                      15        36  ...        6         0
levemente_positivo             0        16  ...        7         1
neutral                        0         4  ...       10         1
negativo                       1         0  ...        2         4
[5 rows x 5 columns]
Tiempo de esta condición (incluye k-fold + entrenamiento final): 7.3 minutos
Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es (condición A)
RESUMEN FINAL — RoBERTa-es (BERTIN)
  condicion  f1_macro  n_excluidos_nulo_texto
0         B  0.451625                       6
1         A  0.510252                       6
```

### `0c8b4cb`, celda 16 (contador 19)

`!python "/content/drive/MyDrive/Working_Paper/entrenar_roberta_multisemilla.py" --semillas 42,123,2024,7,99`

```
Semillas a correr: [42, 123, 2024, 7, 99]
Epocas fijas: 4 (k-fold NO se repite por semilla)
Ids de test excluidos por nulo_texto (compartido A/B): 6
  Semilla 42 — Condicion B
{'train_runtime': '66.04', 'train_samples_per_second': '52.34', 'train_steps_per_second': '3.271', 'train_loss': '1.185', 'epoch': '4'}
  F1-macro: 0.5682  |  Log Loss: 1.0820  |  PR-AUC: 0.6219  |  1.2 min
  Semilla 42 — Condicion A
{'train_runtime': '77.55', 'train_samples_per_second': '46.99', 'train_steps_per_second': '2.94', 'train_loss': '1.216', 'epoch': '4'}
  F1-macro: 0.4811  |  Log Loss: 1.1751  |  PR-AUC: 0.5347  |  1.4 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es/multisemilla/detalle_multisemilla_parcial.csv (2 corridas completadas)
  Semilla 123 — Condicion B
{'train_runtime': '74.02', 'train_samples_per_second': '46.69', 'train_steps_per_second': '2.918', 'train_loss': '1.208', 'epoch': '4'}
  F1-macro: 0.4897  |  Log Loss: 1.1989  |  PR-AUC: 0.5075  |  1.3 min
  Semilla 123 — Condicion A
{'train_runtime': '77.7', 'train_samples_per_second': '46.9', 'train_steps_per_second': '2.934', 'train_loss': '1.158', 'epoch': '4'}
  F1-macro: 0.4748  |  Log Loss: 1.2077  |  PR-AUC: 0.4919  |  1.4 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es/multisemilla/detalle_multisemilla_parcial.csv (4 corridas completadas)
  Semilla 2024 — Condicion B
{'train_runtime': '74.15', 'train_samples_per_second': '46.61', 'train_steps_per_second': '2.913', 'train_loss': '1.282', 'epoch': '4'}
  F1-macro: 0.4852  |  Log Loss: 1.1884  |  PR-AUC: 0.5396  |  1.3 min
  Semilla 2024 — Condicion A
{'train_runtime': '77.82', 'train_samples_per_second': '46.82', 'train_steps_per_second': '2.93', 'train_loss': '1.211', 'epoch': '4'}
  F1-macro: 0.4123  |  Log Loss: 1.3254  |  PR-AUC: 0.4340  |  1.4 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es/multisemilla/detalle_multisemilla_parcial.csv (6 corridas completadas)
  Semilla 7 — Condicion B
{'train_runtime': '74.14', 'train_samples_per_second': '46.62', 'train_steps_per_second': '2.913', 'train_loss': '0.9739', 'epoch': '4'}
  F1-macro: 0.5601  |  Log Loss: 1.0688  |  PR-AUC: 0.6018  |  1.3 min
  Semilla 7 — Condicion A
{'train_runtime': '77.8', 'train_samples_per_second': '46.84', 'train_steps_per_second': '2.931', 'train_loss': '1.119', 'epoch': '4'}
  F1-macro: 0.4480  |  Log Loss: 1.1880  |  PR-AUC: 0.4938  |  1.4 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es/multisemilla/detalle_multisemilla_parcial.csv (8 corridas completadas)
  Semilla 99 — Condicion B
{'train_runtime': '74.19', 'train_samples_per_second': '46.58', 'train_steps_per_second': '2.911', 'train_loss': '0.9847', 'epoch': '4'}
  F1-macro: 0.4754  |  Log Loss: 1.1395  |  PR-AUC: 0.5636  |  1.3 min
  Semilla 99 — Condicion A
{'train_runtime': '77.75', 'train_samples_per_second': '46.87', 'train_steps_per_second': '2.933', 'train_loss': '1.234', 'epoch': '4'}
  F1-macro: 0.4351  |  Log Loss: 1.1907  |  PR-AUC: 0.5085  |  1.4 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es/multisemilla/detalle_multisemilla_parcial.csv (10 corridas completadas)
  RESUMEN — 5 SEMILLAS
 semilla  f1_macro_A  f1_macro_B  diferencia_B_menos_A favorece
       7    0.448008    0.560067              0.112059        B
      42    0.481107    0.568178              0.087071        B
      99    0.435106    0.475401              0.040294        B
     123    0.474797    0.489718              0.014921        B
    2024    0.412272    0.485160              0.072888        B
  Diferencia B-A -- media: 0.0654  desv.est.: 0.0383
  Semillas donde favorece B: 5/5  |  favorece A: 0/5
  DIAGNOSTICO: la ordenacion B vs A fue ESTABLE en las 5 semillas.
  Esto respalda tratar el resultado de BERTIN como un hallazgo
  arquitectonico legitimo, no como varianza de entrenamiento.
  CSVs guardados en /content/drive/MyDrive/Working_Paper/resultados_colab/roberta_es/multisemilla/:
    detalle_multisemilla.csv
    resumen_multisemilla.csv
    predicciones_s<semilla>_<condicion>.csv (uno por semilla y condicion)
```

### `5cc821d`, celda 1 (contador 7)

`!nvidia-smi`

```
Fri Aug 28 17:18:57 2026
| NVIDIA-SMI 580.82.07              Driver Version: 580.82.07      CUDA Version: 13.0     |
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|   0  Tesla T4                       Off |   00000000:00:04.0 Off |                    0 |
| N/A   39C    P8             13W /   70W |       0MiB /  15360MiB |      0%      Default |
|                                         |                        |                  N/A |
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|  No running processes found                                                             |
```

### `5cc821d`, celda 8 (contador 9)

`!python "/content/drive/MyDrive/Working_Paper/entrenar_beto.py" --modo preview`

```
Ids de test excluidos por nulo_texto (compartido entre A y B): 6 → [1685, 1784, 1857, 1901, 2045, 2110]
  BETO — Condición B  [PREVIEW]
Train completo: 40 | Test: 10
  [PREVIEW] K-fold de épocas omitido — se usa 1 época(s) fija(s).
  → Épocas elegidas para el entrenamiento final: 1
{'train_runtime': '1.67', 'train_samples_per_second': '23.95', 'train_steps_per_second': '1.796', 'train_loss': '1.677', 'epoch': '1'}
F1-macro beto Condición B (comparable): 0.0727
Log Loss: 1.5697
PR-AUC macro: 0.3848
Casos excluidos por nulo_texto: 6 / 10 (60.0%)
                    precision    recall  f1-score   support
      muy_positivo       0.00      0.00      0.00         1
          positivo       0.00      0.00      0.00         1
levemente_positivo       0.00      0.00      0.00         2
           neutral       0.29      0.50      0.36         4
          negativo       0.00      0.00      0.00         2
          accuracy                           0.20        10
         macro avg       0.06      0.10      0.07        10
      weighted avg       0.11      0.20      0.15        10
Matriz de confusión:
                    muy_positivo  positivo  ...  neutral  negativo
muy_positivo                   0         0  ...        1         0
positivo                       0         0  ...        1         0
levemente_positivo             0         0  ...        2         0
neutral                        0         0  ...        2         0
negativo                       0         0  ...        1         0
[5 rows x 5 columns]
Tiempo de esta condición (incluye k-fold + entrenamiento final): 0.1 minutos
Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto (condición B_preview)
  BETO — Condición A  [PREVIEW]
Train completo: 40 | Test: 10
  [PREVIEW] K-fold de épocas omitido — se usa 1 época(s) fija(s).
  → Épocas elegidas para el entrenamiento final: 1
{'train_runtime': '0.7897', 'train_samples_per_second': '50.66', 'train_steps_per_second': '3.799', 'train_loss': '1.64', 'epoch': '1'}
F1-macro beto Condición A (comparable): 0.1200
Log Loss: 1.5577
PR-AUC macro: 0.5280
Casos excluidos por nulo_texto: 6 / 10 (60.0%)
                    precision    recall  f1-score   support
      muy_positivo       0.00      0.00      0.00         1
          positivo       0.00      0.00      0.00         1
levemente_positivo       0.00      0.00      0.00         2
           neutral       0.50      0.75      0.60         4
          negativo       0.00      0.00      0.00         2
          accuracy                           0.30        10
         macro avg       0.10      0.15      0.12        10
      weighted avg       0.20      0.30      0.24        10
Matriz de confusión:
                    muy_positivo  positivo  ...  neutral  negativo
muy_positivo                   0         0  ...        1         0
positivo                       0         0  ...        0         0
levemente_positivo             0         1  ...        1         0
neutral                        0         1  ...        3         0
negativo                       0         1  ...        1         0
[5 rows x 5 columns]
Tiempo de esta condición (incluye k-fold + entrenamiento final): 0.0 minutos
Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto (condición A_preview)
RESUMEN FINAL — BETO  [PREVIEW]
  condicion  f1_macro  n_excluidos_nulo_texto
0         B  0.072727                       6
1         A  0.120000                       6
Si todo corrió sin errores, ejecuta con --modo completo (o sin argumento) para la corrida real.
```

### `5cc821d`, celda 9 (contador 10)

`!python "/content/drive/MyDrive/Working_Paper/entrenar_beto.py" --modo completo`

```
Ids de test excluidos por nulo_texto (compartido entre A y B): 6 → [1685, 1784, 1857, 1901, 2045, 2110]
  BETO — Condición B
Train completo: 864 | Test: 183
  ── K-fold 1/5 ──
{'eval_loss': '1.349', 'eval_f1_macro': '0.3967', 'eval_runtime': '0.9062', 'eval_samples_per_second': '161.1', 'eval_steps_per_second': '11.04', 'epoch': '1'}
{'eval_loss': '1.169', 'eval_f1_macro': '0.4398', 'eval_runtime': '0.9253', 'eval_samples_per_second': '157.8', 'eval_steps_per_second': '10.81', 'epoch': '2'}
{'eval_loss': '1.065', 'eval_f1_macro': '0.4987', 'eval_runtime': '0.9327', 'eval_samples_per_second': '156.5', 'eval_steps_per_second': '10.72', 'epoch': '3'}
{'eval_loss': '1.083', 'eval_f1_macro': '0.4753', 'eval_runtime': '0.9427', 'eval_samples_per_second': '154.9', 'eval_steps_per_second': '10.61', 'epoch': '4'}
{'train_runtime': '57.15', 'train_samples_per_second': '50.25', 'train_steps_per_second': '3.149', 'train_loss': '0.9442', 'epoch': '4'}
  Fold 1 — F1-macro por época: [0.397, 0.44, 0.499, 0.475]
  ── K-fold 2/5 ──
{'eval_loss': '1.428', 'eval_f1_macro': '0.2997', 'eval_runtime': '1.384', 'eval_samples_per_second': '153.1', 'eval_steps_per_second': '10.11', 'epoch': '1'}
{'eval_loss': '1.128', 'eval_f1_macro': '0.5095', 'eval_runtime': '1.424', 'eval_samples_per_second': '148.8', 'eval_steps_per_second': '9.829', 'epoch': '2'}
{'eval_loss': '1.039', 'eval_f1_macro': '0.5801', 'eval_runtime': '1.456', 'eval_samples_per_second': '145.7', 'eval_steps_per_second': '9.619', 'epoch': '3'}
{'eval_loss': '1.019', 'eval_f1_macro': '0.5639', 'eval_runtime': '1.476', 'eval_samples_per_second': '143.6', 'eval_steps_per_second': '9.485', 'epoch': '4'}
{'train_runtime': '56.84', 'train_samples_per_second': '45.88', 'train_steps_per_second': '2.885', 'train_loss': '1.008', 'epoch': '4'}
  Fold 2 — F1-macro por época: [0.3, 0.51, 0.58, 0.564]
  ── K-fold 3/5 ──
{'eval_loss': '1.437', 'eval_f1_macro': '0.3606', 'eval_runtime': '1.165', 'eval_samples_per_second': '143.4', 'eval_steps_per_second': '9.443', 'epoch': '1'}
{'eval_loss': '1.202', 'eval_f1_macro': '0.4275', 'eval_runtime': '1.209', 'eval_samples_per_second': '138.1', 'eval_steps_per_second': '9.098', 'epoch': '2'}
{'eval_loss': '1.173', 'eval_f1_macro': '0.5106', 'eval_runtime': '1.189', 'eval_samples_per_second': '140.4', 'eval_steps_per_second': '9.249', 'epoch': '3'}
{'eval_loss': '1.158', 'eval_f1_macro': '0.496', 'eval_runtime': '1.164', 'eval_samples_per_second': '143.5', 'eval_steps_per_second': '9.452', 'epoch': '4'}
{'train_runtime': '62.13', 'train_samples_per_second': '44.88', 'train_steps_per_second': '2.833', 'train_loss': '0.9491', 'epoch': '4'}
  Fold 3 — F1-macro por época: [0.361, 0.427, 0.511, 0.496]
  ── K-fold 4/5 ──
{'eval_loss': '1.389', 'eval_f1_macro': '0.4105', 'eval_runtime': '1.029', 'eval_samples_per_second': '141.9', 'eval_steps_per_second': '9.719', 'epoch': '1'}
{'eval_loss': '1.156', 'eval_f1_macro': '0.4882', 'eval_runtime': '1.03', 'eval_samples_per_second': '141.8', 'eval_steps_per_second': '9.711', 'epoch': '2'}
{'eval_loss': '1.154', 'eval_f1_macro': '0.5015', 'eval_runtime': '1.037', 'eval_samples_per_second': '140.7', 'eval_steps_per_second': '9.639', 'epoch': '3'}
{'eval_loss': '1.175', 'eval_f1_macro': '0.5359', 'eval_runtime': '1.034', 'eval_samples_per_second': '141.2', 'eval_steps_per_second': '9.672', 'epoch': '4'}
{'train_runtime': '62.81', 'train_samples_per_second': '45.72', 'train_steps_per_second': '2.866', 'train_loss': '0.9313', 'epoch': '4'}
  Fold 4 — F1-macro por época: [0.411, 0.488, 0.501, 0.536]
  ── K-fold 5/5 ──
{'eval_loss': '1.481', 'eval_f1_macro': '0.2233', 'eval_runtime': '1.379', 'eval_samples_per_second': '140', 'eval_steps_per_second': '9.43', 'epoch': '1'}
{'eval_loss': '1.219', 'eval_f1_macro': '0.4821', 'eval_runtime': '1.363', 'eval_samples_per_second': '141.7', 'eval_steps_per_second': '9.541', 'epoch': '2'}
{'eval_loss': '1.202', 'eval_f1_macro': '0.4706', 'eval_runtime': '1.372', 'eval_samples_per_second': '140.6', 'eval_steps_per_second': '9.473', 'epoch': '3'}
{'eval_loss': '1.218', 'eval_f1_macro': '0.4924', 'eval_runtime': '1.371', 'eval_samples_per_second': '140.7', 'eval_steps_per_second': '9.479', 'epoch': '4'}
{'train_runtime': '60.39', 'train_samples_per_second': '44.44', 'train_steps_per_second': '2.782', 'train_loss': '0.9526', 'epoch': '4'}
  Fold 5 — F1-macro por época: [0.223, 0.482, 0.471, 0.492]
  F1-macro promedio por época (across 5 folds):
    Época 1: 0.3382 ± 0.0691
    Época 2: 0.4694 ± 0.0309
    Época 3: 0.5123 ± 0.0364
    Época 4: 0.5127 ± 0.0324  ← elegida
  → Épocas elegidas para el entrenamiento final: 4
{'loss': '1.624', 'grad_norm': '5.553', 'learning_rate': '1.727e-05', 'epoch': '0.3704'}
{'loss': '1.551', 'grad_norm': '8.24', 'learning_rate': '1.825e-05', 'epoch': '0.7407'}
{'loss': '1.381', 'grad_norm': '10.16', 'learning_rate': '1.619e-05', 'epoch': '1.111'}
{'loss': '1.059', 'grad_norm': '11.53', 'learning_rate': '1.412e-05', 'epoch': '1.481'}
{'loss': '0.957', 'grad_norm': '12.72', 'learning_rate': '1.206e-05', 'epoch': '1.852'}
{'loss': '0.7511', 'grad_norm': '6.601', 'learning_rate': '1e-05', 'epoch': '2.222'}
{'loss': '0.6233', 'grad_norm': '12.72', 'learning_rate': '7.938e-06', 'epoch': '2.593'}
{'loss': '0.6098', 'grad_norm': '13.44', 'learning_rate': '5.876e-06', 'epoch': '2.963'}
{'loss': '0.441', 'grad_norm': '7.512', 'learning_rate': '3.814e-06', 'epoch': '3.333'}
{'loss': '0.4049', 'grad_norm': '6.037', 'learning_rate': '1.753e-06', 'epoch': '3.704'}
{'train_runtime': '70.88', 'train_samples_per_second': '48.76', 'train_steps_per_second': '3.048', 'train_loss': '0.899', 'epoch': '4'}
F1-macro beto Condición B (comparable): 0.5219
Log Loss: 1.0614
PR-AUC macro: 0.5891
Casos excluidos por nulo_texto: 6 / 183 (3.3%)
                    precision    recall  f1-score   support
      muy_positivo       0.49      0.57      0.52        30
          positivo       0.58      0.60      0.59        75
levemente_positivo       0.62      0.51      0.56        45
           neutral       0.40      0.40      0.40        20
          negativo       0.50      0.57      0.53         7
          accuracy                           0.55       177
         macro avg       0.52      0.53      0.52       177
      weighted avg       0.55      0.55      0.55       177
Matriz de confusión:
                    muy_positivo  positivo  ...  neutral  negativo
muy_positivo                  17        11  ...        2         0
positivo                      17        45  ...        4         0
levemente_positivo             0        15  ...        5         2
neutral                        1         5  ...        8         2
negativo                       0         1  ...        1         4
[5 rows x 5 columns]
Tiempo de esta condición (incluye k-fold + entrenamiento final): 6.4 minutos
Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto (condición B)
  BETO — Condición A
Train completo: 911 | Test: 183
  ── K-fold 1/5 ──
{'eval_loss': '1.439', 'eval_f1_macro': '0.3258', 'eval_runtime': '1.229', 'eval_samples_per_second': '142.4', 'eval_steps_per_second': '8.953', 'epoch': '1'}
{'eval_loss': '1.28', 'eval_f1_macro': '0.4217', 'eval_runtime': '1.261', 'eval_samples_per_second': '138.8', 'eval_steps_per_second': '8.722', 'epoch': '2'}
{'eval_loss': '1.29', 'eval_f1_macro': '0.4161', 'eval_runtime': '1.227', 'eval_samples_per_second': '142.6', 'eval_steps_per_second': '8.963', 'epoch': '3'}
{'eval_loss': '1.341', 'eval_f1_macro': '0.4065', 'eval_runtime': '1.221', 'eval_samples_per_second': '143.3', 'eval_steps_per_second': '9.006', 'epoch': '4'}
{'train_runtime': '65.4', 'train_samples_per_second': '45.02', 'train_steps_per_second': '2.814', 'train_loss': '0.9863', 'epoch': '4'}
  Fold 1 — F1-macro por época: [0.326, 0.422, 0.416, 0.407]
  ── K-fold 2/5 ──
{'eval_loss': '1.464', 'eval_f1_macro': '0.3651', 'eval_runtime': '1.33', 'eval_samples_per_second': '142.8', 'eval_steps_per_second': '9.02', 'epoch': '1'}
{'eval_loss': '1.216', 'eval_f1_macro': '0.5695', 'eval_runtime': '1.336', 'eval_samples_per_second': '142.2', 'eval_steps_per_second': '8.98', 'epoch': '2'}
{'eval_loss': '1.094', 'eval_f1_macro': '0.5727', 'eval_runtime': '1.346', 'eval_samples_per_second': '141.1', 'eval_steps_per_second': '8.913', 'epoch': '3'}
{'eval_loss': '1.08', 'eval_f1_macro': '0.598', 'eval_runtime': '1.34', 'eval_samples_per_second': '141.8', 'eval_steps_per_second': '8.958', 'epoch': '4'}
{'train_runtime': '64.31', 'train_samples_per_second': '44.84', 'train_steps_per_second': '2.861', 'train_loss': '1.043', 'epoch': '4'}
  Fold 2 — F1-macro por época: [0.365, 0.569, 0.573, 0.598]
  ── K-fold 3/5 ──
{'eval_loss': '1.405', 'eval_f1_macro': '0.3408', 'eval_runtime': '1.281', 'eval_samples_per_second': '143.6', 'eval_steps_per_second': '9.368', 'epoch': '1'}
{'eval_loss': '1.181', 'eval_f1_macro': '0.4267', 'eval_runtime': '1.286', 'eval_samples_per_second': '143', 'eval_steps_per_second': '9.328', 'epoch': '2'}
{'eval_loss': '1.11', 'eval_f1_macro': '0.4807', 'eval_runtime': '1.291', 'eval_samples_per_second': '142.5', 'eval_steps_per_second': '9.296', 'epoch': '3'}
{'eval_loss': '1.131', 'eval_f1_macro': '0.4884', 'eval_runtime': '1.288', 'eval_samples_per_second': '142.8', 'eval_steps_per_second': '9.316', 'epoch': '4'}
{'train_runtime': '64.48', 'train_samples_per_second': '45.1', 'train_steps_per_second': '2.854', 'train_loss': '1.035', 'epoch': '4'}
  Fold 3 — F1-macro por época: [0.341, 0.427, 0.481, 0.488]
  ── K-fold 4/5 ──
{'eval_loss': '1.458', 'eval_f1_macro': '0.3969', 'eval_runtime': '1.077', 'eval_samples_per_second': '142.1', 'eval_steps_per_second': '9.284', 'epoch': '1'}
{'eval_loss': '1.134', 'eval_f1_macro': '0.4283', 'eval_runtime': '1.081', 'eval_samples_per_second': '141.5', 'eval_steps_per_second': '9.248', 'epoch': '2'}
{'eval_loss': '1.063', 'eval_f1_macro': '0.5165', 'eval_runtime': '1.079', 'eval_samples_per_second': '141.8', 'eval_steps_per_second': '9.267', 'epoch': '3'}
{'eval_loss': '1.075', 'eval_f1_macro': '0.5041', 'eval_runtime': '1.083', 'eval_samples_per_second': '141.3', 'eval_steps_per_second': '9.237', 'epoch': '4'}
{'train_runtime': '66.34', 'train_samples_per_second': '45.7', 'train_steps_per_second': '2.894', 'train_loss': '1.045', 'epoch': '4'}
  Fold 4 — F1-macro por época: [0.397, 0.428, 0.517, 0.504]
  ── K-fold 5/5 ──
{'eval_loss': '1.472', 'eval_f1_macro': '0.3991', 'eval_runtime': '1.469', 'eval_samples_per_second': '142.3', 'eval_steps_per_second': '9.531', 'epoch': '1'}
{'eval_loss': '1.15', 'eval_f1_macro': '0.4717', 'eval_runtime': '1.473', 'eval_samples_per_second': '141.9', 'eval_steps_per_second': '9.506', 'epoch': '2'}
{'eval_loss': '1.042', 'eval_f1_macro': '0.5022', 'eval_runtime': '1.474', 'eval_samples_per_second': '141.8', 'eval_steps_per_second': '9.5', 'epoch': '3'}
{'eval_loss': '1', 'eval_f1_macro': '0.5522', 'eval_runtime': '1.472', 'eval_samples_per_second': '141.9', 'eval_steps_per_second': '9.507', 'epoch': '4'}
{'train_runtime': '63.3', 'train_samples_per_second': '44.36', 'train_steps_per_second': '2.78', 'train_loss': '1.087', 'epoch': '4'}
  Fold 5 — F1-macro por época: [0.399, 0.472, 0.502, 0.552]
  F1-macro promedio por época (across 5 folds):
    Época 1: 0.3655 ± 0.0293
    Época 2: 0.4636 ± 0.0559
    Época 3: 0.4976 ± 0.0509
    Época 4: 0.5098 ± 0.0644  ← elegida
  → Épocas elegidas para el entrenamiento final: 4
{'loss': '1.643', 'grad_norm': '4.266', 'learning_rate': '1.652e-05', 'epoch': '0.3509'}
{'loss': '1.551', 'grad_norm': '5.631', 'learning_rate': '1.844e-05', 'epoch': '0.7018'}
{'loss': '1.439', 'grad_norm': '8.038', 'learning_rate': '1.649e-05', 'epoch': '1.053'}
{'loss': '1.147', 'grad_norm': '8.757', 'learning_rate': '1.454e-05', 'epoch': '1.404'}
{'loss': '1.003', 'grad_norm': '12.16', 'learning_rate': '1.259e-05', 'epoch': '1.754'}
{'loss': '0.9553', 'grad_norm': '8.092', 'learning_rate': '1.063e-05', 'epoch': '2.105'}
{'loss': '0.7247', 'grad_norm': '8.906', 'learning_rate': '8.683e-06', 'epoch': '2.456'}
{'loss': '0.7048', 'grad_norm': '14.94', 'learning_rate': '6.732e-06', 'epoch': '2.807'}
{'loss': '0.5814', 'grad_norm': '5.922', 'learning_rate': '4.78e-06', 'epoch': '3.158'}
{'loss': '0.5497', 'grad_norm': '7.201', 'learning_rate': '2.829e-06', 'epoch': '3.509'}
{'loss': '0.5398', 'grad_norm': '4.967', 'learning_rate': '8.78e-07', 'epoch': '3.86'}
{'train_runtime': '74.49', 'train_samples_per_second': '48.92', 'train_steps_per_second': '3.061', 'train_loss': '0.9681', 'epoch': '4'}
F1-macro beto Condición A (comparable): 0.4648
Log Loss: 1.1479
PR-AUC macro: 0.5171
Casos excluidos por nulo_texto: 6 / 183 (3.3%)
                    precision    recall  f1-score   support
      muy_positivo       0.47      0.50      0.48        30
          positivo       0.57      0.56      0.56        75
levemente_positivo       0.54      0.44      0.49        45
           neutral       0.29      0.35      0.32        20
          negativo       0.40      0.57      0.47         7
          accuracy                           0.50       177
         macro avg       0.45      0.49      0.46       177
      weighted avg       0.51      0.50      0.50       177
Matriz de confusión:
                    muy_positivo  positivo  ...  neutral  negativo
muy_positivo                  15        11  ...        2         1
positivo                      16        42  ...        5         0
levemente_positivo             0        14  ...        9         2
neutral                        1         6  ...        7         3
negativo                       0         1  ...        1         4
[5 rows x 5 columns]
Tiempo de esta condición (incluye k-fold + entrenamiento final): 6.8 minutos
Guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto (condición A)
RESUMEN FINAL — BETO
  condicion  f1_macro  n_excluidos_nulo_texto
0         B  0.521898                       6
1         A  0.464841                       6
```

### `5cc821d`, celda 11 (contador 12)

`!python "/content/drive/MyDrive/Working_Paper/entrenar_beto_multisemilla.py" --modo preview`

```
Semillas a correr: [42, 123, 2024, 7, 99]
Epocas fijas: 4 (k-fold NO se repite por semilla)
Ids de test excluidos por nulo_texto (compartido A/B): 6
  Semilla 42 — Condicion B  [PREVIEW]
{'train_runtime': '1.181', 'train_samples_per_second': '33.88', 'train_steps_per_second': '2.541', 'train_loss': '1.677', 'epoch': '1'}
  F1-macro: 0.0727  |  Log Loss: 1.5697  |  PR-AUC: 0.3848  |  0.1 min
  Semilla 42 — Condicion A  [PREVIEW]
{'train_runtime': '0.7363', 'train_samples_per_second': '54.33', 'train_steps_per_second': '4.074', 'train_loss': '1.639', 'epoch': '1'}
  F1-macro: 0.0889  |  Log Loss: 1.5916  |  PR-AUC: 0.3617  |  0.0 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/detalle_multisemilla_parcial_preview.csv (2 corridas completadas)
  Semilla 123 — Condicion B  [PREVIEW]
{'train_runtime': '0.7394', 'train_samples_per_second': '54.1', 'train_steps_per_second': '4.057', 'train_loss': '1.579', 'epoch': '1'}
  F1-macro: 0.1091  |  Log Loss: 1.5830  |  PR-AUC: 0.3881  |  0.0 min
  Semilla 123 — Condicion A  [PREVIEW]
{'train_runtime': '0.7414', 'train_samples_per_second': '53.95', 'train_steps_per_second': '4.047', 'train_loss': '1.615', 'epoch': '1'}
  F1-macro: 0.0800  |  Log Loss: 1.6211  |  PR-AUC: 0.3436  |  0.0 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/detalle_multisemilla_parcial_preview.csv (4 corridas completadas)
  Semilla 2024 — Condicion B  [PREVIEW]
{'train_runtime': '0.7423', 'train_samples_per_second': '53.88', 'train_steps_per_second': '4.041', 'train_loss': '1.628', 'epoch': '1'}
  F1-macro: 0.0667  |  Log Loss: 1.7097  |  PR-AUC: 0.3103  |  0.0 min
  Semilla 2024 — Condicion A  [PREVIEW]
{'train_runtime': '0.7565', 'train_samples_per_second': '52.88', 'train_steps_per_second': '3.966', 'train_loss': '1.659', 'epoch': '1'}
  F1-macro: 0.0800  |  Log Loss: 1.7294  |  PR-AUC: 0.4245  |  0.0 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/detalle_multisemilla_parcial_preview.csv (6 corridas completadas)
  Semilla 7 — Condicion B  [PREVIEW]
{'train_runtime': '0.7461', 'train_samples_per_second': '53.61', 'train_steps_per_second': '4.021', 'train_loss': '1.653', 'epoch': '1'}
  F1-macro: 0.2111  |  Log Loss: 1.5723  |  PR-AUC: 0.4799  |  0.0 min
  Semilla 7 — Condicion A  [PREVIEW]
{'train_runtime': '0.7471', 'train_samples_per_second': '53.54', 'train_steps_per_second': '4.016', 'train_loss': '1.666', 'epoch': '1'}
  F1-macro: 0.0909  |  Log Loss: 1.6026  |  PR-AUC: 0.3736  |  0.0 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/detalle_multisemilla_parcial_preview.csv (8 corridas completadas)
  Semilla 99 — Condicion B  [PREVIEW]
{'train_runtime': '0.7454', 'train_samples_per_second': '53.66', 'train_steps_per_second': '4.025', 'train_loss': '1.639', 'epoch': '1'}
  F1-macro: 0.1000  |  Log Loss: 1.6533  |  PR-AUC: 0.3747  |  0.0 min
  Semilla 99 — Condicion A  [PREVIEW]
{'train_runtime': '0.7451', 'train_samples_per_second': '53.68', 'train_steps_per_second': '4.026', 'train_loss': '1.661', 'epoch': '1'}
  F1-macro: 0.1000  |  Log Loss: 1.6500  |  PR-AUC: 0.4982  |  0.0 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/detalle_multisemilla_parcial_preview.csv (10 corridas completadas)
  RESUMEN — 5 SEMILLAS
 semilla  f1_macro_A  f1_macro_B  diferencia_B_menos_A favorece
       7    0.090909    0.211111              0.120202        B
      42    0.088889    0.072727             -0.016162        A
      99    0.100000    0.100000              0.000000        A
     123    0.080000    0.109091              0.029091        B
    2024    0.080000    0.066667             -0.013333        A
  Diferencia B-A -- media: 0.0240  desv.est.: 0.0567
  Semillas donde favorece B: 2/5  |  favorece A: 3/5
  DIAGNOSTICO: la ordenacion B vs A CAMBIO de signo entre semillas.
  Esto es inesperado: pondria en duda tambien la estabilidad del
  resultado original de BETO, y ameritaria revisar si el protocolo de
  semillas multiples tiene algun sesgo no identificado.
  CSVs guardados en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/:
    detalle_multisemilla_preview.csv
    resumen_multisemilla_preview.csv
    predicciones_s<semilla>_<condicion>_preview.csv (uno por semilla y condicion)
```

### `5cc821d`, celda 12 (contador 13)

`!python "/content/drive/MyDrive/Working_Paper/entrenar_beto_multisemilla.py" --semillas 42,123,2024,7,99`

```
Semillas a correr: [42, 123, 2024, 7, 99]
Epocas fijas: 4 (k-fold NO se repite por semilla)
Ids de test excluidos por nulo_texto (compartido A/B): 6
  Semilla 42 — Condicion B
{'train_runtime': '63.83', 'train_samples_per_second': '54.15', 'train_steps_per_second': '3.384', 'train_loss': '0.8844', 'epoch': '4'}
  F1-macro: 0.5347  |  Log Loss: 1.0770  |  PR-AUC: 0.5833  |  1.1 min
  Semilla 42 — Condicion A
{'train_runtime': '71.6', 'train_samples_per_second': '50.89', 'train_steps_per_second': '3.184', 'train_loss': '0.9501', 'epoch': '4'}
  F1-macro: 0.5301  |  Log Loss: 1.1490  |  PR-AUC: 0.5544  |  1.2 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/detalle_multisemilla_parcial.csv (2 corridas completadas)
  Semilla 123 — Condicion B
{'train_runtime': '70.85', 'train_samples_per_second': '48.78', 'train_steps_per_second': '3.049', 'train_loss': '0.8889', 'epoch': '4'}
  F1-macro: 0.4964  |  Log Loss: 1.0747  |  PR-AUC: 0.5807  |  1.2 min
  Semilla 123 — Condicion A
{'train_runtime': '74.49', 'train_samples_per_second': '48.92', 'train_steps_per_second': '3.061', 'train_loss': '0.9389', 'epoch': '4'}
  F1-macro: 0.4667  |  Log Loss: 1.1523  |  PR-AUC: 0.5461  |  1.3 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/detalle_multisemilla_parcial.csv (4 corridas completadas)
  Semilla 2024 — Condicion B
{'train_runtime': '70.81', 'train_samples_per_second': '48.81', 'train_steps_per_second': '3.05', 'train_loss': '0.8928', 'epoch': '4'}
  F1-macro: 0.5169  |  Log Loss: 1.1180  |  PR-AUC: 0.5525  |  1.2 min
  Semilla 2024 — Condicion A
{'train_runtime': '74.48', 'train_samples_per_second': '48.93', 'train_steps_per_second': '3.061', 'train_loss': '0.9631', 'epoch': '4'}
  F1-macro: 0.4579  |  Log Loss: 1.1501  |  PR-AUC: 0.5069  |  1.3 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/detalle_multisemilla_parcial.csv (6 corridas completadas)
  Semilla 7 — Condicion B
{'train_runtime': '70.78', 'train_samples_per_second': '48.83', 'train_steps_per_second': '3.052', 'train_loss': '0.8523', 'epoch': '4'}
  F1-macro: 0.5350  |  Log Loss: 1.0537  |  PR-AUC: 0.6119  |  1.2 min
  Semilla 7 — Condicion A
{'train_runtime': '74.57', 'train_samples_per_second': '48.86', 'train_steps_per_second': '3.057', 'train_loss': '0.9093', 'epoch': '4'}
  F1-macro: 0.4750  |  Log Loss: 1.1520  |  PR-AUC: 0.5701  |  1.3 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/detalle_multisemilla_parcial.csv (8 corridas completadas)
  Semilla 99 — Condicion B
{'train_runtime': '70.8', 'train_samples_per_second': '48.81', 'train_steps_per_second': '3.051', 'train_loss': '0.8831', 'epoch': '4'}
  F1-macro: 0.5335  |  Log Loss: 1.1403  |  PR-AUC: 0.5535  |  1.2 min
  Semilla 99 — Condicion A
{'train_runtime': '74.41', 'train_samples_per_second': '48.97', 'train_steps_per_second': '3.064', 'train_loss': '0.9413', 'epoch': '4'}
  F1-macro: 0.3980  |  Log Loss: 1.2117  |  PR-AUC: 0.4813  |  1.3 min
  [checkpoint] Progreso guardado en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/detalle_multisemilla_parcial.csv (10 corridas completadas)
  RESUMEN — 5 SEMILLAS
 semilla  f1_macro_A  f1_macro_B  diferencia_B_menos_A favorece
       7    0.474965    0.534977              0.060012        B
      42    0.530086    0.534662              0.004576        B
      99    0.398008    0.533469              0.135461        B
     123    0.466709    0.496445              0.029736        B
    2024    0.457858    0.516941              0.059083        B
  Diferencia B-A -- media: 0.0578  desv.est.: 0.0491
  Semillas donde favorece B: 5/5  |  favorece A: 0/5
  DIAGNOSTICO: la ordenacion B vs A fue ESTABLE en las 5 semillas,
  igual que en el resultado original de una sola semilla. Esto confirma
  que el protocolo de semillas multiples NO esta sesgado a favor de B
  por diseno, y que el efecto de BETO SI es una senal real y estable,
  a diferencia de lo que se encontro originalmente en BERTIN.
  CSVs guardados en /content/drive/MyDrive/Working_Paper/resultados_colab/beto/multisemilla/:
    detalle_multisemilla.csv
    resumen_multisemilla.csv
    predicciones_s<semilla>_<condicion>.csv (uno por semilla y condicion)
```
