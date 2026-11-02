# Anexo C — Reglas de calidad
> Catálogos implementado y de diseño, correspondencia, umbrales y matriz regla × corpus.
> Generado por `scripts/18_anexos_esquema_general.py`. No editar a mano.

## a) Catálogo implementado (09a_procesar_condicion_a.py)
Criterio literal y línea del código; acción de 09a: toda violación rechaza el registro. Violaciones de `detalle_error` (ejecución 4, Condición A); las corregidas reasignan 4 casos de canal "n/a" de RQ-04 a RQ-06 (`cambios_agosto_2026.md`, §20).

| codigo | campo | descripcion_09a | criterio_literal | accion | linea_09a | restriccion_esquema | violaciones_registradas | violaciones_corregidas |
|---|---|---|---|---|---|---|---|---|
| RQ-01 | texto | Texto nulo o vacío | if not texto: | rechazar el registro | 74 | texto NOT NULL; CHECK (CHAR_LENGTH(texto) >= 5) (script 13, retroalimentacion) | 9 | 9 |
| RQ-02 | num_sesion (id_sesion) | id_sesion nulo — registro no contextualizable | if pd.isna(id_sesion) or id_sesion is None: | rechazar el registro | 88 | id_sesion NOT NULL (script 13) | 50 | 50 |
| RQ-03 | fecha_real (fecha_registro) | fecha_registro nula | if pd.isna(fecha) or fecha is None: | rechazar el registro | 93 | fecha_registro NOT NULL (script 13) | 41 | 41 |
| RQ-04 | canal_captura | canal_captura nulo | if pd.isna(canal) or canal is None: | rechazar el registro | 104 | canal_captura NOT NULL (script 13) | 20 | 16 |
| RQ-05 | fecha_real (fecha_registro) | fecha_registro con formato inválido (no ISO 8601) | pd.to_datetime(str(fecha), format="%Y-%m-%d") falla | rechazar el registro | 98 | tipo DATE de fecha_registro (parcial) | 10 | 10 |
| RQ-06 | canal_captura | canal_captura fuera del catálogo definido | if str(canal).lower().strip() not in CANAL_CATALOGO: | rechazar el registro | 108 | CHECK canal_captura IN catálogo (script 13) | 13 | 17 |
| RQ-07 | texto | Duplicado exacto o cuasi-duplicado detectado | texto_key = texto[:200].lower().strip(); if texto_key in textos_vistos | rechazar el registro | 112 | — | 34 | 34 |
| RQ-08 | texto | Texto no informativo sin valor analítico | if texto.lower().strip() in TEXTOS_NO_INFORMATIVOS: | rechazar el registro | 79 | — | 12 | 12 |
| RQ-09 | texto | Texto con longitud insuficiente (< 20 caracteres) | if len(texto) < 20: | rechazar el registro | 83 | — (el CHECK de 5 caracteres no coincide con el umbral de 20) | 12 | 12 |

CSV: `anexo_C_reglas_calidad_catalogo_implementado.csv`

## b) Catálogo de diseño (11 reglas)
Transcripción literal de la tabla de `Borradores/Working_Paper_Marco_Gobernado_v1.docx` (2026-08-09).

