"""Declara como restricciones de esquema las reglas de calidad de la tabla retroalimentacion.

ESTADO (2026-10-08): ejecutado con --modo aplicar el 2026-08-31 23:24 por la
autora; las restricciones ya existen en la base de datos. NO debe volver a
ejecutarse: intentaría crear de nuevo las dos restricciones CHECK y MySQL lo
rechazaría. Antes de aplicarlo se imputaron a mano 23 fechas faltantes. Ver
docs/cambios_agosto_2026.md, sección 5.

Cierra la brecha documentada en el Reporte Metodológico (sección 16, "Brecha
entre gobernanza declarada e implementada"): las reglas de calidad solo se
aplicaban en la capa de aplicación (01_deduplicar_y_cargar.py,
02_fusionar_y_cargar.py, 09a_procesar_condicion_a.py) y no estaban declaradas
como NOT NULL / CHECK en el esquema de MySQL, de modo que cualquier vía de
ingesta que no pasara por esos scripts podía insertar registros que las violaran.

Restricciones que agrega (la cita original a 11_procesar_condicion_a.py
corresponde a 09a_procesar_condicion_a.py):

  RQ-01  texto            NOT NULL, CHECK (CHAR_LENGTH(texto) >= 5)
  RQ-02  id_sesion        NOT NULL
  RQ-03  fecha_registro   NOT NULL
  RQ-04  canal_captura    NOT NULL
  RQ-06  canal_captura    CHECK (canal_captura IN ('formulario','papel',
                                 'app','email','desconocido'))

El umbral de 5 caracteres no coincide con RQ-09 (20 caracteres) y no se declaran
RQ-05, RQ-07, RQ-08 ni RQ-09; ver docs/propuestas_mejora_arquitectura.md.

En modo preview (por defecto) inspecciona el esquema real y muestra las
sentencias sin ejecutarlas. En modo aplicar genera y verifica un respaldo con
mysqldump, pide confirmación y ejecuta los ALTER TABLE; se detiene si hay filas
que ya violan alguna regla.

Entradas:
    Tabla retroalimentacion (esquema en information_schema) y, en modo aplicar,
    mysqldump disponible en el PATH.
Salidas:
    En modo aplicar: backup_antes_constraints_<timestamp>.sql y el esquema
    modificado. En modo preview: solo salida en consola.
"""

import sys
import os
import shutil
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_engine, get_connection, _get_credentials

TABLA = "retroalimentacion"
CANAL_CATALOGO = ["formulario", "papel", "app", "email", "desconocido"]


def hacer_backup() -> Path | None:
    """Genera y verifica un respaldo completo de la base de datos con mysqldump.

    Verifica el tamaño y la presencia de sentencias INSERT reales, no solo de
    estructura. Pasa la contraseña por la variable de entorno MYSQL_PWD en vez de
    -p, para que no quede visible en la lista de procesos.

    Returns:
        pathlib.Path | None: Ruta del respaldo verificado, o None si algo falló (en
        cuyo caso --modo aplicar debe abortar).
    """
    if shutil.which("mysqldump") is None:
        print("[ERROR] mysqldump no está instalado o no está en el PATH.")
        return None

    creds = _get_credentials()
    ruta_backup = Path(f"backup_antes_constraints_{datetime.now().strftime('%Y%m%d_%H%M')}.sql")

    comando = [
        "mysqldump",
        "-h", creds["DB_HOST"],
        "-P", str(creds["DB_PORT"]),
        "-u", creds["DB_USER"],
        creds["DB_NAME"],
    ]
    env = os.environ.copy()
    env["MYSQL_PWD"] = creds["DB_PASSWORD"]

    print(f"Generando respaldo en {ruta_backup} ...")
    try:
        with open(ruta_backup, "w") as f:
            resultado = subprocess.run(comando, stdout=f, stderr=subprocess.PIPE,
                                        text=True, env=env)
    except FileNotFoundError:
        print("[ERROR] no se pudo ejecutar mysqldump.")
        return None

    if resultado.returncode != 0:
        print(f"[ERROR] mysqldump terminó con código {resultado.returncode}")
        print(f"  {resultado.stderr.strip()}")
        return None

    tamano_kb = ruta_backup.stat().st_size / 1024
    contenido = ruta_backup.read_text(errors="ignore")
    n_inserts = contenido.count("INSERT INTO")

    print(f"  Tamaño del backup: {tamano_kb:.1f} KB")
    print(f"  Sentencias INSERT encontradas: {n_inserts}")

    if tamano_kb < 1 or n_inserts == 0:
        print("[ERROR] el backup parece vacío o solo contiene estructura, sin datos.")
        print("  NO se continuará con los cambios de esquema hasta resolver esto.")
        return None

    print(f"  [OK] Backup verificado correctamente: {ruta_backup}")
    return ruta_backup


