"""Construye la versión segmentada de la condición cruda inyectando defectos de calidad.

Parte de los segmentos de la condición gobernada y replica las proporciones de
error observadas en la auditoría del corpus original. Un mismo segmento puede
recibir más de un defecto. La mayoría de los defectos afectan metadatos,
validaciones o trazabilidad; tres alteran el texto del segmento (nulo_texto,
texto_no_informativo y cuasi_duplicado; ver docs/guia_operativa_scripts.md).

Entradas:
    Tabla segmento_retroalimentacion (flag_excluir = 0).
Salidas:
    Tabla segmento_condicion_a y outputs/auditoria_inyeccion_segmentos.csv.
"""

import sys, random, argparse
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_engine, get_connection

SEMILLA = 42  # reproducibilidad — misma semilla siempre = mismos segmentos afectados

# --- DISTRIBUCIÓN DE DEFECTOS (proporcional a auditoria_inyeccion.csv) ---

TASA_AFECTACION = 0.579  # 88/152 registros originales tenían al menos 1 error

DISTRIBUCION_ERRORES = {
    "nulo_id_sesion"      : 0.1825,
    "nulo_canal"          : 0.1429,
    "canal_fuera_catalogo": 0.1349,
    "nulo_fecha"          : 0.1190,
    "formato_fecha"       : 0.1111,
    "duplicado_exacto"    : 0.0952,
    "texto_no_informativo": 0.0952,
    "nulo_texto"          : 0.0635,
    "cuasi_duplicado"     : 0.0556,
}

CANALES_INVALIDOS = ["whatsapp", "presencial", "otro", "n/a", "sin especificar"]
FECHAS_INVALIDAS  = ["2026-13-45", "31/02/2026", "ayer", "hace dos semanas", ""]
TEXTOS_NO_INFORMATIVOS = ["ok", "bien", "nada", "no sé", "regular", "todo bien"]

# --- CREAR TABLA ---

def crear_tabla():
    """Crea la tabla de segmentos de la condición cruda en la base de datos si no existe.

    Returns:
        None
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS segmento_condicion_a (
                    id_segmento_a       INT AUTO_INCREMENT PRIMARY KEY,
                    id_segmento_origen  INT NOT NULL,
                    id_registro         INT NULL,
                    categoria           VARCHAR(50) NULL,
                    texto_segmento      TEXT NULL,
                    fecha_registro      VARCHAR(50) NULL,
                    canal_captura       VARCHAR(50) NULL,
                    etiqueta_sentimiento VARCHAR(20) NULL,
                    tipo_error_inyectado VARCHAR(50) NULL,
                    fecha_construccion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (id_segmento_origen)
                        REFERENCES segmento_retroalimentacion(id_segmento)
                )
            """)
            conn.commit()
            print("  Tabla segmento_condicion_a verificada")
    finally:
        conn.close()

# --- INYECCIÓN DE DEFECTOS ---

def asignar_errores(df: pd.DataFrame, rng: random.Random) -> dict:
    """Asigna tipos de error a una muestra de segmentos, replicando las proporciones de referencia.

    Args:
        df (pandas.DataFrame): Segmentos disponibles para afectar.
        rng (random.Random): Generador de números aleatorios para reproducibilidad.

    Returns:
        dict: Mapeo de identificador de segmento a la lista de errores asignados.
    """
    n_total = len(df)
    n_afectados = round(n_total * TASA_AFECTACION)
    ids_afectados = rng.sample(list(df["id_segmento"]), n_afectados)

    n_errores_total = round(n_total * TASA_AFECTACION * (126/88))  # ratio errores/afectados original
    pool_errores = []
    for tipo, prop in DISTRIBUCION_ERRORES.items():
        pool_errores += [tipo] * round(n_errores_total * prop)
    rng.shuffle(pool_errores)

    asignacion = {sid: [] for sid in ids_afectados}
    idx = 0
    # primero garantizar 1 error por afectado
    for sid in ids_afectados:
        if idx < len(pool_errores):
            asignacion[sid].append(pool_errores[idx]); idx += 1
    # repartir el resto (errores múltiples por registro) aleatoriamente entre afectados
    while idx < len(pool_errores):
        sid = rng.choice(ids_afectados)
        asignacion[sid].append(pool_errores[idx]); idx += 1

    return asignacion

def aplicar_defecto(row: dict, tipo_error: str, texto_para_duplicar: str = None) -> dict:
    """Aplica un defecto estructural sobre una copia de un segmento.

    Args:
        row (dict): Datos del segmento sobre el que aplicar el defecto.
        tipo_error (str): Tipo de defecto a aplicar.
        texto_para_duplicar (str, optional): Texto de referencia para defectos de duplicación.

    Returns:
        dict: Copia del segmento con el defecto aplicado.
    """
    r = dict(row)
    if tipo_error == "nulo_id_sesion":
        r["id_registro"] = None
    elif tipo_error == "nulo_canal":
        r["canal_captura"] = None
    elif tipo_error == "canal_fuera_catalogo":
        r["canal_captura"] = random.choice(CANALES_INVALIDOS)
    elif tipo_error == "nulo_fecha":
        r["fecha_registro"] = None
    elif tipo_error == "formato_fecha":
        r["fecha_registro"] = random.choice(FECHAS_INVALIDAS)
    elif tipo_error == "nulo_texto":
        r["texto_segmento"] = None
    elif tipo_error == "texto_no_informativo":
        r["texto_segmento"] = random.choice(TEXTOS_NO_INFORMATIVOS)
    elif tipo_error == "duplicado_exacto":
        pass  # se maneja aparte (inserta una fila extra idéntica)
    elif tipo_error == "cuasi_duplicado":
        if r.get("texto_segmento"):
            r["texto_segmento"] = r["texto_segmento"] + " " + r["texto_segmento"].split()[0]
    return r

