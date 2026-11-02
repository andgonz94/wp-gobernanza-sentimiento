"""Verifica el entorno local antes de ejecutar las validaciones.

Comprueba, en orden: que se usa el Python del entorno virtual; que las librerías
del perfil local se importan, con sus versiones; que existe .env y la conexión a
MySQL funciona; que el corpus conserva los 799 segmentos activos auditados; y que
existen los insumos que organiza 13b_preparar_insumos_validacion.py.

Entradas:
    Code/.env, la base de datos y los destinos de construir_mapeo() de 13b.
Salidas:
    outputs/entorno_verificado.txt (evidencia para la bitácora). Código de
    salida 0 si el entorno está listo, 1 si hay problemas.
"""

import importlib
import importlib.metadata
import importlib.util
import platform
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent          # .../Code
sys.path.insert(0, str(RAIZ))

LIBRERIAS = {                                           # nombre de import -> distribución
    "pandas": "pandas", "numpy": "numpy", "sklearn": "scikit-learn",
    "scipy": "scipy", "matplotlib": "matplotlib", "sqlalchemy": "SQLAlchemy",
    "pymysql": "PyMySQL", "dotenv": "python-dotenv", "anthropic": "anthropic",
}

# Conteo auditado esperado (Briefing, sección 2): 799 segmentos activos
CONTEO_ESPERADO_ACTIVOS = 799



def cargar_mapeo_13b():
    """Obtiene los destinos de insumos desde construir_mapeo() del script 13b.

    Una sola fuente de verdad: 13b define qué archivos organiza y dónde los deja.
    Las rutas de origen no importan aquí; solo se usan los destinos.

    Returns:
        list[pathlib.Path]: Rutas de destino, relativas a Code/.
    """
    ruta = RAIZ / "scripts" / "13b_preparar_insumos_validacion.py"
    spec = importlib.util.spec_from_file_location("insumos_13b", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return [destino.relative_to(RAIZ) for _, destino in modulo.construir_mapeo(RAIZ, RAIZ)]


registro = []          # líneas para el archivo de evidencia
fallos = 0


def log(msg=""):
    """Imprime un mensaje y lo guarda en el registro de evidencia.

    Args:
        msg (str): Mensaje.
    """
    print(msg)
    registro.append(msg)


def ok(msg):
    """Registra una comprobación superada.

    Args:
        msg (str): Mensaje.
    """
    log(f"   [OK] {msg}")


def fallo(msg):
    """Registra una comprobación fallida y aumenta el contador de fallos.

    Args:
        msg (str): Mensaje.
    """
    global fallos
    fallos += 1
    log(f"   [ERROR] {msg}")


def verificar_interprete():
    """Comprueba que el intérprete pertenece a un entorno virtual."""
    log("\n[1] Intérprete de Python")
    log(f"  Versión   : {platform.python_version()} ({platform.machine()})")
    log(f"  Ejecutable: {sys.executable}")
    if sys.prefix != sys.base_prefix:
        ok("Entorno virtual activo")
    else:
        fallo("NO hay entorno virtual activo. Ejecuta: source .venv/bin/activate")


def verificar_librerias():
    """Comprueba que cada librería del perfil local se importa y registra su versión."""
    log("\n[2] Librerías del perfil local")
    for modulo, nombre in LIBRERIAS.items():
        try:
            importlib.import_module(modulo)
            ok(f"{nombre:<14} {importlib.metadata.version(nombre)}")
        except (ImportError, importlib.metadata.PackageNotFoundError):
            fallo(f"{nombre:<14} NO instalada")


def verificar_bd():
    """Comprueba el archivo .env, la conexión a MySQL y el conteo de segmentos activos."""
    log("\n[3] Configuración y conexión a MySQL")
    if not (RAIZ / ".env").exists():
        fallo(f"No existe {RAIZ / '.env'}")
        return
    ok(".env encontrado")
    try:
        import sqlalchemy as sa
        from config.db_connection import get_engine
        with get_engine().connect() as conn:
            version = conn.execute(sa.text("SELECT VERSION()")).scalar()
            ok(f"Conexión exitosa (MySQL {version})")

            log("\n[4] Integridad del corpus (trazabilidad)")
            activos = conn.execute(sa.text(
                "SELECT COUNT(*) FROM segmento_retroalimentacion "
                "WHERE COALESCE(flag_excluir, 0) = 0"
            )).scalar()
            if activos == CONTEO_ESPERADO_ACTIVOS:
                ok(f"Segmentos activos: {activos} (coincide con lo auditado)")
            else:
                fallo(f"Segmentos activos: {activos} (esperado {CONTEO_ESPERADO_ACTIVOS})"
                      " -> revisar la migración de la BD")
    except Exception as e:
        fallo(f"Error de BD: {type(e).__name__}: {e}")


def verificar_entradas():
    """Comprueba que existen todos los insumos que organiza el script 13b."""
    log("\n[5] Insumos de validación (mapeo de 13b)")
    archivos = cargar_mapeo_13b()
    faltantes = [a for a in archivos if not (RAIZ / a).exists()]
    if faltantes:
        fallo(f"Faltan {len(faltantes)} de {len(archivos)} insumos")
        for a in faltantes:
            log(f"       - {a}")
    else:
        ok(f"{len(archivos)} insumos presentes")


def main():
    """Ejecuta las verificaciones, guarda la evidencia y termina con el código de salida."""
    log(f"Verificación de entorno — {datetime.now():%Y-%m-%d %H:%M:%S}")
    log(f"Raíz del proyecto: {RAIZ}")
    verificar_interprete()
    verificar_librerias()
    verificar_bd()
    verificar_entradas()

    log("\n" + ("ENTORNO LISTO" if fallos == 0 else f" {fallos} problema(s) por resolver"))

    salida = RAIZ / "outputs" / "entorno_verificado.txt"
    salida.parent.mkdir(exist_ok=True)
    salida.write_text("\n".join(registro), encoding="utf-8")
    print(f"\n[OK] Evidencia guardada en: {salida}")
    sys.exit(0 if fallos == 0 else 1)


if __name__ == "__main__":
    main()