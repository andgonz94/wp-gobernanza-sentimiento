"""Genera variantes sintéticas por paráfrasis para las clases minoritarias.

Usa un modelo de lenguaje para producir las variantes e inserta cada una de
forma simétrica en ambas condiciones experimentales: con el texto íntegro en la
condición gobernada, y con el mismo texto sujeto a la misma lógica de
degradación de metadatos en la condición cruda.

Entradas:
    Tabla segmento_retroalimentacion; API de Anthropic.
Salidas:
    outputs/augmentation_variantes_v2.csv y la tabla augmentation_segmentos.
"""

import sys, os, json, time, random, argparse
from pathlib import Path
import pandas as pd
import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from config.db_connection import get_engine, get_connection

# --- CONFIGURACIÓN ---

MODELO     = "claude-haiku-4-5"
MAX_TOKENS = 1000
PAUSA_SEG  = 0.4
SEMILLA    = 42

# Cuántas variantes generar por segmento según clase (ground truth actualizado)
VARIANTES_POR_CLASE = {
    "negativo": 4,   # 35 × 4 = 140 → ~175 total con originales
    "neutral" : 2,   # 88 × 2 = 176 → ~264 total con originales
}

SYSTEM_PROMPT = """Eres un experto en paráfrasis de texto educativo en español colombiano.
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

Sin texto adicional, sin markdown."""

# Mismos catálogos de defectos usados en 09_construir_condicion_a_segmentos.py,
# para que la degradación estructural sea consistente entre scripts.
CANALES_INVALIDOS = ["whatsapp", "presencial", "otro", "n/a", "sin especificar"]
FECHAS_INVALIDAS  = ["2026-13-45", "31/02/2026", "ayer", "hace dos semanas", ""]

# --- GENERACIÓN DE VARIANTES (una sola vez, texto compartido A/B) ---

def generar_variantes(cliente, texto: str, etiqueta: str, n_variantes: int) -> list:
    """Genera variantes por paráfrasis de un texto, preservando su sentido y sentimiento.

    Args:
        cliente: Cliente de la API del modelo de lenguaje.
        texto (str): Texto original a parafrasear.
        etiqueta (str): Etiqueta de sentimiento del texto original.
        n_variantes (int): Número de variantes a generar.

    Returns:
        list: Lista de variantes de texto generadas.
    """
    prompt = (f"Etiqueta de sentimiento: {etiqueta}\n\n"
              f"Texto original:\n{texto[:600]}\n\n"
              f"Genera exactamente {n_variantes} variantes.")
    try:
        response = cliente.messages.create(
            model=MODELO, max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        resultado = json.loads(raw)
        variantes = resultado.get("variantes", [])
        return [v.strip() for v in variantes if isinstance(v, str) and len(v.strip()) >= 20]
    except Exception as e:
        print(f"    [ERROR] {str(e)[:80]}")
        return []

# --- INYECCIÓN DE DEFECTOS SOBRE UNA VARIANTE (para condicion='A') ---

def degradar_para_condicion_a(rng: random.Random) -> dict:
    """Genera metadatos degradados para una variante sintética de la condición cruda.

    Args:
        rng (random.Random): Generador de números aleatorios para reproducibilidad.

    Returns:
        dict: Metadatos de registro, fecha y canal (degradados o limpios), y el tipo de error inyectado si lo hubo.
    """
    resultado = {
        "id_registro": None,  # se sobreescribe fuera con el id_registro real si no hay defecto
        "fecha_registro": "2026-05-13",
        "canal_captura": "formulario",
        "tipo_error_inyectado": None,
    }
    if rng.random() >= 0.579:
        return resultado  # sin defecto

    # Defectos de metadato aplicables a una variante sintética (no se
    # incluyen duplicado_exacto / cuasi_duplicado / nulo_texto /
    # texto_no_informativo porque esos alterarían el TEXTO, que debe
    # permanecer idéntico entre A y B). Proporciones renormalizadas
    # sobre estos 5 tipos, a partir de auditoria_inyeccion.csv:
    #   nulo_id_sesion       18.25 → 26.43%
    #   nulo_canal           14.29 → 20.70%
    #   canal_fuera_catalogo 13.49 → 19.54%
    #   nulo_fecha           11.90 → 17.24%
    #   formato_fecha        11.11 → 16.09%
    posibles = ["nulo_id_sesion", "nulo_canal", "canal_fuera_catalogo",
                "nulo_fecha", "formato_fecha"]
    pesos    = [26.43, 20.70, 19.54, 17.24, 16.09]
    tipo = rng.choices(posibles, weights=pesos, k=1)[0]

    if tipo == "nulo_id_sesion":
        resultado["id_registro_nulo"] = True
    elif tipo == "nulo_canal":
        resultado["canal_captura"] = None
    elif tipo == "canal_fuera_catalogo":
        resultado["canal_captura"] = rng.choice(CANALES_INVALIDOS)
    elif tipo == "nulo_fecha":
        resultado["fecha_registro"] = None
    elif tipo == "formato_fecha":
        resultado["fecha_registro"] = rng.choice(FECHAS_INVALIDAS)
    resultado["tipo_error_inyectado"] = tipo
    return resultado

# --- TABLA ---

def verificar_tabla():
    """Crea la tabla de segmentos de augmentation en la base de datos si no existe.

    Returns:
        None
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS augmentation_segmentos (
                    id_aug              INT AUTO_INCREMENT PRIMARY KEY,
                    id_segmento_origen  INT NOT NULL,
                    id_registro         INT NULL,
                    categoria           VARCHAR(50) NOT NULL,
                    texto_segmento      TEXT NOT NULL,
                    etiqueta_sentimiento VARCHAR(20) NOT NULL,
                    es_sintetico        TINYINT(1) DEFAULT 1,
                    condicion           VARCHAR(10) NOT NULL,
                    tipo_error_inyectado VARCHAR(150) NULL,
                    fecha_generacion    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (id_segmento_origen)
                        REFERENCES segmento_retroalimentacion(id_segmento)
                )
            """)
            conn.commit()
            print("  Tabla augmentation_segmentos verificada")
    finally:
        conn.close()

