# Cambios de agosto de 2026 en los scripts 14 y 15 — análisis forense

Fecha del análisis: 2026-10-03.
Herramienta: `tools/verificar_equivalencia.py` (compara AST normalizados: sin
docstrings, sin anotaciones de tipo, sin contenido de cadenas; los comentarios no
forman parte del AST). Las cadenas que difieren **fuera de `print()`** se informan
aparte como aviso, porque pueden ser nombres de columnas, rutas o claves.

## 1. Verificación retroactiva de la limpieza (`b83f2b3`..`1835b1b`)

Comando:

```bash
python tools/verificar_equivalencia.py --commit $(git rev-list --reverse b83f2b3^..1835b1b)
```

| Resultado | Detalle |
|---|---|
| 22 scripts comparados contra el padre de su commit | **22/22 sin diferencias de lógica** (AST normalizado idéntico) |
| Cadenas distintas fuera de `print()` | **0** en los 22 (los cambios de texto estuvieron todos dentro de mensajes impresos) |
| `7f0c1ab` | No modifica archivos `.py` (solo la guía) |

Scripts cubiertos: 00, 00b, 01, 02, 03, 04, 05, 06, 07, 08, 08b, los tres `09_*`,
09a, 09b, 10, 11, 12, 14, 15 y 16. Código de salida 0.

**Conclusión:** la limpieza de docstrings y emoticones no alteró la lógica de ningún
script. Esto incluye el 16, que no tiene cambios posteriores a `b83f2b3`
(`git log b83f2b3..HEAD -- scripts/16_generar_graficos.py` no devuelve commits).

## 2. Script 14 — `0881636` (limpio) vs `ee52030` (agosto)

### Cambios de lógica detectados

| # | Ubicación | Cambio |
|---|---|---|
| 1 | módulo, línea 66 | Nueva importación `from scipy.stats import norm` |
| 2 | módulo, líneas 69-70 | Nuevas constantes `Z_ALPHA_2 = norm.ppf(0.975)` y `Z_BETA_80 = norm.ppf(0.80)` |
| 3 | `potencia_y_n_requerido` (línea 117) | Función nueva: deriva el error estándar del semiancho del IC 95 % (`(ci_high − ci_low) / (2·1.96)`) y calcula una potencia retrospectiva aproximada (normal, bilateral) y el n pareado requerido para 80 % de potencia, escalando el EE como 1/√n. Devuelve NaN si la diferencia es 0 o el EE no es positivo |
| 4 | `bootstrap_pareado` (línea 188) | Calcula `prop_b_mejor = mean(diffs > 0)` y llama a `potencia_y_n_requerido`; el diccionario devuelto agrega `prop_remuestras_B_mejor`, `potencia_retrospectiva_aprox` y `n_requerido_80pct_potencia` |
| 5 | `main` (línea 240) | Imprime las tres métricas nuevas (o un aviso si no están definidas) |
| 6 | `main` (línea 255) | `bootstrap_resultados.csv` pasa de 9 a 12 columnas (las tres nuevas, antes de `n_pares`) |

### Lo que NO cambió

- El cálculo de `diff_obs`, del IC 95 % (percentiles), del `p_valor_aprox` bilateral y
  de `significativo_95` es idéntico. Las métricas nuevas se calculan **después** del
  remuestreo y no consumen el generador aleatorio (`default_rng(42)`), así que la
  secuencia de remuestreos y los valores ya reportados no pueden haber cambiado por
  este motivo. Se comprobará empíricamente en la Fase 4.
- El gráfico de distribuciones (`bootstrap_distribuciones.png`) no cambió.

### Hallazgo: el p de una cola nunca estuvo en el código versionado

El mensaje de `ee52030` y la NOTA METODOLÓGICA hablan de "retirar la lectura de una
cola". Sin embargo, ni el commit inicial (`788f4ff`) ni la versión limpia (`0881636`)
calculan un p unilateral: ambos calculan solo el bilateral
(`2 * min(mean(diffs <= 0), mean(diffs >= 0))`). `git log -S "una cola"` solo
encuentra `ee52030`. Por tanto, el retiro afecta a la **interpretación** reportada
(probablemente el p bilateral dividido entre 2, como dice la nota), no al código. El
mensaje del commit es correcto en intención pero puede leerse como si se hubiera
borrado código; conviene precisarlo en la documentación (sin reescribir el historial).

### Efecto probable sobre las salidas

| Salida | Efecto |
|---|---|
| `outputs/bootstrap_resultados.csv` | 3 columnas nuevas; las 9 existentes, mismos valores |
| Salida de consola | Líneas nuevas `[descriptivo]` y `[prospectivo]` |
| `bootstrap_distribuciones.png` | Sin cambios |
| Scripts posteriores | El 16 no lee `bootstrap_resultados.csv` (lee `resultados_*.csv`, `matriz_confusion_*.csv` y `kfold_epocas_*.csv`). El 15 no lo lee. Sin efecto aguas abajo |

### ¿Afecta resultados ya reportados?

- **Valores inferenciales (diferencia, IC, p bilateral): no**, por construcción. Pendiente
  de confirmación empírica en la Fase 4 (tabla de aceptación).
- **Texto de la tesis: sí, potencialmente.** Si algún documento reportó un p de una cola
  para BETO (p ≈ 0.046 si fuera 0.092/2), esa lectura queda retirada por decisión
  metodológica. `[VERIFICAR]` en el Reporte Metodológico (fuera del alcance de esta tarea
  modificarlo).
- Las tres métricas nuevas no se habían reportado antes; su uso está en evaluación
  metodológica (ver "Fuera de alcance": `potencia_retrospectiva`).

### Observaciones adicionales (no se corrigen aquí)

- **Dependencia no declarada:** `scipy` no aparece en `requirements.txt` ni en
  `requirements-local.txt`. Hoy está instalada (1.18.1) solo como dependencia
  transitiva de scikit-learn. Debe declararse explícitamente al conciliar requisitos
  (Fase 4, punto 3).
- `potencia_y_n_requerido` asume un IC simétrico y aproximadamente normal; con un IC
  percentil asimétrico (p. ej. bertin_roberta: [−0.151, 0.029] con diferencia −0.059)
  el EE derivado es una aproximación. La propia nota lo declara como aproximación de
  primer orden.

## 3. Script 15 — `1835b1b` (limpio) vs staging (agosto)

### Cambios de lógica detectados

| # | Ubicación | Cambio |
|---|---|---|
| 1 | módulo, línea 60 | Nueva constante `DEFECTOS_QUE_TOCAN_TEXTO = {"nulo_texto", "texto_no_informativo"}` |
| 2 | `cargar_defectos_por_segmento` (línea 63) | Función nueva: consulta (solo lectura) `segmento_condicion_a`, colapsa a una fila por `id_segmento_origen` uniendo los tipos de defecto (separados por coma) y clasifica cada segmento en `afecta_texto` o `solo_metadatos` |
| 3 | `desagregar_cambios_por_defecto` (línea 176) | Función nueva: cruza los casos que cambian de predicción con la clase de defecto (`sin_defecto` si el segmento no tiene defecto) y cuenta flips por modelo y clase, con su porcentaje |
| 4 | `main` (línea 279) | Nueva sección (d): si hay casos que cambian, genera `flips_por_clase_defecto.csv` y `casos_que_cambian_con_clase_defecto.csv` e imprime una tabla pivote y una nota interpretativa |
| 5 | `main` (línea 303) | Lista los dos CSV nuevos en el resumen final |

Las funciones existentes (`cargar_metadatos`, `cargar_predicciones_con_meta`,
`analisis_por_categoria`, `analisis_negativo_por_naturaleza`, `casos_que_cambian`) no
tienen cambios de lógica: los análisis (a), (b) y (c) producen las mismas salidas.

### Hallazgo: `cuasi_duplicado` sí modifica el texto y queda mal clasificado

La constante del cambio 1 y el docstring de `cargar_defectos_por_segmento` afirman que
solo `nulo_texto` y `texto_no_informativo` modifican el texto, y que `cuasi_duplicado`
"agrega una fila extra". El código de `09_construir_condicion_a_segmentos.py`
(`aplicar_defecto`, líneas 140-142) dice otra cosa: `cuasi_duplicado` **modifica el
texto del propio segmento** (le añade su primera palabra al final) y **no** agrega fila;
solo `duplicado_exacto` agrega una fila extra (líneas 206-207).

Comprobación en la BD (consulta de solo lectura, 2026-10-03):

- Las 21 filas con defecto único `cuasi_duplicado` tienen texto distinto al de
  `segmento_retroalimentacion` (0 de 21 iguales). Lo mismo ocurre en todas las
  combinaciones que incluyen `cuasi_duplicado`.
- Aplicando la regla del script 15 a los 463 segmentos con defecto: 97 quedan como
  `afecta_texto` y 366 como `solo_metadatos`, de los cuales **30 tienen
  `cuasi_duplicado` sin otro defecto de texto**, es decir, se clasifican como
  "texto idéntico" cuando su texto en la Condición A sí difiere.

**Efecto probable:** en la sección (d), los flips de esos 30 segmentos (los que caigan
en el conjunto de prueba) se cuentan como `solo_metadatos`, lo que **infla la
proporción de flips "con texto idéntico"** y, con ella, el argumento de que parte de la
volatilidad se debe a varianza de entrenamiento. La magnitud depende de cuántos de
esos 30 están en prueba y cambian de predicción; se cuantificará al ejecutar el 15 en
la Fase 4. No se corrige en la Fase 2 (que registra el script tal como quedó); la
corrección, si se aprueba, irá en un commit de lógica separado.

