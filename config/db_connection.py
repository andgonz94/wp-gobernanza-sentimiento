"""Centraliza la conexión a la base de datos MySQL del proyecto.

Todos los scripts del pipeline obtienen aquí su conexión, con credenciales leídas
del archivo .env de Code/ (nunca versionado).

Entradas:
    Code/.env con DB_HOST, DB_PORT, DB_NAME, DB_USER y DB_PASSWORD.
Salidas:
    Motor de SQLAlchemy (get_engine) o conexión PyMySQL (get_connection).
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import sqlalchemy as sa
import pymysql

_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

def _get_credentials():
    """Lee las credenciales de la base de datos desde las variables de entorno.

    Returns:
        dict: Valores de DB_HOST, DB_PORT, DB_NAME, DB_USER y DB_PASSWORD.

    Raises:
        EnvironmentError: Si falta alguna variable distinta de DB_PASSWORD.
    """
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    creds = {k: os.getenv(k) for k in required}
    missing = [k for k, v in creds.items() if not v and k != "DB_PASSWORD"]
    if missing:
        raise EnvironmentError(f"Faltan variables en .env: {missing}")
    return creds

def get_engine():
    """Crea un motor de SQLAlchemy con el driver PyMySQL.

    Returns:
        sqlalchemy.engine.Engine: Motor con pool_pre_ping activado.
    """
    c = _get_credentials()
    url = sa.URL.create(
        drivername="mysql+pymysql",
        username=c["DB_USER"],
        password=c["DB_PASSWORD"],
        host=c["DB_HOST"],
        port=int(c["DB_PORT"]),
        database=c["DB_NAME"],
    )
    return sa.create_engine(url, pool_pre_ping=True)

def get_connection():
    """Abre una conexión PyMySQL con cursor de diccionarios y codificación utf8mb4.

    Returns:
        pymysql.connections.Connection: Conexión abierta; el llamador debe cerrarla.
    """
    c = _get_credentials()
    return pymysql.connect(
        host=c["DB_HOST"],
        port=int(c["DB_PORT"]),
        db=c["DB_NAME"],
        user=c["DB_USER"],
        password=c["DB_PASSWORD"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

def test_connection():
    """Comprueba la conexión e imprime la versión del servidor y la base activa.

    Returns:
        bool: True si la conexión funciona, False si no.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            version = conn.execute(sa.text("SELECT VERSION()")).scalar()
            database = conn.execute(sa.text("SELECT DATABASE()")).scalar()
        print(f"[OK] Conexión exitosa")
        print(f"    Servidor MySQL : {version}")
        print(f"    Base de datos  : {database}")
        return True
    except Exception as e:
        print(f"[ERROR] Error de conexión: {e}")
        return False

if __name__ == "__main__":
    test_connection()
