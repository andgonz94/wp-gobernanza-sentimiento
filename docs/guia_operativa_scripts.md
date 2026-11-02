# Guía operativa de scripts

> Este documento reúne las notas operativas (rutas de carpetas, nombres de 
> archivos esperados, de dónde descargar cada insumo, orden de ejecución) 
> que antes vivían en el encabezado de cada script. Se movieron aquí para 
> que el código que se comparte en GitHub quede limpio y general, sin 
> perder esta información para quien ejecute el pipeline.
>
> Cada vez que se limpie un script nuevo, 
> agregar su entrada aquí siguiendo el mismo formato.
>
> Los scripts en `scripts/colab/` no corren localmente: están escritos para
> Google Colab con GPU y dependen de las 4 tablas exportadas por
> `12_exportar_tablas_para_colab.py`, subidas manualmente a Google Drive.
>
> Los scripts que quedaron fuera del flujo operativo se manejan de dos formas:
> **históricos** (`scripts/historico/`) para los que ya no son necesarios para
> reconstruir el pipeline pero sostienen una decisión metodológica documentada
> (no se borran, por trazabilidad ante el jurado); y **retirados** (eliminados
> del repo) para los que eran solo utilidades de respaldo sin valor de
> trazabilidad. Ver la sección "Scripts retirados" al final de este documento.

---

## Orden de ejecución

Orden real reconstruido el 2026-10-08 a partir de las fechas de los archivos de salida, de la creación de las tablas (`information_schema.TABLES`) y de las dependencias entre scripts. La numeración no se cambia (rompería las referencias del Reporte Metodológico); este orden resuelve, en particular, los tres scripts con prefijo `09_`. Las fechas marcadas con `[VERIFICAR]` son inferidas.

| Paso | Script | Evidencia (fecha) | Depende de |
|---|---|---|---|
| 0 | `00_test_conexion.py`, `00b_inspeccionar_esquema.py`, `00c_verificar_entorno.py` | — | — |
| 1 | `01_deduplicar_y_cargar.py` | `corpus_deduplicado.csv` (2026-05-14 20:42) | CSV de transcripciones |
| 2 | `02_fusionar_y_cargar.py` | `corpus_final.csv` y ejecución 2 de `ejecucion_pipeline` (2026-05-14 21:22) | 1 y revisión manual de sesiones |
| 3 | `07_resegmentar_corpus_completo.py` | `segmentos_claude_api_completo.csv` (2026-05-19 17:25) | 2 |
| 4 | `04_etiquetar_sentimiento.py` | `etiquetas_cargar_20260519_1752.csv` | 3 |
| 5 | `05_construir_condicion_a.py` | `condicion_A.csv`, `comparativa_calidad.csv` (2026-05-19 19:15) | 2 |
| 6 | `09_reetiquetar_positivos.py` | `reetiquetado_positivos_20260519_2049.csv` | 4 |
| 7 | `09a_procesar_condicion_a.py` | `reporte_comparativo_condiciones.csv` y ejecución 4 (2026-06-01 23:02) | 5 |
| 8 | `09_cargar_revision_manual.py` | `revision_manual_procesada.csv` (2026-06-02 11:56) | 6 y revisión manual |
| 9 | `09_construir_condicion_a_segmentos.py` | tabla `segmento_condicion_a` (2026-08-05 22:04) `[VERIFICAR]`: la tabla pudo recrearse después de su primera ejecución | 8 |
| 10 | `08_data_augmentation.py` (o su recarga desde CSV) | tabla `augmentation_segmentos` (2026-08-05 23:00) | 8 |
| 11 | `10_split_train_test.py` | tabla `split_asignacion` (2026-08-06 00:26) | 9 y 10 |
| 12 | `11_entrenar_baseline.py` | `predicciones_{A,B}_baseline.csv` (2026-08-12 15:42) | 11 |
| 12b | `11b_baseline_vectorizador_por_condicion.py` | `outputs/sensibilidad_vectorizador/` (2026-11-02) | 11 y 16 |
| 13 | `12_exportar_tablas_para_colab.py` → `colab/` | corridas principales de Colab (2026-08-12 a 2026-08-28) | 11 |
| 14 | `13_agregar_constraints_esquema.py` | respaldo y reconstrucción de `retroalimentacion` (2026-08-31 23:24). Ya aplicado; no reejecutar | 2 |
| 15 | `13b_preparar_insumos_validacion.py` | `manifiesto_insumos.csv` | 12 y 13 |
| 16 | `14_bootstrap_pareado.py` → `14b_bootstrap_multisemilla.py` | `bootstrap_resultados.csv`, `outputs/multisemilla/` | 15 |
| 17 | `15_analisis_errores.py`, `16_generar_graficos.py` | salidas de análisis y figuras | 15 |
| 18 | `17_figuras_trazables.py` | `manifiesto_figuras.csv` | 16 y 17 |
| 19 | `18_anexos_esquema_general.py` | `docs/anexos/` | 14, 14b (con y sin `--excluir-fuga`) y 15 |
| 20 | `19_auditoria_privacidad.py` | `docs/auditoria_privacidad.md` (2026-10-09) | — (solo lectura del historial de Git y de la BD) |

Los tres `09_` no dependen entre sí en un solo sentido: `09_reetiquetar_positivos.py` (paso 6) modifica etiquetas que después revisa `09_cargar_revision_manual.py` (paso 8), y `09_construir_condicion_a_segmentos.py` (paso 9) parte de los segmentos ya revisados y excluidos.

---

## Cómo leer este documento

Cada script tiene su propia sección con:
- **Qué hace**: resumen de una línea (ya está también en el docstring del script).
- **Estructura de carpetas esperada**: qué debe existir antes de correrlo.
- **De dónde vienen los insumos**: qué se genera localmente vs. qué hay que descargar de Drive u otra fuente.
- **Salidas**: qué archivos produce y dónde quedan.
- **Uso**: comando para ejecutarlo.

---

## `00_test_conexion.py`

**Qué hace:** verifica la conexión a MySQL con las credenciales del `.env` y lista las tablas disponibles en el esquema.

