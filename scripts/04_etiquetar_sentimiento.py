"""Etiqueta los segmentos con una escala de intensidad emocional de 5 niveles.

Asigna la etiqueta de sentimiento de cada segmento de retroalimentación con un
modelo de lenguaje de Claude, genera un reporte de distribución de etiquetas y,
opcionalmente, guarda los resultados en la base de datos.

Entradas:
    Tabla segmento_retroalimentacion; API de Anthropic.
Salidas:
    outputs/etiquetas_{test,cargar}_<timestamp>.csv; opcionalmente,
    actualización de las etiquetas en segmento_retroalimentacion.
"""

import sys, os, json, time, argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from config.db_connection import get_engine, get_connection

# --- CONFIGURACIÓN ---

MODELO        = "claude-haiku-4-5"
MAX_TOKENS    = 150
PAUSA_SEG     = 0.3   # pausa entre llamadas para evitar rate limit
CATEGORIAS_EXCLUIR = ["general"]

ETIQUETAS = {
    "5": "muy_positivo",
    "4": "positivo",
    "3": "neutral",
    "2": "negativo",
    "1": "muy_negativo",
}

SYSTEM_PROMPT = """Eres un experto en análisis de sentimiento educativo en español colombiano.
Tu tarea es etiquetar fragmentos de entrevistas con estudiantes sobre su experiencia 
en sesiones académicas de un programa llamado [PROGRAMA].

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

Donde N es el número del 1 al 5. Sin texto adicional, sin markdown."""

# --- ETIQUETADO ---