| RQ | Dimensión | Campo(s) | Condición de fallo | Acción | Descripción |
|---|---|---|---|---|---|
| RQ-01 | Completitud | texto | texto IS NULL o vacío | Rechazar | Texto obligatorio. Sin él el registro no tiene valor analítico. |
| RQ-02 | Completitud | id_sesion | id_sesion IS NULL | Rechazar | Sin sesión el registro no puede contextualizarse. |
| RQ-03 | Completitud | fecha_registro | Fecha IS NULL | Rechazar | Fecha obligatoria para análisis longitudinal. |
| RQ-04 | Completitud | canal_captura | Canal IS NULL o vacío | Corregir → 'desconocido' | Canal nulo: imputar 'desconocido' y documentar en bitácora. |
| RQ-05 | Validez | fecha_registro | Formato ≠ YYYY-MM-DD o futura | Rechazar | Fechas mal formadas o futuras indican error de captura. |
| RQ-06 | Validez | canal_captura | Valor fuera del catálogo | Corregir → 'desconocido' | Solo se aceptan: formulario, papel, app, email. |
| RQ-07 | Validez | etiqueta_sentimiento | Valor fuera del esquema | Rechazar | Etiquetas fuera de {positivo, neutral, negativo} indican error de etiquetado. |
| RQ-08 | Unicidad | hash_texto + id_sesion | Hash+sesión ya existe | Rechazar | Duplicado detectado por hash MD5 del texto normalizado. |
| RQ-09 | Consistencia | texto | Longitud < 3 caracteres | Rechazar | Textos muy cortos (ej. 'ok', 'sí') sin valor analítico. |
| RQ-10 | Consistencia | texto | Solo números/puntuación | Rechazar | El texto debe contener al menos una letra del alfabeto. |
| RQ-11 | Trazabilidad | id_ejecucion | Ausente al insertar | Rechazar | Todo registro debe estar vinculado a una ejecución del pipeline. |

CSV: `anexo_C_reglas_calidad_catalogo_diseno.csv`

## c) Correspondencia diseño → implementado

| regla_diseno | regla_implementada | tipo_de_cambio | observacion |
|---|---|---|---|
| RQ-01 | RQ-01 | sin cambio | 09a: texto vacío tras strip. Los cargadores de B (01, 02) la aplican como len(texto) < 5. |
| RQ-02 | RQ-02 | sin cambio | 09a valida num_sesion, que es el id de sesión en el CSV de A. |
| RQ-03 | RQ-03 | sin cambio |  |
| RQ-04 | RQ-04 | acción modificada | Diseño: corregir a 'desconocido'. 09a: rechazar. |
| RQ-05 | RQ-05 | criterio modificado | 09a solo verifica el formato %Y-%m-%d; no verifica fechas futuras. |
| RQ-06 | RQ-06 | acción y criterio modificados | Diseño: corregir a 'desconocido'; catálogo sin 'desconocido'. 09a: rechazar; el catálogo incluye 'desconocido'. |
| RQ-07 | — | no implementada | Etiqueta fuera de {positivo, neutral, negativo}: el esquema final tiene 5 clases. No es una regla del 09a; 04_etiquetar_sentimiento.py asigna 'neutral' a etiquetas no reconocidas, sin registrarlo (sin casos en la ejecución: 0 errores en etiquetas_cargar_20260519_1752.csv). El código RQ-07 se reutilizó para duplicados. |
| RQ-08 | RQ-07 | renumerada y criterio modificado | Diseño: hash MD5 del texto normalizado + id_sesion. 09a: primeros 200 caracteres en minúsculas, sin considerar la sesión. [VERIFICAR] emparejamiento. |
| RQ-09 | RQ-09 | criterio modificado | Diseño: < 3 caracteres. 09a: < 20 caracteres. |
| RQ-10 | — | no implementada | Solo números o puntuación: ningún script lo verifica. [VERIFICAR] si RQ-08 o RQ-09 del 09a cubren la intención. |
| RQ-11 | — | no implementada como regla | id_ejecucion obligatorio: 01, 02 y 09a siempre lo asignan al insertar (por construcción), pero ninguna regla lo valida y la columna admite NULL en el esquema. |
| — | RQ-08 | agregada | Texto no informativo (lista cerrada de expresiones). Sin equivalente en el diseño; [VERIFICAR] relación con RQ-10 de diseño. |

CSV: `anexo_C_reglas_calidad_correspondencia.csv`

## d) Umbrales de longitud en el pipeline
Ubicación exacta de cada criterio de longitud.