`[VERIFICAR]`: que el texto que ve el modelo en la Condición A sea el de
`segmento_condicion_a` sin transformaciones posteriores (09a/12) que reviertan el
cambio de `cuasi_duplicado`, y que el `id_segmento` de los CSV de predicciones
corresponda a `id_segmento_origen`. Ambos supuestos están implícitos en el cruce que
hace el script 15.

### Efecto probable sobre las salidas

| Salida | Efecto |
|---|---|
| `errores_por_categoria.csv`, `errores_negativo_por_naturaleza.csv`, `casos_que_cambian_entre_condiciones.csv` | Sin cambios |
| `flips_por_clase_defecto.csv`, `casos_que_cambian_con_clase_defecto.csv` | **Nuevos**, afectados por el hallazgo de `cuasi_duplicado` |
| Base de datos | Una consulta `SELECT` adicional; sin escritura |
| Scripts posteriores | El 16 no lee salidas del 15. Sin efecto aguas abajo |

### ¿Afecta resultados ya reportados?

- Análisis (a), (b) y (c): **no**.
- Sección (d): es nueva. Si su resultado (proporción de flips con texto idéntico, cita a
  Dodge et al., 2020) ya se usó en algún documento, ese número está sesgado hacia
  `solo_metadatos` por el hallazgo anterior. `[VERIFICAR]` si se reportó.

## 4. Script 16

Sin cambios posteriores a la limpieza (`b83f2b3`); su limpieza está verificada como
equivalente en la sección 1. No consume salidas del 14 ni del 15, así que los cambios
de agosto no lo afectan.

## 5. Script 13 — restricciones de esquema aplicadas el 2026-08-31

Análisis del 2026-10-08, solo con `SHOW` y `SELECT`; el script no se ejecutó.
Registrado sin modificaciones en `6d3a152`.

### Qué hace

Agrega a la tabla `retroalimentacion`:

| Regla | Restricción |
|---|---|
| RQ-01 | `texto NOT NULL` y `CHECK (CHAR_LENGTH(texto) >= 5)` (`chk_texto_longitud`) |
| RQ-02 | `id_sesion NOT NULL` |
| RQ-03 | `fecha_registro NOT NULL` |
| RQ-04 | `canal_captura NOT NULL` |
| RQ-06 | `CHECK (canal_captura IN ('formulario','papel','app','email','desconocido'))` (`chk_canal_catalogo`) |

Con `--modo aplicar` genera un respaldo con `mysqldump`, lo verifica, pide confirmación
en consola y ejecuta los `ALTER TABLE`.

### Evidencia de que se ejecutó

| Fuente | Dato |
|---|---|
| `crear_tablas.sql` (`788f4ff`) | `id_sesion`, `fecha_registro` y `canal_captura` admiten `NULL`; sin `CHECK` |
| `SHOW CREATE TABLE retroalimentacion` (2026-10-08) | Las cuatro columnas son `NOT NULL`; existen `chk_texto_longitud` y `chk_canal_catalogo`, con los mismos nombres y definiciones que genera el script |
| `information_schema.TABLES` | `CREATE_TIME` de `retroalimentacion` = 2026-08-31 23:24:55, aunque `segmento_retroalimentacion` (creada el 2026-08-05) ya la referenciaba: la tabla se reconstruyó, como ocurre con `ALTER ... MODIFY ... NOT NULL` |
| Respaldo `backup_antes_constraints_20260831_2324.sql` | Nombre con el formato exacto del script. Volcado terminado el 2026-08-31 23:24:49, seis segundos antes de la reconstrucción. Su esquema de `retroalimentacion` no tiene las restricciones |
| Registros binarios de MySQL | Ya rotaron (quedan `binlog.000178`–`.000183`); sin registro directo del `ALTER` |

**Confirmación de la autora (2026-10-08):** lo ejecutó ella en el equipo anterior
alrededor del 2026-08-31; nadie más tenía acceso.

**Respaldo:** según la autora, quedó en el equipo anterior. Sin embargo, el 2026-10-08
se localizó una copia en el equipo actual, en
`Working_paper/backup_antes_constraints_20260831_2324.sql` (1,8 MB, fuera del
repositorio), probablemente traída en la migración entre equipos. Contiene datos de
estudiantes: no se versiona.

**Verificación del respaldo (2026-10-08)**, leyendo el archivo sin cargarlo en MySQL y
sin imprimir contenido de estudiantes:

| Comprobación | Resultado |
|---|---|
| (a) Definición de `retroalimentacion` | `texto` `NOT NULL` (ya lo era en `crear_tablas.sql`); `id_sesion`, `fecha_registro` y `canal_captura` admiten `NULL`; ninguna restricción `CHECK` |
| (b) Número de registros | 211 en el respaldo (un único `INSERT`), 211 en la BD actual, mismos `id_registro` |
| (b) Coincidencia campo a campo | 9 de las 10 columnas distintas de `id_registro`, idénticas en los 211 registros (incluidos `texto`, etiquetas y justificaciones, con `NULL` tratado como valor) |
| (b) `ingesta_timestamp` | Difiere en los 211 registros por exactamente +5 h. Es un artefacto del volcado: `mysqldump` escribe los `TIMESTAMP` en UTC (`SET TIME_ZONE='+00:00'`) y el servidor opera en −05. Corregido el desfase, coinciden |

Conclusión: el contenido de `retroalimentacion` no cambió entre el respaldo y el estado
actual. **Pero el respaldo no refleja el estado original de los datos**: se generó
después de imputar 23 fechas (ver la subsección siguiente).

### ¿Alteró datos? El script no; una imputación previa, sí

**Corrección del 2026-10-08.** En una primera versión de esta sección se concluyó que no
se habían alterado datos. Al recuperar el resumen de la conversación de agosto se
verificó que, antes de aplicar las restricciones, se imputaron 23 valores faltantes de
`fecha_registro`.

| Evidencia | Resultado |
|---|---|
| `outputs/corpus_final.csv` (2026-05-14, insumo de la carga) | 23 de 152 registros con `fecha_real` nula, en las posiciones 2, 7, 13, 15, 17, 19, 21, 23, 25, 40-52 y 65 |
| Scripts de carga (`01`, `02`) | Insertan `None` cuando falta la fecha: esos registros entraron a la BD con `fecha_registro` `NULL` |
| BD actual | Exactamente esos 23 `id_registro` (todos de la ejecución 2) tienen `fecha_registro = DATE(ingesta_timestamp)` = 2026-05-14. Ningún otro registro la tiene |
| Respaldo `backup_antes_constraints_20260831_2324.sql` | 0 `NULL` en `fecha_registro`, y fechas idénticas a las actuales |

**Orden de operaciones reconstruido:**

1. **Imputación**, antes del 2026-08-31 23:24:49: `UPDATE` de los 23 `NULL` con
   `DATE(ingesta_timestamp)`. No está en ningún script del repositorio ni en `files/`.
   Según el resumen de agosto, se hizo para poder aplicar `NOT NULL`. Los registros
   binarios ya rotaron, así que la sentencia exacta no se puede recuperar.
2. **Script 13 con `--modo aplicar`:** diagnóstico (0 violaciones, gracias a la
   imputación), respaldo con `mysqldump` (23:24:49), confirmación y `ALTER TABLE`
   (reconstrucción de la tabla a las 23:24:55).

El script 13 no contiene ningún `UPDATE`: no imputa ni modifica filas. Con
`STRICT_TRANS_TABLES`, sin la imputación previa el `MODIFY ... NOT NULL` de
`fecha_registro` habría fallado.

**Implicación para la gobernanza:** durante el experimento (mayo-agosto de 2026), 23
registros no cumplían RQ-03 (`fecha_registro` obligatoria). La proporción depende del
denominador:

| Denominador | Definición | Afectados | Proporción |
|---|---|---|---|
| 211 | Todas las filas de `retroalimentacion`: 152 de la ejecución 2 (Condición B cargada el 2026-05-14) más 59 de la ejecución 4 (documentos de la Condición A que pasaron `09a` el 2026-06-01) | 23 | 10,9 % |
| 152 | Registros de la ejecución 2: el corpus gobernado tal como se cargó | 23 | 15,1 % |
| **148** | **Registros que originan los 799 segmentos activos** (los 152 menos los ids 9, 78, 109 y 111, que no tienen segmentos) | **23** | **15,5 %** |
| **799** | **Segmentos activos** (equivalente en segmentos de la cifra anterior) | **88** | **11,0 %** |

Cifra principal para el capítulo (decisión de la autora, 2026-10-08): 23 de los 148
registros que originan el corpus de análisis (15,5 %), equivalentes a 88 de los 799
segmentos activos (11,0 %). Si se cuentan también los segmentos excluidos, son 92 de
821. El denominador de 211 no es el corpus gobernado, porque incluye los 59 registros
de la Condición A.

Los mismos 23 registros tenían también `num_sesion` vacío en `corpus_final.csv`
(método de asignación `sin_sesion`); `id_sesion` en la BD no estaba nulo, porque se
asigna a partir de `nombre_sesion` al crear la tabla `sesion`.

