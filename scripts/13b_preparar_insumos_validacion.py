"""Organiza las salidas de los modelos en las carpetas que esperan los scripts 14, 15 y 16.

Sustituye la copia y el renombrado manual de archivos, que era frágil (nombres
distintos entre baseline y transformers, riesgo de copiar una versión _preview) y
no dejaba trazabilidad. Deja un manifiesto con la huella SHA-256 de cada archivo,
que permite demostrar qué archivo exacto alimentó cada resultado. La regla de
nombres vive solo en construir_mapeo(), que también usa 00c_verificar_entorno.py.

Entradas:
    --origen-baseline: salidas de 11_entrenar_baseline.py (por defecto, outputs/).
    --origen-colab: copia local de MyDrive/working_paper/resultados_colab/, con
    las subcarpetas beto/, roberta_es/ y beto_sin_finetuning/.
Salidas:
    outputs/bootstrap_input/*.csv, outputs/graficos_input/<modelo>/*.csv y
    outputs/manifiesto_insumos.csv (destino, origen, sha256, filas, fecha).
"""

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent           # .../Code
DESTINO = RAIZ / "outputs"
CONDICIONES = ("A", "B")

# Carpetas de Colab (nombre de subcarpeta en Drive)
COLAB_FT = {"beto": "beto", "roberta": "roberta_es"}          # con fine-tuning
COLAB_PROBING = "beto_sin_finetuning"

# Nombre del archivo de predicciones principales en cada carpeta de Colab.
# En roberta_es/ las predicciones principales se guardaron como
# roberta_predicciones_{c}.csv; no confundir con multisemilla/.
PREDICCIONES_COLAB = {
    "beto": "predicciones_{c}.csv",
    "roberta_es": "roberta_predicciones_{c}.csv",
    "beto_sin_finetuning": "predicciones_{c}.csv",
}


def construir_mapeo(origen_baseline: Path, origen_colab: Path) -> list[tuple[Path, Path]]:
    """Construye la lista explícita de pares (origen, destino).

    Toda regla de nombres de archivo vive aquí.

    Args:
        origen_baseline (pathlib.Path): Carpeta con las salidas del baseline.
        origen_colab (pathlib.Path): Copia local de resultados_colab/.

    Returns:
        list[tuple[pathlib.Path, pathlib.Path]]: Pares (origen, destino).
    """
    m = []
    bi = DESTINO / "bootstrap_input"
    gi = DESTINO / "graficos_input"

    for c in CONDICIONES:
        # --- Insumos del bootstrap y del análisis de errores ---
        m.append((origen_baseline / f"predicciones_{c}_baseline.csv",
                  bi / f"baseline_predicciones_{c}.csv"))
        for prefijo, carpeta in COLAB_FT.items():
            m.append((origen_colab / carpeta / PREDICCIONES_COLAB[carpeta].format(c=c),
                      bi / f"{prefijo}_predicciones_{c}.csv"))
        m.append((origen_colab / COLAB_PROBING / PREDICCIONES_COLAB[COLAB_PROBING].format(c=c),
                  bi / f"beto_probing_predicciones_{c}.csv"))

        # --- Insumos de los gráficos ---
        m.append((origen_baseline / f"matriz_confusion_{c}.csv",
                  gi / "baseline" / f"matriz_confusion_{c}.csv"))
        for carpeta in [*COLAB_FT.values(), COLAB_PROBING]:
            for archivo in (f"resultado_{c}.csv", f"matriz_confusion_{c}.csv"):
                m.append((origen_colab / carpeta / archivo, gi / carpeta / archivo))
        for carpeta in COLAB_FT.values():                    # solo fine-tuning tiene k-fold
            archivo = f"kfold_epocas_{c}.csv"
            m.append((origen_colab / carpeta / archivo, gi / carpeta / archivo))

    m.append((origen_baseline / "resultados_baseline.csv",
              gi / "baseline" / "resultados_baseline.csv"))
    return m


def sha256(ruta: Path) -> str:
    """Calcula la huella SHA-256 de un archivo, leyéndolo por bloques.

    Args:
        ruta (pathlib.Path): Archivo a resumir.

    Returns:
        str: Huella hexadecimal.
    """
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def validar_contenido(origen: Path) -> str | None:
    """Aplica chequeos mínimos de contenido a un archivo de origen.

    Rechaza las salidas de modo preview y, en los archivos de predicciones, exige
    las columnas id_segmento, y_true e y_pred.

    Args:
        origen (pathlib.Path): Archivo a validar.

    Returns:
        str | None: Mensaje de error, o None si el archivo es válido.
    """
    if "_preview" in origen.name:
        return "es una salida de modo preview, no la definitiva"
    if "predicciones_" in origen.name:
        cols = set(pd.read_csv(origen, nrows=0).columns)
        faltan = {"id_segmento", "y_true", "y_pred"} - cols
        if faltan:
            return f"faltan columnas {sorted(faltan)}"
    return None


def main():
    """Valida todos los orígenes y, en modo completo, copia los archivos y escribe el manifiesto."""
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--origen-colab", required=True, type=Path)
    p.add_argument("--origen-baseline", default=DESTINO, type=Path)
    p.add_argument("--modo", choices=["preview", "completo"], default="preview")
    args = p.parse_args()

    mapeo = construir_mapeo(args.origen_baseline.expanduser().resolve(),
                            args.origen_colab.expanduser().resolve())
    print(f"Modo: {args.modo.upper()}  |  {len(mapeo)} archivos a organizar\n")

    problemas, filas_manifiesto = [], []
    for origen, destino in mapeo:
        rel = destino.relative_to(RAIZ)
        if not origen.exists():
            problemas.append(f"NO EXISTE  {origen}")
            print(f"  [ERROR] {rel}  <- no encontrado")
            continue
        error = validar_contenido(origen)
        if error:
            problemas.append(f"{origen}: {error}")
            print(f"  [ERROR] {rel}  <- {error}")
            continue

        n_filas = len(pd.read_csv(origen))
        print(f"  [OK] {rel}  <- {origen.parent.name}/{origen.name} ({n_filas} filas)")
        filas_manifiesto.append({
            "destino": str(rel), "origen": str(origen), "sha256": sha256(origen),
            "filas": n_filas,
            "modificado_origen": datetime.fromtimestamp(origen.stat().st_mtime).isoformat(timespec="seconds"),
        })

    if problemas:
        print(f"\n[ERROR] {len(problemas)} problema(s). No se copió nada. Resuélvelos y vuelve a ejecutar.")
        sys.exit(1)

    # Coherencia: todas las predicciones deben cubrir el mismo conjunto de prueba
    tamanos = {f["filas"] for f in filas_manifiesto if "predicciones" in f["destino"]}
    if len(tamanos) > 1:
        print(f"\n[AVISO] Los archivos de predicciones tienen tamaños distintos: {sorted(tamanos)}")
        print("   Revisa antes de continuar: deberían cubrir el mismo conjunto de prueba.")

    if args.modo == "preview":
        print("\n[OK] PREVIEW OK — nada fue escrito. Ejecuta con --modo completo para copiar.")
        return

    for f in filas_manifiesto:
        destino = RAIZ / f["destino"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f["origen"], destino)          # copy2 conserva fecha de modificación
    df = pd.DataFrame(filas_manifiesto)
    df.insert(0, "fecha_copia", datetime.now().isoformat(timespec="seconds"))
    df.to_csv(DESTINO / "manifiesto_insumos.csv", index=False)
    print(f"\n[OK] {len(df)} archivos copiados. Manifiesto: outputs/manifiesto_insumos.csv")


if __name__ == "__main__":
    main()