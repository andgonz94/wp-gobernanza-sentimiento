"""Reclasifica los segmentos positivos en dos niveles de intensidad.

Usa un modelo de lenguaje para la reclasificación. Actualiza automáticamente la
base de datos solo con las reclasificaciones de alta confianza y deja el resto
en un CSV para revisión manual.

Entradas:
    Tabla segmento_retroalimentacion; API de Anthropic.
Salidas:
    outputs/reetiquetado_positivos_<timestamp>.csv; actualización de
    segmento_retroalimentacion.
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

MODELO     = "claude-haiku-4-5"
MAX_TOKENS = 200
PAUSA_SEG  = 0.3

SYSTEM_PROMPT = """Eres un experto en análisis de sentimiento educativo en español colombiano.
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
}"""

def reclasificar_segmento(cliente, texto: str, id_segmento: int) -> dict:
    """Reclasifica un segmento positivo en uno de dos niveles de intensidad mediante un modelo de lenguaje.

    Args:
        cliente: Cliente de la API del modelo de lenguaje.
        texto (str): Texto del segmento a reclasificar.
        id_segmento (int): Identificador del segmento.

    Returns:
        dict: Nueva etiqueta, nivel de confianza, justificación y error si lo hubo.
    """
    try:
        response = cliente.messages.create(
            model=MODELO,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Segmento a clasificar:\n{texto[:600]}"
            }]
        )
        raw = response.content[0].text.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        resultado = json.loads(raw)
        etiqueta = resultado.get("etiqueta","positivo")
        if etiqueta not in ["positivo","levemente_positivo"]:
            etiqueta = "positivo"
        return {
            "etiqueta"     : etiqueta,
            "confianza"    : resultado.get("confianza","media"),
            "justificacion": resultado.get("justificacion","")[:200],
            "error"        : None,
        }
    except Exception as e:
        return {
            "etiqueta"     : "positivo",
            "confianza"    : "baja",
            "justificacion": f"Error: {str(e)[:80]}",
            "error"        : str(type(e).__name__),
        }

def imprimir_reporte(df_resultados: pd.DataFrame):
    """Imprime un resumen de la reclasificación, con distribución por etiqueta y confianza.

    Args:
        df_resultados (pandas.DataFrame): Resultados de la reclasificación.

    Returns:
        None
    """
    sep = "─"*60
    total = len(df_resultados)
    print(f"\n{sep}")
    print("  REPORTE DE RE-ETIQUETADO — Paso 9")
    print(sep)
    print(f"  Segmentos procesados      : {total}")
    print(f"  Errores de API            : "
          f"{df_resultados['error'].notna().sum()}")

    print(f"\n  Nueva distribución:")
    for et, n in df_resultados["etiqueta_nueva"].value_counts().items():
        print(f"    {et:<25} {n:>5}  ({n/total*100:.1f}%)")

    print(f"\n  Por confianza:")
    for c, n in df_resultados["confianza"].value_counts().items():
        print(f"    {c:<25} {n:>5}  ({n/total*100:.1f}%)")

    # Cuántos se actualizarían automáticamente vs revisión manual
    auto = df_resultados[df_resultados["confianza"] == "alta"]
    manual = df_resultados[df_resultados["confianza"].isin(["media","baja"])]
    print(f"\n  Actualización automática (confianza alta)  : {len(auto)}")
    print(f"  Requieren revisión manual (media/baja)     : {len(manual)}")
    print(sep)

def cargar_reetiquetado(df_resultados: pd.DataFrame):
    """Actualiza en la base de datos únicamente las reclasificaciones de alta confianza.

    Args:
        df_resultados (pandas.DataFrame): Resultados de la reclasificación.

    Returns:
        None
    """
    conn = get_connection()
    actualizados = 0
    try:
        with conn.cursor() as cur:
            # Solo actualizar los de confianza alta
            df_alta = df_resultados[
                (df_resultados["confianza"] == "alta") &
                (df_resultados["etiqueta_nueva"] == "levemente_positivo") &
                (df_resultados["error"].isna())
            ]
            for _, row in df_alta.iterrows():
                cur.execute("""
                    UPDATE segmento_retroalimentacion
                    SET etiqueta_sentimiento   = %s,
                        confianza_etiqueta     = %s,
                        justificacion_etiqueta = %s
                    WHERE id_segmento = %s
                """, (
                    row["etiqueta_nueva"],
                    row["confianza"],
                    row["justificacion"],
                    int(row["id_segmento"]),
                ))
                actualizados += 1
        conn.commit()
        print(f"\n  Segmentos actualizados automáticamente : {actualizados}")
        print(f"  Pendientes de revisión manual          : "
              f"{len(df_resultados) - actualizados}")
    except Exception as e:
        conn.rollback()
        print(f"\n  [ERROR] {e}"); raise
    finally:
        conn.close()

def main():
    """Ejecuta el flujo de reclasificación y carga a partir de argumentos de línea de comandos.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["preview","cargar"],
                        default="preview")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY no encontrada en .env")
        sys.exit(1)

    cliente = anthropic.Anthropic(api_key=api_key)
    engine  = get_engine()

    # Leer segmentos positivos
    df = pd.read_sql("""
        SELECT id_segmento, id_registro, categoria,
               texto_segmento, etiqueta_sentimiento,
               confianza_etiqueta
        FROM segmento_retroalimentacion
        WHERE etiqueta_sentimiento = 'positivo'
        ORDER BY id_segmento
    """, engine)

    print(f"\nSegmentos 'positivo' a reclasificar: {len(df)}")
    costo = len(df) * 0.00015
    print(f"Costo estimado: ~${costo:.2f} USD")
    print(f"Tiempo estimado: ~{len(df)*PAUSA_SEG/60:.0f} minutos")

    if args.modo == "preview":
        # Probar con 5 segmentos
        print(f"\nModo PREVIEW — probando con 5 segmentos...\n")
        muestra = df.sample(min(5, len(df)), random_state=42)
        resultados_prev = []
        for _, row in muestra.iterrows():
            r = reclasificar_segmento(
                cliente, row["texto_segmento"], int(row["id_segmento"]))
            resultados_prev.append(r)
            print(f"  [{r['etiqueta']:<20}] [{r['confianza']:<5}] "
                  f"{row['texto_segmento'][:90]}...")
            time.sleep(PAUSA_SEG)
        print("\nSi la reclasificación se ve bien ejecuta con --modo cargar")
        return

    # Modo cargar
    print(f"\nReclasificando {len(df)} segmentos...")
    resultados = []
    for i, (_, row) in enumerate(df.iterrows()):
        if i % 50 == 0:
            print(f"  Procesando {i+1}/{len(df)}...")
        r = reclasificar_segmento(
            cliente, row["texto_segmento"], int(row["id_segmento"]))
        resultados.append({
            "id_segmento"   : int(row["id_segmento"]),
            "id_registro"   : int(row["id_registro"]),
            "categoria"     : row["categoria"],
            "texto_preview" : row["texto_segmento"][:150],
            "etiqueta_orig" : row["etiqueta_sentimiento"],
            "etiqueta_nueva": r["etiqueta"],
            "confianza"     : r["confianza"],
            "justificacion" : r["justificacion"],
            "error"         : r["error"],
        })
        time.sleep(PAUSA_SEG)

    df_resultados = pd.DataFrame(resultados)
    imprimir_reporte(df_resultados)

    # Guardar CSV completo para revisión manual
    out = Path("outputs")
    csv_path = out / f"reetiquetado_positivos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    df_resultados.to_csv(csv_path, index=False)
    print(f"\n  CSV completo guardado en: {csv_path.name}")
    print(f"  Abre ese CSV, revisa los de confianza 'media' y 'baja'")
    print(f"  y ajusta manualmente la columna etiqueta_nueva donde sea necesario.")

    cargar_reetiquetado(df_resultados)

    # Mostrar distribución final
    print(f"\n  Distribución final en BD:")
    df_final = pd.read_sql("""
        SELECT etiqueta_sentimiento, COUNT(*) as n
        FROM segmento_retroalimentacion
        WHERE etiqueta_sentimiento IS NOT NULL
        GROUP BY etiqueta_sentimiento
        ORDER BY n DESC
    """, engine)
    print(df_final.to_string(index=False))

if __name__ == "__main__":
    main()