# Gobernanza de datos y análisis de sentimiento en retroalimentación estudiantil

Código del working paper de la Maestría en Analítica y Gerencia de Datos (Universidad Sergio
Arboleda) sobre el efecto de un marco de gobernanza de datos en la calidad de un corpus de
retroalimentación estudiantil y en el desempeño de modelos de análisis de sentimiento.
El diseño compara dos condiciones construidas sobre el mismo corpus: una parcialmente
gobernada (B) y una degradada de forma controlada (A).

## Contenido

| Carpeta | Qué contiene |
|---|---|
| `scripts/` | Flujo completo, numerado en orden de ejecución (00 a 19); `colab/` contiene el entrenamiento de BETO y BERTIN en GPU |
| `config/` | Conexión a la base de datos MySQL (lee las credenciales de un `.env` que no se publica) |
| `tools/` | Utilidades de verificación |
| `docs/` | Guía operativa de los scripts, bitácora de la auditoría del código y tablas complementarias |
| `crear_tablas.sql` | Esquema de la base de datos (sin datos) |

El inventario de scripts, su orden de ejecución y sus insumos y salidas están en
`docs/guia_operativa_scripts.md`.

## Datos

Los datos no se publican. El corpus está formado por entrevistas a estudiantes menores de
edad, y ni las transcripciones ni los datos derivados de ellas (segmentos, etiquetas,
predicciones) forman parte de este repositorio. Por eso el código documenta el proceso, pero
no puede ejecutarse sin acceso a la base de datos original.

## Versión pública

Este repositorio es una copia del estado final del repositorio de trabajo, publicada sin su
historial de cambios. En la copia, los nombres de programa, de sesión y de lugar que
aparecían en el código y en la documentación se reemplazaron por marcadores
(`[PROGRAMA]`, `[PROGRAMA_1]`, `[PROGRAMA_2]`, `[SESION]`, `[LUGAR_O_NOMBRE]`). Esos valores solo afectan a la lectura de
las rutas de los archivos de audio, a un nombre de columna y al texto de los prompts; la lógica
del flujo es la misma. Se omitieron además las notas internas de trabajo de la auditoría,
y las referencias a ellas se reemplazaron por la fecha de la decisión correspondiente. Los
identificadores de commit que citan los documentos de `docs/` remiten al historial del
repositorio de trabajo, que no se publica.

## Entorno

Python 3.12. Las versiones exactas de las dependencias locales están en
`requirements-local.lock.txt`; el entrenamiento en Colab y sus versiones se describen en
`docs/registro_entorno_colab.md`.
