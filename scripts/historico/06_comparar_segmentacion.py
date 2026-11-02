"""
Compara la segmentación temática obtenida por palabras clave con la
obtenida mediante un modelo de lenguaje de Claude, sobre una muestra
representativa de entrevistas. Evalúa diferencias en número de
segmentos y en coincidencia de categorías, y genera un reporte y
archivos de comparación.
"""

import sys, os, json, time, argparse
from pathlib import Path
import pandas as pd
import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from config.db_connection import get_engine

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────

MODELO     = "claude-haiku-4-5"
MAX_TOKENS = 2000
PAUSA_SEG  = 0.5

CATEGORIAS = [
    "metodologia",
    "experiencia_docente",
    "aprendizaje",
    "impacto_emocional",
    "sugerencias"
]

SYSTEM_PROMPT = f"""Eres un experto en análisis de entrevistas educativas en español colombiano.
Tu tarea es segmentar y clasificar fragmentos de entrevistas con estudiantes sobre 
su experiencia en un programa educativo llamado [PROGRAMA].

CATEGORÍAS DISPONIBLES (solo puedes usar estas):
- metodologia: comentarios sobre el enfoque lúdico, didáctico, dinámicas, materiales
- experiencia_docente: trato del docente, evaluación, dominio de grupo, retroalimentación
- aprendizaje: contenidos aprendidos, habilidades, conexión con conocimiento previo
- impacto_emocional: emociones sentidas, seguridad, ansiedad, motivación, relaciones sociales
- sugerencias: críticas constructivas, propuestas de mejora, cambios sugeridos

INSTRUCCIONES:
1. Divide el texto en fragmentos temáticos coherentes
2. Ignora las partes del entrevistador (presentaciones, preguntas, consentimiento)
3. Solo incluye respuestas del estudiante con contenido real
4. Clasifica cada fragmento en UNA de las 5 categorías
5. Descarta fragmentos menores de 30 caracteres

Responde ÚNICAMENTE con un JSON con esta estructura exacta:
{{
  "segmentos": [
    {{
      "categoria": "nombre_categoria",
      "texto": "fragmento del estudiante",
      "justificacion": "por qué esta categoría en máximo 10 palabras"
    }}
  ]
}}

Sin texto adicional, sin markdown, sin explicaciones fuera del JSON."""

# ─────────────────────────────────────────────
# SEGMENTACIÓN CON CLAUDE API
# ─────────────────────────────────────────────

def segmentar_con_claude(cliente, texto: str, id_registro: int) -> list:
    """Segmenta y clasifica una entrevista en fragmentos temáticos mediante un modelo de lenguaje.

    Args:
        cliente: Cliente de la API del modelo de lenguaje.
        texto (str): Texto completo de la entrevista.
        id_registro (int): Identificador del registro al que pertenece la entrevista.

    Returns:
        list: Lista de segmentos válidos con su categoría, texto y justificación.
    """
    # Limitar texto para no exceder tokens
    texto_limitado = texto[:4000] if len(texto) > 4000 else texto

    try:
        response = cliente.messages.create(
            model=MODELO,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Entrevista a segmentar:\n\n{texto_limitado}"
            }]
        )
        raw = response.content[0].text.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        resultado = json.loads(raw)
        segmentos = resultado.get("segmentos", [])

        # Validar categorías
        segmentos_validos = []
        for s in segmentos:
            cat = s.get("categoria","").lower().strip()
            texto_seg = s.get("texto","").strip()
            if cat in CATEGORIAS and len(texto_seg) >= 30:
                segmentos_validos.append({
                    "id_registro"   : id_registro,
                    "categoria"     : cat,
                    "texto_segmento": texto_seg,
                    "justificacion" : s.get("justificacion","")[:200],
                    "fuente"        : "claude_api",
                })
        return segmentos_validos

    except json.JSONDecodeError as e:
        print(f"    Error JSON en registro {id_registro}: {str(e)[:80]}")
        return []
    except Exception as e:
        print(f"    Error API en registro {id_registro}: {str(e)[:80]}")
        return []

# ─────────────────────────────────────────────
# COMPARACIÓN
# ─────────────────────────────────────────────