**Requisitos previos:** archivo `.env` en la raíz del proyecto con `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, y el servidor MySQL corriendo.

**Uso:**
```
python scripts/00_test_conexion.py
```

---

## `00b_inspeccionar_esquema.py`

**Qué hace:** consulta `information_schema` para imprimir las columnas reales (tipo, nulabilidad, claves) de las tablas `sesion`, `retroalimentacion`, `ejecucion_pipeline` y `detalle_error`. Correr antes de escribir cualquier script que dependa de nombres de columnas, ya que estos se han corregido varias veces durante el proyecto.

**Requisitos previos:** conexión a MySQL configurada vía `.env`.

**Uso:**
```
python scripts/00b_inspeccionar_esquema.py
```

---

## `00c_verificar_entorno.py`

**Qué hace:** verifica el entorno local antes de las validaciones: Python del `.venv`, librerías del perfil local con sus versiones (`importlib.metadata`), `.env` y conexión a MySQL, los 799 segmentos activos, y la presencia de los insumos que organiza `13b` (los toma de `construir_mapeo()`, una sola fuente de verdad).

**Salidas:** `outputs/entorno_verificado.txt`. Código de salida 0 si el entorno está listo.

**Uso:**
```
python scripts/00c_verificar_entorno.py
```

---

## `01_deduplicar_y_cargar.py`

**Qué hace:** deduplica transcripciones crudas por archivo de audio, infiere metadatos de sesión (componente, zona, bloque, número de sesión) a partir de la ruta del archivo o, como respaldo, de la fecha de creación, y opcionalmente carga los registros válidos a la base de datos.

**Insumo esperado:** un CSV de transcripciones crudas (ver `data/transcriptions_202605132350.csv` como ejemplo de estructura: columnas `id`, `created_at`, `audio_path`, `model_used`, `language`, `duration_s`, `text`, `segments`).

**Salidas** (`outputs/`):
- `reporte_descartados.csv` — registros eliminados por duplicado.
- `corpus_deduplicado.csv` — registros conservados y enriquecidos.
- `revision_manual_sesiones.csv` — registros cuya sesión no pudo inferirse con certeza (requieren revisión manual antes de continuar el pipeline).

**Uso:**
```
python scripts/01_deduplicar_y_cargar.py --csv data/transcriptions_202605132350.csv --modo preview
python scripts/01_deduplicar_y_cargar.py --csv data/transcriptions_202605132350.csv --modo cargar
```
El modo `preview` no escribe en la base de datos; usar `cargar` solo después de revisar el reporte y el CSV de revisión manual.

---

## `02_fusionar_y_cargar.py`

**Qué hace:** fusiona el corpus deduplicado con las correcciones manuales de sesión (las correcciones sobrescriben la asignación automática), recalcula los metadatos derivados y, opcionalmente, carga los registros a la base de datos.

**Insumos esperados** (`outputs/`, generados por `01_deduplicar_y_cargar.py` y su revisión manual):
- `corpus_deduplicado.csv`
- `revision_manual_sesiones.csv` — con la columna `num_sesion` completada donde corresponda.

**Salidas:**
- `outputs/corpus_final.csv` — corpus fusionado, para auditoría.

**Uso:**
```
python scripts/02_fusionar_y_cargar.py --modo preview
python scripts/02_fusionar_y_cargar.py --modo cargar
```
El modo `preview` no escribe en la base de datos; usar `cargar` solo después de revisar el reporte.

---

## `historico/03_segmentar_entrevistas.py` — histórico, no operativo

> Movido a `scripts/historico/` porque `07_resegmentar_corpus_completo.py` no depende de sus resultados en absoluto — lee directamente de `retroalimentacion`, no de los segmentos que este script genera. Reconstruir el pipeline desde cero hoy no requiere correr este script. Se conserva (no se elimina) porque sus salidas fueron el insumo de `06_comparar_segmentacion.py`, cuya evidencia cuantitativa sostiene la decisión de reemplazar la segmentación por palabras clave por segmentación con modelo de lenguaje (ver nota metodológica en `07_resegmentar_corpus_completo.py` más abajo).

**Qué hace:** segmenta las entrevistas transcritas en fragmentos temáticos usando patrones de texto y palabras clave (versión basada en reglas, reemplazada por `07_resegmentar_corpus_completo.py`, que usa un modelo de lenguaje). Separa las intervenciones del entrevistador de las del estudiante y clasifica cada fragmento por categoría.

**Insumos esperados:**
- El CSV de transcripciones crudas original (mismo que en `01_deduplicar_y_cargar.py`).
- `outputs/corpus_final.csv` (generado por `02_fusionar_y_cargar.py`).
- Registros ya cargados en la tabla `retroalimentacion` de MySQL (se usan para vincular cada segmento con su `id_registro`).

**Salidas:**
- `outputs/segmentos_preview.csv`

**Uso:**
```
python scripts/historico/03_segmentar_entrevistas.py --csv data/transcriptions_202605132350.csv --modo preview
python scripts/historico/03_segmentar_entrevistas.py --csv data/transcriptions_202605132350.csv --modo cargar
```
El modo `preview` no escribe en la base de datos.

---

## `04_etiquetar_sentimiento.py`

**Qué hace:** llama a la API de Claude para etiquetar cada segmento con una escala de intensidad emocional de 5 niveles (`muy_positivo`, `positivo`, `neutral`, `negativo`, `muy_negativo`), guarda un CSV de auditoría y, opcionalmente, actualiza la base de datos.

**Requisitos previos:**
- `ANTHROPIC_API_KEY` en `.env`.
- Segmentos ya cargados en la tabla `segmento_retroalimentacion` (categoría distinta de `general`).

**Salidas** (`outputs/`):
- `etiquetas_test_<timestamp>.csv` o `etiquetas_cargar_<timestamp>.csv` — CSV de auditoría con las etiquetas asignadas.

**Uso:**
```
python scripts/04_etiquetar_sentimiento.py --modo test     # prueba con 10 segmentos, no toca la BD
python scripts/04_etiquetar_sentimiento.py --modo cargar   # etiqueta todo y actualiza MySQL
```
Revisar el CSV de auditoría en modo `test` antes de correr `cargar`.

---

## `05_construir_condicion_a.py`

**Qué hace:** construye la Condición A (datos crudos no gobernados) inyectando errores controlados y reproducibles (semilla fija) sobre el corpus base gobernado, y compara las métricas de calidad de ambas condiciones.

**Tasas de inyección** (definidas en la Fase 3 del documento de trabajo):
- Nulos en id_sesion: 15% · texto: 5% · fecha_registro: 10% · canal_captura: 12%
- Duplicados exactos: 8% · cuasi-duplicados: 5%
- Formato de fecha inválido: 8% · canal fuera de catálogo: 10% · texto no informativo: 7%

**Insumo esperado:** `outputs/corpus_final.csv` (corpus base gobernado, generado por `02_fusionar_y_cargar.py`).

**Salidas** (`outputs/`, solo en modo `generar`):
- `condicion_A.csv`
- `auditoria_inyeccion.csv`
- `comparativa_calidad.csv`

**Uso:**
```
python scripts/05_construir_condicion_a.py --modo preview
python scripts/05_construir_condicion_a.py --modo generar
```

---

## `historico/06_comparar_segmentacion.py` — histórico, no operativo

> Movido a `scripts/historico/` porque ya cumplió su función: generó la evidencia cuantitativa que justificó reemplazar la segmentación por palabras clave por segmentación con modelo de lenguaje. No es parte del flujo que se re-ejecuta, pero sus salidas (`comparacion_segmentacion.csv`, `comparacion_lado_a_lado.csv`) son la evidencia citada como trazabilidad de esa decisión — no se elimina.

**Qué hace:** compara la segmentación por palabras clave (`historico/03_segmentar_entrevistas.py`) contra la segmentación con modelo de lenguaje, sobre una muestra estratificada de entrevistas, para evaluar diferencias en número de segmentos y coincidencia de categorías.

**Requisitos previos:**
- `ANTHROPIC_API_KEY` en `.env`.
- Segmentos por palabras clave ya cargados en `segmento_retroalimentacion`.
- Registros de `retroalimentacion` con texto de longitud suficiente.

**Salidas** (`outputs/`):
- `segmentos_claude_api.csv`
- `comparacion_segmentacion.csv`
- `comparacion_lado_a_lado.csv` — para revisar diferencias entrevista por entrevista.

**Uso:**
```
python scripts/historico/06_comparar_segmentacion.py --n 10
python scripts/historico/06_comparar_segmentacion.py --n 5
```

---

## `07_resegmentar_corpus_completo.py`

**Qué hace:** resegmenta el corpus completo de entrevistas usando un modelo de lenguaje, reemplazando la segmentación anterior basada en palabras clave. Respalda la segmentación previa antes de sobrescribirla.

**Decisión metodológica que motiva este script:** la comparación sobre una muestra de entrevistas (`historico/06_comparar_segmentacion.py`) mostró que el método de palabras clave (`historico/03_segmentar_entrevistas.py`) sobreparticionaba el texto (10.7 vs 6.7 segmentos promedio por entrevista, diferencia del 37%), comprometiendo la coherencia temática de las unidades de análisis exigida por el marco gobernado (Fase 3). La resegmentación con modelo de lenguaje se documenta como decisión de preparación de datos basada en evidencia empírica, no como sustitución del objetivo analítico. Los segmentos resultantes alimentan el etiquetado de sentimiento (`04_etiquetar_sentimiento.py`) y el modelado posterior.

**Requisitos previos:**
- `ANTHROPIC_API_KEY` en `.env`.
- Corpus cargado en la tabla `retroalimentacion` de MySQL.

**Artefactos de trazabilidad de la decisión** (`outputs/`, generados por scripts previos):
- `comparacion_segmentacion.csv` — evidencia cuantitativa de la decisión.
- `comparacion_lado_a_lado.csv` — detalle por entrevista.

**Salidas** (`outputs/`):
- `segmentos_palabras_clave_backup_<timestamp>.csv` — respaldo del método anterior antes de sobrescribir.
- `segmentos_claude_api_completo.csv` — CSV de auditoría de los nuevos segmentos.

**Uso:**
```
python scripts/07_resegmentar_corpus_completo.py --modo preview
python scripts/07_resegmentar_corpus_completo.py --modo cargar
```
Después de cargar, re-ejecutar `04_etiquetar_sentimiento.py --modo cargar` para actualizar las etiquetas de sentimiento sobre los nuevos segmentos.

---

## `08_data_augmentation.py`

**Qué hace:** genera variantes sintéticas por paráfrasis para las clases minoritarias (`negativo`, `neutral`) usando un modelo de lenguaje, e inserta cada variante de forma simétrica en ambas condiciones: texto íntegro en la condición gobernada, mismo texto con metadatos degradados en la condición cruda (misma lógica de `09_construir_condicion_a_segmentos.py`). Toda variante queda marcada con `es_sintetico=1` para trazabilidad.

**Historial de corrección (contenido antes en el encabezado del script, referenciado internamente como "v2"):**
- La fuente ahora lee `segmento_retroalimentacion` filtrando `flag_excluir=0`, sobre el ground truth ya auditado (excluye el segmento 1806 por baja calidad de transcripción; el segmento 2441 quedó reclasificado a `neutral`).
- Conteos objetivo actualizados: `negativo=35` (antes 37), `neutral=88` (antes 84).
- El `DELETE` antes de insertar ahora borra solo las condiciones que se regeneran en la corrida, no la tabla completa (bug corregido de una versión anterior).
- Principio de simetría A/B: las variantes de texto se generan una sola vez con la API; el mismo texto se inserta tal cual en `condicion='B'` y, tras la misma degradación de metadatos usada en `09_construir_condicion_a_segmentos.py`, en `condicion='A'` — así el contenido textual es idéntico entre condiciones (Documento de Trabajo, sección 8) y el augmentation no introduce una variable de confusión adicional.

> Igual que en `07_resegmentar_corpus_completo.py`, esta trazabilidad de decisiones vivía solo en el encabezado del script. Candidata a moverse a `docs/decisiones_metodologicas.md` cuando se cree ese documento.

**Requisitos previos:**
- `ANTHROPIC_API_KEY` en `.env`.
- Segmentos auditados en `segmento_retroalimentacion` (columna `flag_excluir`).

**Salidas:**
- `outputs/augmentation_variantes_v2.csv` — CSV de auditoría de las variantes generadas.
- Tabla `augmentation_segmentos` en MySQL (creada automáticamente si no existe).

**Uso:**
```
python scripts/08_data_augmentation.py --modo preview   # prueba con 3 segmentos, no toca la BD
python scripts/08_data_augmentation.py --modo cargar    # genera y carga todas las variantes
```

---

## `09_cargar_revision_manual.py`

**Qué hace:** carga las correcciones manuales del re-etiquetado de segmentos, marca automáticamente cuáles excluir por falta de valor analítico (o usa la columna `Eliminar` del Excel de revisión si está presente) y, opcionalmente, valida cada etiqueta manual contra un modelo de lenguaje antes de actualizar la base de datos.

**Insumo esperado:** `outputs/revision_manual_etiquetas.xlsx` (o `.csv`) — planilla de revisión manual con las columnas `id_segmento`, `texto_segmento`, `etiqueta_nueva` y, opcionalmente, `Eliminar`.

**Requisitos previos (solo si se usa `--validar`):** `ANTHROPIC_API_KEY` en `.env`.

**Salidas:**
- `outputs/revision_manual_procesada.csv`

**Uso:**
```
python scripts/09_cargar_revision_manual.py --csv outputs/revision_manual_etiquetas.csv --modo preview
python scripts/09_cargar_revision_manual.py --csv outputs/revision_manual_etiquetas.csv --modo preview --validar
python scripts/09_cargar_revision_manual.py --csv outputs/revision_manual_etiquetas.csv --modo cargar --validar
```

---

## `09_construir_condicion_a_segmentos.py`

**Qué hace:** construye la versión segmentada de la Condición A inyectando defectos de calidad sobre los segmentos ya existentes en `segmento_retroalimentacion` (Condición B). La mayoría de los defectos afectan metadatos, validaciones o trazabilidad; tres alteran el texto del segmento (ver el principio metodológico). Un mismo segmento puede recibir más de un defecto.

**Principio metodológico (Documento de Trabajo, sección 8):** A y B parten del mismo corpus de texto base; la Condición A no introduce textos nuevos y conserva en todos los casos la etiqueta de sentimiento del segmento. Seis de los nueve tipos de defecto dejan el texto idéntico: `nulo_id_sesion`, `nulo_canal`, `canal_fuera_catalogo`, `nulo_fecha`, `formato_fecha` y `duplicado_exacto` (este último agrega una fila adicional con el mismo texto). Los otros tres alteran deliberadamente el texto del segmento afectado, porque simulan defectos de calidad textual que la gobernanza debe detectar:
- `nulo_texto`: se elimina el texto.
- `texto_no_informativo`: se reemplaza por una frase sin valor analítico.
- `cuasi_duplicado`: se repite la primera palabra al final (definición a nivel de segmento; difiere de la usada a nivel de documento en el script 05).

Para comparar A y B segmento a segmento, "texto idéntico" se determina comparando directamente el texto de ambas condiciones, no por el tipo de defecto.

> Nota: el Documento de Trabajo (sección 8) formuló el principio como identidad estricta del contenido textual; la implementación lo precisa como se describe aquí. Desviación declarada en el capítulo de Metodología, sección 3.1.

**Proporciones replicadas de `auditoria_inyeccion.csv`** (152 registros originales → 88 afectados, 126 errores, 57.9% tasa de afectación):
- `nulo_id_sesion` 18.25% · `nulo_canal` 14.29% · `canal_fuera_catalogo` 13.49%
- `nulo_fecha` 11.90% · `formato_fecha` 11.11%
- `duplicado_exacto` 9.52% · `texto_no_informativo` 9.52%
- `nulo_texto` 6.35% · `cuasi_duplicado` 5.56%

> Al igual que en `07_resegmentar_corpus_completo.py` y `08_data_augmentation.py`, este principio metodológico vivía solo en el encabezado del script. Candidato a moverse a `docs/decisiones_metodologicas.md` cuando se cree ese documento.

**Insumo esperado:** segmentos en `segmento_retroalimentacion` con `flag_excluir = 0`.

**Salidas:**
- Tabla `segmento_condicion_a` en MySQL (creada automáticamente si no existe).
- `outputs/auditoria_inyeccion_segmentos.csv`

**Uso:**
```
python scripts/09_construir_condicion_a_segmentos.py --modo preview
python scripts/09_construir_condicion_a_segmentos.py --modo cargar
```

---

## `09_reetiquetar_positivos.py`

**Qué hace:** reclasifica los segmentos etiquetados como `positivo` en dos niveles (`positivo`: valoración clara y sostenida; `levemente_positivo`: valoración tibia, condicionada o con reservas) usando un modelo de lenguaje con criterios operativos explícitos. Actualiza automáticamente la base de datos solo con las reclasificaciones de confianza alta; las de confianza media/baja quedan marcadas en el CSV para revisión manual.

**Requisitos previos:**
- `ANTHROPIC_API_KEY` en `.env`.
- Segmentos con `etiqueta_sentimiento = 'positivo'` en `segmento_retroalimentacion`.

**Salidas** (`outputs/`):
- `reetiquetado_positivos_<timestamp>.csv` — resultado completo para revisión manual de los casos de confianza media/baja.

**Uso:**
```
python scripts/09_reetiquetar_positivos.py --modo preview   # prueba con 5 segmentos, no toca la BD
python scripts/09_reetiquetar_positivos.py --modo cargar    # reclasifica todo y actualiza los de alta confianza
```
Revisar el CSV y corregir manualmente los casos de confianza media/baja antes de considerarlos definitivos.

---

## `09a_procesar_condicion_a.py`

**Qué hace:** procesa la Condición A (datos crudos sintéticos) a través del pipeline de gobernanza, simulando qué pasaría sin el marco gobernado: valida cada registro contra las reglas de calidad (RQ-01 a RQ-09), registra cada violación en `detalle_error` y carga a `retroalimentacion` solo los registros que pasan, generando un reporte comparativo contra la Condición B.

**Insumos esperados** (`outputs/`, generados por `05_construir_condicion_a.py`):
- `condicion_A.csv`
- `auditoria_inyeccion.csv`

**Salidas:**
- `outputs/reporte_comparativo_condiciones.csv`

**Uso:**
```
python scripts/09a_procesar_condicion_a.py --modo preview   # simula sin tocar la BD
python scripts/09a_procesar_condicion_a.py --modo cargar    # procesa y carga los registros válidos
```
Siguiente paso sugerido: `08_data_augmentation.py --modo preview`.

---

## Scripts retirados

Eliminados del repositorio (no en `scripts/historico/`) porque eran utilidades de respaldo o quedaron superadas, sin valor de trazabilidad metodológica que sostener.

### `08b_cargar_augmentation_desde_csv.py`
Cargaba a `augmentation_segmentos` las variantes ya generadas por `08_data_augmentation.py` (desde `outputs/augmentation_variantes_v2.csv`), sin volver a llamar al modelo de lenguaje — un plan B para cuando la carga a MySQL fallaba por un problema de esquema después de ya haber gastado la llamada a la API. Duplicaba la lógica de `08_data_augmentation.py` casi por completo. Se retiró porque la carga en su momento se completó exitosamente y ya no cumple ninguna función; si se necesitara de nuevo, es más simple agregarle a `08_data_augmentation.py` una opción `--desde-csv` que reutilizar este script aparte.

### `09b_construir_dataset_final.py`
Construía `outputs/dataset_final.csv`, `dataset_train.csv` y `dataset_test.csv` con un split train/test por segmento individual, sin agrupar por `id_registro` ni por `id_segmento_origen` (ver la nota de fuga de datos que tenía esta sección antes de retirarlo). Se confirmó que `11_entrenar_baseline.py` usa la tabla `split_asignacion` (construida por `10_split_train_test.py`, con split agrupado y sin fuga de augmentation), no estos CSV — este script quedó completamente superado por `10_split_train_test.py` y sus salidas no se usaban en el modelado real. Se retiró en vez de dejarlo como histórico porque no sostiene ninguna decisión metodológica documentada: simplemente fue la primera versión del split, luego corregida.

---

## `10_split_train_test.py`

**Qué hace:** genera un único split (80/20) train/test, agrupado por `id_registro`, para reutilizarlo de forma idéntica en los 3 modelos (baseline, BETO, RoBERTa-es) y en ambas condiciones (A y B). Guarda el resultado en la tabla `split_asignacion`, que es la que efectivamente consume `11_entrenar_baseline.py` (y, se espera, los scripts de entrenamiento de BETO/RoBERTa).

**Principios metodológicos aplicados** (contenido antes en el encabezado del script):
1. **Split agrupado por entrevista:** todos los segmentos de un mismo `id_registro` caen en el mismo lado (train o test), evitando que el modelo "reconozca" el estilo de un estudiante que ya vio en entrenamiento.
2. **Estratificación aproximada** por `etiqueta_sentimiento` usando `StratifiedGroupKFold`, para que la distribución de clases en train y test sea lo más parecida posible al corpus completo sin violar la agrupación.
3. **Augmentation sin fuga:** una variante sintética solo se incorpora a train si su segmento de origen también cayó en train; si el origen cayó en test, la variante se descarta por completo.
4. **Mismo test set entre condiciones:** el mismo conjunto de `id_registro` en test se usa para A y B, garantizando que la comparación sea sobre exactamente los mismos casos.

**Insumos esperados:** segmentos reales y sintéticos ya cargados en MySQL (`segmento_retroalimentacion`, `augmentation_segmentos`).

**Salidas:**
- Tabla `split_asignacion` en MySQL (creada automáticamente si no existe).
- `outputs/split_asignacion.csv` — respaldo.

**Uso:**
```
python scripts/10_split_train_test.py
```

---

## `11_entrenar_baseline.py`

**Qué hace:** entrena y evalúa un modelo baseline (TF-IDF + regresión logística) en ambas condiciones, usando el split agrupado de `split_asignacion` (`10_split_train_test.py`). Guarda métricas, matrices de confusión y predicciones por caso, en el mismo formato que se espera de los scripts de BETO/RoBERTa-es, para que sean directamente comparables.

**Estrategia híbrida para texto degradado en Condición A (Opción 3, acordada explícitamente — contenido antes en el encabezado del script):**
- Los segmentos de Condición A con defecto `nulo_texto` (texto perdido) se **excluyen** del cálculo de F1-macro comparativo (no son clasificables por diseño), pero se cuentan y reportan aparte como "tasa de pérdida de información por falta de gobernanza".
- Los segmentos con `texto_no_informativo` (texto reemplazado por "ok", "bien", etc.) **sí se incluyen** en el cálculo de F1-macro — son procesables, y se espera que generen errores de clasificación reales, que es precisamente el efecto que se quiere medir.
- Para que la comparación A vs. B sea sobre exactamente los mismos `id_segmento`, el mismo subconjunto de exclusión (`nulo_texto`) se aplica también al test de B, aunque B nunca tenga ese defecto — así el F1-macro comparado es "manzanas con manzanas" en tamaño N.

**Insumo esperado:** tabla `split_asignacion` en MySQL (generada por `10_split_train_test.py`).

**Salidas** (`outputs/`):
- `resultados_baseline.csv`, `matriz_confusion_{A,B}.csv`, `pr_auc_por_clase_{A,B}.csv`, `predicciones_{A,B}_baseline.csv`

**Uso:**
```
python scripts/11_entrenar_baseline.py
```

---

## `11b_baseline_vectorizador_por_condicion.py`

**Qué hace:** análisis de sensibilidad del baseline (plan del 2026-11-02). Repite el TF-IDF con regresión logística con un vectorizador ajustado sobre el entrenamiento de cada condición, en lugar del único ajustado sobre B del script 11, y estima Δ con `bootstrap_pareado` del 14, por segmento y por entrevista, con y sin el conjunto de fuga. Reutiliza la carga, la construcción de conjuntos y el conjunto comparable del 11. Antes de calcular, verifica que con el vectorizador único reproduce las predicciones originales (`outputs/bootstrap_input/baseline_predicciones_{A,B}.csv`); si no, se detiene. El resultado principal del baseline sigue siendo el del 11.

**Salidas** (`outputs/sensibilidad_vectorizador/`): `predicciones_{A,B}_baseline.csv` y `bootstrap_resultados.csv`.

**Uso:**
```
python scripts/11b_baseline_vectorizador_por_condicion.py --modo preview    # verifica y muestra, no escribe
python scripts/11b_baseline_vectorizador_por_condicion.py --modo completo
```

---

## `12_exportar_tablas_para_colab.py`

**Qué hace:** exporta a CSV las tablas necesarias para el ajuste fino de BETO y RoBERTa-es en Google Colab, donde no hay acceso directo a la base MySQL local: `split_asignacion`, `segmento_retroalimentacion` (solo columnas necesarias, `flag_excluir=0`), `segmento_condicion_a` y `augmentation_segmentos`.

**Salidas:**
- `outputs/colab/split_asignacion.csv`
- `outputs/colab/segmento_retroalimentacion.csv`
- `outputs/colab/segmento_condicion_a.csv`
- `outputs/colab/augmentation_segmentos.csv`

Después de generarlos, subir la carpeta a Google Drive (por ejemplo, `MyDrive/working_paper/datos_colab/`) para usarlos desde el notebook de Colab.

**Uso:**
```
python scripts/12_exportar_tablas_para_colab.py
```

---

## `colab/entrenar_beto.py`

**Qué hace:** ajusta finamente BETO (`dccuchile/bert-base-spanish-wwm-cased`) para clasificación de sentimiento en 5 clases, entrenado y evaluado en ambas condiciones de forma secuencial. Usa k-fold (5 folds, agrupado por entrevista y estratificado) para decidir el número óptimo de épocas antes de reentrenar una sola vez sobre el train completo, y aplica la misma estrategia híbrida de evaluación que `11_entrenar_baseline.py` (exclusión de `nulo_texto` del F1 comparable).

**Entorno:** Google Colab con GPU (Entorno de ejecución > Cambiar tipo de entorno de ejecución > GPU). Requiere `!pip install -q transformers datasets evaluate accelerate` y montar Google Drive.

**Insumo esperado:** las 4 tablas de `12_exportar_tablas_para_colab.py`, subidas a `MyDrive/working_paper/datos_colab/` (ajustar `RUTA_DATOS` si la carpeta es otra).

**Modo preview (correr primero):** entrena 1 época sobre una muestra reducida (40 train / 10 test por condición), sin guardar el modelo final — valida en minutos que rutas, esquema y bucle de entrenamiento funcionan, antes de comprometer 15-30 min de GPU por condición en la corrida completa.

**Salidas** (`MyDrive/working_paper/resultados_colab/beto/`, guardadas después de cada condición para no perder progreso si la sesión se desconecta):
- `resultado_{A,B}.csv`, `kfold_epocas_{A,B}.csv`, `matriz_confusion_{A,B}.csv`, `pr_auc_por_clase_{A,B}.csv`, `predicciones_{A,B}.csv`, `classification_report_{A,B}.txt`
- `modelo_final_{A,B}/` (solo en modo completo)
- `resumen_beto_A_vs_B.csv`

**Uso:**
```
python entrenar_beto.py --modo preview
python entrenar_beto.py --modo completo   (o sin argumento, es el default)
```

---

## `colab/entrenar_roberta.py`

**Qué hace:** igual que `entrenar_beto.py`, pero para RoBERTa-es / BERTIN (`bertin-project/bertin-roberta-base-spanish`). Misma lógica de carga, k-fold, entrenamiento y evaluación híbrida.

**Entorno, insumo y modo preview:** igual que `entrenar_beto.py`.

**Salidas:** igual que `entrenar_beto.py`, en `MyDrive/working_paper/resultados_colab/roberta_es/`, con `resumen_roberta_A_vs_B.csv` en vez de `resumen_beto_A_vs_B.csv`.

**Uso:**
```
python entrenar_roberta.py --modo preview
python entrenar_roberta.py --modo completo   (o sin argumento, es el default)
```

---

## `colab/entrenar_roberta_multisemilla.py`

**Qué hace:** reentrena BERTIN 5 veces por condición (semillas 42, 123, 2024, 7 y 99), variando solo la semilla, con 4 épocas fijas y sin repetir el k-fold. Reinicia la semilla justo antes de crear el modelo. Análisis de sensibilidad del plan multisemilla fijado el 2026-10-08.

**Advertencia:** El docstring y los mensajes de DIAGNOSTICO contienen interpretaciones escritas antes del análisis; no reflejan los resultados. Ver el plan multisemilla del 2026-10-08 y sus resultados.

**Requiere:** `entrenar_roberta.py` en la misma carpeta de Drive (lo importa) y los mismos CSV en `RUTA_DATOS` que usa ese script.

**Salidas** (`MyDrive/Working_Paper/resultados_colab/roberta_es/multisemilla/`): `predicciones_s<semilla>_{A,B}.csv` (solo `id_segmento`, `y_true`, `y_pred`), `detalle_multisemilla.csv`, `detalle_multisemilla_parcial.csv` (guardado incremental por semilla) y `resumen_multisemilla.csv`.

**Uso (Colab):**
```
!python entrenar_roberta_multisemilla.py --semillas 42,123,2024,7,99
!python entrenar_roberta_multisemilla.py --modo preview   # prueba rápida
```

---

## `colab/entrenar_beto_multisemilla.py`

**Qué hace:** igual que `entrenar_roberta_multisemilla.py`, para BETO; sirve de control del protocolo multisemilla.

**Advertencia:** El docstring y los mensajes de DIAGNOSTICO contienen interpretaciones escritas antes del análisis; no reflejan los resultados. Ver el plan multisemilla del 2026-10-08 y sus resultados.

**Requiere:** `entrenar_beto.py` en la misma carpeta de Drive y los mismos CSV en `RUTA_DATOS`.

**Salidas:** igual que el de RoBERTa, en `MyDrive/Working_Paper/resultados_colab/beto/multisemilla/`.

**Uso (Colab):**
```
!python entrenar_beto_multisemilla.py --semillas 42,123,2024,7,99
!python entrenar_beto_multisemilla.py --modo preview   # prueba rápida
```

---

## `colab/beto_sin_finetuning.py`

**Qué hace:** evalúa BETO como extractor de representaciones congelado (linear probing) — sin ajustar ninguno de sus pesos, entrena una regresión logística sobre sus embeddings (mean pooling de la última capa oculta), igual que el baseline TF-IDF pero sobre embeddings de BETO. Sirve para cuantificar cuánto aporta el ajuste fino completo (`entrenar_beto.py`) frente a usar el modelo preentrenado tal cual.

**Requisitos previos:** debe ejecutarse desde la misma carpeta que `entrenar_beto.py` — lo importa como módulo (`import entrenar_beto as eb`) para reutilizar la carga de datos, `ETIQUETAS`, `MODELO_CHECKPOINT`, etc.

**Salidas** (`MyDrive/working_paper/resultados_colab/beto_sin_finetuning/`):
- `resultado_{A,B}.csv`, `matriz_confusion_{A,B}.csv`, `pr_auc_por_clase_{A,B}.csv`, `predicciones_{A,B}.csv`, `classification_report_{A,B}.txt`
- `resumen_beto_sinfinetuning_A_vs_B.csv`

**Uso:**
```
python beto_sin_finetuning.py
```

---

## `colab/diagnostico_tokenizacion.py`

**Qué hace:** compara cómo BETO y BERTIN tokenizan el mismo corpus (fertilidad, longitud de secuencia, proporción de ejemplos truncados por `MAX_LENGTH`), para diagnosticar si la diferencia de estabilidad observada entre ambos modelos durante el entrenamiento se explica parcialmente por diferencias de tokenización. No entrena ningún modelo — corre en segundos.

**Requisitos previos:** debe ejecutarse desde la misma carpeta que `entrenar_beto.py` (lo importa como módulo).

**Uso:**
```
python diagnostico_tokenizacion.py
```

---

## `colab/diagnostico_hiperparametros_roberta.py`

**Qué hace:** prueba rápida (un solo fold, ~2-3 min) para confirmar si bajar el learning rate (2e-5→1e-5) y el recorte de gradiente (max_grad_norm 1.0→0.5) reduce la inestabilidad de entrenamiento observada en BERTIN. Compara ambas configuraciones sobre el mismo fold de la Condición B e imprime grad_norm y F1-macro por época, lado a lado.

**Requisitos previos:** debe ejecutarse desde la misma carpeta que `entrenar_roberta.py` (lo importa como módulo).

**Uso:**
```
python diagnostico_hiperparametros_roberta.py
```

---

## `13_agregar_constraints_esquema.py` — ya aplicado, no reejecutar

**Qué hace:** declara como restricciones del esquema de `retroalimentacion` las reglas RQ-01 a RQ-04 y RQ-06 (`NOT NULL` y dos `CHECK`), con respaldo previo verificado y confirmación en consola.

**Estado:** ejecutado por la autora con `--modo aplicar` el 2026-08-31 23:24, después de imputar a mano 23 fechas faltantes. No debe volver a ejecutarse: fallaría al intentar crear de nuevo las restricciones `CHECK`. El modo preview es de solo lectura. Detalle en `docs/cambios_agosto_2026.md`, sección 5.

**Uso (solo inspección):**
```
python scripts/13_agregar_constraints_esquema.py            # preview, no modifica nada
```

---

## `13b_preparar_insumos_validacion.py`

**Qué hace:** copia las salidas del baseline y de Colab a `outputs/bootstrap_input/` y `outputs/graficos_input/` con nombres normalizados, rechaza archivos `_preview` y deja un manifiesto con la huella SHA-256 de cada archivo. Toma las predicciones principales de RoBERTa con su nombre real (`roberta_predicciones_{A,B}.csv`), no las de `multisemilla/`.

**Insumos:** salidas del baseline (originales en `Working_paper/outputs/`) y copia local de `MyDrive/Working_Paper/resultados_colab/`.

**Salidas:** `outputs/bootstrap_input/*.csv` (8), `outputs/graficos_input/<modelo>/*.csv` (19) y `outputs/manifiesto_insumos.csv`.

**Uso:** primero preview; solo si dice `PREVIEW OK`, completo.
```
python scripts/13b_preparar_insumos_validacion.py --origen-baseline ../outputs --origen-colab "<ruta a resultados_colab>" --modo preview
python scripts/13b_preparar_insumos_validacion.py --origen-baseline ../outputs --origen-colab "<ruta a resultados_colab>" --modo completo
```

---

## `14_bootstrap_pareado.py`

**Qué hace:** calcula un bootstrap pareado sobre la diferencia F1-macro(B) - F1-macro(A) para cada uno de los modelos evaluados (baseline, BETO, BERTIN/RoBERTa-es, BETO sin ajuste), y genera un resumen consolidado con intervalos de confianza al 95%, p-valor aproximado y significancia.

**Por qué pareado:** para todo `id_segmento` sin defecto de texto, el contenido que ve el modelo es idéntico entre A y B (solo cambian metadatos que el modelo de texto no usa). Los defectos de texto son `nulo_texto`, `texto_no_informativo` y `cuasi_duplicado` (ver el principio metodológico de `09_construir_condicion_a_segmentos.py`); en esos segmentos el texto difiere entre A y B, pero el par sigue siendo válido porque se trata del mismo segmento con la misma etiqueta. Esto permite remuestrear los mismos `id_segmento` en ambas condiciones simultáneamente, en vez de tratarlas como muestras independientes — más potente estadísticamente, equivalente a un test t pareado frente a uno de dos muestras independientes.

**Estructura de carpetas esperada** (`outputs/bootstrap_input/`, nombres exactos):
```
baseline_predicciones_A.csv       (ya está en outputs/, solo renombrar)
baseline_predicciones_B.csv
beto_predicciones_A.csv           (descargar de Drive: resultados_colab/beto/predicciones_A.csv)
beto_predicciones_B.csv           (idem, predicciones_B.csv)
roberta_predicciones_A.csv        (descargar de Drive: resultados_colab/roberta_es/predicciones_A.csv)
roberta_predicciones_B.csv        (idem, predicciones_B.csv)
beto_probing_predicciones_A.csv   (descargar de Drive: resultados_colab/beto_sin_finetuning/predicciones_A.csv)
beto_probing_predicciones_B.csv   (idem, predicciones_B.csv)
```
Cada CSV debe tener columnas `id_segmento`, `y_true`, `y_pred` (y opcionalmente `prob_<clase>`, no usadas en este script).

**Salidas** (`outputs/`):
- `bootstrap_resultados.csv`: por configuración, F1-macro de A y B, diferencia, IC 95 %, `p_valor_aprox` (bilateral), `significativo_95`, `ee_bootstrap` (desviación estándar de la distribución bootstrap de Δ), `emd_80` (efecto mínimo detectable con 80 % de potencia) y `n_pares`. Desde 2026-10 ya no incluye `prop_remuestras_B_mejor`, `potencia_retrospectiva_aprox` ni `n_requerido_80pct_potencia`.
- `bootstrap_distribuciones.png`: un panel por configuración con Δ, IC 95 % y p (sin etiqueta de "significativo").

Los insumos los organiza `13b_preparar_insumos_validacion.py`; no copiarlos a mano.

**Uso:**
```
python scripts/14_bootstrap_pareado.py
```

**Bootstrap por entrevista (inferencia principal desde el 2026-11-02):** `python scripts/14_bootstrap_pareado.py --por-entrevista` (y con `--excluir-fuga` para la sensibilidad). Remuestrea entrevistas únicas por contenido (`grupos_por_entrevista`: el `id_registro` de cada segmento, con los 17 pares de texto idéntico unidos en un solo grupo; lee la BD) en lugar de segmentos. Escribe `outputs/bootstrap_resultados_por_entrevista{,_sin_fuga}.csv` y su figura, con la columna adicional `n_entrevistas` (30 en n = 177; 25 en n = 157). El remuestreo por segmento queda como comparación; sin la opción, el script reproduce exactamente sus salidas anteriores.

---

## `15_analisis_errores.py`

**Qué hace:** combina las predicciones de los modelos (baseline, BETO, BERTIN/RoBERTa-es) con los metadatos del corpus para responder tres preguntas de análisis de errores:
- **(a)** ¿En qué categorías temáticas se concentran los errores de cada modelo, y difiere esa concentración entre Condición A y B?
- **(b)** Dentro de los errores de la clase `negativo`, ¿se concentran en alguna naturaleza específica (`pedagogico` / `institucional_logistico` / `afectivo_momentaneo`)?
- **(c)** Casos donde la predicción cambia entre condiciones para el mismo `id_segmento` (correcto en B, incorrecto en A, o viceversa) — el diagnóstico más directo del efecto de la gobernanza, caso por caso, con el texto real.

**Requisitos previos:**
- `outputs/bootstrap_input/` ya organizado con los CSV de predicciones (ver `14_bootstrap_pareado.py`).
- Acceso a la base de datos local (usa la columna `naturaleza_negativo` de `segmento_retroalimentacion`).

**Salidas** (`outputs/`):
- `errores_por_categoria.csv`
- `errores_negativo_por_naturaleza.csv`
- `casos_que_cambian_entre_condiciones.csv`
- `flips_por_clase_defecto.csv` y `casos_que_cambian_con_clase_defecto.csv`: sección (d), flips según si el texto es idéntico entre A y B (comparación directa del texto desde 2026-10-08, `96f2b5f`).

**Uso:**
```
python scripts/15_analisis_errores.py
```

---

## `16_generar_graficos.py`

**Qué hace:** genera las 3 figuras del reporte metodológico a partir de los CSV reales guardados por los scripts de entrenamiento — no usa ningún número transcrito manualmente.

**Estructura de carpetas esperada** (ajustar ruta si difiere):
```
outputs/graficos_input/
  baseline/
    resultados_baseline.csv       (generado por 11_entrenar_baseline.py; ya está en outputs/, solo copiar)
    matriz_confusion_A.csv
    matriz_confusion_B.csv
  beto/
    resultado_A.csv                (descargar de Drive: resultados_colab/beto/)
    resultado_B.csv
    matriz_confusion_A.csv
    matriz_confusion_B.csv
    kfold_epocas_A.csv
    kfold_epocas_B.csv
  beto_sin_finetuning/
    resultado_A.csv                (descargar de Drive: resultados_colab/beto_sin_finetuning/)
    resultado_B.csv
    matriz_confusion_A.csv
    matriz_confusion_B.csv
  roberta_es/
    resultado_A.csv                (descargar de Drive: resultados_colab/roberta_es/)
    resultado_B.csv
    matriz_confusion_A.csv
    matriz_confusion_B.csv
    kfold_epocas_A.csv
    kfold_epocas_B.csv
```

**Salidas** (`outputs/`):
- `01_metricas_por_configuracion.png`
- `02_matrices_confusion.png` (una fila por modelo, sujeto a qué carpetas existan)
- `03_curvas_kfold_epocas.png` (solo BETO y RoBERTa-es, que son los que tienen k-fold)

Los insumos de `outputs/graficos_input/` los organiza `13b_preparar_insumos_validacion.py`. Regeneradas el 2026-10-08: valores idénticos a las figuras del 2026-08-21.

**Uso:**
```
python scripts/16_generar_graficos.py
```

---

## `14b_bootstrap_multisemilla.py`

**Qué hace:** ejecuta el plan de análisis multisemilla fijado el 2026-10-08: bootstrap pareado por semilla (reutiliza el del 14), agregado descriptivo con prueba de signos, bootstrap de dos niveles (semillas y casos), Holm y criterio de robustez. Análisis de sensibilidad exploratorio.

**Insumos:** `resultados_colab/{beto,roberta_es}/multisemilla/` (predicciones por semilla y `detalle_multisemilla.csv`) y `outputs/bootstrap_resultados.csv` (corrida principal, solo como referencia).

**Salidas** (`outputs/multisemilla/`): `bootstrap_por_semilla.csv`, `agregado_por_modelo.csv`, `holm_configuraciones_principales.csv`, `descriptivo_logloss_prauc.csv` y `manifiesto_insumos_multisemilla.csv`.

**Uso** (después del 14):
```
python scripts/14b_bootstrap_multisemilla.py --origen-colab "<ruta a resultados_colab>"
```

**Sensibilidad a la fuga:** `python scripts/14_bootstrap_pareado.py --excluir-fuga` y después `python scripts/14b_bootstrap_multisemilla.py --origen-colab "<ruta>" --excluir-fuga`. Excluyen los 22 segmentos de `IDS_FUGA` y escriben en `outputs/bootstrap_resultados_sin_fuga.csv`, `outputs/bootstrap_distribuciones_sin_fuga.png` y `outputs/multisemilla_sin_fuga/`, sin tocar las salidas principales.

**Por entrevista:** con `--por-entrevista` (después de `14 --por-entrevista`), el bootstrap por semilla y el segundo nivel del bootstrap de dos niveles remuestrean entrevistas; escribe en `outputs/multisemilla_por_entrevista{,_sin_fuga}/`.

---

## `17_figuras_trazables.py`

**Qué hace:** genera la figura de sensibilidad a la semilla y la tabla de calidad estructural, y escribe el manifiesto de todas las figuras y tablas del documento (script, commit y huellas SHA-256 de insumos y salida). Verifica que los insumos de 14 y 16 coincidan con `manifiesto_insumos.csv`.

**Salidas** (`outputs/`): `sensibilidad_semilla.png`, `tabla_calidad_estructural.csv` (desde `comparativa_calidad.csv` del 2026-05-19, anterior a la imputación de fechas) y `manifiesto_figuras.csv`.

**Uso** (al final, después de 14, 14b y 16):
```
python scripts/17_figuras_trazables.py
```

---

## `18_anexos_esquema_general.py`

**Qué hace:** genera en `docs/anexos/` los cinco anexos de la tesis (Markdown y CSV) desde sus fuentes, sin transcribir cifras. Numeración fijada el 2026-10-09 (sin cronograma; difiere del Esquema General):

| Anexo | Archivo | Fuentes |
|---|---|---|
| A. Diccionario de datos (versión liviana) | `anexo_A_diccionario_datos*` | `information_schema`, `SHOW CREATE TABLE`, sentencias CREATE TABLE del respaldo del 2026-08-31 (no los datos), `Fase2_Metadatos_Minimos.docx` |
| B. Prompts de la API de Claude | `anexo_B_prompts_api*` | Código de 04, 07, 08 y 09_reetiquetar_positivos (con `ast`) e historial de Git de esos archivos |
| C. Reglas de calidad (antes D) | `anexo_C_reglas_calidad*` | Código de 01, 02, 04, 07, 09 y 09a, BD, `Working_Paper_Marco_Gobernado_v1.docx` |
| D. Código y repositorio | `anexo_D_codigo_repositorio*` | Tabla "Orden de ejecución" de esta guía, docstrings, etiqueta citable `v1.2-anexos-2026-10`, requisitos y `registro_entorno_colab.md` |
| E. Resultados complementarios | `anexo_E_resultados*` | Matrices de confusión de `graficos_input/` y salidas de 14, 14b y 15 |

Borra los `anexo_*` anteriores antes de escribir. Los nombres de programa y los nombres propios que aparezcan en los prompts se reemplazan por una marca (`tools/terminos_privacidad.py`). No editar los anexos a mano.

**Uso** (al final, después de 14 y 14b con y sin `--excluir-fuga`, y de 15):
```
python scripts/18_anexos_esquema_general.py
```

---

## `19_auditoria_privacidad.py`

**Qué hace:** recorre todas las versiones de todos los archivos del historial de Git (ramas y etiquetas locales y remotas), las rutas, los mensajes de commit y de etiqueta y los objetos inalcanzables, y busca nombres propios, nombres de archivo de audio, nombres de institución educativa, nombres de sesión y de programa y texto de estudiantes. Los términos se derivan en tiempo de ejecución de la BD y de los CSV del corpus (`tools/terminos_privacidad.py`) y nunca se escriben: el reporte da archivo, commit, tipo de hallazgo y número de términos, sin reproducirlos. Solo lectura; no modifica el historial.

**Salidas:** `docs/auditoria_privacidad.md` y `docs/auditoria_privacidad.csv`.

**Uso:**
```
python scripts/19_auditoria_privacidad.py
```

---

## [siguiente script a documentar aquí, mismo formato]