| etapa | criterio | unidad | efecto | ubicacion |
|---|---|---|---|---|
| diseño | Longitud < 3 caracteres | registro | rechazar (RQ-09 de diseño) | Borradores/Working_Paper_Marco_Gobernado_v1.docx, tabla de reglas |
| código | if not texto or len(texto) < 5: | registro (carga de B) | rechazar; RQ-01 en detalle_error | scripts/01_deduplicar_y_cargar.py:380 |
| código | if not texto or len(texto) < 5: | registro (carga de B) | rechazar; RQ-01 en detalle_error | scripts/02_fusionar_y_cargar.py:237 |
| código | if len(texto) < 20: | registro (Condición A) | rechazar; RQ-09 | scripts/09a_procesar_condicion_a.py:83 |
| código | texto_key = texto[:200].lower().strip() | registro (Condición A) | clave de duplicado RQ-07 | scripts/09a_procesar_condicion_a.py:112 |
| código | AND LENGTH(texto) > 50 | registro | solo se segmentan registros de más de 50 caracteres | scripts/07_resegmentar_corpus_completo.py:243 |
| código | texto_limitado = texto[:4000] if len(texto) > 4000 else texto | registro | solo los primeros 4.000 caracteres se envían a segmentar | scripts/07_resegmentar_corpus_completo.py:86 |
| código | if cat in CATEGORIAS and len(texto_s) >= 30: | segmento | se descartan fragmentos de menos de 30 caracteres | scripts/07_resegmentar_corpus_completo.py:106 |
| código | if not texto or len(texto.strip()) < 20: | segmento | excluir (flag_excluir) | scripts/09_cargar_revision_manual.py:63 |
| código | if len(texto.split()) < 8: | segmento | excluir (menos de 8 palabras) | scripts/09_cargar_revision_manual.py:67 |
| código | return [v.strip() for v in variantes if isinstance(v, str) and len(v.strip()) >= 20] | variante sintética | se descartan variantes de menos de 20 caracteres | scripts/08_data_augmentation.py:91 |
| código | MAX_LENGTH   = 128 | secuencia de tokens | truncamiento al tokenizar (BETO, BERTIN) | scripts/colab/entrenar_beto.py:70 |
| esquema | (char_length(`texto`) >= 5) | registro | MySQL rechaza la inserción | retroalimentacion.chk_texto_longitud (script 13) |

CSV: `anexo_C_reglas_calidad_umbrales_longitud.csv`

## e) Nota sobre la deduplicación
El corpus de la Condición B tiene 17 pares de registros con texto idéntico
(`docs/cambios_agosto_2026.md`, §18-19). No los detectó ninguna regla, por dos razones:

1. **El script 01 deduplica por nombre de archivo de audio** (`deduplicar()`,
   `drop_duplicates(subset="audio_filename")`), no por texto. Los 17 pares tienen nombres de
   archivo distintos, aunque la misma duración y el mismo modelo de transcripción: casi con
   seguridad es el mismo audio guardado con dos nombres.
2. **RQ-07 solo se aplica a la Condición A.** El 09a valida `condicion_A.csv`; los
   registros de B se cargaron con 01 y 02, que solo aplican RQ-01 (`len(texto) < 5`).
   Reproduciendo la validación del 09a en memoria (2026-10-09), RQ-07 marca 34 registros
   en A: 17 en las filas que agrega la inyección de duplicados, 14 que son la segunda
   aparición de un par natural de B, y 3 textos no informativos inyectados que se repiten
   ("." y "nada que decir"). Los otros 3 pares naturales no se detectan porque la
   inyección alteró el texto de uno de sus gemelos. Es decir, la regla de duplicados
   habría detectado la mayoría de estos pares, pero no se aplicó al corpus gobernado.

Consecuencia: fuga entre entrenamiento y prueba en 5 pares (20 de los 177 segmentos
evaluados). El análisis de sensibilidad del 2026-10-09 no cambia las conclusiones según
su criterio (Anexo E).