def comparar_segmentaciones(df_keywords: pd.DataFrame,
                             df_claude: pd.DataFrame,
                             id_registro: int) -> dict:
    """Compara la segmentación por palabras clave con la del modelo de lenguaje para un registro.

    Args:
        df_keywords (pandas.DataFrame): Segmentos obtenidos por palabras clave.
        df_claude (pandas.DataFrame): Segmentos obtenidos por el modelo de lenguaje.
        id_registro (int): Identificador del registro a comparar.

    Returns:
        dict: Métricas de comparación entre ambos métodos para el registro.
    """
    kw   = df_keywords[df_keywords["id_registro"] == id_registro]
    api  = df_claude[df_claude["id_registro"] == id_registro]

    n_kw  = len(kw)
    n_api = len(api)

    # Distribución de categorías por método
    cats_kw  = kw["categoria"].value_counts().to_dict()
    cats_api = api["categoria"].value_counts().to_dict()

    # Coincidencia de categorías (qué categorías aparecen en ambos)
    set_kw  = set(cats_kw.keys())
    set_api = set(cats_api.keys())
    cats_comunes    = set_kw & set_api
    cats_solo_kw    = set_kw - set_api
    cats_solo_api   = set_api - set_kw

    # Ratio de coincidencia
    if set_kw | set_api:
        coincidencia = len(cats_comunes) / len(set_kw | set_api)
    else:
        coincidencia = 0.0

    return {
        "id_registro"       : id_registro,
        "n_segmentos_kw"    : n_kw,
        "n_segmentos_api"   : n_api,
        "diferencia_n"      : abs(n_kw - n_api),
        "cats_kw"           : str(cats_kw),
        "cats_api"          : str(cats_api),
        "cats_comunes"      : str(sorted(cats_comunes)),
        "cats_solo_keywords": str(sorted(cats_solo_kw)),
        "cats_solo_claude"  : str(sorted(cats_solo_api)),
        "coincidencia_cats" : round(coincidencia * 100, 1),
    }

# ─────────────────────────────────────────────
# REPORTE
# ─────────────────────────────────────────────

