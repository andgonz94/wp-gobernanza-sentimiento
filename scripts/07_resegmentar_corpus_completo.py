"""Resegmenta el corpus completo de entrevistas con un modelo de lenguaje.

Reemplaza la segmentación previa basada en palabras clave. Respalda la
segmentación anterior antes de sobrescribirla y genera un reporte y un CSV de
auditoría de los nuevos segmentos.

Entradas:
    Tablas retroalimentacion y segmento_retroalimentacion; API de Anthropic.
Salidas:
    outputs/segmentos_palabras_clave_backup_<timestamp>.csv,
    outputs/segmentos_claude_api_completo.csv y la tabla
    segmento_retroalimentacion reemplazada.
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

SYSTEM_PROMPT = """Eres un experto en análisis de entrevistas educativas en español colombiano.
Tu tarea es segmentar y clasificar fragmentos de entrevistas con estudiantes sobre
su experiencia en un programa educativo llamado [PROGRAMA].

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

Sin texto adicional, sin markdown, sin explicaciones fuera del JSON."""

# --- SEGMENTACIÓN ---

def segmentar_con_claude(cliente, texto: str, id_registro: int) -> list:
    """Segmenta y clasifica una entrevista en fragmentos temáticos mediante un modelo de lenguaje.

    Args:
        cliente: Cliente de la API del modelo de lenguaje.
        texto (str): Texto completo de la entrevista.
        id_registro (int): Identificador del registro al que pertenece la entrevista.

    Returns:
        list: Lista de segmentos válidos con su categoría, texto y justificación.
    """
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

        validos = []
        for s in segmentos:
            cat      = s.get("categoria","").lower().strip()
            texto_s  = s.get("texto","").strip()
            if cat in CATEGORIAS and len(texto_s) >= 30:
                validos.append({
                    "id_registro"      : id_registro,
                    "categoria"        : cat,
                    "texto_segmento"   : texto_s,
                    "justificacion"    : s.get("justificacion","")[:200],
                    "metodo_segment"   : "claude_api",
                    "inicio_seg"       : None,
                    "fin_seg"          : None,
                })
        return validos

    except json.JSONDecodeError as e:
        print(f"    JSON error id={id_registro}: {str(e)[:60]}")
        return []
    except Exception as e:
        print(f"    API error id={id_registro}: {str(e)[:60]}")
        return []

# --- REPORTE ---

def imprimir_reporte(resultados: list, n_errores: int):
    """Imprime un resumen de la resegmentación, con distribución por categoría.

    Args:
        resultados (list): Lista de entrevistas procesadas, cada una con sus segmentos.
        n_errores (int): Número de entrevistas que fallaron durante la segmentación.

    Returns:
        None
    """
    from collections import Counter
    total = sum(len(r["segmentos"]) for r in resultados)
    sep = "─"*60
    print(f"\n{sep}")
    print("  REPORTE DE RESEGMENTACIÓN — Paso 7")
    print(sep)
    print(f"  Entrevistas procesadas    : {len(resultados):>6}")
    print(f"  Entrevistas con error API : {n_errores:>6}")
    print(f"  Total segmentos generados : {total:>6}")
    print(f"  Promedio por entrevista   : {total/max(len(resultados),1):>6.1f}")

    segs_por = [len(r["segmentos"]) for r in resultados]
    print(f"  Mín / Máx por entrevista  : "
          f"{min(segs_por)} / {max(segs_por)}")

    print(f"\n  Distribución por categoría:")
    cats = Counter(
        s["categoria"]
        for r in resultados
        for s in r["segmentos"]
    )
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"    {cat:<25} {n:>5}  ({n/total*100:.1f}%)")
    print(sep)

# --- CARGA A MYSQL ---

def cargar_segmentos(resultados: list):
    """Reemplaza los segmentos existentes en la base de datos por los nuevos segmentos generados.

    Args:
        resultados (list): Lista de entrevistas procesadas, cada una con sus segmentos.

    Returns:
        None
    """
    conn = get_connection()
    insertados = 0
    try:
        with conn.cursor() as cur:
            # Respaldar conteo anterior
            cur.execute("SELECT COUNT(*) as n FROM segmento_retroalimentacion")
            n_anterior = cur.fetchone()["n"]
            print(f"  Segmentos anteriores en BD : {n_anterior}")

            # Limpiar tabla
            cur.execute("DELETE FROM segmento_retroalimentacion")
            conn.commit()
            print(f"  Tabla limpiada")

            # Insertar nuevos segmentos
            for r in resultados:
                for s in r["segmentos"]:
                    cur.execute("""
                        INSERT INTO segmento_retroalimentacion
                            (id_registro, categoria, texto_segmento,
                             inicio_seg, fin_seg, metodo_segmentacion)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        r["id_registro"],
                        s["categoria"],
                        s["texto_segmento"],
                        s["inicio_seg"],
                        s["fin_seg"],
                        "claude_api",
                    ))
                    insertados += 1

            conn.commit()
        print(f"\n  Segmentos insertados : {insertados}")
        print(f"  Diferencia vs anterior  : "
              f"{insertados - n_anterior:+d} segmentos")

    except Exception as e:
        conn.rollback()
        print(f"\n  [ERROR] {e}"); raise
    finally:
        conn.close()

