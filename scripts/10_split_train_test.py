"""Genera la partición única de entrenamiento y prueba para todos los modelos.

Agrupa por entrevista de origen (id_registro) y estratifica por etiqueta de
sentimiento, para reutilizar la misma asignación en los distintos modelos y en
ambas condiciones experimentales. Asigna el augmentation sin fuga de datos entre
particiones.

Entradas:
    Tablas segmento_retroalimentacion y augmentation_segmentos.
Salidas:
    Tabla split_asignacion y outputs/split_asignacion.csv (respaldo).
"""

import sys
from pathlib import Path
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_engine, get_connection

SEMILLA = 42
N_SPLITS_PARA_80_20 = 5  # 1 fold de 5 ≈ 20% test


def construir_split():
    """Construye la asignación de train/test agrupada por entrevista, incluyendo el augmentation usable sin fuga.

    Returns:
        pandas.DataFrame: Asignación final de cada segmento u observación sintética a train o test, por condición.
    """
    engine = get_engine()

    # --- 1. Corpus real activo (idéntico en contenido para A y B) ---
    df_real = pd.read_sql("""
        SELECT id_segmento, id_registro, categoria, etiqueta_sentimiento
        FROM segmento_retroalimentacion
        WHERE flag_excluir = 0
    """, engine)
    print(f"Segmentos reales activos: {len(df_real)}")
    print(f"id_registro únicos: {df_real['id_registro'].nunique()}")

    # --- 2. Split agrupado y estratificado ---
    sgkf = StratifiedGroupKFold(n_splits=N_SPLITS_PARA_80_20,
                                 shuffle=True, random_state=SEMILLA)
    X = df_real["id_segmento"].values
    y = df_real["etiqueta_sentimiento"].values
    groups = df_real["id_registro"].values

    train_idx, test_idx = next(sgkf.split(X, y, groups))
    ids_train_segmento = set(df_real.iloc[train_idx]["id_segmento"])
    ids_test_segmento  = set(df_real.iloc[test_idx]["id_segmento"])
    ids_train_registro = set(df_real.iloc[train_idx]["id_registro"])
    ids_test_registro  = set(df_real.iloc[test_idx]["id_registro"])

    # Verificación: ningún id_registro debe aparecer en ambos lados
    interseccion = ids_train_registro & ids_test_registro
    assert len(interseccion) == 0, f"¡Fuga de datos! id_registro en ambos lados: {interseccion}"

    print(f"\nSplit real — train: {len(ids_train_segmento)} segmentos "
          f"({len(ids_train_registro)} id_registro)")
    print(f"Split real — test : {len(ids_test_segmento)} segmentos "
          f"({len(ids_test_registro)} id_registro)")

    print("\nDistribución de clases en TRAIN:")
    print(df_real[df_real["id_segmento"].isin(ids_train_segmento)]
          ["etiqueta_sentimiento"].value_counts())
    print("\nDistribución de clases en TEST:")
    print(df_real[df_real["id_segmento"].isin(ids_test_segmento)]
          ["etiqueta_sentimiento"].value_counts())

    # --- 3. Augmentation — solo entra a TRAIN si su origen cayó en TRAIN ---
    df_aug = pd.read_sql("""
        SELECT id_aug, id_segmento_origen, condicion, etiqueta_sentimiento
        FROM augmentation_segmentos
    """, engine)

    df_aug["origen_en_train"] = df_aug["id_segmento_origen"].isin(ids_train_segmento)
    df_aug["origen_en_test"]  = df_aug["id_segmento_origen"].isin(ids_test_segmento)

    n_descartados = (~df_aug["origen_en_train"] & ~df_aug["origen_en_test"]).sum()
    if n_descartados:
        print(f"\n{n_descartados} filas de augmentation con id_segmento_origen "
              f"no encontrado en el corpus activo (probablemente excluido) — se descartan.")

    df_aug_usable = df_aug[df_aug["origen_en_train"]].copy()
    df_aug_descartado = df_aug[df_aug["origen_en_test"]].copy()

    print(f"\nAugmentation total: {len(df_aug)}")
    print(f"Augmentation incorporado a TRAIN (origen en train): {len(df_aug_usable)}")
    print(f"Augmentation descartado (origen cayó en TEST, evita fuga): {len(df_aug_descartado)}")
    print("\nAugmentation usable por condición y clase:")
    print(df_aug_usable.groupby(["condicion", "etiqueta_sentimiento"]).size())

    # --- 4. Construir tabla de asignación final ---
    filas = []

    for _, r in df_real.iterrows():
        split = "train" if r["id_segmento"] in ids_train_segmento else "test"
        for cond in ["A", "B"]:
            filas.append({
                "id_referencia": r["id_segmento"],
                "tipo_id": "id_segmento",
                "condicion": cond,
                "origen": "real",
                "etiqueta_sentimiento": r["etiqueta_sentimiento"],
                "split": split,
            })

    for _, r in df_aug_usable.iterrows():
        filas.append({
            "id_referencia": r["id_aug"],
            "tipo_id": "id_aug",
            "condicion": r["condicion"],
            "origen": "sintetico",
            "etiqueta_sentimiento": r["etiqueta_sentimiento"],
            "split": "train",  # por construcción, solo entran los de origen en train
        })

    df_split = pd.DataFrame(filas)

    print(f"\nTotal filas en la asignación final (real×2 condiciones + sintético usable): {len(df_split)}")
    print("\nResumen final por condición / split / origen:")
    print(df_split.groupby(["condicion", "split", "origen"]).size())

    return df_split


def guardar_en_bd(df_split: pd.DataFrame):
    """Guarda la asignación de train/test en la base de datos, reemplazando la existente.

    Args:
        df_split (pandas.DataFrame): Asignación de train/test a guardar.

    Returns:
        None
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS split_asignacion (
                    id_fila         INT AUTO_INCREMENT PRIMARY KEY,
                    id_referencia   INT NOT NULL,
                    tipo_id         VARCHAR(20) NOT NULL,
                    condicion       VARCHAR(10) NOT NULL,
                    origen          VARCHAR(20) NOT NULL,
                    etiqueta_sentimiento VARCHAR(20) NOT NULL,
                    split           VARCHAR(10) NOT NULL,
                    semilla         INT DEFAULT 42,
                    fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("DELETE FROM split_asignacion")
            conn.commit()

            for _, r in df_split.iterrows():
                cur.execute("""
                    INSERT INTO split_asignacion
                        (id_referencia, tipo_id, condicion, origen,
                         etiqueta_sentimiento, split)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (int(r["id_referencia"]), r["tipo_id"], r["condicion"],
                      r["origen"], r["etiqueta_sentimiento"], r["split"]))
            conn.commit()
        print(f"\nTabla split_asignacion cargada: {len(df_split)} filas")
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    df_split = construir_split()

    out = Path("outputs")
    out.mkdir(exist_ok=True)
    df_split.to_csv(out / "split_asignacion.csv", index=False)
    print(f"\nCSV de respaldo guardado: outputs/split_asignacion.csv")

    guardar_en_bd(df_split)