def imprimir_reporte(df_comparacion: pd.DataFrame,
                     df_kw: pd.DataFrame,
                     df_api: pd.DataFrame):
    """Imprime un resumen comparativo de ambos métodos de segmentación.

    Args:
        df_comparacion (pandas.DataFrame): Métricas de comparación por registro.
        df_kw (pandas.DataFrame): Segmentos obtenidos por palabras clave.
        df_api (pandas.DataFrame): Segmentos obtenidos por el modelo de lenguaje.

    Returns:
        None
    """
    sep = "─"*65
    print(f"\n{sep}")
    print("  COMPARACIÓN DE SEGMENTACIÓN: Palabras Clave vs Claude API")
    print(sep)

    n = len(df_comparacion)
    print(f"  Entrevistas comparadas          : {n}")
    print(f"\n  Segmentos totales por método:")
    print(f"    Palabras clave                : {df_kw['id_registro'].isin(df_comparacion['id_registro']).sum()} "
          f"→ {len(df_kw[df_kw['id_registro'].isin(df_comparacion['id_registro'])])}")
    print(f"    Claude API                    : {len(df_api)}")

    print(f"\n  Promedio de segmentos por entrevista:")
    print(f"    Palabras clave                : "
          f"{df_comparacion['n_segmentos_kw'].mean():.1f}")
    print(f"    Claude API                    : "
          f"{df_comparacion['n_segmentos_api'].mean():.1f}")

    print(f"\n  Coincidencia promedio de categorías : "
          f"{df_comparacion['coincidencia_cats'].mean():.1f}%")
    print(f"  Coincidencia mínima                 : "
          f"{df_comparacion['coincidencia_cats'].min():.1f}%")
    print(f"  Coincidencia máxima                 : "
          f"{df_comparacion['coincidencia_cats'].max():.1f}%")

    print(f"\n  Distribución de categorías — Palabras Clave:")
    for cat, n in df_kw[df_kw["id_registro"].isin(
            df_comparacion["id_registro"])]["categoria"].value_counts().items():
        print(f"    {cat:<25} {n:>4}")

    print(f"\n  Distribución de categorías — Claude API:")
    for cat, n in df_api["categoria"].value_counts().items():
        print(f"    {cat:<25} {n:>4}")

    print(f"\n  Detalle por entrevista:")
    print(f"  {'id_reg':>6} {'n_kw':>6} {'n_api':>6} "
          f"{'coincidencia':>14} {'cats_comunes'}")
    print(f"  {'':─>6} {'':─>6} {'':─>6} {'':─>14} {'':─>30}")
    for _, row in df_comparacion.iterrows():
        print(f"  {int(row['id_registro']):>6} "
              f"{int(row['n_segmentos_kw']):>6} "
              f"{int(row['n_segmentos_api']):>6} "
              f"{row['coincidencia_cats']:>13.1f}% "
              f"  {row['cats_comunes'][:40]}")
    print(sep)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    """Ejecuta el flujo de segmentación con modelo de lenguaje y comparación contra palabras clave.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10,
                        help="Número de entrevistas a comparar (default: 10)")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY no encontrada en .env"); sys.exit(1)

    cliente = anthropic.Anthropic(api_key=api_key)
    engine  = get_engine()

    # ── Leer segmentación existente (palabras clave) ──────
    print("\nLeyendo segmentación existente desde MySQL...")
    df_kw = pd.read_sql("""
        SELECT s.id_segmento, s.id_registro, s.categoria,
               s.texto_segmento, s.etiqueta_sentimiento
        FROM segmento_retroalimentacion s
        WHERE s.categoria != 'general'
    """, engine)
    print(f"  Segmentos en MySQL (palabras clave): {len(df_kw)}")

    # ── Seleccionar muestra representativa ───────────────
    df_retro = pd.read_sql("""
        SELECT r.id_registro, r.texto, r.id_sesion,
               s.nombre_sesion, r.canal_captura
        FROM retroalimentacion r
        LEFT JOIN sesion s ON r.id_sesion = s.id_sesion
        WHERE r.texto IS NOT NULL
        AND LENGTH(r.texto) > 200
    """, engine)

    # Estratificar: tomar muestra variada por sesión
    grupos = []
    for _, grupo in df_retro.groupby("id_sesion"):
        grupos.append(grupo.sample(min(1, len(grupo)), random_state=42))
    df_estratificado = pd.concat(grupos, ignore_index=True)
    muestra = df_estratificado.sample(
        min(args.n, len(df_estratificado)), random_state=42
    ).reset_index(drop=True)

    print(f"  Entrevistas seleccionadas para muestra: {len(muestra)}")
    print(f"  Sesiones representadas: "
          f"{muestra['nombre_sesion'].nunique()}")

    # ── Segmentar con Claude API ──────────────────────────
    print(f"\nSegmentando {len(muestra)} entrevistas con Claude API...")
    print(f"  Costo estimado: ~${len(muestra)*0.015:.2f} USD\n")

    segmentos_api = []
    for i, (_, row) in enumerate(muestra.iterrows()):
        print(f"  [{i+1}/{len(muestra)}] id_registro={int(row['id_registro'])} "
              f"| sesion={str(row['nombre_sesion'])[:40]}")
        segs = segmentar_con_claude(
            cliente,
            str(row["texto"]),
            int(row["id_registro"])
        )
        print(f"           → {len(segs)} segmentos generados")
        segmentos_api.extend(segs)
        time.sleep(PAUSA_SEG)

    df_api = pd.DataFrame(segmentos_api) if segmentos_api else pd.DataFrame(
        columns=["id_registro","categoria","texto_segmento",
                 "justificacion","fuente"])

    print(f"\n  Total segmentos Claude API: {len(df_api)}")

    # ── Comparar ──────────────────────────────────────────
    print("\nComparando segmentaciones...")
    comparaciones = []
    for id_reg in muestra["id_registro"].unique():
        comp = comparar_segmentaciones(df_kw, df_api, int(id_reg))
        comparaciones.append(comp)

    df_comp = pd.DataFrame(comparaciones)
    imprimir_reporte(df_comp, df_kw, df_api)

    # ── Guardar resultados ────────────────────────────────
    out = Path("outputs")
    out.mkdir(exist_ok=True)

    df_api.to_csv(out/"segmentos_claude_api.csv", index=False)
    df_comp.to_csv(out/"comparacion_segmentacion.csv", index=False)

    # CSV unificado para análisis lado a lado
    df_kw_muestra = df_kw[df_kw["id_registro"].isin(
        muestra["id_registro"])].copy()
    df_kw_muestra["fuente"] = "palabras_clave"
    df_api["fuente"] = "claude_api"

    cols = ["id_registro","categoria","texto_segmento","fuente"]
    df_lado_a_lado = pd.concat(
        [df_kw_muestra[cols], df_api[cols]], ignore_index=True
    ).sort_values(["id_registro","fuente"])
    df_lado_a_lado.to_csv(out/"comparacion_lado_a_lado.csv", index=False)

    print(f"\n  Archivos guardados:")
    print(f"      outputs/segmentos_claude_api.csv")
    print(f"      outputs/comparacion_segmentacion.csv")
    print(f"      outputs/comparacion_lado_a_lado.csv")
    print(f"\n  Abre comparacion_lado_a_lado.csv para revisar")
    print(f"  las diferencias entre métodos entrevista por entrevista.")

if __name__ == "__main__":
    main()