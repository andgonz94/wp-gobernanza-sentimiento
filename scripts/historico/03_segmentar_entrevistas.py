"""
Segmenta entrevistas transcritas en fragmentos temáticos basados en
patrones de texto y palabras clave, separando las intervenciones del
entrevistador de las del estudiante y clasificando cada fragmento del
estudiante por categoría. Genera un preview y, opcionalmente, carga
los segmentos a la base de datos.
"""

import sys, re, argparse
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_engine, get_connection

# ─────────────────────────────────────────────
# CATÁLOGO DE CATEGORÍAS
# ─────────────────────────────────────────────
CATEGORIAS = {
    "metodologia": [
        "lúdic","ludic","juego","jugar","dinamic","didactic","didáctic",
        "actividad","metodolog","forma de aprender","estrategia","taller",
        "material","recurso","colorid","divertid","interesante","entretenid",
        "diferente","innovador","creativ","practic","participativ","interactiv",
        "primaria","volver a","acostumbrad","epídactic","epidactic","charlas",
        "método","metodo","herramienta","escrito","aburrido"
    ],
    "experiencia_docente": [
        "profe","profesor","profesora","docente","maestr",
        "diego","juliet","glorita","explica","enseña","trato",
        "atiende","ayuda","simpático","amable","estricto","firme",
        "dominio","evalúa","evalua","retroalimentación","retroalimentacion",
        "escucha","paciencia","manejo","control","bulla","regaña",
        "respuestas malas","expresa","dialoga","charla con","muy bien",
        "con todos","atiende a","pasa grupo"
    ],
    "aprendizaje": [
        "aprendí","aprendi","aprender","aprendizaje","conocimiento",
        "entendí","entendi","entender","comprendí","comprendi",
        "tema","contenido","concepto","teoría","teoria",
        "matemática","matematica","lectura","escritura","lectoescritura",
        "literatura","lenguaje","aplicar","útil","util","sirve",
        "futuro","quedarmelo","quedarme","camino","habilidad",
        "formas de aprender","entre más","va a ser mejor"
    ],
    "impacto_emocional": [
        "sentí","senti","sentir","emoción","emocion",
        "alegría","alegria","feliz","contento","ansiedad","ansioso",
        "nervioso","miedo","seguro","seguridad","confianza","cómodo",
        "comodo","libre","tranquilo","motivado","motivación","motivacion",
        "gustó","encantó","encanto","difícil","dificil",
        "costó","esfuerzo","relacionar","integrar","social",
        "intensamente","emociones","tristeza","vergüenza","bonito",
        "muy social","poco social","romper el hielo","comancia"
    ],
    "sugerencias": [
        "mejorar","mejora","cambiar","cambio","propongo","propuesta",
        "sugiero","sugerencia","recomiendo","falta","faltar",
        "necesita","debería","deberia","ojalá","ojala",
        "sería bueno","organización","organizacion","por mejorar",
        "transporte","logística","logistica","grupos","organizar",
        "aunque","sin embargo","pero hay","podría","podria",
        "más firme","mas firme","más concreto","mas concreto"
    ]
}

# Patrón para dividir por marcadores del entrevistador
PATRON_SPLIT = re.compile(
    r'(?:Ok[,\.\s]|Listo[,\.\s]|Vale[,\.\s]|Bien[,\.\s]|Ah[,\.\s])'
    r'|(?:¿[A-ZÁÉÍÓÚÜÑ][^?]{5,}\?)'
    r'|(?:cuéntame|cuentame|dime cómo|dime como|cómo te|como te|'
    r'qué te|que te|por qué|por que|qué notas|que notas|'
    r'de pronto|digamos que)',
    re.IGNORECASE
)

# Frases que indican que el fragmento es del entrevistador
PATRON_ENTREVISTADOR = re.compile(
    r'^(entonces[,\s]|primero[,\s]|ahora[,\s]sí|'
    r'consentimiento|autoriza|grabada|confidencial|'
    r'voluntaria|timitamos|te invitamos|dice así|'
    r'hola[,\s].{0,30}(buenas|cómo|como|tardes|días)|'
    r'buenas (tardes|días|noches)[,\s]|'
    r'nos encontramos|estamos acá|estamos aquí|'
    r'en este momento con|con el estudiante|con la estudiante)',
    re.IGNORECASE
)

