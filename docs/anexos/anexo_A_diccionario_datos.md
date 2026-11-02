# Anexo A — Diccionario de datos (versión liviana)
> Tablas retroalimentacion, segmento_retroalimentacion, segmento_condicion_a, ejecucion_pipeline y detalle_error: tipo, nulos, descripción, regla asociada y cambios del 2026-08-31.
> Generado por `scripts/18_anexos_esquema_general.py`. No editar a mano.

## Columnas
Filas el 2026-10-09: `retroalimentacion` 211, `segmento_retroalimentacion` 821, `segmento_condicion_a` 862, `ejecucion_pipeline` 3, `detalle_error` 201.

Tipo, nulos y clave de `information_schema`; nulos observados por consulta. Descripción de `Fase2_Metadatos_Minimos.docx` (metadatos M-01 a M-07) cuando existe; si no, declarada en el script 18. Cambio del 2026-08-31: comparación de cada columna con la sentencia CREATE TABLE del respaldo `backup_antes_constraints_20260831_2324.sql` (script 13); se leen solo las sentencias de esquema, no los datos. Regla de calidad: "impl." es el catálogo implementado en 09a y "diseño" el catálogo de 11 reglas (Anexo C). El 09a validó los documentos de la Condición A; la carga de B solo aplicó el filtro de menos de 5 caracteres (matriz regla × corpus del Anexo C).

