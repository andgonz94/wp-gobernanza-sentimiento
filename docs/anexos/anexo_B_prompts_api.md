# Anexo B — Prompts de la API de Claude
> Prompts literales, modelo y parámetros de los scripts 04, 07, 08 y 09_reetiquetar_positivos.
> Generado por `scripts/18_anexos_esquema_general.py`. No editar a mano.

## B.1 Parámetros de las llamadas
Extraído del código con `ast` (no transcrito). La API key no aparece en el código: se lee de `.env` con `os.getenv`, y este anexo no la incluye. Los nombres de programa y los nombres propios se reemplazan por una marca entre corchetes; los términos se obtienen en tiempo de ejecución de la tabla `sesion` y de los nombres de archivo de audio (`tools/terminos_privacidad.py`). Las frases de ejemplo del prompt de 09_reetiquetar_positivos son expresiones genéricas escritas en el prompt, sin identificadores. Historial: el texto del prompt, el modelo y `max_tokens` se comparan en todas las versiones de Git (columna `historial_prompt`).

**Nota sobre la versión ejecutada:** los prompts entraron al repositorio el 21 de agosto de 2026, después de su ejecución (mayo-junio de 2026; columna `evidencia_ejecucion`). No cambiaron en ninguna versión registrada, pero no hay registro del texto exacto usado en la ejecución.

| script | modelo | max_tokens | parametros_fijados | no_fijados | pausa_entre_llamadas_s | seleccion_entrada | preprocesamiento_entrada | llamada | evidencia_ejecucion | historial_prompt | marcas_privacidad |
|---|---|---|---|---|---|---|---|---|---|---|---|
| scripts/04_etiquetar_sentimiento.py | claude-haiku-4-5 | 150 | model=MODELO, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT | temperature, top_p, top_k, stop_sequences (valor por defecto de la API) | 0.3 | SELECT id_segmento, id_registro, categoria, texto_segmento FROM segmento_retroalimentacion WHERE categoria NOT IN ('general') ORDER BY id_segmento (línea 208) | texto[:800] | scripts/04_etiquetar_sentimiento.py:78 | outputs/etiquetas_cargar_20260519_1752.csv (2026-05-19 17:52) | sin cambios en 3 versiones (primera en Git: 788f4ff 2026-08-21) | nombre del programa |
| scripts/07_resegmentar_corpus_completo.py | claude-haiku-4-5 | 2000 | model=MODELO, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT | temperature, top_p, top_k, stop_sequences (valor por defecto de la API) | 0.5 | SELECT id_registro, texto FROM retroalimentacion WHERE texto IS NOT NULL AND LENGTH(texto) > 50 ORDER BY id_registro (línea 239) | texto_limitado = texto[:4000] if len(texto) > 4000 else texto | scripts/07_resegmentar_corpus_completo.py:88 | outputs/segmentos_claude_api_completo.csv (2026-05-19 17:25) | sin cambios en 3 versiones (primera en Git: 788f4ff 2026-08-21) | nombre del programa |
| scripts/08_data_augmentation.py | claude-haiku-4-5 | 1000 | model=MODELO, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT | temperature, top_p, top_k, stop_sequences (valor por defecto de la API) | 0.4 | SELECT id_segmento, id_registro, categoria, texto_segmento, etiqueta_sentimiento FROM segmento_retroalimentacion WHERE etiqueta_sentimiento IN ({placeholders}) AND flag_excluir = 0 ORDER BY etiqueta_sentimiento, id_segmento (línea 286) | texto[:600] | scripts/08_data_augmentation.py:82 | outputs/augmentation_variantes.csv (2026-06-02 10:47) | sin cambios en 3 versiones (primera en Git: 788f4ff 2026-08-21) | ninguna |
| scripts/09_reetiquetar_positivos.py | claude-haiku-4-5 | 200 | model=MODELO, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT | temperature, top_p, top_k, stop_sequences (valor por defecto de la API) | 0.3 | SELECT id_segmento, id_registro, categoria, texto_segmento, etiqueta_sentimiento, confianza_etiqueta FROM segmento_retroalimentacion WHERE etiqueta_sentimiento = 'positivo' ORDER BY id_segmento (línea 192) | texto[:600] | scripts/09_reetiquetar_positivos.py:67 | outputs/reetiquetado_positivos_20260519_2049.csv (2026-05-19 20:49) | sin cambios en 3 versiones (primera en Git: 788f4ff 2026-08-21) | ninguna |