# --- CARGA — corrige el bug del DELETE global de la v1 ---

def cargar_augmentation(resultados: list, rng: random.Random):
    """Inserta las variantes generadas en ambas condiciones experimentales.

    Args:
        resultados (list): Lista de segmentos originales con sus variantes generadas.
        rng (random.Random): Generador de números aleatorios para la degradación de metadatos.

    Returns:
        None
    """
    conn = get_connection()
    insertados_b = insertados_a = 0
    try:
        with conn.cursor() as cur:
            # Bug corregido: borra SOLO las condiciones que se regeneran en esta corrida
            cur.execute("DELETE FROM augmentation_segmentos WHERE condicion IN ('A','B')")
            conn.commit()

            for r in resultados:
                for variante in r["variantes"]:
                    # --- Inserción para Condición B: texto tal cual, metadatos "limpios" ---
                    cur.execute("""
                        INSERT INTO augmentation_segmentos
                            (id_segmento_origen, id_registro, categoria, texto_segmento,
                             etiqueta_sentimiento, es_sintetico, condicion, tipo_error_inyectado)
                        VALUES (%s, %s, %s, %s, %s, 1, 'B', NULL)
                    """, (r["id_segmento"], r["id_registro"], r["categoria"],
                          variante, r["etiqueta"]))
                    insertados_b += 1

                    # --- Inserción para Condición A: MISMO texto, metadatos degradados ---
                    degradado = degradar_para_condicion_a(rng)
                    id_registro_a = None if degradado.get("id_registro_nulo") else r["id_registro"]
                    cur.execute("""
                        INSERT INTO augmentation_segmentos
                            (id_segmento_origen, id_registro, categoria, texto_segmento,
                             etiqueta_sentimiento, es_sintetico, condicion, tipo_error_inyectado)
                        VALUES (%s, %s, %s, %s, %s, 1, 'A', %s)
                    """, (r["id_segmento"], id_registro_a, r["categoria"],
                          variante, r["etiqueta"], degradado["tipo_error_inyectado"]))
                    insertados_a += 1
            conn.commit()
        print(f"\n  Variantes insertadas — Condición B: {insertados_b} | Condición A: {insertados_a}")
    except Exception as e:
        conn.rollback()
        print(f"\n  [ERROR] {e}"); raise
    finally:
        conn.close()

# --- REPORTE ---

def imprimir_reporte(resultados: list, df_originales: pd.DataFrame):
    """Imprime un resumen de las variantes generadas por clase de sentimiento.

    Args:
        resultados (list): Lista de segmentos originales con sus variantes generadas.
        df_originales (pandas.DataFrame): Distribución de etiquetas antes del augmentation.

    Returns:
        None
    """
    from collections import Counter
    sep = "─" * 60
    total_variantes = sum(len(r["variantes"]) for r in resultados)
    total_errores = sum(1 for r in resultados if not r["variantes"])

    print(f"\n{sep}")
    print("  REPORTE DE DATA AUGMENTATION v2 — simétrico A/B")
    print(sep)
    print(f"\n  Segmentos originales procesados : {len(resultados)}")
    print(f"  Variantes generadas (por condición): {total_variantes}")
    print(f"  Total insertado (A+B)              : {total_variantes * 2}")
    print(f"  Errores de generación               : {total_errores}")

    print(f"\n  Distribución ANTES del augmentation (ground truth auditado):")
    for et, n in df_originales["etiqueta_sentimiento"].value_counts().items():
        print(f"    {et:<20} {n:>5}")

    conteo_var = Counter(r["etiqueta"] for r in resultados for _ in r["variantes"])
    print(f"\n  Variantes generadas por clase (aplican a A y a B por igual):")
    for et, n in conteo_var.items():
        print(f"    {et:<20} {n:>5}")
    print(sep)