**Métricas de calidad estructural (completitud A frente a B): calculadas antes de la
imputación.** `outputs/comparativa_calidad.csv` lo generó el script 05 el 2026-05-19
19:15, sobre `corpus_final.csv` y no sobre la BD. Reporta una completitud de B de
89,9 %. Recalculada hoy con la misma regla (campos `text`, `num_sesion`, `fecha_real`),
da 89,9 %, e incluye los 23 `num_sesion` y las 23 `fecha_real` vacíos. Si se hubieran
imputado las fechas, sería 95,0 %. `outputs/reporte_comparativo_condiciones.csv`
(script 09a, 2026-06-01) también es anterior a la imputación. Ambas cifras reflejan,
por tanto, el estado real de los datos durante el experimento, no el estado posterior
a la imputación del 2026-08-31. La imputación con la fecha de ingesta tampoco recupera la fecha real del registro:
es un valor de relleno y debe declararse como tal.

Los modelos de texto no usan `fecha_registro`, así que la imputación no afecta los
resultados de clasificación.

### Defectos de la revisión estática

1. **Umbral de RQ-01 sin respaldo en las reglas implementadas.** `chk_texto_longitud`
   exige 5 caracteres, pero en `09a_procesar_condicion_a.py` RQ-01 es "texto nulo o
   vacío" y RQ-09 es "longitud menor a 20 caracteres". El 5 no corresponde a ninguna.
2. **Cobertura menor a la anunciada.** El docstring habla de las reglas RQ-01 a RQ-09,
   pero solo implementa RQ-01, 02, 03, 04 y 06. Faltan RQ-05 (formato de fecha; el tipo
   `DATE` lo cubre en parte), RQ-07 (duplicados), RQ-08 (texto no informativo) y RQ-09
   (longitud), sin declarar por qué.
3. **Referencia a un script inexistente.** Cita `11_procesar_condicion_a.py`; el
   correcto es `09a_procesar_condicion_a.py`.

Además: el script no debe volver a ejecutarse. Con `--modo aplicar` omitiría los
`NOT NULL`, pero intentaría crear de nuevo las dos restricciones `CHECK` y MySQL lo
rechazaría por nombre duplicado.

### ¿Afecta resultados ya reportados?

No a resultados numéricos. Sí al texto: si el Reporte Metodológico (sección 16)
describe la "brecha entre gobernanza declarada e implementada" como abierta, está
desactualizado para `retroalimentacion`. La brecha sigue abierta para
`segmento_retroalimentacion` (ver `docs/propuestas_mejora_arquitectura.md`).
`[VERIFICAR]` en el reporte.

## 6. Hallazgo metodológico: dos definiciones de `cuasi_duplicado`

Detectado en la auditoría del supuesto "defectos que no modifican el texto"
(2026-10-08). Es un hallazgo sobre el diseño de la Condición A, no solo el origen del
error de la sección (d) del 15.

| Nivel | Script | Definición implementada |
|---|---|---|
| Documento | `05_construir_condicion_a.py`, líneas 131-142 | "Mismo texto, distinta sesión": se agrega una **copia** del registro con `num_sesion` desplazado y `nombre_sesion` con el sufijo `_duplicado`. El texto no cambia y se forma un par cuasi-duplicado |
| Segmento | `09_construir_condicion_a_segmentos.py`, líneas 140-142 | Se **modifica** el propio segmento: se repite su primera palabra al final. No se agrega ninguna fila |

Consecuencias:

1. **El mismo nombre designa operaciones distintas.** En el 05 es un defecto de
   duplicación (metadatos distintos, texto igual); en el 09 es una perturbación del
   texto.
2. **En el 09, `cuasi_duplicado` en general no produce un par cuasi-duplicado.** De los
   37 segmentos con ese defecto, solo en 7 aparece el texto original en otra fila de
   `segmento_condicion_a`: en 3 porque el segmento también recibió `duplicado_exacto`
   (la fila extra conserva el texto sin perturbar) y en 4 porque otro segmento del corpus
   tiene exactamente el mismo texto. En los 30
   restantes, el segmento perturbado no tiene "gemelo" en A, así que una regla de
   detección de duplicados (RQ-07) no tendría con qué compararlo. El defecto funciona
   como ruido textual menor, no como duplicación.
3. **No hay justificación documentada.** Ni el docstring ni los comentarios del 09
   explican la elección de "repetir la primera palabra", ni en la versión actual ni en
   el commit inicial (`788f4ff`). La tasa (5,56 %) sí se documenta: proviene de
   `auditoria_inyeccion.csv`.
4. **Origen probable del error del 15:** la sección (d) supone la definición del 05
   (texto igual) aplicada a datos generados con la del 09.

`[VERIFICAR]` cómo describe el capítulo de Metodología el defecto `cuasi_duplicado` y si
la desviación declarada en la sección 3.1 lo cubre.

## 7. Verificación: la etiqueta de sentimiento se conserva entre A y B

Consulta de solo lectura (2026-10-08) sobre las 862 filas de `segmento_condicion_a`,
cruzadas con `segmento_retroalimentacion` por `id_segmento_origen`:

| Grupo | Filas en A | Etiqueta igual a B | Etiqueta distinta | Etiqueta nula en A |
|---|---|---|---|---|
| Sin defecto | 336 | 336 | 0 | 0 |
| Con defecto, texto igual a B | 391 | 391 | 0 | 0 |
| Con defecto, texto distinto de B | 135 | 135 | 0 | 0 |
| **Total** | **862** | **862** | **0** | **0** |

En la augmentation (`augmentation_segmentos`, 316 filas por condición), el multiconjunto
de pares (texto, etiqueta) es idéntico entre A y B.

