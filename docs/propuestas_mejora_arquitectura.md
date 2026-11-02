# Propuestas de mejora de arquitectura

Propuestas registradas para evaluación. **Ninguna está aplicada.** Cada una requiere
acuerdo explícito antes de ejecutarse.

## Esquema de la base de datos

### 1. Restricciones equivalentes para `segmento_retroalimentacion` (2026-10-08)

El script 13 cerró la brecha entre gobernanza declarada e implementada solo en
`retroalimentacion` (ver `docs/cambios_agosto_2026.md`, sección 5). El corpus de
análisis (799 segmentos activos) está en `segmento_retroalimentacion`, que no tiene
restricciones `CHECK` equivalentes. Por ejemplo, ninguna regla de esquema impide un
`texto_segmento` vacío o una `etiqueta_sentimiento` fuera del catálogo de cinco clases.

Antes de proponer sentencias concretas habría que:
- Definir qué reglas RQ aplican a un segmento (no todas las de registro aplican).
- Contar con `SELECT` cuántos segmentos actuales violarían cada una.
- Confirmar que ninguna escritura del pipeline (scripts 07, 09, 09a) dependa de valores
  que la restricción prohibiría.

### 2. Umbral de longitud de texto: 5 frente a 20 caracteres (2026-10-08)

Precisión del 2026-10-09: el 5 replica RQ-01 de los cargadores de B (01 y 02); ver
`docs/cambios_agosto_2026.md`, §21 y el Anexo C (umbrales de longitud).

`chk_texto_longitud` exige `CHAR_LENGTH(texto) >= 5`, pero la regla implementada en la
capa de aplicación (RQ-09, `09a_procesar_condicion_a.py`) usa 20 caracteres, y RQ-01
solo exige texto no vacío. El umbral de 5 no corresponde a ninguna regla documentada.
Opciones:
- Alinear la restricción con RQ-09 (20 caracteres), tras contar violaciones.
- Mantener 5 y documentarlo como un piso técnico distinto de RQ-09.

En ambos casos hay que declararlo en el Reporte Metodológico.

## Código

### 9. Leer `condicion_A.csv` sin convertir `n/a` en nulo (2026-10-09)

`09a_procesar_condicion_a.py` lee `condicion_A.csv` con `pd.read_csv` por defecto, que
convierte el canal inválido `"n/a"` en nulo; 4 violaciones de RQ-06 quedaron registradas
como RQ-04. Propuesta: leer con `keep_default_na=False, na_values=[""]`, o retirar `"n/a"`
del catálogo de canales inválidos del 05. No se aplica: cambiaría `detalle_error`, que es
evidencia de lo ejecutado.

### 10. Ampliar la búsqueda de épocas (2026-10-09)

La época elegida por el k-fold fue la 4, igual al tope `EPOCAS_MAX = 4`, en los cuatro
casos. Para un trabajo futuro: ampliar el tope (por ejemplo, a 8) o usar parada temprana
con validación. Requiere reentrenar en Colab.


### 3. Desacoplar `colab/beto_sin_finetuning.py` de `colab/entrenar_beto.py`

`beto_sin_finetuning.py` importa funciones de un script ejecutable. Propuesta: extraer
las funciones comunes (carga de datos, métricas, utilidades de tokenización) a un
módulo compartido que importen ambos scripts.

### 4. Colisión de numeración de los scripts `09_`

Hay tres scripts con prefijo `09_` más `09a` y `09b`. No se renumeran, porque rompería
las referencias del Reporte Metodológico. El orden real de ejecución se documentará en
la sección "Orden de ejecución" de `docs/guia_operativa_scripts.md` (Fase 5).

### 5. Salida descriptiva en los scripts multisemilla (2026-10-08)

`colab/entrenar_beto_multisemilla.py` y `colab/entrenar_roberta_multisemilla.py`
imprimen al final un bloque `DIAGNOSTICO` con conclusiones escritas de antemano según el
signo de las diferencias (por ejemplo, "respalda tratar el resultado de BERTIN como un
hallazgo arquitectónico legítimo" o "respalda reportar BERTIN como NO CONCLUYENTE").
Propuesta: reemplazarlo por una salida descriptiva, sin interpretación: conteo de
semillas con B > A y con B < A, media y desviación estándar de la diferencia. La
interpretación corresponde al análisis y al texto del reporte, no al script. Como son
versiones ejecutadas, el cambio iría en un commit propio y no altera los resultados ya
generados.

### 6. Docstrings de los scripts multisemilla con interpretaciones previas (2026-10-08)

Los docstrings de `colab/entrenar_beto_multisemilla.py` y
`colab/entrenar_roberta_multisemilla.py` afirman como hechos interpretaciones escritas
antes del análisis multisemilla. Por ejemplo, que el resultado original de BETO "SÍ
reflejaba una señal real y estable" o que el protocolo "revirtió" el resultado de
BERTIN. El análisis del plan del 2026-10-08 no las confirma: ningún modelo superó el
criterio de robustez a la semilla. Propuesta: reescribirlos como descripción del diseño
(qué se varía, qué se fija, qué se guarda), sin conclusiones, en un commit propio. Son
versiones ejecutadas: el cambio sería solo de documentación, verificado con
`tools/verificar_equivalencia.py`. Mientras tanto, la guía operativa lo advierte.

### 11. Deduplicar por texto en la carga de B y segmentar el texto completo (2026-10-09)

Aplicar a la Condición B la detección de duplicados por texto (RQ-07) y eliminar el
truncamiento a 4.000 caracteres del script 07. Ambos cambios alteran el corpus y exigen
rehacer la segmentación, el etiquetado y los entrenamientos: solo para un trabajo futuro.

## Entorno

### 7. `requirements-colab.txt` con versiones fijadas

Fijar las versiones de `torch`, `transformers` y `datasets` usadas en Colab. Las
versiones de los entrenamientos originales no se registraron: es una limitación que
debe declararse, y las versiones que se fijen ahora no garantizan reproducir esos
entrenamientos.

### 8. Declarar `scipy` explícitamente (resuelto)

Declarada en `requirements-local.txt` el 2026-10-08 (`e87beaa`).

## Métricas del bootstrap (resuelto)

La propuesta de reemplazar `potencia_retrospectiva` por un análisis de efecto mínimo
detectable se aprobó el 2026-10-07 (`ee_bootstrap` y `emd_80`). Se mantiene aquí como antecedente.
