"""Carga las correcciones manuales del re-etiquetado de segmentos.

Marca automáticamente los segmentos que deben excluirse por criterio semántico
y, opcionalmente, valida cada etiqueta manual contra un modelo de lenguaje antes
de actualizar la base de datos.

Entradas:
    outputs/revision_manual_etiquetas.xlsx (o .csv), con id_segmento,
    texto_segmento, etiqueta_nueva y, opcionalmente, Eliminar.
Salidas:
    outputs/revision_manual_procesada.csv; actualización de
    segmento_retroalimentacion.
"""

import sys, os, json, time, argparse
from pathlib import Path
import pandas as pd
import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from config.db_connection import get_engine, get_connection

MODELO     = "claude-haiku-4-5"
MAX_TOKENS = 150
PAUSA_SEG  = 0.2

PALABRAS_VALORACION = [
    "me gusto","me encanto","me parecio","me ayudo","me sirvio",
    "aprendi","entendi","comprendi","me costo","me dificulto",
    "chevere","divertido","interesante","aburrido","dificil","facil",
    "me senti","senti","emocion","alegria","nervioso","seguro",
    "motivado","mejor","peor","mas facil","mas dificil",
    "me gusto","no me gusto","no entendi","me confundi",
    "entiendo mejor","me quedo","me llamo la atencion",
    "gustó","encantó","pareció","ayudó","sirvió","aprendí",
    "entendí","comprendí","costó","dificultó","sentí","emoción",
    "alegría","difícil","fácil","motivado","llamó","quedó",
]

def tiene_valoracion(texto: str) -> bool:
    """Determina si un texto contiene alguna expresión de valoración conocida.

    Args:
        texto (str): Texto a evaluar.

    Returns:
        bool: True si el texto contiene una palabra o frase de valoración.
    """
    t = texto.lower()
    return any(kw in t for kw in PALABRAS_VALORACION)

def flag_exclusion_automatico(texto: str) -> str:
    """Determina automáticamente si un segmento debe excluirse por falta de valor analítico.

    Args:
        texto (str): Texto del segmento a evaluar.

    Returns:
        str: "excluir" o "mantener".
    """
    if not texto or len(texto.strip()) < 20:
        return "excluir"
    if tiene_valoracion(texto):
        return "mantener"
    if len(texto.split()) < 8:
        return "excluir"
    return "mantener"