Conclusión: la etiqueta de sentimiento es idéntica entre A y B para todos los
segmentos, incluidos los 135 cuyo texto alteran los defectos. Esto respalda la
redacción del principio metodológico en la guía ("conserva en todos los casos la
etiqueta de sentimiento del segmento").

## 8. Hallazgo metodológico: el `bootstrap_resultados.csv` del 2026-08-30 mezcla semillas

Detectado el 2026-10-08 al preparar la prueba de aceptación (Fase 4). Análisis de
solo lectura; no se ejecutó nada ni se movió ningún archivo.

**Ninguna cifra de `Working_paper/outputs/bootstrap_resultados.csv` (2026-08-30 23:15)
debe usarse.** El archivo y su carpeta de insumos `Working_paper/outputs/bootstrap_input/`
(2026-08-30 23:09-23:10) se conservan sin cambios como evidencia.

### Qué insumos usó

Se compararon los insumos del `bootstrap_input/` del 30 de agosto con las salidas de
Colab en Drive (`MyDrive/working_paper/resultados_colab/`), por huella SHA-256 y por
contenido:

| Configuración | Insumo usado el 2026-08-30 | ¿Es la corrida principal? |
|---|---|---|
| baseline | `predicciones_{A,B}_baseline.csv` | Sí (idéntico byte a byte) |
| beto_sin_finetuning | `beto_sin_finetuning/predicciones_{A,B}.csv` | Sí (idéntico byte a byte) |
| beto | `beto/multisemilla/predicciones_s2024_{A,B}.csv` | **No**: semilla 2024 del análisis multisemilla; difiere de la principal en 47 y 51 de 177 predicciones |
| bertin_roberta | `roberta_es/multisemilla/predicciones_s2024_{A,B}.csv` | **No**: semilla 2024; difiere en 70 y 77 de 177 predicciones |

El `y_true` coincide en todos los casos: las diferencias están solo en las predicciones.

### Efecto sobre las cifras

| Configuración | Corrida principal (Δ = F1 B − F1 A) | Archivo del 2026-08-30 (semilla 2024) |
|---|---|---|
| beto | +0.0571 | +0.0591, IC [0.0036, 0.1184], p = 0.039 (significativo) |
| bertin_roberta | −0.0586 | +0.0729, IC [−0.0246, 0.1698], p = 0.128 (cambia de signo) |
| baseline | +0.0259 | +0.0259 (mismo insumo) |
| beto_sin_finetuning | +0.0161 | +0.0161 (mismo insumo) |

La tabla de referencia de la prueba de aceptación corresponde a las
corridas principales, no a este archivo.

**Probable intención (verificado el 2026-10-08):** la semilla 2024 es, en ambos modelos,
la más cercana a la media del multisemilla y exactamente su mediana:

| Modelo | Media (5 semillas) | Mediana | Distancia de s2024 a la media | Siguiente semilla más cercana |
|---|---|---|---|---|
| BETO | +0.0578 | +0.0591 (s2024) | 0.0013 | s7, 0.0022 |
| BERTIN | +0.0654 | +0.0729 (s2024) | 0.0074 | s42, 0.0216 |

Por tanto, el archivo no parece un error de copia: parece un bootstrap sobre una
"semilla representativa" elegida a partir de los resultados. Aun así, sus cifras no
deben usarse como resultado principal: mezcla esa semilla con las corridas principales
del baseline y de BETO sin ajuste fino, y la elección se hizo después de ver los
resultados. El tratamiento de la variabilidad entre semillas corresponde al plan
multisemilla (fijado el 2026-10-08). `[VERIFICAR]` que ningún documento haya
tomado cifras de él, en particular el p = 0.039 de BETO.

### Corrida principal identificada

Las predicciones principales son `beto/predicciones_{A,B}.csv` (2026-08-28) y
`roberta_es/roberta_predicciones_{A,B}.csv`. Su F1-macro coincide con
`resultado_{A,B}.csv` y su matriz de confusión recalculada coincide con
`matriz_confusion_{A,B}.csv` de la misma carpeta. En RoBERTa, el script de Drive escribe
`predicciones_{c}.csv`, pero el archivo se llama `roberta_predicciones_{c}.csv` y tiene
fecha 2026-08-30 22:46, poco antes de organizar el `bootstrap_input/`: probablemente se
renombró a mano. `[VERIFICAR]`. El script 13b se ajustó para tomarlo con su nombre real
(`679f3b3`).

## 9. Inventario del análisis multisemilla (2026-10-08, solo lectura)

### Archivos

No hay carpeta `outputs/multisemilla/` ni en `Code/` ni en `Working_paper/`. Todo está
en Drive:

| Carpeta | Contenido | Fechas |
|---|---|---|
| `resultados_colab/beto/multisemilla/` | `predicciones_s{42,123,2024,7,99}_{A,B}.csv` (177 filas, 3 columnas: `id_segmento`, `y_true`, `y_pred`), `detalle_multisemilla.csv`, `resumen_multisemilla.csv` y versiones `_parcial` y `_preview`; 10 carpetas `checkpoints_s*_{A,B}` (0 B en la copia local) | 2026-08-28 12:49-13:20 |
| `resultados_colab/roberta_es/multisemilla/` | Lo mismo, sin archivos `_preview` | 2026-08-27 01:19-01:31 |

Semillas: 42, 123, 2024, 7 y 99. Modelos: BETO y BERTIN. Condiciones: A y B. No hay
multisemilla del baseline ni de BETO sin ajuste fino.

### Código que lo generó

- `entrenar_beto_multisemilla.py` (2026-08-27) y `entrenar_roberta_multisemilla.py`
  (2026-08-27), en `MyDrive/working_paper/`, con `SEMILLAS_DEFAULT = [42, 123, 2024, 7,
  99]`. Importan el script base (`import entrenar_beto as er` / `entrenar_roberta as er`).
  Se registraron en Git el 2026-10-08 (`0c8b4cb`), junto con las versiones ejecutadas de
  los scripts base.
- Copias locales: `Working_paper/files/entrenar_beto_multisemilla.py` es idéntica a la de
  Drive. `files/entrenar_roberta_multisemilla.py` (29 KB) es en realidad una copia de
  `entrenar_roberta.py` con otro nombre. `Descargas/entrenar_roberta_multisemilla.py`
  es la versión con el `NameError` (`fila_semilla`, línea 252); la de Drive es la
  corregida (sin esa línea y con guardado incremental en `detalle_multisemilla_parcial.csv`).
- **Versiones ejecutadas:** los `.pyc` de Python 3.13 en `MyDrive/working_paper/__pycache__`
  registran fuentes de `entrenar_beto.py` (29041 bytes) y `entrenar_roberta.py` (29085
  bytes) del 2026-08-28 y 2026-08-27, iguales en tamaño a las versiones de Drive. Cada
  script de Drive es anterior a sus salidas y no se modificó después
  (`entrenar_roberta_multisemilla.py` 01:18, primera salida 01:19).
- `scripts/test_colab.ipynb`: las versiones en staging y de trabajo, sin registrar,
  contienen las salidas de la ejecución de `entrenar_beto_multisemilla.py` (en modo
  preview y completo). La versión registrada en Git no lo menciona.

### Semilla de las corridas principales

`entrenar_beto.py` y `entrenar_roberta.py` usan `SEMILLA = 42`, tanto en Git como en
Drive. Aun así, la corrida principal **no coincide** con la semilla 42 del
multisemilla: comparten 137 y 131 de 177 predicciones (BETO A y B) y 115 y 120 (RoBERTa).
Causa probable, según el código registrado en `0c8b4cb`: ambas usan los mismos datos y
4 épocas (el k-fold de las cuatro corridas principales eligió 4, igual que
`EPOCAS_FIJAS = 4` del multisemilla), pero la corrida principal fija la semilla una sola
vez al importar el módulo, y el k-fold de selección de épocas consume el generador
aleatorio antes del entrenamiento final. El multisemilla, en cambio, llama a
`set_seed(semilla)` justo antes de `from_pretrained`. La cabeza de clasificación se
inicializa, por tanto, desde estados aleatorios distintos. Sin reejecutar no se puede
descartar además el no determinismo de la GPU.

### Diferencia de F1-macro B − A por semilla

| Corrida | BETO | BERTIN |
|---|---|---|
| Principal (semilla 42) | +0.0571 | **−0.0586** |
| s42 | +0.0046 | +0.0871 |
| s123 | +0.0297 | +0.0149 |
| s2024 | +0.0591 | +0.0729 |
| s7 | +0.0600 | +0.1121 |
| s99 | +0.1355 | +0.0403 |
| Media multisemilla (DE) | +0.0578 (0.0491) | +0.0654 (0.0383) |
| Semillas con B > A | 5/5 | 5/5 |

Los valores coinciden con `resumen_multisemilla.csv` de cada carpeta. **La corrida
principal de BERTIN es la única de seis con diferencia negativa.** Es un hallazgo
metodológico relevante para la interpretación de BERTIN y para la discusión sobre la
inestabilidad entre corridas (Dodge et al., 2020, ya citado en el script 15).

### Versiones de los scripts de Colab en Git y en Drive

Las versiones de `entrenar_beto.py` y `entrenar_roberta.py` registradas en Git
(`1a97748`) no son las de Drive (2026-08-27 y 2026-08-28), que son las que produjeron
las corridas principales. Según `tools/verificar_equivalencia.py`, la versión de Drive
agrega `_kwarg_warmup`, que usa `warmup_ratio` o `warmup_steps` según la versión
instalada de transformers (v5 eliminó `warmup_ratio`), y cambia las rutas de Drive
(`working_paper` → `Working_Paper`). Con transformers v4 ambas versiones son
equivalentes; con v5, la de Git fallaría. `beto_sin_finetuning.py` solo difiere en las
rutas.

## 11. Verificaciones de la Fase 4 (2026-10-08, solo SELECT)

### a) Registros de origen del corpus

Los 799 segmentos activos provienen de **148** `id_registro` distintos (no 152).

| Grupo de `retroalimentacion` (211) | Registros | Origen |
|---|---|---|
| Con segmentos | 148 | Ejecución 2 (2026-05-14), que cargó 152 registros (ids 1-152) |
| Sin segmentos, ejecución 2 | 4 | Ids 9, 78, 109 y 111. El 9 tiene el mismo texto que el 6. Causa de los otros tres `[VERIFICAR]` |
| Sin segmentos, ejecución 4 | 59 | Ids 212-270 (2026-06-01), cargados por `09a` (171 procesados, 112 rechazados). Los 59 tienen el mismo texto que algún registro de la ejecución 2: son documentos de la Condición A que pasaron la validación |

El 152 del capítulo es el total cargado en la ejecución 2, no el número de registros
con segmentos. `retroalimentacion` mezcla los 152 registros de B con 59 de la Condición
A procesada.

### b) Identidad textual entre A y B sin defecto textual

| Alcance | Sin defecto textual | Texto idéntico | No coinciden |
|---|---|---|---|
| Filas primarias de A (las que evalúa el modelo) | 672 | 672 (100 %) | 0 |
| Todas las filas de A | 735 | 727 (98,9 %) | 8 |

Las 8 que no coinciden son filas extra de `duplicado_exacto` (orígenes 1685, 1752, 1774,
1901, 1933, 2291, 2419 y 2440) cuyo origen también tiene un defecto de texto. El 09
etiqueta la fila extra solo como `duplicado_exacto`, sin los demás tipos. Clasificada
por origen, la identidad es del 100 %. Control: los 127 segmentos con defecto textual
difieren todos.

### c) Segmento 1683

Sin defectos inyectados, una sola fila en A, texto idéntico en A y B (también en
comparación binaria; 76 caracteres), etiqueta `positivo` en ambas condiciones,
conjunto de prueba. No está entre los 30 segmentos con `cuasi_duplicado` mal
clasificados.

## 13. Fase 4: prueba de aceptación, multisemilla y sección (d) (2026-10-08)

### Insumos (`13b --modo completo`)

27 archivos copiados a `outputs/` con `manifiesto_insumos.csv`. Las predicciones de
BETO y RoBERTa son las de las corridas principales (SHA-256 `d70975…`/`98c943…` y
`e3e318…`/`ee6578…`), no las de la semilla 2024.

### Prueba de aceptación del script 14

| Configuración | Esperado | `46216f2` (antes del reemplazo) | `HEAD` (con `ee_bootstrap`) | `ee_bootstrap` | `emd_80` |
|---|---|---|---|---|---|
| baseline | +0.026 [−0.030, 0.084] p 0.390 | Igual | Igual | 0.0290 | 0.0812 |
| beto_sin_finetuning | +0.016 [−0.038, 0.070] p 0.536 | Igual | Igual | 0.0277 | 0.0775 |
| beto | +0.057 [−0.008, 0.122] p 0.092 | Igual | Igual | 0.0335 | 0.0939 |
| bertin_roberta | −0.059 [−0.151, 0.029] p 0.202 | Igual | Igual | 0.0460 | 0.1288 |

Diferencia, IC y p bilateral idénticos sin redondeo entre `46216f2` y `HEAD`. Entorno
congelado en `requirements-local.lock.txt` (Python 3.12.4). Nota: el registro muestra
`PyMySQL==1.2.3`, no 2.2.8 como decía la documentación interna.

Con la versión `46216f2` también se registraron las métricas retiradas (solo como
evidencia): `prop_remuestras_B_mejor` 0.805 / 0.954 / 0.101 / 0.732 y
`potencia_retrospectiva_aprox` 0.145 / 0.403 / 0.247 / 0.090 (baseline, beto,
bertin_roberta, beto_sin_finetuning).

Holm sobre las 4 configuraciones principales: p ajustados 0.780 (baseline), 0.368
(beto), 0.605 (bertin_roberta) y 0.780 (beto_sin_finetuning).

### Plan multisemilla (`14b_bootstrap_multisemilla.py`, `92801b2`)

Plan fijado en `2c39c91` (17:41:21) y script registrado en `92801b2` (17:44:20), ambos
antes de ejecutar. Resultados en `outputs/multisemilla/`.

| Modelo | Semilla | Δ B−A | IC 95 % | p (descriptivo) | EMD |
|---|---|---|---|---|---|
| BETO | 42 | +0.0046 | [−0.0846, 0.0825] | 0.941 | 0.119 |
| BETO | 123 | +0.0297 | [−0.0579, 0.1105] | 0.503 | 0.120 |
| BETO | 2024 | +0.0591 | [0.0036, 0.1184] | 0.039 | 0.081 |
| BETO | 7 | +0.0600 | [−0.0090, 0.1477] | 0.094 | 0.112 |
| BETO | 99 | +0.1355 | [0.0580, 0.2164] | 0.001 | 0.114 |
| BERTIN | 42 | +0.0871 | [−0.0011, 0.1849] | 0.053 | 0.134 |
| BERTIN | 123 | +0.0149 | [−0.0892, 0.1187] | 0.795 | 0.147 |
| BERTIN | 2024 | +0.0729 | [−0.0246, 0.1698] | 0.128 | 0.139 |
| BERTIN | 7 | +0.1121 | [0.0450, 0.1836] | 0.001 | 0.099 |
| BERTIN | 99 | +0.0403 | [−0.0723, 0.1511] | 0.495 | 0.159 |

| Modelo | Media (DE) | Mín. / máx. | B > A | p signos | IC 95 % dos niveles | p dos niveles | p Holm | Corrida principal | Robusto |
|---|---|---|---|---|---|---|---|---|---|
| BETO | +0.0578 (0.0491) | +0.0046 / +0.1355 | 5/5 | 0.0625 | [−0.0073, 0.1269] | 0.084 | 0.134 | +0.0571 | No |
| BERTIN | +0.0654 (0.0383) | +0.0149 / +0.1121 | 5/5 | 0.0625 | [−0.0059, 0.1335] | 0.067 | 0.134 | −0.0586 | No |

Descriptivos (media y DE de 5 semillas): Log Loss BETO A 1.163 (0.027), B 1.093
(0.035); BERTIN A 1.217 (0.062), B 1.136 (0.060). PR-AUC BETO A 0.532 (0.037), B 0.576
(0.025); BERTIN A 0.493 (0.037), B 0.567 (0.046).

Según el criterio g) del plan, ningún modelo es robusto a la semilla: el signo es
consistente (5/5), pero el IC agregado no excluye cero tras Holm. La fila s2024 de BETO
reproduce exactamente las cifras del archivo del 2026-08-30, como se esperaba.