| tabla | columna | tipo | admite_nulos | clave | nulos_observados | descripcion | fuente_descripcion | regla_calidad | cambio_2026_08_31 |
|---|---|---|---|---|---|---|---|---|---|
| retroalimentacion | id_registro | int | no | PRI | 0 | M-01 Identificador único: Permite referenciar, auditar y vincular cada registro de forma unívoca a lo largo de todo el ciclo de vida del dato. | Fase2_Metadatos_Minimos.docx | — | no |
| retroalimentacion | texto | text | no |  | 0 | M-02 Retroalimentación textual: Es el objeto de análisis central. Sin él el registro no tiene valor analítico ni puede alimentar ningún modelo de NLP. | Fase2_Metadatos_Minimos.docx | impl. RQ-01, RQ-07, RQ-08, RQ-09; diseño RQ-01, RQ-08, RQ-09, RQ-10 | sí: CHECK nuevo chk_texto_longitud |
| retroalimentacion | id_sesion | int | no | MUL | 0 | M-03 Identificador de sesión: Contextualiza el comentario dentro de una sesión académica específica. Habilita análisis longitudinales y comparación entre cohortes. | Fase2_Metadatos_Minimos.docx | impl. RQ-02; diseño RQ-02 | sí: int DEFAULT NULL → int NOT NULL |
| retroalimentacion | fecha_registro | date | no |  | 0 | M-04 Fecha de registro: Permite ordenar los comentarios en el tiempo, construir series temporales y detectar variaciones en la experiencia estudiantil por período. | Fase2_Metadatos_Minimos.docx | impl. RQ-03, RQ-05; diseño RQ-03, RQ-05 | sí: date DEFAULT NULL → date NOT NULL |
| retroalimentacion | canal_captura | varchar(50) | no |  | 0 | M-05 Canal de captura: Permite estratificar el análisis por medio de recolección (formulario, papel, app, email). Controla el sesgo de canal en el corpus. | Fase2_Metadatos_Minimos.docx | impl. RQ-04, RQ-06; diseño RQ-04, RQ-06 | sí: varchar(50) DEFAULT NULL → varchar(50) NOT NULL; CHECK nuevo chk_canal_catalogo |
| retroalimentacion | ingesta_timestamp | timestamp | sí |  | 0 | M-06 Marca temporal de ingesta: Registra cuándo entró el dato al sistema de gobernanza. Componente esencial de trazabilidad: permite reconstruir el historial de procesamiento. | Fase2_Metadatos_Minimos.docx | — | no |
| retroalimentacion | id_ejecucion | int | sí | MUL | 0 | M-07 Identificador de ejecución: Vincula cada registro a la ejecución del pipeline que lo procesó. Permite auditar qué reglas se aplicaron, cuántos errores se detectaron y el estado final de la ejecución. | Fase2_Metadatos_Minimos.docx | diseño RQ-11 (no implementada) | no |
| retroalimentacion | duracion_segundos | int | sí |  | 0 | Duración del audio de la entrevista, en segundos (02). | script 18 | — | no |
| retroalimentacion | etiqueta_sentimiento | varchar(20) | sí |  | 211 | Etiqueta a nivel de documento; sin uso (el etiquetado es por segmento). | script 18 | diseño RQ-07 (no implementada) | no |
| retroalimentacion | confianza_etiqueta | varchar(10) | sí |  | 211 | Confianza de la etiqueta de documento; sin uso. | script 18 | — | no |
| retroalimentacion | justificacion_etiqueta | text | sí |  | 211 | Justificación de la etiqueta de documento; sin uso. | script 18 | — | no |
| segmento_retroalimentacion | id_segmento | int | no | PRI | 0 | Identificador del segmento (PK). | script 18 | — | no |
| segmento_retroalimentacion | id_registro | int | no | MUL | 0 | Entrevista de origen (FK a retroalimentacion). | script 18 | — | no |
| segmento_retroalimentacion | categoria | varchar(50) | no |  | 0 | Categoría temática asignada al segmentar (07). | script 18 | — | no |
| segmento_retroalimentacion | texto_segmento | text | no |  | 0 | Texto del segmento devuelto por la API (07). | script 18 | — | no |
| segmento_retroalimentacion | inicio_seg | float | sí |  | 821 | Inicio del segmento en el audio; sin uso con la segmentación por API. | script 18 | — | no |
| segmento_retroalimentacion | fin_seg | float | sí |  | 821 | Fin del segmento en el audio; sin uso con la segmentación por API. | script 18 | — | no |
| segmento_retroalimentacion | etiqueta_sentimiento | varchar(20) | sí |  | 0 | Etiqueta de sentimiento de 5 clases: verdad de referencia (04, 09_reetiquetar_positivos, 09_cargar_revision_manual). | script 18 | diseño RQ-07 (no implementada) | no |
| segmento_retroalimentacion | confianza_etiqueta | varchar(10) | sí |  | 0 | Confianza declarada por el modelo de lenguaje al etiquetar (04). | script 18 | — | no |
| segmento_retroalimentacion | justificacion_etiqueta | text | sí |  | 0 | Justificación del modelo de lenguaje al etiquetar (04). | script 18 | — | no |
| segmento_retroalimentacion | metodo_segmentacion | varchar(20) | sí |  | 0 | Método de segmentación (07). | script 18 | — | no |
| segmento_retroalimentacion | flag_excluir | tinyint(1) | sí |  | 0 | 1 si la revisión manual excluyó el segmento (09_cargar_revision_manual). | script 18 | — | no |
| segmento_retroalimentacion | naturaleza_negativo | varchar(40) | sí |  | 786 | Subtipo de los segmentos negativos, según la revisión manual. | script 18 | — | no |
| segmento_retroalimentacion | justificacion_revision_v2 | text | sí |  | 819 | Justificación del cambio en la revisión manual. | script 18 | — | no |
| segmento_retroalimentacion | fecha_revision_v2 | timestamp | sí |  | 811 | Fecha del cambio en la revisión manual. | script 18 | — | no |
| segmento_condicion_a | id_segmento_a | int | no | PRI | 0 | Identificador del segmento de la Condición A (PK). | script 18 | — | no |
| segmento_condicion_a | id_segmento_origen | int | no | MUL | 0 | Segmento de B del que proviene (FK a segmento_retroalimentacion). | script 18 | — | no |
| segmento_condicion_a | id_registro | int | sí |  | 120 | Entrevista de origen. El defecto nulo_id_sesion se inyecta anulando esta columna (la tabla no tiene id_sesion); las filas duplicado_exacto copian el valor nulo del original (09_construir_condicion_a_segmentos). | script 18 | — | no |
| segmento_condicion_a | categoria | varchar(50) | sí |  | 0 | Categoría temática copiada del segmento de origen. | script 18 | — | no |
| segmento_condicion_a | texto_segmento | text | sí |  | 44 | Texto del segmento, alterado si el defecto es nulo_texto, texto_no_informativo o cuasi_duplicado; las filas duplicado_exacto copian el texto (o el nulo) del original. | script 18 | — | no |
| segmento_condicion_a | fecha_registro | varchar(50) | sí |  | 71 | Fecha como texto libre, con defectos de nulo o formato inyectados. | script 18 | — | no |
| segmento_condicion_a | canal_captura | varchar(50) | sí |  | 89 | Canal con defectos de nulo o fuera de catálogo inyectados. | script 18 | — | no |
| segmento_condicion_a | etiqueta_sentimiento | varchar(20) | sí |  | 0 | Etiqueta copiada del segmento de origen (idéntica en A y B). | script 18 | — | no |
| segmento_condicion_a | tipo_error_inyectado | varchar(150) | sí |  | 336 | Defectos inyectados, separados por coma; nulo si la fila no tiene defectos. | script 18 | defectos que las reglas impl. RQ-01 a RQ-09 detectarían en documentos | no |
| ejecucion_pipeline | id_ejecucion | int | no | PRI | 0 | Identificador de la ejecución (PK). | script 18 | — | no |
| ejecucion_pipeline | inicio | timestamp | no |  | 0 | Inicio de la ejecución. | script 18 | — | no |
| ejecucion_pipeline | fin | timestamp | sí |  | 1 | Fin de la ejecución; nulo si no terminó. | script 18 | — | no |
| ejecucion_pipeline | estado | varchar(50) | no |  | 0 | en_proceso, completado o fallido (CHECK chk_estado). | script 18 | — | no |
| ejecucion_pipeline | registros_procesados | int | sí |  | 0 | Registros leídos por la ejecución. | script 18 | — | no |
| ejecucion_pipeline | registros_rechazados | int | sí |  | 0 | Registros rechazados por las reglas de calidad. | script 18 | — | no |
| detalle_error | id_error | int | no | PRI | 0 | Identificador de la violación (PK). | script 18 | — | no |
| detalle_error | id_registro | int | sí |  | 201 | Registro afectado; nulo porque los rechazados no se insertan. | script 18 | — | no |
| detalle_error | id_ejecucion | int | no | MUL | 0 | Ejecución que detectó la violación (FK). | script 18 | — | no |
| detalle_error | codigo_regla | varchar(20) | no |  | 0 | Código de la regla violada (catálogo implementado, Anexo C). | script 18 | registra RQ-01 a RQ-09 (impl.) | no |
| detalle_error | descripcion | text | no |  | 0 | Descripción de la regla violada. | script 18 | — | no |
| detalle_error | valor_recibido | text | sí |  | 0 | Valor que violó la regla. | script 18 | — | no |
| detalle_error | timestamp_error | timestamp | sí |  | 0 | Momento de la detección. | script 18 | — | no |

CSV: `anexo_A_diccionario_datos_columnas.csv`
