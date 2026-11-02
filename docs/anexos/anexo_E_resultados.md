# Anexo E — Resultados complementarios
> Métricas por clase de las 8 combinaciones de modelo y condición, bootstrap, multisemilla y sensibilidad a la fuga.
> Generado por `scripts/18_anexos_esquema_general.py`. No editar a mano.

## E.1 Precisión, cobertura y F1 por clase (8 combinaciones de modelo y condición)
Calculadas desde las matrices de confusión registradas (`outputs/graficos_input/<modelo>/matriz_confusion_{A,B}.csv`, n = 177). Cobertura = recall. BERTIN = `roberta_es`.

| configuracion | condicion | clase | precision | cobertura | f1 | soporte |
|---|---|---|---|---|---|---|
| baseline | A | muy_positivo | 0.5161 | 0.5333 | 0.5246 | 30 |
| baseline | A | positivo | 0.5352 | 0.5067 | 0.5205 | 75 |
| baseline | A | levemente_positivo | 0.38 | 0.4222 | 0.4 | 45 |
| baseline | A | neutral | 0.3125 | 0.25 | 0.2778 | 20 |
| baseline | A | negativo | 0.4444 | 0.5714 | 0.5 | 7 |
| baseline | B | muy_positivo | 0.4375 | 0.4667 | 0.4516 | 30 |
| baseline | B | positivo | 0.5256 | 0.5467 | 0.5359 | 75 |
| baseline | B | levemente_positivo | 0.4468 | 0.4667 | 0.4565 | 45 |
| baseline | B | neutral | 0.5 | 0.3 | 0.375 | 20 |
| baseline | B | negativo | 0.5 | 0.5714 | 0.5333 | 7 |
| beto_sin_finetuning | A | muy_positivo | 0.5333 | 0.5333 | 0.5333 | 30 |
| beto_sin_finetuning | A | positivo | 0.5072 | 0.4667 | 0.4861 | 75 |
| beto_sin_finetuning | A | levemente_positivo | 0.3774 | 0.4444 | 0.4082 | 45 |
| beto_sin_finetuning | A | neutral | 0.3529 | 0.3 | 0.3243 | 20 |
| beto_sin_finetuning | A | negativo | 0.375 | 0.4286 | 0.4 | 7 |
| beto_sin_finetuning | B | muy_positivo | 0.6 | 0.6 | 0.6 | 30 |
| beto_sin_finetuning | B | positivo | 0.5588 | 0.5067 | 0.5315 | 75 |
| beto_sin_finetuning | B | levemente_positivo | 0.4 | 0.4889 | 0.44 | 45 |
| beto_sin_finetuning | B | neutral | 0.3333 | 0.25 | 0.2857 | 20 |
| beto_sin_finetuning | B | negativo | 0.3333 | 0.4286 | 0.375 | 7 |
| beto | A | muy_positivo | 0.4688 | 0.5 | 0.4839 | 30 |
| beto | A | positivo | 0.5676 | 0.56 | 0.5638 | 75 |
| beto | A | levemente_positivo | 0.5405 | 0.4444 | 0.4878 | 45 |
| beto | A | neutral | 0.2917 | 0.35 | 0.3182 | 20 |
| beto | A | negativo | 0.4 | 0.5714 | 0.4706 | 7 |
| beto | B | muy_positivo | 0.4857 | 0.5667 | 0.5231 | 30 |
| beto | B | positivo | 0.5844 | 0.6 | 0.5921 | 75 |
| beto | B | levemente_positivo | 0.6216 | 0.5111 | 0.561 | 45 |
| beto | B | neutral | 0.4 | 0.4 | 0.4 | 20 |
| beto | B | negativo | 0.5 | 0.5714 | 0.5333 | 7 |
| bertin_roberta | A | muy_positivo | 0.5152 | 0.5667 | 0.5397 | 30 |
| bertin_roberta | A | positivo | 0.5625 | 0.48 | 0.518 | 75 |
| bertin_roberta | A | levemente_positivo | 0.4565 | 0.4667 | 0.4615 | 45 |
| bertin_roberta | A | neutral | 0.3571 | 0.5 | 0.4167 | 20 |
| bertin_roberta | A | negativo | 0.6667 | 0.5714 | 0.6154 | 7 |
| bertin_roberta | B | muy_positivo | 0.5 | 0.4667 | 0.4828 | 30 |
| bertin_roberta | B | positivo | 0.5517 | 0.4267 | 0.4812 | 75 |
| bertin_roberta | B | levemente_positivo | 0.3699 | 0.6 | 0.4576 | 45 |
| bertin_roberta | B | neutral | 0.5 | 0.3 | 0.375 | 20 |
| bertin_roberta | B | negativo | 0.5 | 0.4286 | 0.4615 | 7 |