### Sección (d) del 15: versión registrada frente a corregida

Las secciones (a), (b) y (c) son idénticas entre `7a314e1` y `HEAD`. La salida de
`7a314e1` es además idéntica byte a byte a la del 2026-08-26 en
`Working_paper/outputs/`: si se reportaron cifras de la sección (d) de agosto, son las
de la versión sin corregir.

| Modelo | Clase | Registrada (`7a314e1`) | Corregida (`HEAD`) |
|---|---|---|---|
| baseline | sin_defecto | 7 (26,9 %) | 7 (26,9 %) |
| baseline | solo_metadatos | 9 (34,6 %) | 6 (23,1 %) |
| baseline | afecta_texto | 10 (38,5 %) | 13 (50,0 %) |
| beto | sin_defecto | 14 (35,9 %) | 14 (35,9 %) |
| beto | solo_metadatos | 15 (38,5 %) | 12 (30,8 %) |
| beto | afecta_texto | 10 (25,6 %) | 13 (33,3 %) |
| bertin_roberta | sin_defecto | 27 (46,6 %) | 27 (46,6 %) |
| bertin_roberta | solo_metadatos | 23 (39,7 %) | 21 (36,2 %) |
| bertin_roberta | afecta_texto | 8 (13,8 %) | 10 (17,2 %) |

Flips con texto idéntico (sin_defecto + solo_metadatos): baseline 61,5 % → 50,0 %; BETO
74,4 % → 66,7 %; BERTIN 86,2 % → 82,8 %. Se reclasificaron 8 flips de 6 segmentos,
todos con `cuasi_duplicado`. El segmento 1683 cambia de predicción en BETO (B correcto,
A incorrecto) y en BERTIN (A correcto, B incorrecto), en ambos casos con texto idéntico.

### Huellas SHA-256 de las salidas

| Archivo (`outputs/`) | SHA-256 |
|---|---|
| `bootstrap_resultados.csv` | `269e203dae4067bda6d0a5804f31115ad7fd84d1fda45d2bd7ed7086394fe104` |
| `errores_por_categoria.csv` | `316884c17bf3fcd2402729c6caeff5a6c20cff584aa557e04e00ac5ba6042b2e` |
| `errores_negativo_por_naturaleza.csv` | `56299159213f94e9f2ecf7ea4c31087849c84c6d0fe95277934c2e98fa0daa1b` |
| `casos_que_cambian_entre_condiciones.csv` | `8f37725faef743cb9a28bcf65937b4c872c06631d1f884066bb9b6af502d3722` |
| `flips_por_clase_defecto.csv` | `df4ec7979fec4d66073561231057e5cdeced9852489ec1256917eea9cdae89e5` |
| `casos_que_cambian_con_clase_defecto.csv` | `b74be0c0c2e97adc6866810d54bda6530745ef20d6306ba00a1017795a926b78` |
| `multisemilla/bootstrap_por_semilla.csv` | `9c80bc292cab0569d056b55d6a84413cba7292d681aaeee121b730c574f0a03b` |
| `multisemilla/agregado_por_modelo.csv` | `87ea5209dc99ec4a85eb0180f4a271010a29447f686a50f3d9f33a0f3314aea6` |
| `multisemilla/holm_configuraciones_principales.csv` | `4d9e935afa47eb99f5b373c3d22903015e4547081d8aa72aa3ede857ba847552` |
| `multisemilla/descriptivo_logloss_prauc.csv` | `8313fc2a8531d15298286cb27b3651c1f617f6b208375fd16603d2017cd91800` |
| `multisemilla/manifiesto_insumos_multisemilla.csv` | `59b90309b335f024e9df75bedaf726b2fd104814fa77b188135bbfee2d233f99` |
| `manifiesto_insumos.csv` | `3e15894a3af5c7a8363cb37b27a19314b82cb221e8e0fbbd97e924ca3591a7c5` |
| `bootstrap_distribuciones.png` | `14042a8b801eea6a8c4b390454a3874b51f52c5ee1f3a2d9a3550046f3354c2c` |
| `01_metricas_por_configuracion.png` | `5a5ef41a7e228464fdbfb3594de882ace9f8c058dc56bd61e1b812bb6c9b978c` |
| `02_matrices_confusion.png` | `7fe445897e739179f976e46c6df2ff45e696d74f06e8e082f667e618b8fdb2f8` |
| `03_curvas_kfold_epocas.png` | `7775d0bc391c6cbbceb5b69311872c86e07a28ae37e91bacb04742524d6d754a` |

## 15. Catálogo de reglas de calidad: 9 frente a 11 reglas (2026-10-08, solo lectura)

Búsqueda de "RQ-10", "RQ-11", "RQ10" y "RQ11" en el repositorio, en `Working_paper/`
(texto extraído de 14 `.docx`, 3 `.xlsx` y 37 `.pdf`; uno de ellos,
`Metodologias_reconocidas_CRISPDM.pdf`, sin texto extraíble) y en
`MyDrive/Working_Paper/` (solo `.py`, `.pyc` y `.csv` en la copia local).

### Hallazgos

| Archivo | Fecha | ¿RQ-10/11? | Contenido |
|---|---|---|---|
| `Borradores/Fase2_Metadatos_Minimos.docx` | 2026-03-24 | No | Menciona "las 11 reglas de calidad" sin tabla; cita RQ-01, RQ-05, RQ-06 (corrige a `desconocido`) y RQ-09 |
| `Borradores/Working_Paper_Marco_Gobernado_v1.docx` | 2026-08-09 | **Sí** | "Once reglas de calidad (RQ-01 a RQ-11)", con tabla completa (abajo) |
| `AGENTS.md` y `Code/docs/CLAUDE_junio.md` | 2026-08-06 y 2026-08-04 | **Sí** | Las 9 reglas del código más RQ-10 "Normalización textual básica (aplicada en generación del corpus base)" y RQ-11 "(referida en Fase 2 como implícita — confirmar definición exacta si se va a citar formalmente)" |
| `Borradores/Reporte_Metodologico.docx` | 2026-08-14 | No | "Reglas de calidad RQ-01 a RQ-09"; RQ-08 contenido no informativo y RQ-09 longitud insuficiente |
| `Borradores/Esquema_General_Trabajo_de_Grado.docx` | 2026-09-01 | No | "Reglas de calidad RQ-01 a RQ-09"; prevé un "Anexo D — Reglas de calidad RQ-01 a RQ-09" |
| `scripts/09a_procesar_condicion_a.py` (código) | — | No | Catálogo implementado de 9 reglas; cualquier violación rechaza el registro |