# ─────────────────────────────────────────────
# SEGMENTACIÓN
# ─────────────────────────────────────────────

def es_fragmento_entrevistador(texto: str) -> bool:
    """Determina si un fragmento de texto corresponde al entrevistador y no al estudiante.

    Args:
        texto (str): Fragmento de texto a evaluar.

    Returns:
        bool: True si el fragmento parece pertenecer al entrevistador.
    """
    t = texto.strip()
    palabras = len(t.split())
    if palabras <= 5:
        return True
    if PATRON_ENTREVISTADOR.search(t):
        return True
    return False

def clasificar_categoria(texto: str) -> str:
    """Clasifica un fragmento de texto en una categoría temática según coincidencias de palabras clave.

    Args:
        texto (str): Fragmento de texto a clasificar.

    Returns:
        str: Nombre de la categoría con mayor coincidencia, o una categoría residual si no hay ninguna.
    """
    t = texto.lower()
    scores = {cat: sum(1 for kw in kws if kw in t)
              for cat, kws in CATEGORIAS.items()}
    max_score = max(scores.values())
    if max_score == 0:
        return "general"
    for cat in CATEGORIAS:
        if scores[cat] == max_score:
            return cat
    return "general"

def segmentar_entrevista(texto_completo: str) -> list:
    """Divide una entrevista en segmentos temáticos del estudiante, descartando las intervenciones del entrevistador.

    Args:
        texto_completo (str): Transcripción completa de la entrevista.

    Returns:
        list: Lista de segmentos, cada uno con su categoría y texto.
    """
    if not texto_completo or len(texto_completo.strip()) < 50:
        return []

    # Dividir por marcadores
    fragmentos_raw = PATRON_SPLIT.split(texto_completo)

    # Filtrar y limpiar
    fragmentos_estudiante = []
    for f in fragmentos_raw:
        f = f.strip()
        if len(f) < 30:
            continue
        if es_fragmento_entrevistador(f):
            continue
        fragmentos_estudiante.append(f)

    if not fragmentos_estudiante:
        cat = clasificar_categoria(texto_completo)
        return [{"categoria": cat,
                 "texto_segmento": texto_completo.strip(),
                 "inicio_seg": None, "fin_seg": None}]

    # Clasificar y agrupar consecutivos de la misma categoría
    segmentos = []
    for f in fragmentos_estudiante:
        cat = clasificar_categoria(f)
        if segmentos and segmentos[-1]["categoria"] == cat:
            segmentos[-1]["texto_segmento"] += " " + f
        else:
            segmentos.append({
                "categoria": cat,
                "texto_segmento": f,
                "inicio_seg": None,
                "fin_seg": None,
            })

    # Filtrar segmentos muy cortos
    segmentos = [s for s in segmentos if len(s["texto_segmento"]) >= 40]

    return segmentos if segmentos else [{
        "categoria": clasificar_categoria(texto_completo),
        "texto_segmento": texto_completo.strip(),
        "inicio_seg": None, "fin_seg": None
    }]

# ─────────────────────────────────────────────
# REPORTE
# ─────────────────────────────────────────────

def imprimir_reporte(resultados):
    """Imprime un resumen de la segmentación, con distribución por categoría y una muestra de segmentos.

    Args:
        resultados (list): Lista de entrevistas procesadas, cada una con sus segmentos.

    Returns:
        None
    """
    from collections import Counter, defaultdict
    total = sum(len(r["segmentos"]) for r in resultados)
    sep = "─"*60
    print(f"\n{sep}\n  REPORTE DE SEGMENTACIÓN — Paso 3\n{sep}")
    print(f"  Entrevistas procesadas    : {len(resultados):>6}")
    print(f"  Total segmentos generados : {total:>6}")
    print(f"  Promedio por entrevista   : {total/len(resultados):>6.1f}")

    # Distribución de segmentos por entrevista
    segs_por_entrevista = [len(r["segmentos"]) for r in resultados]
    print(f"  Mín / Máx por entrevista  : "
          f"{min(segs_por_entrevista)} / {max(segs_por_entrevista)}")

    print(f"\n  Distribución por categoría:")
    cats = Counter(s["categoria"] for r in resultados for s in r["segmentos"])
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"    {cat:<30} {n:>5}  ({n/total*100:.1f}%)")
    print(sep)

    print("\n  MUESTRA (2 segmentos por categoría):")
    por_cat = defaultdict(list)
    for r in resultados:
        for s in r["segmentos"]:
            por_cat[s["categoria"]].append(s["texto_segmento"])

    for cat, textos in sorted(por_cat.items()):
        print(f"\n  [{cat.upper()}]")
        for t in textos[:2]:
            print(f"    → {t[:150].replace(chr(10),' ')}...")
    print(sep)