# --- MAIN ---

def main():
    """Ejecuta el flujo de generación y carga de variantes a partir de argumentos de línea de comandos.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["preview", "cargar"], default="preview")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY no encontrada en .env"); sys.exit(1)

    cliente = anthropic.Anthropic(api_key=api_key)
    engine = get_engine()
    rng = random.Random(SEMILLA)

    clases_objetivo = list(VARIANTES_POR_CLASE.keys())
    placeholders = ",".join(["'" + c + "'" for c in clases_objetivo])

    # --- Fuente corregida: ground truth ya auditado ---
    df = pd.read_sql(f"""
        SELECT id_segmento, id_registro, categoria, texto_segmento, etiqueta_sentimiento
        FROM segmento_retroalimentacion
        WHERE etiqueta_sentimiento IN ({placeholders})
          AND flag_excluir = 0
        ORDER BY etiqueta_sentimiento, id_segmento
    """, engine)

    df_ground_truth = pd.read_sql("""
        SELECT etiqueta_sentimiento
        FROM segmento_retroalimentacion
        WHERE flag_excluir = 0 AND etiqueta_sentimiento IS NOT NULL
    """, engine)

    print(f"\nSegmentos a aumentar (ground truth auditado, flag_excluir=0): {len(df)}")
    for et in clases_objetivo:
        n = len(df[df["etiqueta_sentimiento"] == et])
        v = VARIANTES_POR_CLASE[et]
        print(f"  {et:<20} {n:>4} originales × {v} variantes "
              f"= ~{n*v} nuevos por condición → total {n*v*2} (A+B) → gran total {n*(v+1)} por condición")

    costo = len(df) * max(VARIANTES_POR_CLASE.values()) * 0.0003
    print(f"\n  Costo estimado (1 sola generación, se reutiliza en A y B): ~${costo:.2f} USD")
    print(f"  Tiempo estimado: ~{len(df)*PAUSA_SEG/60:.0f} minutos")

    if args.modo == "preview":
        print(f"\nModo PREVIEW — probando con 3 segmentos...")
        muestra = df.sample(min(3, len(df)), random_state=SEMILLA)
        for _, row in muestra.iterrows():
            n_var = VARIANTES_POR_CLASE.get(row["etiqueta_sentimiento"], 2)
            vars_ = generar_variantes(cliente, row["texto_segmento"],
                                       row["etiqueta_sentimiento"], n_var)
            print(f"\n  [{row['etiqueta_sentimiento'].upper()}]")
            print(f"  Original  : {row['texto_segmento'][:100]}...")
            for i, v in enumerate(vars_, 1):
                print(f"  Variante {i}: {v[:100]}...")
                degradado = degradar_para_condicion_a(rng)
                id_reg_preview = None if degradado.get("id_registro_nulo") else row["id_registro"]
                print(f"    → Condición A recibiría: id_registro={id_reg_preview}, "
                      f"fecha_registro={degradado['fecha_registro']}, "
                      f"canal_captura={degradado['canal_captura']}, "
                      f"tipo_error_inyectado={degradado['tipo_error_inyectado']}")
            time.sleep(PAUSA_SEG)
        print("\nSi las variantes y la degradación se ven bien, ejecuta con --modo cargar")
        return

    # Modo cargar
    verificar_tabla()
    print(f"\nGenerando variantes para {len(df)} segmentos...")

    resultados = []
    for i, (_, row) in enumerate(df.iterrows()):
        if i % 10 == 0:
            print(f"  Procesando {i+1}/{len(df)}...")
        n_var = VARIANTES_POR_CLASE.get(row["etiqueta_sentimiento"], 2)
        variantes = generar_variantes(cliente, row["texto_segmento"],
                                       row["etiqueta_sentimiento"], n_var)
        resultados.append({
            "id_segmento": int(row["id_segmento"]),
            "id_registro": int(row["id_registro"]) if pd.notna(row["id_registro"]) else None,
            "categoria": row["categoria"],
            "etiqueta": row["etiqueta_sentimiento"],
            "texto_original": row["texto_segmento"],
            "variantes": variantes,
        })
        time.sleep(PAUSA_SEG)

    imprimir_reporte(resultados, df_ground_truth)

    out = Path("outputs")
    out.mkdir(exist_ok=True)
    rows = []
    for r in resultados:
        for v in r["variantes"]:
            rows.append({
                "id_segmento_origen": r["id_segmento"],
                "categoria": r["categoria"],
                "etiqueta": r["etiqueta"],
                "texto_original": r["texto_original"][:200],
                "variante": v,
            })
    pd.DataFrame(rows).to_csv(out / "augmentation_variantes_v2.csv", index=False)
    print(f"\n  [OK] CSV guardado: outputs/augmentation_variantes_v2.csv")

    cargar_augmentation(resultados, rng)

if __name__ == "__main__":
    main()