# --- Reglas mapeadas a restricciones ---
# Columnas que deben quedar NOT NULL, con su regla RQ asociada
COLUMNAS_NOT_NULL = {
    "texto": "RQ-01",
    "id_sesion": "RQ-02",
    "fecha_registro": "RQ-03",
    "canal_captura": "RQ-04",
}


def diagnosticar_filas_existentes(engine):
    """Cuenta las filas que ya violan cada regla antes de aplicar las restricciones.

    Verificación de seguridad obligatoria. También desglosa por estado de
    ejecucion_pipeline: si la tabla mezclara filas de la Condición A, aplicar estas
    restricciones aquí destruiría la capacidad de representar sus defectos
    deliberados.

    Args:
        engine (sqlalchemy.engine.Engine): Motor de conexión.

    Returns:
        int: Total de violaciones encontradas.
    """
    total = pd.read_sql(f"SELECT COUNT(*) AS n FROM {TABLA}", engine)["n"].iloc[0]

    nulos = pd.read_sql(f"""
        SELECT
            SUM(id_sesion IS NULL) AS id_sesion_nulo,
            SUM(fecha_registro IS NULL) AS fecha_registro_nulo,
            SUM(canal_captura IS NULL) AS canal_captura_nulo,
            SUM(canal_captura IS NOT NULL
                AND canal_captura NOT IN ('formulario','papel','app','email','desconocido')
            ) AS canal_fuera_catalogo,
            SUM(CHAR_LENGTH(texto) < 5) AS texto_muy_corto
        FROM {TABLA}
    """, engine)

    print(f"\n{'='*60}\n  DIAGNOSTICO DE FILAS EXISTENTES (n={total})\n{'='*60}")
    print(nulos.to_string(index=False))

    # ¿Esta tabla mezcla ejecuciones de Condicion A y Condicion B?
    try:
        por_estado = pd.read_sql(f"""
            SELECT ep.estado, COUNT(*) AS n_filas,
                   SUM(r.id_sesion IS NULL) AS con_id_sesion_nulo,
                   SUM(r.fecha_registro IS NULL) AS con_fecha_nula,
                   SUM(r.canal_captura IS NULL) AS con_canal_nulo
            FROM {TABLA} r
            JOIN ejecucion_pipeline ep ON r.id_ejecucion = ep.id_ejecucion
            GROUP BY ep.estado
        """, engine)
        print(f"\n  Desglose por tipo de ejecución (ejecucion_pipeline.estado):")
        print(por_estado.to_string(index=False))
        if "condicion_a" in por_estado["estado"].astype(str).str.lower().values:
            print(f"\n  [AVISO] ALERTA: esta tabla SI contiene filas de una ejecución con "
                  f"estado 'condicion_a'. Si esas filas tienen nulos (columna "
                  f"'con_*_nulo' > 0 en esa fila), aplicar NOT NULL aquí "
                  f"DESTRUIRÍA la simulación de Condición A. NO continúes con "
                  f"--modo aplicar hasta resolver esto explícitamente.")
    except Exception as e:
        print(f"\n  (No se pudo desglosar por ejecucion_pipeline.estado: {e})")

    total_violaciones = int(nulos.iloc[0].sum())
    return total_violaciones


def inspeccionar_esquema(engine):
    """Lee el esquema real de la tabla desde information_schema.

    Nunca se asumen tipos de columna sin verificarlos contra la base de datos.

    Args:
        engine (sqlalchemy.engine.Engine): Motor de conexión.

    Returns:
        pandas.DataFrame: Nombre, tipo, nulabilidad y tipo completo de cada columna.

    Raises:
        RuntimeError: Si la tabla no existe en la base de datos activa.
    """
    df = pd.read_sql(f"""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_TYPE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = '{TABLA}'
        ORDER BY ORDINAL_POSITION
    """, engine)
    if df.empty:
        raise RuntimeError(
            f"No se encontro la tabla '{TABLA}' en la base de datos activa. "
            f"Verifica el nombre de tabla antes de continuar."
        )
    return df


def construir_sentencias(esquema: pd.DataFrame):
    """Arma la lista de ALTER TABLE a partir del esquema real inspeccionado.

    Si una columna esperada no existe, avisa y la omite en vez de fallar en
    silencio; si ya es NOT NULL, también la omite.

    Args:
        esquema (pandas.DataFrame): Esquema devuelto por inspeccionar_esquema().

    Returns:
        tuple: Lista de pares (sentencia SQL, descripción) y lista de avisos.
    """
    cols_presentes = set(esquema["COLUMN_NAME"])
    sentencias = []
    avisos = []

    for columna, regla in COLUMNAS_NOT_NULL.items():
        if columna not in cols_presentes:
            avisos.append(f"AVISO: columna '{columna}' (regla {regla}) no existe en "
                           f"'{TABLA}' -- se omite. Verifica el nombre real de la columna.")
            continue
        tipo = esquema.loc[esquema["COLUMN_NAME"] == columna, "COLUMN_TYPE"].iloc[0]
        ya_not_null = (esquema.loc[esquema["COLUMN_NAME"] == columna, "IS_NULLABLE"].iloc[0] == "NO")
        if ya_not_null:
            avisos.append(f"  {columna}: ya es NOT NULL, se omite ({regla}).")
            continue
        sentencias.append((
            f"ALTER TABLE {TABLA} MODIFY COLUMN {columna} {tipo} NOT NULL",
            f"{regla}: {columna} obligatorio"
        ))

    if "texto" in cols_presentes:
        sentencias.append((
            f"ALTER TABLE {TABLA} ADD CONSTRAINT chk_texto_longitud "
            f"CHECK (CHAR_LENGTH(texto) >= 5)",
            "RQ-01: longitud mínima de texto"
        ))
    if "canal_captura" in cols_presentes:
        lista = ",".join(f"'{c}'" for c in CANAL_CATALOGO)
        sentencias.append((
            f"ALTER TABLE {TABLA} ADD CONSTRAINT chk_canal_catalogo "
            f"CHECK (canal_captura IN ({lista}))",
            "RQ-06: canal_captura dentro del catálogo definido"
        ))

    return sentencias, avisos