CSV: `anexo_E_resultados_metricas_por_clase.csv`

## E.2 Verificación: F1-macro recalculado frente al registrado

| configuracion | condicion | n | f1_macro_recalculado | f1_macro_registrado | coincide |
|---|---|---|---|---|---|
| baseline | A | 177 | 0.444583 | 0.444583 | True |
| baseline | B | 177 | 0.470483 | 0.470483 | True |
| beto_sin_finetuning | A | 177 | 0.430386 | 0.430386 | True |
| beto_sin_finetuning | B | 177 | 0.446437 | 0.446437 | True |
| beto | A | 177 | 0.464841 | 0.464841 | True |
| beto | B | 177 | 0.521898 | 0.521898 | True |
| bertin_roberta | A | 177 | 0.510252 | 0.510252 | True |
| bertin_roberta | B | 177 | 0.451625 | 0.451625 | True |

CSV: `anexo_E_resultados_verificacion_f1_macro.csv`

## E.3 Bootstrap pareado, análisis principal (n = 177)
Salida de `14_bootstrap_pareado.py`.

| modelo | f1_macro_B | f1_macro_A | diferencia_B_menos_A | ci95_low | ci95_high | p_valor_aprox | significativo_95 | ee_bootstrap | emd_80 | n_pares |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 0.4705 | 0.4446 | 0.0259 | -0.0298 | 0.0842 | 0.39 | False | 0.029 | 0.0812 | 177 |
| beto | 0.5219 | 0.4648 | 0.0571 | -0.0083 | 0.1222 | 0.092 | False | 0.0335 | 0.0939 | 177 |
| bertin_roberta | 0.4516 | 0.5103 | -0.0586 | -0.1515 | 0.0291 | 0.2016 | False | 0.046 | 0.1288 | 177 |
| beto_sin_finetuning | 0.4464 | 0.4304 | 0.0161 | -0.0379 | 0.0703 | 0.5364 | False | 0.0277 | 0.0775 | 177 |

CSV: `anexo_E_resultados_bootstrap_principal.csv`

## E.4 Corrección de Holm sobre las 4 configuraciones
Salida de `14b_bootstrap_multisemilla.py`.

| modelo | diferencia_B_menos_A | ci95_low | ci95_high | p_valor_aprox | p_holm |
|---|---|---|---|---|---|
| baseline | 0.0259 | -0.0298 | 0.0842 | 0.39 | 0.78 |
| beto | 0.0571 | -0.0083 | 0.1222 | 0.092 | 0.368 |
| bertin_roberta | -0.0586 | -0.1515 | 0.0291 | 0.2016 | 0.6048 |
| beto_sin_finetuning | 0.0161 | -0.0379 | 0.0703 | 0.5364 | 0.78 |

CSV: `anexo_E_resultados_holm_principal.csv`

## E.5 Multisemilla: bootstrap pareado por semilla
Los p por semilla son descriptivos.

| modelo | semilla | f1_macro_A | f1_macro_B | diferencia_B_menos_A | ci95_low | ci95_high | p_valor_aprox | ee_bootstrap | emd_80 | n_pares |
|---|---|---|---|---|---|---|---|---|---|---|
| beto | 42 | 0.5301 | 0.5347 | 0.0046 | -0.0846 | 0.0825 | 0.9408 | 0.0425 | 0.1192 | 177 |
| beto | 123 | 0.4667 | 0.4964 | 0.0297 | -0.0579 | 0.1105 | 0.5028 | 0.0428 | 0.1198 | 177 |
| beto | 2024 | 0.4579 | 0.5169 | 0.0591 | 0.0036 | 0.1184 | 0.0392 | 0.0291 | 0.0814 | 177 |
| beto | 7 | 0.475 | 0.535 | 0.06 | -0.009 | 0.1477 | 0.0944 | 0.04 | 0.1122 | 177 |
| beto | 99 | 0.398 | 0.5335 | 0.1355 | 0.058 | 0.2164 | 0.0008 | 0.0406 | 0.1137 | 177 |
| bertin_roberta | 42 | 0.4811 | 0.5682 | 0.0871 | -0.0011 | 0.1849 | 0.0532 | 0.0479 | 0.1342 | 177 |
| bertin_roberta | 123 | 0.4748 | 0.4897 | 0.0149 | -0.0892 | 0.1187 | 0.7948 | 0.0526 | 0.1474 | 177 |
| bertin_roberta | 2024 | 0.4123 | 0.4852 | 0.0729 | -0.0246 | 0.1698 | 0.128 | 0.0496 | 0.139 | 177 |
| bertin_roberta | 7 | 0.448 | 0.5601 | 0.1121 | 0.045 | 0.1836 | 0.0012 | 0.0351 | 0.0985 | 177 |
| bertin_roberta | 99 | 0.4351 | 0.4754 | 0.0403 | -0.0723 | 0.1511 | 0.4948 | 0.0566 | 0.1587 | 177 |