# --- MAIN ---

def main():
    """Ejecuta el flujo de resegmentación y carga a partir de argumentos de línea de comandos.

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

    # Leer corpus completo
    print("\nLeyendo corpus desde MySQL...")
    df = pd.read_sql("""
        SELECT id_registro, texto
        FROM retroalimentacion
        WHERE texto IS NOT NULL
        AND LENGTH(texto) > 50
        ORDER BY id_registro
    """, engine)
    print(f"  Entrevistas a procesar: {len(df)}")

    # Respaldar segmentación actual
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    df_backup = pd.read_sql(
        "SELECT * FROM segmento_retroalimentacion", engine)
    backup_path = out / f"segmentos_palabras_clave_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    df_backup.to_csv(backup_path, index=False)
    print(f"  [OK] Backup guardado en: {backup_path.name}")

    if args.modo == "preview":
        costo = len(df) * 0.015
        tiempo = len(df) * PAUSA_SEG / 60
        print(f"\n  Costo estimado  : ~${costo:.2f} USD")
        print(f"  Tiempo estimado : ~{tiempo:.0f} minutos")
        print(f"\nModo PREVIEW — sin cambios en BD.")
        print("Ejecuta con --modo cargar cuando estés lista.")
        return

    # Segmentar corpus completo
    print(f"\nResegmentando {len(df)} entrevistas con Claude API...")
    print(f"  Costo estimado  : ~${len(df)*0.015:.2f} USD")
    print(f"  Tiempo estimado : ~{len(df)*PAUSA_SEG/60:.0f} minutos\n")

    resultados  = []
    n_errores   = 0

    for i, (_, row) in enumerate(df.iterrows()):
        if i % 10 == 0:
            print(f"  Procesando {i+1}/{len(df)}...")

        segs = segmentar_con_claude(
            cliente, str(row["texto"]), int(row["id_registro"]))

        if not segs:
            n_errores += 1

        resultados.append({
            "id_registro": int(row["id_registro"]),
            "segmentos"  : segs,
        })
        time.sleep(PAUSA_SEG)

    imprimir_reporte(resultados, n_errores)

    # Guardar CSV de auditoría
    rows = []
    for r in resultados:
        for s in r["segmentos"]:
            rows.append({
                "id_registro"   : r["id_registro"],
                "categoria"     : s["categoria"],
                "texto_segmento": s["texto_segmento"],
                "justificacion" : s["justificacion"],
            })
    df_export = pd.DataFrame(rows)
    df_export.to_csv(out/"segmentos_claude_api_completo.csv", index=False)
    print(f"\n  CSV de auditoría: outputs/segmentos_claude_api_completo.csv")

    # Cargar a MySQL
    print("\nCargando en MySQL...")
    cargar_segmentos(resultados)

    print(f"\n  Siguiente paso:")
    print(f"  Ejecuta el script 04 para re-etiquetar sentimiento:")
    print(f"  python scripts/04_etiquetar_sentimiento.py --modo cargar")

if __name__ == "__main__":
    main()