def main():
    """Inspecciona, diagnostica y, solo con --modo aplicar y confirmación, modifica el esquema."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=["preview", "aplicar"], default="preview")
    args = parser.parse_args()

    engine = get_engine()
    print(f"Inspeccionando esquema real de la tabla '{TABLA}'...")
    esquema = inspeccionar_esquema(engine)
    print(esquema.to_string(index=False))

    total_violaciones = diagnosticar_filas_existentes(engine)

    sentencias, avisos = construir_sentencias(esquema)

    if avisos:
        print(f"\n{'='*60}\n  AVISOS\n{'='*60}")
        for a in avisos:
            print(f"  {a}")

    if not sentencias:
        print("\nNo hay restricciones pendientes por agregar -- el esquema ya "
              "cumple todas las reglas mapeadas. Nada que hacer.")
        return

    if args.modo == "aplicar" and total_violaciones > 0:
        print(f"\n{'='*60}")
        print(f"  [AVISO] DETENIDO: hay {total_violaciones} violaciones existentes en la tabla")
        print(f"  (ver el diagnóstico arriba). Aplicar NOT NULL ahora fallaría, o peor,")
        print(f"  podría borrar información si decides limpiar antes sin revisar bien.")
        print(f"  Revisa manualmente esas filas primero -- especialmente si pertenecen")
        print(f"  a una ejecución de Condición A, en cuyo caso este NO es el lugar")
        print(f"  correcto para aplicar estos constraints.")
        print(f"{'='*60}")
        return

    print(f"\n{'='*60}\n  SENTENCIAS {'A APLICAR' if args.modo == 'aplicar' else 'EN PREVIEW (no se ejecuta nada)'}\n{'='*60}")
    for sql, descripcion in sentencias:
        print(f"\n  -- {descripcion}")
        print(f"  {sql};")

    if args.modo == "preview":
        print(f"\n{'='*60}")
        print("  Esto fue solo un PREVIEW. No se modificó la base de datos.")
        print("  Corre con --modo aplicar cuando estés listo: el script genera")
        print("  y verifica un respaldo automático antes de tocar el esquema.")
        print(f"{'='*60}")
        return

    print(f"\n{'='*60}")
    print("  Vas a MODIFICAR EL ESQUEMA de una base de datos real.")
    print("  Generando respaldo automático antes de continuar...")
    print(f"{'='*60}")
    ruta_backup = hacer_backup()
    if ruta_backup is None:
        print("\nNo se pudo generar o verificar el respaldo. ABORTANDO sin "
              "hacer ningún cambio al esquema.")
        return

    respuesta = input(
        f"\nRespaldo verificado en {ruta_backup}. "
        f"¿Continuar y aplicar los cambios de esquema? (si/no): "
    )
    if respuesta.strip().lower() not in ("si", "sí"):
        print("Cancelado por el usuario. No se hicieron cambios.")
        return

    exitosas, fallidas = [], []
    with get_connection() as conn:
        with conn.cursor() as cur:
            for sql, descripcion in sentencias:
                try:
                    cur.execute(sql)
                    exitosas.append(descripcion)
                    print(f"  [OK] {descripcion}")
                except Exception as e:
                    fallidas.append((descripcion, str(e)))
                    print(f"  [ERROR] Error en '{descripcion}': {e}")
                    print(f"    (si el error menciona filas existentes que violan la "
                          f"regla, eso es informacion real sobre datos ya cargados "
                          f"que rompen la regla documentada -- hay que decidir si se "
                          f"corrigen esas filas o se documenta como excepción conocida)")
        conn.commit()

    print(f"\n{'='*60}\n  RESUMEN\n{'='*60}")
    print(f"  Aplicadas con éxito: {len(exitosas)}")
    print(f"  Fallidas: {len(fallidas)}")
    if fallidas:
        print(f"\n  Revisa las fallidas antes de dar esto por cerrado en el documento.")


if __name__ == "__main__":
    main()