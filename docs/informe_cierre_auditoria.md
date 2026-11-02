# Informe de cierre de la auditoría del código (2026-10-03 a 2026-10-08)

Auditoría del pipeline de la tesis "Efecto de un marco de gobernanza de datos sobre la
calidad de un corpus de retroalimentación estudiantil y el desempeño de modelos de
análisis de sentimiento". Detalle completo y evidencia en `docs/cambios_agosto_2026.md`
(secciones citadas como §).

Principio aplicado: el código produjo resultados reportados. Primero se registró cada
versión tal como existió y después se mejoró, en commits separados, sin mezclar formato
y lógica. Cada cambio de formato se verificó con `tools/verificar_equivalencia.py`
(comparación de AST sin docstrings, anotaciones ni contenido de cadenas).

## 1. Qué se verificó y con qué evidencia

| Verificación | Evidencia | Resultado |
|---|---|---|
| La limpieza de docstrings de agosto no alteró la lógica | `verificar_equivalencia` sobre 22 commits (`b83f2b3`..`1835b1b`) | 22/22 sin diferencias de lógica (§1) |
| Cambios de lógica de agosto en 14 y 15 | Comparación contra las versiones limpias | 14: tres métricas nuevas; 15: sección (d) (§2, §3) |
| Reproducibilidad del bootstrap (prueba de aceptación) | Script 14 en `46216f2` y en `HEAD`, insumos con SHA-256 en `manifiesto_insumos.csv` | Diferencia, IC 95 % y p idénticos a la tabla de referencia en las 4 configuraciones (§13) |
| Origen de las predicciones de BETO y BERTIN | SHA-256, F1 contra `resultado_{A,B}.csv` y matrices de confusión recalculadas | Corridas principales identificadas; el bootstrap del 2026-08-30 usó la semilla 2024 (§8) |
| Versiones ejecutadas de los scripts de Colab | `.pyc` de Python 3.13 en Drive, fechas de scripts y salidas, SHA-256 | Registradas en `0c8b4cb`; las de Git no eran las ejecutadas (§9) |
| Script 13 (restricciones de esquema) | `information_schema`, respaldo `backup_antes_constraints_20260831_2324.sql`, confirmación de la autora | Aplicado el 2026-08-31 23:24; no alteró datos (§5) |
| Imputación de fechas previa al script 13 | `corpus_final.csv` (mayo), BD actual, respaldo | 23 fechas imputadas con `DATE(ingesta_timestamp)` antes del respaldo (§5) |
| Integridad del corpus | Consultas `SELECT` | 799 segmentos activos de 148 registros; 4 registros sin segmentos (§11, §16) |
| Identidad textual y de etiquetas entre A y B | Consultas `SELECT` | Texto idéntico en el 100 % de las filas primarias sin defecto textual; etiqueta idéntica en las 862 filas (§7, §11) |
| Supuesto "defectos que no modifican el texto" | Auditoría de scripts y documentos | `cuasi_duplicado` sí modifica el texto; doble definición en 05 y 09 (§6) |
| Catálogo de reglas de calidad | Extracción de texto de `.docx`, `.xlsx` y `.pdf` | Catálogo implementado de 9 reglas y de diseño de 11, con la misma numeración (§15) |
| Figuras del script 16 | Insumos con SHA-256 y comparación visual | Valores idénticos a las figuras del 2026-08-21 (§13; `manifiesto_figuras.csv`) |
| Entorno local | `00c_verificar_entorno.py`, `requirements-local.lock.txt` | ENTORNO LISTO; versiones congeladas tras la prueba de aceptación |

## 2. Qué se corrigió

| Corrección | Commit |
|---|---|
| Sección (d) del 15: "texto idéntico" por comparación directa del texto, no por lista de tipos (30 segmentos reclasificados) | `96f2b5f` |
| Script 14: `ee_bootstrap` y `emd_80` reemplazan `prop_b_mejor`, potencia retrospectiva y n requerido | `8743dcf` |
| Script 14: paneles con Δ, IC 95 % y p, sin etiqueta de "significativo" | `fbb140b` |
| Script 13b: toma las predicciones principales de RoBERTa con su nombre real | `679f3b3` |
| Script 00c: mapeo de insumos desde 13b y versiones con `importlib.metadata` | `07927c1` |
| Docstring del 14: el p de una cola nunca estuvo en el código | `46216f2` |
| Guía: principio metodológico de la Condición A precisado (3 de 9 defectos alteran el texto) | `2d53895` |
| Norma de estilo en todos los scripts (00-17, `colab/`, `config/`), verificada como equivalente | `c1f325f`, `fa91072`, `6f9b98a`, `4d1dbc2`, `9398e1f` |
| Requisitos conciliados; `scipy` declarado; `openpyxl` opcional | `e87beaa`, `2eb401e` |
| Trazabilidad de figuras y tablas (script 17, `manifiesto_figuras.csv`) | `7b050f6` |
| Documentación de contexto consolidada; guía con orden de ejecución; `.gitignore` | `b0a0420`, `0a51665`, `329de07` |

## 3. Resultados que produjo la auditoría

- **Análisis principal:** reproducido exactamente. Holm sobre las 4
  configuraciones: ningún p ajustado bajo 0.05.
- **Multisemilla** (plan fijado antes de calcular, `2c39c91`): BETO y BERTIN favorecen a
  B en 5 de 5 semillas, pero el IC de dos niveles incluye cero (p Holm 0.134 en ambos):
  no concluyente frente a la varianza de entrenamiento. La corrida principal de BERTIN
  (−0.059) es la única de seis con signo negativo.