def etiquetar_segmento(cliente: anthropic.Anthropic,
                        texto: str,
                        categoria: str) -> dict:
    """Etiqueta un segmento de texto con su intensidad emocional mediante un modelo de lenguaje.

    Args:
        cliente (anthropic.Anthropic): Cliente de la API del modelo de lenguaje.
        texto (str): Fragmento de texto a etiquetar.
        categoria (str): Categoría temática del fragmento.

    Returns:
        dict: Etiqueta asignada, nivel de confianza, justificación y error si lo hubo.
    """
    prompt = (f"Categoría temática: {categoria}\n\n"
              f"Fragmento de entrevista estudiantil:\n{texto[:800]}")
    try:
        response = cliente.messages.create(
            model=MODELO,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Limpiar posibles markdown fences
        raw = raw.replace("```json","").replace("```","").strip()
        resultado = json.loads(raw)
        etiqueta_num = str(resultado.get("etiqueta","3"))
        return {
            "etiqueta_num"  : etiqueta_num,
            "etiqueta_label": ETIQUETAS.get(etiqueta_num, "neutral"),
            "confianza"     : resultado.get("confianza", "media"),
            "justificacion" : resultado.get("justificacion", "")[:300],
            "error"         : None,
        }
    except json.JSONDecodeError as e:
        return {"etiqueta_num": "3", "etiqueta_label": "neutral",
                "confianza": "baja", "justificacion": f"Error JSON: {str(e)[:100]}",
                "error": "json_error"}
    except Exception as e:
        return {"etiqueta_num": "3", "etiqueta_label": "neutral",
                "confianza": "baja", "justificacion": str(e)[:100],
                "error": str(type(e).__name__)}

# --- REPORTE ---

def imprimir_reporte(df_resultados: pd.DataFrame):
    """Imprime un resumen de la distribución de etiquetas y niveles de confianza asignados.

    Args:
        df_resultados (pandas.DataFrame): Resultados del etiquetado.

    Returns:
        None
    """
    from collections import Counter
    sep = "─"*60
    total = len(df_resultados)
    errores = df_resultados["error"].notna().sum()

    print(f"\n{sep}")
    print("  REPORTE DE ETIQUETADO — Paso 4")
    print(sep)
    print(f"  Segmentos etiquetados   : {total:>6}")
    print(f"  Errores de API          : {errores:>6}")

    print(f"\n  Distribución por etiqueta:")
    for et, n in sorted(df_resultados["etiqueta_label"].value_counts().items(),
                        key=lambda x: -x[1]):
        print(f"    {et:<20} {n:>5}  ({n/total*100:.1f}%)")

    print(f"\n  Distribución por confianza:")
    for c, n in df_resultados["confianza"].value_counts().items():
        print(f"    {c:<20} {n:>5}  ({n/total*100:.1f}%)")

    # Agrupado para modelo (3 clases)
    mapa_3 = {"muy_positivo":"positivo","positivo":"positivo",
               "neutral":"neutral","negativo":"negativo",
               "muy_negativo":"negativo"}
    df_resultados["etiqueta_3clases"] = df_resultados["etiqueta_label"].map(mapa_3)
    print(f"\n  Distribución agrupada (3 clases para modelo):")
    for et, n in df_resultados["etiqueta_3clases"].value_counts().items():
        print(f"    {et:<20} {n:>5}  ({n/total*100:.1f}%)")

    print(sep)

# --- CARGA A MYSQL ---

def cargar_etiquetas(df_resultados: pd.DataFrame):
    """Guarda las etiquetas asignadas en la base de datos.

    Args:
        df_resultados (pandas.DataFrame): Resultados del etiquetado.

    Returns:
        None
    """
    conn = get_connection()
    actualizados = 0
    try:
        with conn.cursor() as cur:
            for _, row in df_resultados.iterrows():
                if row.get("error"):
                    continue
                cur.execute("""
                    UPDATE segmento_retroalimentacion
                    SET etiqueta_sentimiento   = %s,
                        confianza_etiqueta     = %s,
                        justificacion_etiqueta = %s
                    WHERE id_segmento = %s
                """, (
                    row["etiqueta_label"],
                    row["confianza"],
                    row["justificacion"],
                    row["id_segmento"],
                ))
                actualizados += 1
        conn.commit()
        print(f"\n  Segmentos actualizados en MySQL: {actualizados}")
    except Exception as e:
        conn.rollback()
        print(f"\n  [ERROR] {e}"); raise
    finally:
        conn.close()

# --- MAIN ---

def main():
    """Ejecuta el flujo de etiquetado y carga a partir de argumentos de línea de comandos.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["test","cargar"], default="test",
                        help="test=10 segmentos sin BD | cargar=todo a MySQL")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY no encontrada en .env")
        sys.exit(1)

    cliente = anthropic.Anthropic(api_key=api_key)

    # Leer segmentos desde MySQL
    engine = get_engine()
    df = pd.read_sql("""
        SELECT id_segmento, id_registro, categoria, texto_segmento
        FROM segmento_retroalimentacion
        WHERE categoria NOT IN ('general')
        ORDER BY id_segmento
    """, engine)

    print(f"\nSegmentos a etiquetar: {len(df)}")

    if args.modo == "test":
        df = df.sample(min(10, len(df)), random_state=42)
        print(f"Modo TEST — procesando {len(df)} segmentos de muestra\n")
    else:
        print(f"Modo CARGAR — procesando {len(df)} segmentos\n")
        print(f"Costo estimado: ~${len(df)*0.0003:.2f} USD")
        print(f"Tiempo estimado: ~{len(df)*PAUSA_SEG/60:.1f} minutos\n")

    # Etiquetar
    resultados = []
    for i, (_, row) in enumerate(df.iterrows()):
        if i % 50 == 0:
            print(f"  Procesando {i+1}/{len(df)}...")

        resultado = etiquetar_segmento(cliente, row["texto_segmento"], row["categoria"])
        resultados.append({
            "id_segmento"   : row["id_segmento"],
            "id_registro"   : row["id_registro"],
            "categoria"     : row["categoria"],
            "texto_preview" : row["texto_segmento"][:100],
            **resultado,
        })
        time.sleep(PAUSA_SEG)

    df_resultados = pd.DataFrame(resultados)

    imprimir_reporte(df_resultados)

    # Guardar CSV de auditoría
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    csv_path = out / f"etiquetas_{args.modo}_{ts}.csv"
    df_resultados.to_csv(csv_path, index=False)
    print(f"\n  CSV de auditoría: {csv_path}")

    if args.modo == "test":
        print("\n  Muestra de etiquetas asignadas:")
        for _, r in df_resultados.head(5).iterrows():
            print(f"  [{r['etiqueta_label']:<15}] [{r['confianza']:<5}] "
                  f"{r['texto_preview'][:80]}...")
        print("\nSi el test se ve bien ejecuta con --modo cargar")
    else:
        cargar_etiquetas(df_resultados)

if __name__ == "__main__":
    main()