CSV: `anexo_E_resultados_multisemilla_por_semilla.csv`

## E.6 Multisemilla: agregado por modelo
Incluye F1-macro A y B por semilla en E.5 (equivalente a resumen_multisemilla.csv de Colab).

| modelo | n_semillas | media_dif | de_dif | min_dif | max_dif | semillas_B_mayor | semillas_A_mayor | p_signos_binomial | ic95_low_2niveles | ic95_high_2niveles | p_2niveles | p_2niveles_holm | dif_corrida_principal | signo_consistente | robusto_a_semilla |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| beto | 5 | 0.0578 | 0.0491 | 0.0046 | 0.1355 | 5 | 0 | 0.0625 | -0.0073 | 0.1269 | 0.084 | 0.1344 | 0.0571 | True | False |
| bertin_roberta | 5 | 0.0654 | 0.0383 | 0.0149 | 0.1121 | 5 | 0 | 0.0625 | -0.0059 | 0.1335 | 0.0672 | 0.1344 | -0.0586 | True | False |

CSV: `anexo_E_resultados_multisemilla_agregado.csv`

## E.7 Multisemilla: Log Loss y PR-AUC (descriptivo)

| modelo | condicion | n_semillas | log_loss_media | log_loss_de | pr_auc_media | pr_auc_de |
|---|---|---|---|---|---|---|
| beto | A | 5 | 1.163 | 0.0273 | 0.5318 | 0.0366 |
| beto | B | 5 | 1.0927 | 0.0354 | 0.5764 | 0.0246 |
| bertin_roberta | A | 5 | 1.2174 | 0.0615 | 0.4926 | 0.0369 |
| bertin_roberta | B | 5 | 1.1355 | 0.0595 | 0.5669 | 0.0462 |

CSV: `anexo_E_resultados_multisemilla_descriptivo.csv`

## E.8 Flips por clase de defecto (sección d del script 15)
Texto idéntico determinado por comparación directa (versión corregida).

| modelo | clase_defecto | n_flips | pct_del_total_modelo |
|---|---|---|---|
| baseline | afecta_texto | 13 | 50.0 |
| baseline | sin_defecto | 7 | 26.9 |
| baseline | solo_metadatos | 6 | 23.1 |
| bertin_roberta | afecta_texto | 10 | 17.2 |
| bertin_roberta | sin_defecto | 27 | 46.6 |
| bertin_roberta | solo_metadatos | 21 | 36.2 |
| beto | afecta_texto | 13 | 33.3 |
| beto | sin_defecto | 14 | 35.9 |
| beto | solo_metadatos | 12 | 30.8 |

CSV: `anexo_E_resultados_flips_por_clase_defecto.csv`

## E.9 Análisis de sensibilidad a la fuga: bootstrap pareado (n = 157)
**Análisis de sensibilidad**, no principal: excluye los 20 segmentos evaluados expuestos a la fuga (plan del 2026-10-09).

| modelo | f1_macro_B | f1_macro_A | diferencia_B_menos_A | ci95_low | ci95_high | p_valor_aprox | significativo_95 | ee_bootstrap | emd_80 | n_pares |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 0.4056 | 0.385 | 0.0207 | -0.0338 | 0.0748 | 0.4776 | False | 0.0274 | 0.0768 | 157 |
| beto | 0.4733 | 0.4406 | 0.0328 | -0.0344 | 0.1046 | 0.3612 | False | 0.035 | 0.0981 | 157 |
| bertin_roberta | 0.4233 | 0.4992 | -0.0759 | -0.1789 | 0.0168 | 0.1064 | False | 0.0499 | 0.1398 | 157 |
| beto_sin_finetuning | 0.4015 | 0.4011 | 0.0004 | -0.0544 | 0.0533 | 0.9352 | False | 0.0276 | 0.0772 | 157 |

