"""Exporta a CSV las tablas que necesitan los scripts de Colab.

Permite el ajuste fino de modelos de lenguaje en un entorno externo sin acceso
directo a la base de datos local.

Entradas:
    Tablas split_asignacion, segmento_retroalimentacion, segmento_condicion_a y
    augmentation_segmentos.
Salidas:
    outputs/colab/{split_asignacion,segmento_retroalimentacion,
    segmento_condicion_a,augmentation_segmentos}.csv.
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_engine

OUT = Path("outputs/colab")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    """Exporta las tablas del pipeline gobernado a CSV para su uso en un entorno externo.

    Returns:
        None
    """
    engine = get_engine()

    split = pd.read_sql("SELECT * FROM split_asignacion", engine)
    split.to_csv(OUT / "split_asignacion.csv", index=False)
    print(f"split_asignacion.csv: {len(split)} filas")

    real_b = pd.read_sql("""
        SELECT id_segmento, id_registro, categoria, texto_segmento, etiqueta_sentimiento
        FROM segmento_retroalimentacion
        WHERE flag_excluir = 0
    """, engine)
    real_b.to_csv(OUT / "segmento_retroalimentacion.csv", index=False)
    print(f"segmento_retroalimentacion.csv: {len(real_b)} filas")

    cond_a = pd.read_sql("""
        SELECT id_segmento_a, id_segmento_origen, id_registro, categoria,
               texto_segmento, etiqueta_sentimiento, tipo_error_inyectado
        FROM segmento_condicion_a
    """, engine)
    cond_a.to_csv(OUT / "segmento_condicion_a.csv", index=False)
    print(f"segmento_condicion_a.csv: {len(cond_a)} filas")

    aug = pd.read_sql("""
        SELECT id_aug, id_segmento_origen, id_registro, categoria,
               texto_segmento, etiqueta_sentimiento, condicion, tipo_error_inyectado
        FROM augmentation_segmentos
    """, engine)
    aug.to_csv(OUT / "augmentation_segmentos.csv", index=False)
    print(f"augmentation_segmentos.csv: {len(aug)} filas")

    print(f"\nArchivos listos en: {OUT.resolve()}")
    print("   Súbelos a una carpeta en tu Google Drive, por ejemplo:")
    print("   MyDrive/working_paper/datos_colab/")


if __name__ == "__main__":
    main()