- **Sección (d) corregida:** los flips con texto idéntico bajan de 61,5/74,4/86,2 % a
  50,0/66,7/82,8 % (baseline/BETO/BERTIN).

## 4. Limitaciones declaradas

1. **Imputación de 23 fechas** (15,5 % de los 148 registros de origen; 11,0 % de los
   segmentos) con la fecha de ingesta, que no es la fecha real. No afecta a los modelos
   de texto; las métricas de calidad A frente a B son anteriores a la imputación.
2. **Catálogos de reglas divergentes** (diseño 11, implementado 9). El texto de la tesis
   debe declarar cuál describe.
3. **`cuasi_duplicado` con dos definiciones** (05 frente a 09); en el 09 casi nunca forma
   un par cuasi-duplicado.
4. **4 registros sin segmentos** por causa no determinable (sin registro de consola del 07).
5. **Versiones de Colab:** no se fijaron en archivos de requisitos. Lo que se pudo
   establecer está en `docs/registro_entorno_colab.md`: Tesla T4, CUDA 13.0, Python 3.12
   en la primera corrida y 3.13 en la segunda, transformers 5.16.1 en la sesión de
   BERTIN del 27 de agosto (no impresa en la de BETO) y sentencepiece 0.2.2. Las dos
   corridas principales de BETO y BERTIN dieron métricas idénticas en todos los
   decimales; la comparación caso a caso no es posible porque no se conservaron las
   predicciones de la primera.
6. **Multisemilla** con 5 semillas: la prueba de signos no puede bajar de p = 0.0625 y el
   remuestreo por semillas es grueso. La semilla 42 del multisemilla no reproduce la
   corrida principal (distinto mecanismo de fijación de semilla).
7. **Brecha de gobernanza** en `segmento_retroalimentacion`, sin restricciones de
   esquema; el umbral de 5 caracteres del script 13 no coincide con RQ-09.
8. **Pruebas de orden temporal** del plan multisemilla: horas de commit locales (plan
   17:41:21, script 17:44:20, ejecución posterior); el push a GitHub fue posterior a la
   ejecución.
9. **`test_colab.ipynb`** entró por error en `0c8b4cb` (sin datos sensibles; §17).
10. **Fuga entre entrenamiento y prueba por entrevistas duplicadas** (detectada el
    2026-10-09): 17 pares de registros con texto idéntico; en 5, un registro quedó en
    entrenamiento y el otro en prueba. 20 de los 177 segmentos evaluados provienen de
    registros cuyo gemelo está en entrenamiento (7 con texto idéntico). Afecta a ambas
    condiciones; pendiente un análisis de sensibilidad (`cambios_agosto_2026.md`, §18).
11. **Época del k-fold en el tope:** la época elegida (4) coincide con `EPOCAS_MAX` en
    los cuatro casos; BERTIN A seguía mejorando (+0,049 de la época 3 a la 4).
12. **Canal `n/a` leído como nulo:** 4 violaciones de RQ-06 registradas como RQ-04 en
    `detalle_error` (sin efecto en el rechazo).
13. **Segmentación truncada a 4.000 caracteres:** el script 07 solo segmentó los
    primeros 4.000 caracteres de cada entrevista; el 41,6 % del texto del corpus (56 de
    152 entrevistas) no forma parte del análisis. No estaba documentado (§21).
14. **Llamadas a la API sin temperatura fijada** (04, 07, 08 y 09_reetiquetar_positivos):
    rige la temperatura por defecto (1,0), así que la segmentación, el etiquetado y las
    variantes sintéticas no son reproducibles exactamente (§22; Anexo B).
15. **Un nombre propio en el código publicado** (`01_deduplicar_y_cargar.py`) y nombres de
    programa y de sesión en código y bitácora; sin texto de estudiantes en el historial
    (§22).

## 5. Pendiente para la autora (`[VERIFICAR]`)

- Si el Reporte Metodológico o el capítulo usaron cifras del bootstrap del 2026-08-30, la
  lectura de una cola (p ≈ 0.046), la sección (d) sin corregir, o describen la brecha de
  la sección 16 como abierta.
- Qué catálogo de reglas describe el capítulo de Metodología.
- Causa de los 4 registros sin segmentos y por qué `roberta_predicciones_{A,B}.csv` tiene
  ese nombre.

## 5b. Sensibilidad a la fuga (plan del 2026-10-09)

Excluyendo los 20 segmentos evaluados expuestos a la fuga, el criterio del plan se
cumple: en las cuatro configuraciones se mantienen la dirección de Δ y la no
significancia con Holm, y el multisemilla sigue sin ser robusto a la semilla. El F1-macro
absoluto baja en todos los casos; en BETO con ajuste fino Δ baja de +0,057 a +0,033 y en
el multisemilla B > A pasa de 5/5 a 3/5 semillas (§19). Anexos de la tesis generados en
`docs/anexos/` por el script 18 (numeración del 2026-10-09: C = reglas de calidad).

## 6. Propuestas de mejora (no aplicadas)

Ver `docs/propuestas_mejora_arquitectura.md`: restricciones para
`segmento_retroalimentacion`; umbral 5 frente a 20 caracteres; desacoplar
`beto_sin_finetuning.py`; numeración de los `09_`; salida descriptiva y docstrings sin
interpretaciones previas en los scripts multisemilla; `requirements-colab.txt`.

## 7. Notebook `test_colab.ipynb`

Tratado el 2026-10-08 en tres commits: registro de la copia de trabajo tal como estaba
(`5cc821d`), extracción de versiones, sesiones y salidas a
`docs/registro_entorno_colab.md` (`e5fb001`, verificado contra las tres versiones del
notebook) y limpieza de las salidas (`e779443`). Las salidas originales siguen en el
historial de Git.