CSV: `anexo_E_resultados_sensibilidad_bootstrap.csv`

## E.10 Análisis de sensibilidad a la fuga: Holm
**Análisis de sensibilidad.**

| modelo | diferencia_B_menos_A | ci95_low | ci95_high | p_valor_aprox | p_holm |
|---|---|---|---|---|---|
| baseline | 0.0207 | -0.0338 | 0.0748 | 0.4776 | 1.0 |
| beto | 0.0328 | -0.0344 | 0.1046 | 0.3612 | 1.0 |
| bertin_roberta | -0.0759 | -0.1789 | 0.0168 | 0.1064 | 0.4256 |
| beto_sin_finetuning | 0.0004 | -0.0544 | 0.0533 | 0.9352 | 1.0 |

CSV: `anexo_E_resultados_sensibilidad_holm.csv`

## E.11 Análisis de sensibilidad a la fuga: multisemilla por semilla
**Análisis de sensibilidad.**

| modelo | semilla | f1_macro_A | f1_macro_B | diferencia_B_menos_A | ci95_low | ci95_high | p_valor_aprox | ee_bootstrap | emd_80 | n_pares |
|---|---|---|---|---|---|---|---|---|---|---|
| beto | 42 | 0.4924 | 0.4832 | -0.0092 | -0.1114 | 0.0749 | 0.818 | 0.0469 | 0.1315 | 157 |
| beto | 123 | 0.4517 | 0.4357 | -0.016 | -0.1168 | 0.07 | 0.7364 | 0.0467 | 0.1309 | 157 |
| beto | 2024 | 0.4514 | 0.4782 | 0.0268 | -0.0319 | 0.0856 | 0.3664 | 0.0298 | 0.0834 | 157 |
| beto | 7 | 0.4449 | 0.5016 | 0.0568 | -0.0145 | 0.1572 | 0.1296 | 0.0428 | 0.1198 | 157 |
| beto | 99 | 0.3689 | 0.5061 | 0.1372 | 0.0527 | 0.2298 | 0.0004 | 0.0456 | 0.1277 | 157 |
| bertin_roberta | 42 | 0.4784 | 0.5825 | 0.1041 | 0.0052 | 0.2193 | 0.038 | 0.0544 | 0.1525 | 157 |
| bertin_roberta | 123 | 0.4393 | 0.4658 | 0.0265 | -0.1021 | 0.1493 | 0.6744 | 0.063 | 0.1765 | 157 |
| bertin_roberta | 2024 | 0.4022 | 0.4686 | 0.0665 | -0.0416 | 0.1788 | 0.2152 | 0.0552 | 0.1546 | 157 |
| bertin_roberta | 7 | 0.4228 | 0.5313 | 0.1085 | 0.0382 | 0.1785 | 0.0012 | 0.0357 | 0.1 | 157 |
| bertin_roberta | 99 | 0.4162 | 0.4501 | 0.0339 | -0.0971 | 0.166 | 0.6584 | 0.0681 | 0.1908 | 157 |

CSV: `anexo_E_resultados_sensibilidad_multisemilla_por_semilla.csv`

## E.12 Análisis de sensibilidad a la fuga: multisemilla agregado
**Análisis de sensibilidad.**

| modelo | n_semillas | media_dif | de_dif | min_dif | max_dif | semillas_B_mayor | semillas_A_mayor | p_signos_binomial | ic95_low_2niveles | ic95_high_2niveles | p_2niveles | p_2niveles_holm | dif_corrida_principal | signo_consistente | robusto_a_semilla |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| beto | 5 | 0.0391 | 0.0622 | -0.016 | 0.1372 | 3 | 2 | 1.0 | -0.0365 | 0.1179 | 0.2992 | 0.2992 | 0.0328 | False | False |
| bertin_roberta | 5 | 0.0679 | 0.0382 | 0.0265 | 0.1085 | 5 | 0 | 0.0625 | -0.0138 | 0.1417 | 0.0972 | 0.1944 | -0.0759 | True | False |

CSV: `anexo_E_resultados_sensibilidad_multisemilla_agregado.csv`