CSV: `anexo_B_prompts_api_parametros.csv`

## B.2 04_etiquetar_sentimiento.py
Modelo `claude-haiku-4-5`, `max_tokens` = 150, llamada en `scripts/04_etiquetar_sentimiento.py:78`. No se fijan `temperature`, `top_p`, `top_k`, `stop_sequences`: rigen los valores por defecto de la API (temperatura 1,0), así que la respuesta no es determinista.

**Selección de la entrada:** `SELECT id_segmento, id_registro, categoria, texto_segmento FROM segmento_retroalimentacion WHERE categoria NOT IN ('general') ORDER BY id_segmento (línea 208)`.

**Preprocesamiento de la entrada:** `texto[:800]`.

**Parámetros del módulo:**
- `CATEGORIAS_EXCLUIR` = `['general']`
- `ETIQUETAS` = `{'5': 'muy_positivo', '4': 'positivo', '3': 'neutral', '2': 'negativo', '1': 'muy_negativo'}`

**Prompt de sistema** (literal):

```text
Eres un experto en análisis de sentimiento educativo en español colombiano.
Tu tarea es etiquetar fragmentos de entrevistas con estudiantes sobre su experiencia 
en sesiones académicas de un programa llamado [nombre del programa].

Escala de intensidad emocional:
5 = muy_positivo: entusiasmo fuerte, transformación personal, impacto significativo
4 = positivo: valoración favorable clara, satisfacción, aprendizaje positivo
3 = neutral: descriptivo sin valoración clara, ambiguo, mezcla equilibrada
2 = negativo: dificultad, insatisfacción moderada, crítica constructiva
1 = muy_negativo: rechazo claro, experiencia muy negativa, insatisfacción fuerte

Responde ÚNICAMENTE con un JSON con esta estructura exacta:
{
  "etiqueta": "N",
  "confianza": "alta|media|baja",
  "justificacion": "una frase corta explicando la decisión"
}

Donde N es el número del 1 al 5. Sin texto adicional, sin markdown.
```

**Mensaje de usuario** (plantilla literal; entre llaves, la expresión de Python que se sustituye):

```text
Categoría temática: {categoria}

Fragmento de entrevista estudiantil:
{texto[:800]}
```

**Formato de respuesta esperado:** el JSON que pide el prompt de sistema. **Tratamiento de la respuesta:** se eliminan las cercas ```json (scripts/04_etiquetar_sentimiento.py:86) y se lee con json.loads (scripts/04_etiquetar_sentimiento.py:87); etiqueta no reconocida → 'neutral' (scripts/04_etiquetar_sentimiento.py:91); error de JSON → 'neutral', confianza 'baja' (scripts/04_etiquetar_sentimiento.py:96); justificación truncada a 300 caracteres (scripts/04_etiquetar_sentimiento.py:93).

**Marcas de privacidad:** nombre del programa.

## B.3 07_resegmentar_corpus_completo.py
Modelo `claude-haiku-4-5`, `max_tokens` = 2000, llamada en `scripts/07_resegmentar_corpus_completo.py:88`. No se fijan `temperature`, `top_p`, `top_k`, `stop_sequences`: rigen los valores por defecto de la API (temperatura 1,0), así que la respuesta no es determinista.

**Selección de la entrada:** `SELECT id_registro, texto FROM retroalimentacion WHERE texto IS NOT NULL AND LENGTH(texto) > 50 ORDER BY id_registro (línea 239)`.

**Preprocesamiento de la entrada:** `texto_limitado = texto[:4000] if len(texto) > 4000 else texto`.

**Parámetros del módulo:**
- `CATEGORIAS` = `['metodologia', 'experiencia_docente', 'aprendizaje', 'impacto_emocional', 'sugerencias']`

**Prompt de sistema** (literal):

```text
Eres un experto en análisis de entrevistas educativas en español colombiano.
Tu tarea es segmentar y clasificar fragmentos de entrevistas con estudiantes sobre
su experiencia en un programa educativo llamado [nombre del programa].

