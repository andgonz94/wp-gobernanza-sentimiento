"""Verifica la conexión a la base de datos y lista las tablas disponibles.

Prueba rápida de que las credenciales y el motor de base de datos están bien
configurados antes de correr el resto del pipeline.

Entradas:
    Code/.env y la base de datos.
Salidas:
    Solo salida en consola.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.db_connection import test_connection, get_engine
import pandas as pd


def main():
    """Ejecuta la prueba de conexión a la base de datos e imprime las tablas disponibles.

    Returns:
        None
    """
    print("=" * 50)
    print("Test de conexión — Proyecto NLP")
    print("=" * 50)
    ok = test_connection()
    if not ok:
        print("\nRevisa tu archivo .env y que MySQL esté corriendo.")
        sys.exit(1)
    engine = get_engine()
    print("\nTablas disponibles:")
    tablas = pd.read_sql("SHOW TABLES", engine)
    print(tablas.to_string(index=False))


if __name__ == "__main__":
    main()
