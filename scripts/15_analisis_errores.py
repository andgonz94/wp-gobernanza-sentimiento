"""Analiza los errores de clasificación de los modelos cruzándolos con los metadatos del corpus.

Responde a la Pregunta 5 (alcance del análisis de errores de la Fase 6) para el
baseline, BETO y BERTIN:

  (a) ¿En qué categorías temáticas se concentran los errores de cada modelo, y
      difiere esa concentración entre las condiciones A y B?
  (b) Dentro de los errores de la clase negativo, ¿se concentran en alguna
      naturaleza (pedagogico, institucional_logistico, afectivo_momentaneo)?
  (c) ¿Qué casos cambian de predicción entre condiciones para el mismo
      id_segmento? Es el diagnóstico caso por caso del efecto de la gobernanza.
  (d) ¿Qué parte de esos cambios ocurre con texto idéntico entre A y B? Se
      determina comparando directamente el texto (corrección del 2026-10-08).

Entradas:
    outputs/bootstrap_input/{baseline,beto,roberta}_predicciones_{A,B}.csv y las
    tablas segmento_retroalimentacion, segmento_condicion_a (solo lectura).
Salidas:
    outputs/errores_por_categoria.csv, errores_negativo_por_naturaleza.csv,
    casos_que_cambian_entre_condiciones.csv, flips_por_clase_defecto.csv y
    casos_que_cambian_con_clase_defecto.csv.
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_engine

IN_DIR = Path("outputs/bootstrap_input")
OUT_DIR = Path("outputs")
OUT_DIR.mkdir(exist_ok=True)

MODELOS = {
    "baseline": ("baseline_predicciones_A.csv", "baseline_predicciones_B.csv"),
    "beto": ("beto_predicciones_A.csv", "beto_predicciones_B.csv"),
    "bertin_roberta": ("roberta_predicciones_A.csv", "roberta_predicciones_B.csv"),
}


def cargar_metadatos():
    """Carga desde la base de datos los metadatos de los segmentos activos.

    Returns:
        pandas.DataFrame: id_segmento, categoria, texto_segmento y naturaleza_negativo.
    """
    engine = get_engine()
    meta = pd.read_sql("""
        SELECT id_segmento, categoria, texto_segmento, naturaleza_negativo
        FROM segmento_retroalimentacion
        WHERE flag_excluir = 0
    """, engine)
    return meta


def cargar_defectos_por_segmento():
    """Clasifica cada segmento según si su texto en A es idéntico al de B.

    "Texto idéntico" se determina comparando directamente el texto que ve
    el modelo en ambas condiciones, no a partir del tipo de defecto: tres
    tipos alteran el texto (nulo_texto, texto_no_informativo y
    cuasi_duplicado, este último con la definición a nivel de segmento del
    script 09). En A se usa la fila primaria de cada id_segmento_origen (la
    de menor id_segmento_a), la misma que usan los scripts de entrenamiento
    para evaluar; las filas extra de duplicado_exacto solo se usan en
    entrenamiento. La comparación es NULL-segura (`<=>`): un texto nulo en A
    frente a un texto en B cuenta como distinto.

    Los tipos de defecto se colapsan a una fila por segmento, uniendo los de
    todas sus filas, para que el cruce con los casos que cambian no
    multiplique un flip por cada fila duplicada.

    Returns:
        pandas.DataFrame: Una fila por segmento con id_segmento,
        tipo_error_inyectado (tipos unidos por coma, o None) y clase_defecto:
        "afecta_texto" (texto distinto entre A y B), "solo_metadatos" (con
        defecto y texto idéntico) o "sin_defecto".
    """
    engine = get_engine()
    textos = pd.read_sql("""
        SELECT a.id_segmento_origen AS id_segmento,
               (a.texto_segmento <=> s.texto_segmento) AS texto_identico
        FROM segmento_condicion_a a
        JOIN (SELECT id_segmento_origen, MIN(id_segmento_a) AS id_primaria
              FROM segmento_condicion_a
              GROUP BY id_segmento_origen) p
          ON a.id_segmento_a = p.id_primaria
        JOIN segmento_retroalimentacion s
          ON s.id_segmento = a.id_segmento_origen
    """, engine)

    defectos = pd.read_sql("""
        SELECT id_segmento_origen, tipo_error_inyectado
        FROM segmento_condicion_a
        WHERE tipo_error_inyectado IS NOT NULL
    """, engine)
    defectos = (
        defectos.groupby("id_segmento_origen")["tipo_error_inyectado"]
        .apply(lambda serie: ",".join(sorted(set(
            t.strip() for valor in serie for t in str(valor).split(",")
        ))))
        .reset_index()
        .rename(columns={"id_segmento_origen": "id_segmento"})
    )

    clases = textos.merge(defectos, on="id_segmento", how="left")

    def clasificar(fila):
        """Asigna la clase de defecto de un segmento.

        Args:
            fila (pandas.Series): Fila con texto_identico y tipo_error_inyectado.

        Returns:
            str: "afecta_texto", "solo_metadatos" o "sin_defecto".
        """
        if fila["texto_identico"] != 1:
            return "afecta_texto"
        if pd.notna(fila["tipo_error_inyectado"]):
            return "solo_metadatos"
        return "sin_defecto"

    clases["clase_defecto"] = clases.apply(clasificar, axis=1)
    return clases[["id_segmento", "tipo_error_inyectado", "clase_defecto"]]


ETIQUETAS = ["muy_positivo", "positivo", "levemente_positivo", "neutral", "negativo"]
ID2LABEL = {i: e for i, e in enumerate(ETIQUETAS)}


def cargar_predicciones_con_meta(archivo, meta, condicion, modelo):
    """Carga las predicciones de un modelo y las enriquece con los metadatos del corpus.

    Args:
        archivo (str): Nombre del archivo de predicciones en outputs/bootstrap_input/.
        meta (pandas.DataFrame): Metadatos por segmento.
        condicion (str): Condición experimental ("A" o "B").
        modelo (str): Nombre del modelo.

    Returns:
        pandas.DataFrame: Predicciones con etiquetas legibles, metadatos, condición,
        modelo y columna correcto.
    """
    df = pd.read_csv(IN_DIR / archivo)

    # BETO/RoBERTa guardan y_true/y_pred como índices numéricos (0-4),
    # mientras que el baseline los guarda como texto ("negativo", etc.).
    # Se normaliza todo a texto para que el merge/filtrado por nombre de
    # clase (p. ej. "negativo") funcione igual para los 3 modelos.
    for col in ["y_true", "y_pred"]:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].map(ID2LABEL)

    df = df.merge(meta, on="id_segmento", how="left")
    df["condicion"] = condicion
    df["modelo"] = modelo
    df["correcto"] = df["y_true"].astype(str) == df["y_pred"].astype(str)
    return df


def analisis_por_categoria(df_todos):
    """(a) Calcula la tasa de error por categoría temática, modelo y condición.

    Args:
        df_todos (pandas.DataFrame): Predicciones de todos los modelos y condiciones.

    Returns:
        pandas.DataFrame: n, errores y tasa de error por modelo, condición y categoría.
    """
    resumen = (
        df_todos.groupby(["modelo", "condicion", "categoria"])
        .agg(n=("correcto", "size"), errores=("correcto", lambda s: (~s).sum()))
        .reset_index()
    )
    resumen["tasa_error"] = resumen["errores"] / resumen["n"]
    return resumen


def analisis_negativo_por_naturaleza(df_todos):
    """(b) Calcula la tasa de error de la clase negativo según su naturaleza.

    Args:
        df_todos (pandas.DataFrame): Predicciones de todos los modelos y condiciones.

    Returns:
        pandas.DataFrame: Tasa de error por modelo, condición y naturaleza_negativo;
        vacío si no hay casos negativos.
    """
    sub = df_todos[df_todos["y_true"] == "negativo"].copy()
    if sub.empty:
        return pd.DataFrame()
    resumen = (
        sub.groupby(["modelo", "condicion", "naturaleza_negativo"])
        .agg(n=("correcto", "size"), errores=("correcto", lambda s: (~s).sum()))
        .reset_index()
    )
    resumen["tasa_error"] = resumen["errores"] / resumen["n"]
    return resumen


def casos_que_cambian(df_a, df_b, modelo, meta):
    """(c) Identifica los segmentos cuya predicción pasa de correcta a incorrecta entre condiciones.

    Args:
        df_a (pandas.DataFrame): Predicciones enriquecidas de la condición A.
        df_b (pandas.DataFrame): Predicciones enriquecidas de la condición B.
        modelo (str): Nombre del modelo.
        meta (pandas.DataFrame): Metadatos por segmento.

    Returns:
        pandas.DataFrame: Casos que cambian, con su tipo de cambio y texto.
    """
    m = df_a.merge(df_b, on="id_segmento", suffixes=("_A", "_B"))
    cambia_a_peor = m[m["correcto_B"] & ~m["correcto_A"]].copy()  # B acertaba, A falla
    cambia_a_mejor = m[~m["correcto_B"] & m["correcto_A"]].copy()  # A acertaba, B falla

    cambia_a_peor["tipo_cambio"] = "B_correcto_A_incorrecto"
    cambia_a_mejor["tipo_cambio"] = "A_correcto_B_incorrecto"
    cambios = pd.concat([cambia_a_peor, cambia_a_mejor], ignore_index=True)
    cambios["modelo"] = modelo

    cols = ["modelo", "id_segmento", "tipo_cambio", "categoria_A",
            "y_true_A", "y_pred_A", "y_pred_B", "texto_segmento_A"]
    cambios = cambios.rename(columns={"categoria_A": "categoria",
                                       "texto_segmento_A": "texto"})
    return cambios[["modelo", "id_segmento", "tipo_cambio", "categoria",
                     "y_true_A", "y_pred_A", "y_pred_B", "texto"]]


def desagregar_cambios_por_defecto(df_cambios, defectos):
    """(d) Cruza los casos que cambian de predicción con la clase de defecto del segmento.

    Un flip "sin_defecto" o "solo_metadatos" ocurre con el mismo texto de entrada en
    A y B (verificado por comparación directa en cargar_defectos_por_segmento), por
    lo que no puede explicarse por corrupción textual directa: es evidencia (no
    concluyente por sí sola, pero cuantitativa) de que una parte de la volatilidad
    del modelo es varianza de entrenamiento entre corridas independientes, no un
    efecto causal de la gobernanza sobre el dato.

    Args:
        df_cambios (pandas.DataFrame): Casos que cambian, de todos los modelos.
        defectos (pandas.DataFrame): Clase de defecto por segmento.

    Returns:
        tuple: Resumen de flips por modelo y clase (con porcentaje) y detalle de
        casos con su clase.
    """
    m = df_cambios.merge(defectos, on="id_segmento", how="left")
    m["clase_defecto"] = m["clase_defecto"].fillna("sin_defecto")

    resumen = (
        m.groupby(["modelo", "clase_defecto"])
        .size()
        .reset_index(name="n_flips")
    )
    resumen["pct_del_total_modelo"] = (
        resumen["n_flips"] / resumen.groupby("modelo")["n_flips"].transform("sum") * 100
    ).round(1)
    return resumen, m


def main():
    """Ejecuta los análisis (a) a (d) para cada modelo disponible y guarda los CSV."""
    if not IN_DIR.exists():
        print(f"[ERROR] No existe {IN_DIR}. Corre primero 14_bootstrap_pareado.py "
              f"con los archivos ya organizados.")
        return

    meta = cargar_metadatos()
    print(f"Metadatos cargados: {len(meta)} segmentos (categoria, naturaleza_negativo, texto)")

    todos = []
    cambios_todos = []

    for modelo, (archivo_a, archivo_b) in MODELOS.items():
        if not (IN_DIR / archivo_a).exists() or not (IN_DIR / archivo_b).exists():
            print(f"[AVISO] Saltando {modelo}: faltan archivos de predicciones")
            continue

        df_a = cargar_predicciones_con_meta(archivo_a, meta, "A", modelo)
        df_b = cargar_predicciones_con_meta(archivo_b, meta, "B", modelo)
        todos.append(df_a)
        todos.append(df_b)

        cambios = casos_que_cambian(df_a, df_b, modelo, meta)
        cambios_todos.append(cambios)

    if not todos:
        print("No se procesó ningún modelo.")
        return

    df_todos = pd.concat(todos, ignore_index=True)
    df_cambios = pd.concat(cambios_todos, ignore_index=True) if cambios_todos else pd.DataFrame()

    # --- (a) Errores por categoría ---
    resumen_categoria = analisis_por_categoria(df_todos)
    resumen_categoria.to_csv(OUT_DIR / "errores_por_categoria.csv", index=False)
    print(f"\n{'='*60}\n  (a) TASA DE ERROR POR CATEGORÍA TEMÁTICA\n{'='*60}")
    print(resumen_categoria.pivot_table(
        index=["modelo", "categoria"], columns="condicion", values="tasa_error"
    ).round(3).to_string())

    # --- (b) Errores de "negativo" por naturaleza ---
    resumen_negativo = analisis_negativo_por_naturaleza(df_todos)
    if not resumen_negativo.empty:
        resumen_negativo.to_csv(OUT_DIR / "errores_negativo_por_naturaleza.csv", index=False)
        print(f"\n{'='*60}\n  (b) TASA DE ERROR EN 'NEGATIVO' POR NATURALEZA\n{'='*60}")
        print(resumen_negativo.pivot_table(
            index=["modelo", "naturaleza_negativo"], columns="condicion", values="tasa_error"
        ).round(3).to_string())
    else:
        print("\n  (b) No hay casos de 'negativo' con predicciones para analizar.")

    # --- (c) Casos que cambian entre condiciones ---
    if not df_cambios.empty:
        df_cambios.to_csv(OUT_DIR / "casos_que_cambian_entre_condiciones.csv", index=False)
        print(f"\n{'='*60}\n  (c) CASOS QUE CAMBIAN ENTRE CONDICIONES\n{'='*60}")
        resumen_cambios = df_cambios.groupby(["modelo", "tipo_cambio"]).size().reset_index(name="n")
        print(resumen_cambios.to_string(index=False))

        print(f"\n  Ejemplos ilustrativos (hasta 3 por modelo, tipo B_correcto_A_incorrecto):")
        for modelo in df_cambios["modelo"].unique():
            ejemplos = df_cambios[
                (df_cambios["modelo"] == modelo) &
                (df_cambios["tipo_cambio"] == "B_correcto_A_incorrecto")
            ].head(3)
            if len(ejemplos):
                print(f"\n  [{modelo}]")
                for _, r in ejemplos.iterrows():
                    texto_corto = str(r["texto"])[:100]
                    print(f"    id={r['id_segmento']} categoria={r['categoria']} "
                          f"y_true={r['y_true_A']} pred_A={r['y_pred_A']} pred_B={r['y_pred_B']}")
                    print(f"      \"{texto_corto}...\"")
    else:
        print("\n  (c) No se generaron comparaciones de cambio de predicción.")

    # --- (d) Desagregación de flips por clase de defecto ---
    # Pregunta directa: ¿la volatilidad de cada modelo es explicable
    # por corrupción textual, o persiste con texto idéntico entre
    # condiciones (candidata a varianza de entrenamiento, no a
    # sensibilidad real a la gobernanza)?
    if not df_cambios.empty:
        defectos = cargar_defectos_por_segmento()
        resumen_defecto, cambios_con_defecto = desagregar_cambios_por_defecto(df_cambios, defectos)
        resumen_defecto.to_csv(OUT_DIR / "flips_por_clase_defecto.csv", index=False)
        cambios_con_defecto.to_csv(OUT_DIR / "casos_que_cambian_con_clase_defecto.csv", index=False)

        print(f"\n{'='*60}\n  (d) FLIPS POR CLASE DE DEFECTO (texto identico vs no)\n{'='*60}")
        print(resumen_defecto.pivot_table(
            index="modelo", columns="clase_defecto", values="n_flips", fill_value=0
        ).to_string())
        print(f"\n  Nota: 'sin_defecto' y 'solo_metadatos' significan texto IDENTICO")
        print(f"  entre A y B para ese segmento (comparacion directa del texto,")
        print(f"  no por tipo de defecto) — un flip ahi no puede deberse a")
        print(f"  corrupcion textual directa. Un modelo con proporcion alta de")
        print(f"  flips en esas dos categorias es candidato a inestabilidad de")
        print(f"  entrenamiento (Dodge et al., 2020), no necesariamente a mayor")
        print(f"  sensibilidad real a la gobernanza de datos.")
    else:
        print("\n  (d) No hay casos que cambian sobre los cuales desagregar por defecto.")

    print(f"\n{'='*60}")
    print("  [OK] CSVs guardados en outputs/:")
    print("    errores_por_categoria.csv")
    print("    errores_negativo_por_naturaleza.csv")
    print("    casos_que_cambian_entre_condiciones.csv")
    print("    flips_por_clase_defecto.csv")
    print("    casos_que_cambian_con_clase_defecto.csv")


if __name__ == "__main__":
    main()