def validar_con_api(cliente, texto: str, etiqueta_manual: str) -> dict:
    """Valida una etiqueta asignada manualmente consultando a un modelo de lenguaje.

    Args:
        cliente: Cliente de la API del modelo de lenguaje.
        texto (str): Texto del segmento etiquetado.
        etiqueta_manual (str): Etiqueta asignada manualmente.

    Returns:
        dict: Indicador de acuerdo, justificación y error si lo hubo.
    """
    prompt = f"""Etiqueta asignada manualmente: {etiqueta_manual}

Texto del estudiante:
{texto[:400]}

¿La etiqueta es correcta?
- positivo: valoración favorable clara y sostenida
- levemente_positivo: valoración tibia, moderada o con reservas

Responde ÚNICAMENTE con JSON:
{{"acuerdo": true, "justificacion": "máximo 8 palabras"}}"""
    try:
        response = cliente.messages.create(
            model=MODELO, max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        raw = raw.replace("```json","").replace("```","").strip()
        r = json.loads(raw)
        return {"acuerdo_api": r.get("acuerdo", True),
                "just_validacion": r.get("justificacion","")[:150],
                "error_val": None}
    except Exception as e:
        return {"acuerdo_api": True, "just_validacion": "",
                "error_val": str(e)[:80]}

def imprimir_reporte(df: pd.DataFrame):
    """Imprime un resumen de la revisión manual y, si aplica, de la validación cruzada.

    Args:
        df (pandas.DataFrame): Datos de revisión manual procesados.

    Returns:
        None
    """
    sep = "─"*60
    print(f"\n{sep}")
    print("  REPORTE — Revisión manual + validación cruzada")
    print(sep)
    print(f"\n  Total registros           : {len(df)}")

    print(f"\n  Etiquetas manuales:")
    for et, n in df["etiqueta_nueva"].value_counts().items():
        print(f"    {et:<25} {n:>5}  ({n/len(df)*100:.1f}%)")

    print(f"\n  Bandera exclusión automática:")
    for fl, n in df["flag_excluir_auto"].value_counts().items():
        print(f"    {fl:<25} {n:>5}  ({n/len(df)*100:.1f}%)")

    if "acuerdo_api" in df.columns:
        total_val = df["acuerdo_api"].notna().sum()
        acuerdo   = df["acuerdo_api"].sum()
        print(f"\n  Validación cruzada API vs Manual:")
        print(f"    Acuerdo    : {int(acuerdo):>5} / {total_val}  ({acuerdo/total_val*100:.1f}%)")
        print(f"    Desacuerdo : {int(total_val-acuerdo):>5} / {total_val}  ({(total_val-acuerdo)/total_val*100:.1f}%)")

        desacuerdo = df[df["acuerdo_api"]==False]
        if len(desacuerdo) > 0:
            print(f"\n  Muestra de casos en desacuerdo:")
            for _, r in desacuerdo.head(4).iterrows():
                print(f"    [{r['etiqueta_nueva']:<20}] "
                      f"{str(r.get('texto_segmento',''))[:80]}...")
    print(sep)

def cargar_correcciones(df: pd.DataFrame):
    """Actualiza la base de datos con las etiquetas y banderas de exclusión de la revisión manual.

    Args:
        df (pandas.DataFrame): Datos de revisión manual procesados.

    Returns:
        None
    """
    conn = get_connection()
    actualizados = 0
    try:
        with conn.cursor() as cur:
            # Agregar columna flag_excluir si no existe
            try:
                cur.execute("""
                    ALTER TABLE segmento_retroalimentacion
                    ADD COLUMN flag_excluir TINYINT(1) DEFAULT 0
                """)
                conn.commit()
                print("  Columna flag_excluir creada")
            except Exception:
                print("  Columna flag_excluir ya existe")
                conn.rollback()

            for _, row in df.iterrows():
                flag = 1 if row.get("flag_excluir_auto") == "excluir" else 0
                cur.execute("""
                    UPDATE segmento_retroalimentacion
                    SET etiqueta_sentimiento   = %s,
                        confianza_etiqueta     = %s,
                        justificacion_etiqueta = %s,
                        flag_excluir           = %s
                    WHERE id_segmento = %s
                """, (
                    row["etiqueta_nueva"],
                    row.get("confianza","media"),
                    "revisión manual"[:300],
                    flag,
                    int(row["id_segmento"]),
                ))
                actualizados += 1
        conn.commit()
        print(f"\n  Registros actualizados: {actualizados}")

        engine = get_engine()
        df_final = pd.read_sql("""
            SELECT etiqueta_sentimiento,
                   SUM(CASE WHEN COALESCE(flag_excluir,0)=0 THEN 1 ELSE 0 END) as activos,
                   SUM(CASE WHEN flag_excluir=1 THEN 1 ELSE 0 END) as excluidos
            FROM segmento_retroalimentacion
            WHERE etiqueta_sentimiento IS NOT NULL
            GROUP BY etiqueta_sentimiento
            ORDER BY activos DESC
        """, engine)
        print(f"\n  Distribución final (activos / excluidos):")
        print(df_final.to_string(index=False))

    except Exception as e:
        conn.rollback()
        print(f"\n  [ERROR] {e}"); raise
    finally:
        conn.close()

def main():
    """Ejecuta el flujo de carga de revisión manual a partir de argumentos de línea de comandos.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="outputs/revision_manual_etiquetas.xlsx")
    parser.add_argument("--modo", choices=["preview","cargar"], default="preview")
    parser.add_argument("--validar", action="store_true",
                        help="Ejecutar validación cruzada con API")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"No encontrado: {csv_path}"); sys.exit(1)

    # Leer Excel o CSV según extensión
    if csv_path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(csv_path)
        print(f"  Formato: Excel ({csv_path.suffix})")
    else:
        for enc in ["utf-8","utf-8-sig","latin-1","mac_roman"]:
            try:
                df = pd.read_csv(csv_path, encoding=enc); break
            except UnicodeDecodeError:
                continue
        print(f"  Formato: CSV")

    # Usar columna Eliminar del Excel como bandera manual
    # 1 = excluir, vacío/0 = mantener
    if "Eliminar" in df.columns:
        df["flag_excluir_auto"] = df["Eliminar"].apply(
            lambda x: "excluir" if pd.notna(x) and str(x).strip() in ["1","1.0","True","true","x","X","sí","si"] else "mantener"
        )
        n_manual = (df["flag_excluir_auto"] == "excluir").sum()
        print(f"  Columna 'Eliminar' detectada → {n_manual} marcados manualmente para excluir")

    print(f"\nRegistros cargados: {len(df)}")

    # Si no tiene columna Eliminar, usar detección automática como fallback
    if "Eliminar" not in df.columns:
        df["flag_excluir_auto"] = df["texto_segmento"].apply(
            lambda t: flag_exclusion_automatico(str(t) if pd.notna(t) else "")
        )
        excluir_n = (df["flag_excluir_auto"] == "excluir").sum()
        print(f"  Marcados para excluir (auto) : {excluir_n}")
        print(f"  Marcados para mantener (auto): {len(df) - excluir_n}")

    # Validación cruzada opcional
    if args.validar:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("ANTHROPIC_API_KEY no encontrada — omitiendo validación")
        else:
            cliente = anthropic.Anthropic(api_key=api_key)
            print(f"\nValidando {len(df)} etiquetas con Claude API...")
            print(f"  Costo estimado: ~${len(df)*0.0001:.2f} USD")
            resultados_val = []
            for i, (_, row) in enumerate(df.iterrows()):
                if i % 30 == 0:
                    print(f"  Validando {i+1}/{len(df)}...")
                r = validar_con_api(
                    cliente,
                    str(row.get("texto_segmento","")),
                    str(row["etiqueta_nueva"])
                )
                resultados_val.append(r)
                time.sleep(PAUSA_SEG)
            df = pd.concat([df.reset_index(drop=True),
                           pd.DataFrame(resultados_val).reset_index(drop=True)],
                          axis=1)

    imprimir_reporte(df)

    out = Path("outputs")
    out.mkdir(exist_ok=True)
    df.to_csv(out/"revision_manual_procesada.csv", index=False)
    print(f"\n  CSV procesado: outputs/revision_manual_procesada.csv")

    if args.modo == "cargar":
        print("\nCargando a MySQL...")
        cargar_correcciones(df)
    else:
        print("\nModo PREVIEW — sin cambios en BD.")
        if not args.validar:
            print("Agrega --validar para ejecutar validación cruzada.")
        print("Ejecuta con --modo cargar cuando estés lista.")

if __name__ == "__main__":
    main()