Tabla de 11 reglas del borrador del 2026-08-09:

| RQ | Dimensión | Campo | Condición de fallo | Acción |
|---|---|---|---|---|
| RQ-01 | Completitud | texto | nulo o vacío | Rechazar |
| RQ-02 | Completitud | id_sesion | nulo | Rechazar |
| RQ-03 | Completitud | fecha_registro | nula | Rechazar |
| RQ-04 | Completitud | canal_captura | nulo o vacío | Corregir → `desconocido` |
| RQ-05 | Validez | fecha_registro | formato ≠ YYYY-MM-DD o futura | Rechazar |
| RQ-06 | Validez | canal_captura | fuera del catálogo | Corregir → `desconocido` |
| RQ-07 | Validez | etiqueta_sentimiento | fuera de {positivo, neutral, negativo} | Rechazar |
| RQ-08 | Unicidad | hash_texto + id_sesion | hash + sesión ya existe | Rechazar |
| RQ-09 | Consistencia | texto | longitud < 3 caracteres | Rechazar |
| RQ-10 | Consistencia | texto | solo números o puntuación | Rechazar |
| RQ-11 | Trazabilidad | id_ejecucion | ausente al insertar | Rechazar |

### Conclusión

Hay dos catálogos con la misma numeración y distinto contenido:

- **Catálogo de diseño (11 reglas):** Fase 2 (marzo) lo anuncia y el borrador del
  2026-08-09 lo detalla. Es la fuente probable de las "11 reglas" del capítulo.
- **Catálogo implementado (9 reglas):** `09a`, el Reporte Metodológico (agosto) y el
  Esquema General (septiembre, el documento más reciente).

Los mismos códigos significan reglas distintas:

| Código | Diseño (11) | Implementado (9) |
|---|---|---|
| RQ-04, RQ-06 | Corrigen a `desconocido` | Rechazan |
| RQ-07 | Etiqueta fuera del esquema | Duplicado exacto o cuasi-duplicado |
| RQ-08 | Duplicado por hash + sesión | Texto no informativo |
| RQ-09 | Longitud < 3 | Longitud < 20 |
| RQ-10 | Solo números o puntuación | No existe |
| RQ-11 | `id_ejecucion` obligatorio | No existe |

La versión de `AGENTS.md`/`CLAUDE_junio.md` es un tercer intento de conciliación, con
RQ-10 y RQ-11 distintos a los del diseño. `chk_texto_longitud` (5 caracteres, script 13)
no coincide con ninguno de los dos umbrales de RQ-09 (3 o 20). `[VERIFICAR]` qué
catálogo describe el capítulo de Metodología y declarar la diferencia con el
implementado.

## 16. Registros de B sin segmentos activos (2026-10-08, solo lectura)

Los ids 9, 78, 109 y 111 (ejecución 2) **no tienen ninguna fila** entre los 821
segmentos de `segmento_retroalimentacion`: no perdieron segmentos por exclusión (los 22
excluidos provienen de otros 20 registros). La resegmentación con la API de Claude
(script 07, 2026-05-19) no les generó ninguno. `outputs/segmentos_claude_api_completo.csv`
tiene 821 segmentos de 148 registros, sin estos 4.

El 07 procesa todo registro con más de 50 caracteres (los 4 cumplen: 10.761, 1.331, 812
y 300) y, cuando la API devuelve una lista vacía o falla (error de API o JSON inválido),
lo cuenta como "error" sin distinguir entre ambos casos. No se guardó el registro de
consola de esa ejecución, así que no se puede determinar si fue un fallo o una respuesta
sin contenido del estudiante. El largo no explica el caso: el registro 9 es el
15.º más largo y registros más largos sí se segmentaron; el 111 es el más corto (300
caracteres, 23 s de audio). El 9 tiene el mismo texto que el 6. Con la segmentación
anterior por palabras clave (respaldo del 2026-05-19 17:12) tenían 20, 1, 2 y 1
segmentos. `[VERIFICAR]`.

## 17. Inclusión involuntaria de `test_colab.ipynb` en `0c8b4cb`

El commit `0c8b4cb` (2026-10-08, versiones ejecutadas de Colab) incluyó por error
`scripts/test_colab.ipynb`: se hizo con `git add` de los cuatro scripts y `git commit`
sin `--only`, y el notebook estaba en staging desde el inicio de la auditoría. Ya estaba
en GitHub al detectarse.

Revisión del contenido incluido: 17 celdas con salidas de la ejecución de
`entrenar_beto_multisemilla.py` (preview y completo). Sin claves de API, contraseñas,
tokens ni texto de entrevistas; el único correo (`taku@google.com`) proviene de un aviso
de una biblioteca. Decisión de la autora (opción A): se mantiene en el historial sin
reescribirlo; su revisión y limpieza se hacen en la Fase 6.

## 18. Métricas de calidad estructural y épocas del k-fold (2026-10-09, solo lectura)

### Definición operativa de las métricas (`calcular_metricas`, script 05)

Todas se expresan en porcentaje (0-100, un decimal) y se calculan sobre registros de
documento (`corpus_final.csv` para B y la Condición A generada en memoria para A), no
sobre segmentos.

| Métrica | Fórmula | Observación |
|---|---|---|
| Completitud | Celdas no nulas / (n × número de campos), con los campos `text`, `num_sesion`, `fecha_real` y `canal_captura` si existe | B no tiene `canal_captura` (3 campos); A sí (4 campos) |
| Unicidad | 1 − (registros con `text` repetido / n), contando como repetidas las apariciones posteriores a la primera (`duplicated()`, coincidencia exacta del texto) | — |
| Validez de fecha | Fechas con formato `YYYY-MM-DD` / fechas presentes | Las fechas nulas no cuentan |
| Validez de canal | Canales en {formulario, papel, app, email, desconocido} / canales presentes | En B, sin columna de canal, vale 100 por definición (`es_condicion_b`) |
| Trazabilidad | B: 100 si existen las columnas `metodo_sesion` y `nombre_sesion` (50 si no); A: 0 | No se mide sobre los datos |

**Métricas que son 100 % o 0 % por construcción del diseño:** validez de canal de B
(100: el campo no existe en B y el código asigna 100), trazabilidad de B (100: solo
comprueba que existan dos columnas) y trazabilidad de A (0: asignada por código). La
validez de fecha de B (100) sí es medida, pero solo sobre las 129 fechas presentes; las
23 ausentes cuentan en la completitud.

### Unicidad de B: 88,8 %

17 de los 152 registros de `corpus_final.csv` repiten exactamente el texto de otro
(1 − 17/152 = 88,8 %). Son 17 pares, ninguno con el mismo archivo de audio. Expresados
con `id_registro` de la BD (que coincide con la posición en `corpus_final.csv`, no con
su columna `id`):

- 13 pares de un registro "[SESION]" y otro
  "[SESION]": 39-40, 41-146, 42-148, 43-149, 44-152,
  45-98, 46-99, 47-100, 48-101, 49-141, 50-142, 51-143 y 52-145. Es la misma
  transcripción asignada a dos programas.
- 4 pares dentro de la misma sesión del bloque 1: 1-8 (sesión 03), 6-9 (04), 10-12 (05)
  y 11-14 (06). Es la misma transcripción en dos archivos de audio.

`01_deduplicar_y_cargar.py` deduplica por archivo de audio, no por texto, así que estos
pares pasaron a la Condición B. `[VERIFICAR]` si son re-transcripciones del mismo audio
con otro nombre o grabaciones distintas con texto idéntico. El registro 9, uno de los 4
sin segmentos (§16), forma par con el 6.

**Consecuencia: fuga entre entrenamiento y prueba.** La partición agrupa por
`id_registro`, pero los dos registros de un par son entrevistas idénticas con
`id_registro` distinto. En 5 pares (1-8, 10-12, 39-40, 46-99 y 48-101) un registro quedó
en entrenamiento y el otro en prueba. Resultado (solo lectura, Condición B):

| Medida | Valor |
|---|---|
| Segmentos de prueba de registros cuyo gemelo está en entrenamiento | 22 de 183 (12,0 %); 20 de los 177 evaluados |
| De ellos, con texto idéntico a un segmento de entrenamiento | 8 (7 de los 177) |
| De ellos, con similitud ≥ 0,8 (`difflib`) a un segmento de entrenamiento | 18 |

La partición es la misma para A y B, así que la fuga afecta a ambas condiciones. Es
probable que infle las métricas absolutas de todos los modelos; el efecto sobre la
diferencia B − A no se puede anticipar sin calcularlo. `[VERIFICAR]`: análisis de
sensibilidad excluyendo esos 20 segmentos de la evaluación (no requiere reentrenar), o
reconstruir la partición agrupando por texto de la entrevista (requiere reentrenar).

### De dónde sale n_A = 171

152 registros base + 12 duplicados exactos (`int(152 × 0,08)`) + 7 cuasi-duplicados
(`int(152 × 0,05)`) = 171. Los demás defectos modifican registros existentes sin agregar
filas.

### Hallazgo: `n/a` se lee como nulo