CATEGORÍAS DISPONIBLES (solo puedes usar estas exactamente):
- metodologia: comentarios sobre el enfoque lúdico, didáctico, dinámicas, materiales
- experiencia_docente: trato del docente, evaluación, dominio de grupo, retroalimentación
- aprendizaje: contenidos aprendidos, habilidades, conexión con conocimiento previo
- impacto_emocional: emociones sentidas, seguridad, ansiedad, motivación, relaciones sociales
- sugerencias: críticas constructivas, propuestas de mejora, cambios sugeridos

INSTRUCCIONES:
1. Divide el texto en fragmentos temáticos coherentes
2. Ignora completamente las partes del entrevistador
   (presentaciones, preguntas, consentimiento informado, saludos)
3. Solo incluye respuestas del estudiante con contenido analítico real
4. Clasifica cada fragmento en UNA de las 5 categorías
5. Descarta fragmentos menores de 30 caracteres
6. Máximo 10 segmentos por entrevista — prioriza coherencia sobre granularidad

Responde ÚNICAMENTE con un JSON con esta estructura exacta:
{
  "segmentos": [
    {
      "categoria": "nombre_categoria",
      "texto": "fragmento del estudiante",
      "justificacion": "por qué esta categoría en máximo 10 palabras"
    }
  ]
}

Sin texto adicional, sin markdown, sin explicaciones fuera del JSON.
```

**Mensaje de usuario** (plantilla literal; entre llaves, la expresión de Python que se sustituye):

```text
Entrevista a segmentar:

{texto_limitado}
```

**Formato de respuesta esperado:** el JSON que pide el prompt de sistema. **Tratamiento de la respuesta:** se eliminan las cercas ```json (scripts/07_resegmentar_corpus_completo.py:98) y se lee con json.loads (scripts/07_resegmentar_corpus_completo.py:99); solo categorías del catálogo y fragmentos de 30 caracteres o más (scripts/07_resegmentar_corpus_completo.py:106); error de JSON o de API → ningún segmento para la entrevista (scripts/07_resegmentar_corpus_completo.py:120); el máximo de 10 segmentos solo se pide en el prompt; el código no lo verifica.

**Marcas de privacidad:** nombre del programa.

## B.4 08_data_augmentation.py
Modelo `claude-haiku-4-5`, `max_tokens` = 1000, llamada en `scripts/08_data_augmentation.py:82`. No se fijan `temperature`, `top_p`, `top_k`, `stop_sequences`: rigen los valores por defecto de la API (temperatura 1,0), así que la respuesta no es determinista.

**Selección de la entrada:** `SELECT id_segmento, id_registro, categoria, texto_segmento, etiqueta_sentimiento FROM segmento_retroalimentacion WHERE etiqueta_sentimiento IN ({placeholders}) AND flag_excluir = 0 ORDER BY etiqueta_sentimiento, id_segmento (línea 286)`.

**Preprocesamiento de la entrada:** `texto[:600]`.

**Parámetros del módulo:**
- `VARIANTES_POR_CLASE` = `{'negativo': 4, 'neutral': 2}`
- `SEMILLA` = `42`

**Prompt de sistema** (literal):

```text
Eres un experto en paráfrasis de texto educativo en español colombiano.
Tu tarea es generar variantes de fragmentos de entrevistas estudiantiles
manteniendo el MISMO sentido, emoción y registro coloquial del original.

REGLAS ESTRICTAS:
1. Mantén exactamente la misma emoción y sentimiento del original
2. Usa vocabulario similar al español colombiano coloquial
3. Cambia la estructura de las oraciones pero no el significado
4. No añadas información nueva que no esté en el original
5. Cada variante debe sonar natural, como diría un estudiante colombiano
6. Longitud similar al original (±30%)

Responde ÚNICAMENTE con un JSON con esta estructura:
{
  "variantes": [
    "primera variante del texto",
    "segunda variante del texto"
  ]
}

Sin texto adicional, sin markdown.
```