# --- MAIN ---

def main():
    """Ejecuta el flujo de construcción de segmentos de la condición cruda a partir de argumentos de línea de comandos.

    Returns:
        None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["preview", "cargar"], default="preview")
    args = parser.parse_args()

    engine = get_engine()
    rng = random.Random(SEMILLA)
    random.seed(SEMILLA)

    df = pd.read_sql("""
        SELECT id_segmento, id_registro, categoria, texto_segmento,
               etiqueta_sentimiento
        FROM segmento_retroalimentacion
        WHERE flag_excluir = 0
        ORDER BY id_segmento
    """, engine)

    print(f"\nBase de segmentos (Condición B, ya depurada): {len(df)}")

    asignacion = asignar_errores(df, rng)
    n_afectados = len(asignacion)
    n_errores = sum(len(v) for v in asignacion.values())
    print(f"Segmentos a afectar con al menos 1 defecto: {n_afectados} ({n_afectados/len(df)*100:.1f}%)")
    print(f"Total de defectos a inyectar: {n_errores}")

    from collections import Counter
    conteo_tipo = Counter(t for errores in asignacion.values() for t in errores)
    print("\nDistribución de defectos a inyectar:")
    for tipo, n in conteo_tipo.most_common():
        print(f"  {tipo:<25} {n:>4}")

    # Construir filas de salida
    filas_salida = []
    duplicados_extra = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        sid = row_dict["id_segmento"]
        errores = asignacion.get(sid, [])

        fila = {
            "id_segmento_origen": sid,
            "id_registro": row_dict["id_registro"],
            "categoria": row_dict["categoria"],
            "texto_segmento": row_dict["texto_segmento"],
            "fecha_registro": "2026-05-13",  # fecha base simulada, formato válido
            "canal_captura": "formulario",   # canal base simulado, válido
            "etiqueta_sentimiento": row_dict["etiqueta_sentimiento"],
            "tipo_error_inyectado": None,
        }

        for tipo_error in errores:
            fila = aplicar_defecto(fila, tipo_error)
            if tipo_error == "duplicado_exacto":
                duplicados_extra.append(dict(fila, tipo_error_inyectado="duplicado_exacto"))

        fila["tipo_error_inyectado"] = ",".join(errores) if errores else None
        filas_salida.append(fila)

    # Añadir las filas duplicadas como registros adicionales
    filas_salida += duplicados_extra

    df_salida = pd.DataFrame(filas_salida)
    print(f"\nTotal filas en segmento_condicion_a (incl. duplicados inyectados): {len(df_salida)}")

    if args.modo == "preview":
        print("\nModo PREVIEW — muestra de 5 filas con defecto:")
        con_defecto = df_salida[df_salida["tipo_error_inyectado"].notna()]
        print(con_defecto.head(5)[["id_segmento_origen", "tipo_error_inyectado",
                                     "id_registro", "fecha_registro", "canal_captura"]].to_string())
        print("\nSi se ve bien, ejecuta con --modo cargar")
        return

    # Modo cargar
    crear_tabla()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM segmento_condicion_a")  # tabla exclusiva de A, seguro limpiarla completa
            conn.commit()
            for _, r in df_salida.iterrows():
                cur.execute("""
                    INSERT INTO segmento_condicion_a
                        (id_segmento_origen, id_registro, categoria, texto_segmento,
                         fecha_registro, canal_captura, etiqueta_sentimiento,
                         tipo_error_inyectado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    int(r["id_segmento_origen"]),
                    int(r["id_registro"]) if pd.notna(r["id_registro"]) else None,
                    r["categoria"], r["texto_segmento"],
                    r["fecha_registro"], r["canal_captura"],
                    r["etiqueta_sentimiento"], r["tipo_error_inyectado"],
                ))
            conn.commit()
        print(f"\n  segmento_condicion_a construida: {len(df_salida)} filas")
    except Exception as e:
        conn.rollback()
        print(f"\n  [ERROR] {e}"); raise
    finally:
        conn.close()

    # Guardar auditoría CSV, análoga a auditoria_inyeccion.csv
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    auditoria = df_salida[df_salida["tipo_error_inyectado"].notna()][
        ["id_segmento_origen", "tipo_error_inyectado"]
    ].rename(columns={"id_segmento_origen": "indice_original", "tipo_error_inyectado": "tipo_error"})
    auditoria.to_csv(out / "auditoria_inyeccion_segmentos.csv", index=False)
    print(f"  CSV de auditoría guardado: outputs/auditoria_inyeccion_segmentos.csv")

if __name__ == "__main__":
    main()