# ─────────────────────────────────────────────
# CARGA A MYSQL
# ─────────────────────────────────────────────

def cargar_segmentos(resultados):
    """Carga los segmentos generados a la base de datos, reemplazando los existentes.

    Args:
        resultados (list): Lista de entrevistas procesadas, cada una con sus segmentos.

    Returns:
        None
    """
    conn = get_connection()
    insertados = 0
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM segmento_retroalimentacion")
            conn.commit()
            for r in resultados:
                for s in r["segmentos"]:
                    cur.execute("""
                        INSERT INTO segmento_retroalimentacion
                            (id_registro,categoria,texto_segmento,
                             inicio_seg,fin_seg,metodo_segmentacion)
                        VALUES (%s,%s,%s,%s,%s,%s)
                    """, (r["id_registro"], s["categoria"],
                          s["texto_segmento"], s.get("inicio_seg"),
                          s.get("fin_seg"), "automatico"))
                    insertados += 1
            conn.commit()
        print(f"\n  Segmentos insertados: {insertados}")
    except Exception as e:
        conn.rollback()
        print(f"\n  Error: {e}"); raise
    finally:
        conn.close()

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    """Ejecuta el flujo de segmentación y carga a partir de argumentos de línea de comandos.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--modo", choices=["preview","cargar"], default="preview")
    args = parser.parse_args()

    csv_path    = Path(args.csv)
    corpus_path = Path("outputs/corpus_final.csv")
    for p in [csv_path, corpus_path]:
        if not p.exists():
            print(f"No encontrado: {p}"); sys.exit(1)

    print("\nLeyendo datos...")
    for enc in ["utf-8","utf-8-sig","latin-1"]:
        try:
            df_orig = pd.read_csv(csv_path, encoding=enc); break
        except UnicodeDecodeError:
            continue

    df_corpus = pd.read_csv(corpus_path)
    engine    = get_engine()
    df_mysql  = pd.read_sql(
        "SELECT id_registro, texto FROM retroalimentacion", engine)
    print(f"  Registros en MySQL : {len(df_mysql)}")

    df_orig["audio_filename"] = df_orig["audio_path"].apply(
        lambda p: Path(str(p)).name.strip())
    df_orig_dedup = df_orig.sort_values("created_at", ascending=False)\
        .drop_duplicates(subset="audio_filename", keep="first")

    df_merged = df_corpus.merge(
        df_orig_dedup[["audio_filename"]], on="audio_filename", how="left")

    df_merged["texto_key"] = df_merged["text"].astype(str).str.strip().str[:100]
    df_mysql["texto_key"]  = df_mysql["texto"].astype(str).str.strip().str[:100]
    df_final = df_merged.merge(
        df_mysql[["id_registro","texto_key"]], on="texto_key", how="left")
    df_final  = df_final[df_final["id_registro"].notna()]
    print(f"  Registros a segmentar : {len(df_final)}")

    print("\nSegmentando por patrones de texto...")
    resultados = []
    for _, row in df_final.iterrows():
        segs = segmentar_entrevista(
            str(row["text"]) if pd.notna(row["text"]) else "")
        resultados.append({
            "id_registro"   : int(row["id_registro"]),
            "audio_filename": row["audio_filename"],
            "segmentos"     : segs,
        })

    imprimir_reporte(resultados)

    rows = [{"id_registro": r["id_registro"],
             "audio_filename": r["audio_filename"], **s}
            for r in resultados for s in r["segmentos"]]
    pd.DataFrame(rows).to_csv("outputs/segmentos_preview.csv", index=False)
    print(f"\n  Preview guardado en: outputs/segmentos_preview.csv")

    if args.modo == "cargar":
        print("\nCargando en MySQL...")
        cargar_segmentos(resultados)
    else:
        print("\nModo PREVIEW — sin cambios en BD.")
        print("Ejecuta con --modo cargar cuando estés lista.")

if __name__ == "__main__":
    main()