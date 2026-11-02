"""Inspecciona el esquema real de la base de datos en el diccionario de datos de MySQL.

Imprime, para cada tabla relevante, sus columnas con tipo de dato, nulabilidad,
claves y atributos extra. Sirve para verificar nombres de columna antes de escribir
código que toque la base de datos.

Entradas:
    La base de datos (information_schema).
Salidas:
    Solo salida en consola.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.db_connection import get_engine
import pandas as pd

TABLAS = ["sesion", "retroalimentacion", "ejecucion_pipeline", "detalle_error"]

engine = get_engine()
for tabla in TABLAS:
    df = pd.read_sql(
        f"SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY, EXTRA "
        f"FROM information_schema.COLUMNS "
        f"WHERE TABLE_SCHEMA = 'retroalimentacion_estudiantil' "
        f"AND TABLE_NAME = '{tabla}' "
        f"ORDER BY ORDINAL_POSITION",
        engine
    )
    print(f"\n{'='*50}")
    print(f"  Tabla: {tabla}")
    print('='*50)
    print(df.to_string(index=False))