## f) Matriz regla × corpus
Alcance: la matriz describe la validación de **documentos** (registros de entrevista).
Condición B: deduplicación en 01 y carga con 02 (ejecución 2, 2026-05-14; 01 contiene el
mismo bloque de carga). Condición A: validación del 09a sobre `condicion_A.csv`
(ejecución 4); los 59 documentos válidos se cargaron en `retroalimentacion`, pero **el
corpus de A que usan los modelos es `segmento_condicion_a`, que no pasa por ninguna
regla** (es la condición no gobernada, por diseño).

A nivel de segmento, ambas condiciones comparten los controles de B, porque A se
construye a partir de los segmentos de B con `flag_excluir = 0`: solo se segmentan los
primeros 4.000 caracteres de cada entrevista y se descartan fragmentos de menos de 30
caracteres (script 07), y se excluyen segmentos de menos de 20 caracteres o de 8 palabras
o sin valor analítico (script 09_cargar_revision_manual). Ver el apartado d) de umbrales.

En la Condición B, el script 13 (2026-08-31) añadió después restricciones de esquema
sobre `retroalimentacion`, columna "esquema".

| catalogo | regla | criterio | condicion_B_carga_documentos | condicion_A_09a_documentos | esquema |
|---|---|---|---|---|---|
| implementado | RQ-01 | texto nulo o vacío | sí, con otro criterio: `if not texto or len(texto) < 5` — scripts/02_fusionar_y_cargar.py:237 (y scripts/01_deduplicar_y_cargar.py:380) | sí: `if not texto` — scripts/09a_procesar_condicion_a.py:74 | NOT NULL y CHECK ≥ 5 (retroalimentacion, desde 2026-08-31 (script 13)) |
| implementado | RQ-02 | id_sesion nulo | no se valida; se asigna la sesión por nombre (scripts/02_fusionar_y_cargar.py:261). Los 23 registros sin sesión recibieron una sesión comodín (nombre terminado en 'sesion_desconocida') | sí — scripts/09a_procesar_condicion_a.py:88 | NOT NULL (retroalimentacion, desde 2026-08-31 (script 13)) |
| implementado | RQ-03 | fecha_registro nula | no se valida; si falta, se carga NULL (scripts/02_fusionar_y_cargar.py:245); 23 NULL, imputados después (2026-08-31) | sí — scripts/09a_procesar_condicion_a.py:93 | NOT NULL (retroalimentacion, desde 2026-08-31 (script 13)) |
| implementado | RQ-04 | canal_captura nulo | por construcción: canal constante CANAL_CAPTURA = "formulario" (scripts/02_fusionar_y_cargar.py:22) | sí — scripts/09a_procesar_condicion_a.py:104 | NOT NULL (retroalimentacion, desde 2026-08-31 (script 13)) |
| implementado | RQ-05 | formato de fecha inválido | no se rechaza: si pd.to_datetime falla, se carga NULL (scripts/02_fusionar_y_cargar.py:248) | sí — scripts/09a_procesar_condicion_a.py:98 | tipo DATE (parcial) |
| implementado | RQ-06 | canal fuera del catálogo | por construcción: canal constante CANAL_CAPTURA = "formulario" (scripts/02_fusionar_y_cargar.py:22) | sí — scripts/09a_procesar_condicion_a.py:108 | CHECK catálogo (retroalimentacion, desde 2026-08-31 (script 13)) |
| implementado | RQ-07 | duplicado (primeros 200 caracteres) | no por texto; control distinto: solo por nombre de archivo de audio (scripts/01_deduplicar_y_cargar.py:223); 17 pares de texto idéntico pasaron | sí — scripts/09a_procesar_condicion_a.py:112 | — |
| implementado | RQ-08 | texto no informativo | no en la carga de documentos | sí — scripts/09a_procesar_condicion_a.py:79 | — |
| implementado | RQ-09 | texto < 20 caracteres | no en la carga de documentos (solo < 5) | sí — scripts/09a_procesar_condicion_a.py:83 | — |
| diseño | RQ-01 | texto nulo o vacío → rechazar | sí, con otro criterio (< 5) — scripts/02_fusionar_y_cargar.py:237 (y scripts/01_deduplicar_y_cargar.py:380) | sí — scripts/09a_procesar_condicion_a.py:74 | NOT NULL |
| diseño | RQ-02 | id_sesion nulo → rechazar | no se valida; se asigna la sesión por nombre (scripts/02_fusionar_y_cargar.py:261). Los 23 registros sin sesión recibieron una sesión comodín (nombre terminado en 'sesion_desconocida') | sí — scripts/09a_procesar_condicion_a.py:88 | NOT NULL |
| diseño | RQ-03 | fecha nula → rechazar | no se valida; si falta, se carga NULL (scripts/02_fusionar_y_cargar.py:245); 23 NULL, imputados después (2026-08-31) | sí — scripts/09a_procesar_condicion_a.py:93 | NOT NULL |
| diseño | RQ-04 | canal nulo → corregir a 'desconocido' | por construcción: canal constante CANAL_CAPTURA = "formulario" (scripts/02_fusionar_y_cargar.py:22); no se corrige a 'desconocido' | con acción distinta (rechaza) — scripts/09a_procesar_condicion_a.py:104 | NOT NULL |
| diseño | RQ-05 | formato ≠ YYYY-MM-DD o fecha futura → rechazar | no se rechaza: si pd.to_datetime falla, se carga NULL (scripts/02_fusionar_y_cargar.py:248); no verifica fechas futuras | solo formato; no verifica futuras — scripts/09a_procesar_condicion_a.py:98 | tipo DATE (parcial) |
| diseño | RQ-06 | canal fuera del catálogo → corregir a 'desconocido' | por construcción: canal constante CANAL_CAPTURA = "formulario" (scripts/02_fusionar_y_cargar.py:22) | con acción distinta (rechaza) — scripts/09a_procesar_condicion_a.py:108 | CHECK catálogo |
| diseño | RQ-07 | etiqueta fuera de {positivo, neutral, negativo} → rechazar | ninguna regla; el etiquetado asigna 'neutral' a etiquetas no reconocidas (scripts/04_etiquetar_sentimiento.py:91) | ninguna | — |
| diseño | RQ-08 | duplicado por hash + id_sesion → rechazar | criterio distinto: solo por nombre de archivo de audio (scripts/01_deduplicar_y_cargar.py:223); 17 pares de texto idéntico pasaron | criterio distinto (texto, sin sesión) — scripts/09a_procesar_condicion_a.py:112 | — |
| diseño | RQ-09 | texto < 3 caracteres → rechazar | cubierta por el filtro < 5 — scripts/02_fusionar_y_cargar.py:237 (y scripts/01_deduplicar_y_cargar.py:380) | cubierta por < 20 — scripts/09a_procesar_condicion_a.py:83 | CHECK ≥ 5 |
| diseño | RQ-10 | solo números o puntuación → rechazar | ninguna | ninguna | — |
| diseño | RQ-11 | id_ejecucion ausente → rechazar | por construcción: id_ejecucion de la ejecución en curso (scripts/02_fusionar_y_cargar.py:204); sin validación | por construcción, sin validación — scripts/09a_procesar_condicion_a.py:192 | admite NULL |
| control de B | — | deduplicación por nombre de archivo de audio | sí — scripts/01_deduplicar_y_cargar.py:223 | no aplica (A se construye después, desde el corpus deduplicado) | — |
| control de B | — | filtro de texto vacío o < 5 caracteres (registrado como RQ-01) | sí — scripts/02_fusionar_y_cargar.py:237 (y scripts/01_deduplicar_y_cargar.py:380); 0 rechazos en la ejecución 2 | no aplica | CHECK ≥ 5 (script 13) |

CSV: `anexo_C_reglas_calidad_matriz_regla_corpus.csv`