La tabla de calidad (82,2 % de completitud y 88,9 % de validez de canal en A) se
reproduce exactamente al regenerar la Condición A en memoria. Pero al recalcularla desde
`outputs/condicion_A.csv` da 81,6 % y 91,3 %: el catálogo de canales inválidos del 05
incluye el valor `"n/a"`, que `pandas.read_csv` convierte en nulo por defecto. Las 4
filas con ese canal pasan de "fuera de catálogo" a "nulas". `09a_procesar_condicion_a.py`
lee ese CSV con las opciones por defecto, así que en `detalle_error` esas 4 violaciones
quedaron como RQ-04 (canal nulo; 20 en total) en vez de RQ-06 (fuera de catálogo; 13 en
total, ninguna con `n/a`). El rechazo de los registros no cambia, porque ambas reglas
rechazan; sí cambia el conteo por regla.

### Épocas del k-fold

`EPOCAS_MAX = 4` y `K_FOLDS = 5` en `entrenar_beto.py` y `entrenar_roberta.py`. La época
final es la de mayor F1-macro medio entre folds (`np.nanargmax`). Fue la 4 en los cuatro
casos (BETO y BERTIN, A y B; confirmado en `kfold_epocas_{A,B}.csv` y en las salidas del
notebook): la época elegida coincide con el tope de la búsqueda.

| Modelo | Condición | Época 1 | Época 2 | Época 3 | Época 4 | Mejora de la 3 a la 4 |
|---|---|---|---|---|---|---|
| BERTIN | A | 0.1806 | 0.3535 | 0.4404 | 0.4894 | +0.0490 |
| BERTIN | B | 0.1837 | 0.3727 | 0.4787 | 0.4875 | +0.0088 |
| BETO | A | 0.3655 | 0.4636 | 0.4976 | 0.5098 | +0.0122 |
| BETO | B | 0.3382 | 0.4694 | 0.5123 | 0.5127 | +0.0004 |

En BERTIN A la curva seguía subiendo de forma apreciable en la época 4, y en BETO A
también. Como la época elegida es el tope, no se puede descartar que más épocas mejoraran
el resultado, y la mejora potencial no es igual entre condiciones. Es una limitación a
declarar.

## 19. Duplicados de entrevistas: origen, fuga y sensibilidad (2026-10-09)

### El script 01 deduplica por archivo de audio, no por texto

`deduplicar()` en `01_deduplicar_y_cargar.py` elimina los registros con el mismo **nombre
de archivo de audio** (`audio_filename`, sin la ruta) y conserva la transcripción del
modelo prioritario más reciente. No compara el texto. Los 17 pares de §18 tienen nombres
de archivo distintos, pero la misma duración de audio y el mismo modelo de transcripción
en los 17 casos: casi con seguridad es el mismo audio guardado con dos nombres. Por eso
pasaron a la Condición B como registros distintos.

### Los 17 pares (`id_registro`)

| Par | Sesión asignada | Segmentos | Etiquetas | Partición |
|---|---|---|---|---|
| 1-8 | bloque 1, sesión 03 (ambos) | 6 / 6 | idénticas | prueba / entrenamiento |
| 6-9 | bloque 1, sesión 04 (ambos) | 7 / 0 | — | prueba / sin segmentos |
| 10-12 | bloque 1, sesión 05 (ambos) | 8 / 7 | casi idénticas | entrenamiento / prueba |
| 11-14 | bloque 1, sesión 06 (ambos) | 7 / 7 | difieren | entrenamiento / entrenamiento |
| 39-40 | [PROGRAMA] clausura / [PROGRAMA] | 2 / 2 | idénticas | entrenamiento / prueba |
| 41-146 | [PROGRAMA] / [PROGRAMA] clausura | 3 / 2 | difieren | entrenamiento / entrenamiento |
| 42-148 | [PROGRAMA] / [PROGRAMA] clausura | 1 / 1 | difieren | entrenamiento / entrenamiento |
| 43-149 | [PROGRAMA] / [PROGRAMA] clausura | 7 / 7 | idénticas | entrenamiento / entrenamiento |
| 44-152 | [PROGRAMA] / [PROGRAMA] clausura | 1 / 1 | idénticas | entrenamiento / entrenamiento |
| 45-98 | [PROGRAMA] / [PROGRAMA] clausura | 1 / 1 | idénticas | entrenamiento / entrenamiento |
| 46-99 | [PROGRAMA] / [PROGRAMA] clausura | 3 / 2 | mismo tipo | prueba / entrenamiento |
| 47-100 | [PROGRAMA] / [PROGRAMA] clausura | 5 / 5 | difieren | entrenamiento / entrenamiento |
| 48-101 | [PROGRAMA] / [PROGRAMA] clausura | 4 / 4 | difieren | entrenamiento / prueba |
| 49-141 | [PROGRAMA] / [PROGRAMA] clausura | 3 / 3 | idénticas | entrenamiento / entrenamiento |
| 50-142 | [PROGRAMA] / [PROGRAMA] clausura | 2 / 2 | difieren | entrenamiento / entrenamiento |
| 51-143 | [PROGRAMA] / [PROGRAMA] clausura | 2 / 2 | idénticas | prueba / prueba |
| 52-145 | [PROGRAMA] / [PROGRAMA] clausura | 2 / 1 | mismo tipo | entrenamiento / entrenamiento |

La segmentación con la API no fue idéntica entre gemelos (número de segmentos distinto
en 4 pares: 10-12, 41-146, 46-99 y 52-145) y la distribución de etiquetas difiere en 6
pares (11-14, 41-146, 42-148, 47-100, 48-101 y 50-142): el mismo contenido recibió
etiquetas distintas. Es un indicio de la variabilidad del etiquetado `[VERIFICAR]`.

### Segunda vía de fuga: augmentation

12 variantes de augmentation por condición, en entrenamiento, derivan de los registros
10 y 48, gemelos de los registros de prueba 12 y 101. No agregan segmentos al conjunto de
exclusión, porque esos registros ya tenían segmentos en entrenamiento.

### Conjunto de exclusión y plan de sensibilidad

Definido y registrado antes de calcular (`72690a2`, plan del 2026-10-09): 22 segmentos de
prueba (20 de los 177 evaluados), los mismos en A y B: 1654-1659, 1723-1729, 1856, 1857,
1871-1873 y 2107-2110. Implementado con `--excluir-fuga` en 14 y 14b (`03632dc`); las
salidas principales conservaron su huella SHA-256.

**Análisis principal (script 14), n = 157:**

| Configuración | F1 A antes → después | F1 B antes → después | Δ antes | Δ después [IC 95 %] | p antes → después | p Holm antes → después | EE / EMD después |
|---|---|---|---|---|---|---|---|
| baseline | 0.445 → 0.385 | 0.470 → 0.406 | +0.026 | +0.021 [-0.034, +0.075] | 0.390 → 0.478 | 0.780 → 1.000 | 0.027 / 0.077 |
| BETO sin ajuste | 0.430 → 0.401 | 0.446 → 0.401 | +0.016 | +0.000 [-0.054, +0.053] | 0.536 → 0.935 | 0.780 → 1.000 | 0.028 / 0.077 |
| BETO con ajuste fino | 0.465 → 0.441 | 0.522 → 0.473 | +0.057 | +0.033 [-0.034, +0.105] | 0.092 → 0.361 | 0.368 → 1.000 | 0.035 / 0.098 |
| BERTIN | 0.510 → 0.499 | 0.452 → 0.423 | -0.059 | -0.076 [-0.179, +0.017] | 0.202 → 0.106 | 0.605 → 0.426 | 0.050 / 0.140 |

**Multisemilla (14b), n = 157:**

| Modelo | Media (DE) antes → después | B > A | IC 95 % dos niveles después | p (Holm) antes → después | Robusto antes / después |
|---|---|---|---|---|---|
| BETO con ajuste fino | +0.058 (0.049) → +0.039 (0.062) | 5/5 → 3/5 | [-0.036, +0.118] | 0.084 (0.134) → 0.299 (0.299) | No / No |
| BERTIN | +0.065 (0.038) → +0.068 (0.038) | 5/5 → 5/5 | [-0.014, +0.142] | 0.067 (0.134) → 0.097 (0.194) | No / No |

| Semilla | BETO Δ después | BERTIN Δ después |
|---|---|---|
| s42 | -0.0092 | +0.1041 |
| s123 | -0.0160 | +0.0265 |
| s2024 | +0.0268 | +0.0665 |
| s7 | +0.0568 | +0.1085 |
| s99 | +0.1372 | +0.0339 |

**Criterio d) del plan: se cumple.** En las cuatro configuraciones se mantienen la
dirección de Δ y la condición de significancia con Holm (ninguna significativa, antes ni
después), y el resultado del criterio g) del multisemilla no cambia (ningún modelo es
robusto a la semilla). Las conclusiones son robustas a la fuga en ese sentido.

Matices que no cambian el criterio, pero sí la lectura:

- **El F1-macro absoluto baja en todas las configuraciones** (entre 1 y 6,5 puntos), lo
  que es coherente con que la fuga inflaba las métricas.
- **En BETO con ajuste fino la fuga favorecía más a B:** F1 de B −0,049 frente a −0,024
  de A. Δ baja de +0,057 a +0,033 (p 0,092 → 0,361), y en el multisemilla B > A pasa de
  5/5 a 3/5 semillas (media +0,039).
- **BETO sin ajuste** queda en Δ ≈ 0 (+0,0004).
- **BERTIN** mantiene el patrón: la corrida principal se vuelve más negativa (−0,076) y el
  multisemilla sigue con 5/5 semillas a favor de B (media +0,068).

Salidas: `outputs/bootstrap_resultados_sin_fuga.csv`,
`outputs/bootstrap_distribuciones_sin_fuga.png` y `outputs/multisemilla_sin_fuga/`.