**Mensaje de usuario** (plantilla literal; entre llaves, la expresión de Python que se sustituye):

```text
Etiqueta de sentimiento: {etiqueta}

Texto original:
{texto[:600]}

Genera exactamente {n_variantes} variantes.
```

**Formato de respuesta esperado:** el JSON que pide el prompt de sistema. **Tratamiento de la respuesta:** se eliminan las cercas ```json (scripts/08_data_augmentation.py:88) y se lee con json.loads (scripts/08_data_augmentation.py:89); se descartan variantes de menos de 20 caracteres (scripts/08_data_augmentation.py:91); error → ninguna variante (scripts/08_data_augmentation.py:94).

**Marcas de privacidad:** ninguna.

## B.5 09_reetiquetar_positivos.py
Modelo `claude-haiku-4-5`, `max_tokens` = 200, llamada en `scripts/09_reetiquetar_positivos.py:67`. No se fijan `temperature`, `top_p`, `top_k`, `stop_sequences`: rigen los valores por defecto de la API (temperatura 1,0), así que la respuesta no es determinista.

**Selección de la entrada:** `SELECT id_segmento, id_registro, categoria, texto_segmento, etiqueta_sentimiento, confianza_etiqueta FROM segmento_retroalimentacion WHERE etiqueta_sentimiento = 'positivo' ORDER BY id_segmento (línea 192)`.

**Preprocesamiento de la entrada:** `texto[:600]`.

**Prompt de sistema** (literal):

```text
Eres un experto en análisis de sentimiento educativo en español colombiano.
Tu tarea es distinguir entre dos niveles de valoración positiva en comentarios de estudiantes:

DEFINICIONES OPERATIVAS:

positivo: Valoración favorable CLARA y SOSTENIDA. El estudiante expresa satisfacción 
genuina, aprendizaje real o experiencia buena sin reservas significativas.
Ejemplos: "me gustó mucho", "aprendí bastante", "estuvo muy chévere", 
"me parece muy bueno", "fue una experiencia increíble"

levemente_positivo: Valoración favorable TIBIA, CONDICIONADA o con RESERVAS implícitas.
El estudiante valora positivamente pero con moderación, dudas o matices que reducen 
la intensidad.
Ejemplos: "estuvo bien", "más o menos chévere", "no estuvo mal", 
"fue okay", "algo aprendí", "pues sí, estuvo bien supongo"

CRITERIO DE DESEMPATE: Si el texto tiene más elementos de satisfacción clara → positivo.
Si tiene reservas, dudas o lenguaje moderado → levemente_positivo.

Responde ÚNICAMENTE con JSON:
{
  "etiqueta": "positivo" o "levemente_positivo",
  "confianza": "alta" o "media" o "baja",
  "justificacion": "máximo 10 palabras explicando la decisión"
}
```

**Mensaje de usuario** (plantilla literal; entre llaves, la expresión de Python que se sustituye):

```text
Segmento a clasificar:
{texto[:600]}
```

**Formato de respuesta esperado:** el JSON que pide el prompt de sistema. **Tratamiento de la respuesta:** se eliminan las cercas ```json (scripts/09_reetiquetar_positivos.py:77) y se lee con json.loads (scripts/09_reetiquetar_positivos.py:78); etiqueta fuera de {positivo, levemente_positivo} → 'positivo' (scripts/09_reetiquetar_positivos.py:80); error → 'positivo', confianza 'baja' (scripts/09_reetiquetar_positivos.py:88); solo las reclasificaciones de confianza alta se escriben en la BD (scripts/09_reetiquetar_positivos.py:144).

**Marcas de privacidad:** ninguna.
