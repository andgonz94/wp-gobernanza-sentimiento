"""Compara cómo BETO y BERTIN tokenizan el mismo corpus.

Diagnostica si la diferencia de estabilidad entre ambos modelos podría
explicarse por la tokenización: fertilidad, longitud de secuencia resultante y
proporción de ejemplos truncados. No entrena ningún modelo; solo tokeniza y
mide. Se ejecuta en Google Colab.

Entradas:
    segmento_retroalimentacion.csv exportado por 12_exportar_tablas_para_colab.py.
Salidas:
    Solo salida en consola.
"""

import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
from transformers import AutoTokenizer

import entrenar_beto as eb  # reutiliza RUTA_DATOS, MAX_LENGTH, etc.

CHECKPOINT_BETO = "dccuchile/bert-base-spanish-wwm-cased"
CHECKPOINT_BERTIN = "bertin-project/bertin-roberta-base-spanish"


def analizar_tokenizer(nombre, checkpoint, textos, max_length):
    """Analiza cómo un tokenizador fragmenta un corpus, e imprime estadísticas de fertilidad y truncamiento.

    Args:
        nombre (str): Nombre descriptivo del modelo.
        checkpoint (str): Identificador del checkpoint del tokenizador.
        textos (list): Textos a analizar.
        max_length (int): Longitud máxima de secuencia usada en el entrenamiento.

    Returns:
        dict: Estadísticas resumen de tokenización para el modelo.
    """
    print(f"\n{'─'*55}\n  {nombre}  ({checkpoint})\n{'─'*55}")
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)

    n_palabras = [len(t.split()) for t in textos]
    tokens_sin_truncar = [len(tokenizer.encode(t, truncation=False)) for t in textos]
    tokens_truncados = [len(tokenizer.encode(t, truncation=True, max_length=max_length))
                         for t in textos]

    fertilidad = [tok / max(pal, 1) for tok, pal in zip(tokens_sin_truncar, n_palabras)]
    n_truncados = sum(1 for t in tokens_sin_truncar if t > max_length)

    # Proporción de tokens UNK (si el tokenizer tiene uno)
    unk_id = tokenizer.unk_token_id
    n_unk = 0
    n_tokens_total = 0
    if unk_id is not None:
        for t in textos:
            ids = tokenizer.encode(t, truncation=False)
            n_tokens_total += len(ids)
            n_unk += sum(1 for i in ids if i == unk_id)

    print(f"  Palabras por ejemplo (split simple)     — media: {np.mean(n_palabras):.1f}")
    print(f"  Tokens por ejemplo (sin truncar)         — media: {np.mean(tokens_sin_truncar):.1f}"
          f"  mediana: {np.median(tokens_sin_truncar):.0f}  p95: {np.percentile(tokens_sin_truncar, 95):.0f}"
          f"  máx: {np.max(tokens_sin_truncar)}")
    print(f"  Fertilidad (tokens / palabra)            — media: {np.mean(fertilidad):.2f}")
    print(f"  Ejemplos que exceden MAX_LENGTH={max_length}      : {n_truncados} "
          f"({n_truncados/len(textos)*100:.1f}%)")
    if unk_id is not None and n_tokens_total > 0:
        print(f"  Tokens UNK                               : {n_unk} / {n_tokens_total} "
              f"({n_unk/n_tokens_total*100:.3f}%)")
    else:
        print(f"  Tokens UNK                               : N/A (tokenizer sin UNK — "
              f"esperado en byte-level BPE)")

    return {
        "modelo": nombre,
        "tokens_media": np.mean(tokens_sin_truncar),
        "tokens_p95": np.percentile(tokens_sin_truncar, 95),
        "fertilidad_media": np.mean(fertilidad),
        "pct_truncados": n_truncados / len(textos) * 100,
        "pct_unk": (n_unk / n_tokens_total * 100) if (unk_id is not None and n_tokens_total > 0) else None,
    }


if __name__ == "__main__":
    real_b = pd.read_csv(eb.RUTA_DATOS / "segmento_retroalimentacion.csv")
    textos = real_b["texto_segmento"].fillna("").tolist()
    print(f"Corpus: {len(textos)} segmentos reales (Condición B)")

    r_beto = analizar_tokenizer("BETO", CHECKPOINT_BETO, textos, eb.MAX_LENGTH)
    r_bertin = analizar_tokenizer("BERTIN", CHECKPOINT_BERTIN, textos, eb.MAX_LENGTH)

    print(f"\n{'='*55}\n  COMPARACIÓN\n{'='*55}")
    df_comp = pd.DataFrame([r_beto, r_bertin])
    print(df_comp.to_string(index=False))

    dif_fertilidad = (r_bertin["fertilidad_media"] / r_beto["fertilidad_media"] - 1) * 100
    print(f"\n  BERTIN fragmenta {dif_fertilidad:+.1f}% más que BETO "
          f"(fertilidad relativa)")

    if r_bertin["pct_truncados"] > r_beto["pct_truncados"] + 2:
        print(f"  BERTIN trunca notablemente más ejemplos que BETO — "
              f"considerar subir MAX_LENGTH.")
    else:
        print(f"  Proporción de truncamiento similar entre ambos tokenizers — "
              f"MAX_LENGTH={eb.MAX_LENGTH} no parece ser un problema diferencial.")