## 20. Atribución errónea de 4 violaciones en `detalle_error`

El catálogo de canales inválidos del script 05 incluye `"n/a"`. `09a_procesar_condicion_a.py`
lee `condicion_A.csv` con `pd.read_csv` por defecto, que convierte `"n/a"` en nulo. Por
eso, las 4 filas con canal `"n/a"` se registraron en `detalle_error` como **RQ-04 (canal
nulo)** cuando corresponden a **RQ-06 (canal fuera de catálogo)**. Conteos registrados:
RQ-04 = 20 y RQ-06 = 13; corregidos: RQ-04 = 16 y RQ-06 = 17. El rechazo de los registros
no cambia (ambas reglas rechazan) y la tabla de calidad (script 05, calculada en memoria)
no está afectada. `detalle_error` no se modifica: es evidencia de lo ejecutado. Al
reportar conteos por regla, usar los corregidos (propuesta 9 en
`docs/propuestas_mejora_arquitectura.md`).

## 21. Hallazgos al construir el Anexo D, hoy Anexo C (2026-10-09, solo lectura)

### La segmentación solo cubre los primeros 4.000 caracteres de cada entrevista

`07_resegmentar_corpus_completo.py` (línea 86) envía a la API `texto[:4000]`. Ningún
documento del proyecto lo menciona (guía, Reporte Metodológico, Esquema General,
borrador del working paper).

| Medida | Valor |
|---|---|
| Entrevistas de B con más de 4.000 caracteres | 56 de 152 (36,8 %) |
| Caracteres más allá del 4.000 | 259.557 de 624.203 (41,6 % del texto del corpus) |
| Segmentos de entrevistas largas ubicables literalmente en el original | 292 de 441; **ninguno** empieza después del carácter 4.000 |

El 41,6 % del texto recogido no forma parte del corpus de análisis. Afecta por igual a A
y B (A parte de los mismos segmentos), pero condiciona qué partes de las entrevistas se
analizan. Es una limitación que debe declararse. `[VERIFICAR]` si fue una decisión
deliberada (límite de costo o de contexto de la API).

### Origen del umbral de 5 caracteres

`chk_texto_longitud` (script 13) replica RQ-01 tal como la implementan los cargadores de
B: `01_deduplicar_y_cargar.py:380` y `02_fusionar_y_cargar.py:237` rechazan textos de
menos de 5 caracteres y lo registran como RQ-01. No es un umbral arbitrario; es otra
versión de RQ-01, distinta de la del 09a (texto vacío). Corrige lo dicho en §5 y en la
propuesta 2.

### RQ-07 en la Condición A detecta casi todos los duplicados naturales

Reproduciendo la validación del 09a en memoria, RQ-07 marca 34 registros de A: 17 en las
filas que agrega la inyección, 14 segundas apariciones de pares naturales de B y 3
textos no informativos inyectados repetidos. Los otros 3 pares no se detectan porque la
inyección alteró uno de los gemelos. La regla existía, pero solo se aplicó a A.

### `04_etiquetar_sentimiento.py` asigna `neutral` a etiquetas no reconocidas

Si el modelo devuelve una etiqueta fuera del diccionario o un JSON inválido, el 04 asigna
`neutral` (con confianza "baja" en el caso de JSON inválido) y no lo registra como error.
En la ejecución que cargó las etiquetas (`etiquetas_cargar_20260519_1752.csv`, 821
segmentos) no hubo ningún caso. Es un riesgo del código sin efecto en los datos.

### Punto 9: ¿la fuga favorecía a B por memorización?

De los 20 segmentos evaluados excluidos, solo en **3** el segmento gemelo de
entrenamiento más parecido tiene el texto alterado por un defecto en A (2 de los 16 con
similitud ≥ 0,8). En los demás, A también tenía el gemelo intacto en entrenamiento. La
memorización asimétrica por defectos de A explica, a lo sumo, una parte pequeña de que
la exclusión redujera más el F1 de B que el de A en BETO. En 4 de los 20 el propio
segmento de prueba tiene el texto alterado en A.

### Punto 10: pares con etiquetas distintas para el mismo texto

| Par | Gemelo 1 (partición: etiquetas) | Gemelo 2 (partición: etiquetas) |
|---|---|---|
| 11-14 | entrenamiento: lev. pos. 3, neutral 1, positivo 3 | entrenamiento: lev. pos. 3, negativo 1, positivo 3 |
| 41-146 | entrenamiento: lev. pos. 2, positivo 1 | entrenamiento: lev. pos. 1, positivo 1 |
| 42-148 | entrenamiento: muy positivo 1 | entrenamiento: positivo 1 |
| 47-100 | entrenamiento: lev. pos. 1, neutral 2, positivo 2 | entrenamiento: lev. pos. 1, neutral 3, positivo 1 |
| 48-101 | entrenamiento: lev. pos. 2, neutral 1, positivo 1 | **prueba**: lev. pos. 3, neutral 1 |
| 50-142 | entrenamiento: lev. pos. 1, muy positivo 1 | entrenamiento: muy positivo 1, neutral 1 |

Solo el par 48-101 tiene un gemelo en prueba (el 101, en el conjunto de exclusión).

## 22. Anexos renumerados, prompts y auditoría de privacidad (2026-10-09)

**Renumeración (decisión de la autora, 2026-10-09):** A diccionario de datos (versión
liviana), B prompts de la API de Claude, C reglas de calidad (antes D), D código y
repositorio, E resultados complementarios. Se retira el cronograma. Los archivos de
`docs/anexos/` cambian de nombre en consecuencia; el script 18 borra los anteriores al
regenerar.

**Hallazgos al extraer los prompts (Anexo B), sin efecto en los datos ya generados:**

- Ninguna de las cuatro llamadas a la API (04, 07, 08 y 09_reetiquetar_positivos) fija
  `temperature`: rige el valor por defecto (1,0). La segmentación, el etiquetado, la
  reclasificación y las variantes sintéticas no son reproducibles exactamente aunque se
  repita la llamada con el mismo texto. Limitación que debe declararse.
- El 07 pide "máximo 10 segmentos por entrevista" solo en el prompt; el código no lo
  verifica (el máximo observado es 10).
- Si la respuesta del 07 no es un JSON válido (por ejemplo, si se corta en
  `max_tokens = 2000`), la entrevista queda sin segmentos y solo se imprime un aviso en
  consola. `[VERIFICAR]` si explica alguno de los 4 registros sin segmentos (§11, §16):
  uno de ellos (id 9) tiene 10.761 caracteres; los otros tres, entre 300 y 1.331.
- El texto de los prompts, el modelo y `max_tokens` no cambiaron en ninguna versión de
  Git; la primera versión en Git (2026-08-21) es posterior a la ejecución (mayo y junio).
- Los prompts del 04 y del 07 nombran el programa; el anexo lo reemplaza por una marca.

**Auditoría de privacidad del historial** (`scripts/19_auditoria_privacidad.py`,
su reporte no se publica; solo lectura). Sin texto de estudiantes, sin nombres de
archivo de audio y sin nombres de institución educativa en ninguna versión publicada. Se
encontró:

- **Un nombre propio en el código:** `01_deduplicar_y_cargar.py` compara la ruta del audio
  con un fragmento que contiene un nombre propio (probablemente de persona), presente desde el primer commit y
  publicado. No se modificó (registrar antes de mejorar); decisión pendiente de la autora.
- **Nombres de programa** en el código (01, 02, 04, 07 y el histórico 06) y en esta bitácora;
  **nombres de sesión** en esta bitácora. Son nombres genéricos de programa, zona, bloque y
  número de sesión.
- **Objetos inalcanzables locales:** unos 9.300 objetos que no pertenecen a ningún commit
  (sobre todo archivos de bibliotecas de un entorno virtual agregado al área de
  preparación y nunca confirmado). No están publicados; las coincidencias con nombres
  propios en ellos están, por el tipo de archivo, sobre todo en código y licencias de
  bibliotecas (nombres de autores).

## 23. Resumen

| Script | ¿Cambio de lógica en agosto? | ¿Altera resultados reportados? |
|---|---|---|
| 14 | Sí: 3 métricas descriptivas/prospectivas nuevas y 3 columnas en el CSV | No en los valores inferenciales (a confirmar en Fase 4). Sí en la interpretación si se reportó un p de una cola |
| 15 | Sí: sección (d) nueva y 2 CSV nuevos | No en (a)-(c). La sección (d) tiene un error de clasificación (`cuasi_duplicado`, 30 segmentos) |
| 16 | No | No |
| Limpieza 00-16 | No (22/22 equivalentes) | No |
| 13 | Cambio de esquema aplicado el 2026-08-31 (no de código) | No en cifras; sí en el texto si la sección 16 del reporte da la brecha por abierta |

## Limitaciones de este análisis

- La herramienta ignora el contenido de las cadenas. Las diferencias de cadenas fuera
  de `print()` se listan como aviso y se revisaron a mano: en el 14 son los nombres de
  las 3 columnas nuevas; en el 15, los dos tipos de defecto de la constante y los
  nombres de los 2 CSV nuevos. Una cadena modificada **dentro** de `print()` que
  alimente un archivo (no es el caso en estos scripts) pasaría inadvertida.
- Las especificaciones de formato de los f-strings (p. ej. `:.3f`) se tratan como
  contenido de cadena.
- El análisis es estático: confirma que el código de los valores reportados no cambió,
  pero la reproducción numérica exacta se verifica en la Fase 4.
