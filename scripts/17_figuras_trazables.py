"""Genera la figura de sensibilidad a la semilla, la tabla de calidad y el manifiesto de figuras.

Último paso del pipeline de resultados. Ninguna cifra se transcribe a mano: la
figura sale de las salidas del script 14b (y del 14 para la corrida principal),
la tabla de calidad estructural sale de comparativa_calidad.csv (script 05), y el
manifiesto registra, para cada figura o tabla del documento, el script que la
generó, su último commit y las huellas SHA-256 de sus insumos y de la propia
salida. Verifica además que los insumos de los scripts 14 y 16 coincidan con los
registrados en manifiesto_insumos.csv (script 13b).

Entradas:
    outputs/multisemilla/bootstrap_por_semilla.csv y agregado_por_modelo.csv (14b),
    outputs/bootstrap_resultados.csv (14), outputs/comparativa_calidad.csv (05),
    outputs/manifiesto_insumos.csv (13b) y las figuras de los scripts 14 y 16.
Salidas:
    outputs/sensibilidad_semilla.png, outputs/tabla_calidad_estructural.csv,
    outputs/tabla_calidad_estructural_v2.csv y outputs/manifiesto_figuras.csv.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path("outputs")
MULTI = OUT / "multisemilla"
GI = OUT / "graficos_input"
BI = OUT / "bootstrap_input"
CONFIGS_COLAB = ("beto", "roberta_es", "beto_sin_finetuning")
NOMBRES = {"beto": "BETO con ajuste fino", "bertin_roberta": "BERTIN"}

# Registro de figuras y tablas del documento: salida, script e insumos.
REGISTRO = [
    ("bootstrap_distribuciones.png", "scripts/14_bootstrap_pareado.py",
     [BI / f"{m}_predicciones_{c}.csv" for m in ("baseline", "beto", "roberta", "beto_probing")
      for c in "AB"]),
    ("01_metricas_por_configuracion.png", "scripts/16_generar_graficos.py",
     [GI / "baseline" / "resultados_baseline.csv"]
     + [GI / d / f"resultado_{c}.csv" for d in CONFIGS_COLAB for c in "AB"]),
    ("02_matrices_confusion.png", "scripts/16_generar_graficos.py",
     [GI / d / f"matriz_confusion_{c}.csv" for d in ("baseline",) + CONFIGS_COLAB for c in "AB"]),
    ("03_curvas_kfold_epocas.png", "scripts/16_generar_graficos.py",
     [GI / d / f"kfold_epocas_{c}.csv" for d in ("beto", "roberta_es") for c in "AB"]),
    ("sensibilidad_semilla.png", "scripts/17_figuras_trazables.py",
     [MULTI / "bootstrap_por_semilla.csv", MULTI / "agregado_por_modelo.csv",
      OUT / "bootstrap_resultados.csv"]),
    ("tabla_calidad_estructural.csv", "scripts/17_figuras_trazables.py",
     [OUT / "comparativa_calidad.csv"]),
    ("tabla_calidad_estructural_v2.csv", "scripts/17_figuras_trazables.py",
     [OUT / "comparativa_calidad.csv", OUT / "corpus_final.csv", OUT / "condicion_A.csv"]),
]

CAMPOS_COMUNES = ["text", "num_sesion", "fecha_real"]  # presentes en A y en B


def sha256(ruta):
    """Calcula la huella SHA-256 de un archivo.

    Args:
        ruta (pathlib.Path): Archivo a resumir.

    Returns:
        str: Huella hexadecimal.
    """
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def commit_de(script):
    """Devuelve el último commit que modificó un script y si tiene cambios sin registrar.

    Args:
        script (str): Ruta del script relativa a Code/.

    Returns:
        tuple: Hash corto del commit (str) y True si hay cambios sin registrar.
    """
    commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", script],
                            capture_output=True, text=True).stdout.strip()
    sucio = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", script]).returncode != 0
    return commit, sucio


def figura_sensibilidad_semilla():
    """Grafica Δ F1-macro por semilla, con la corrida principal aparte y una línea en cero."""
    por_semilla = pd.read_csv(MULTI / "bootstrap_por_semilla.csv")
    agregado = pd.read_csv(MULTI / "agregado_por_modelo.csv").set_index("modelo")
    principal = pd.read_csv(OUT / "bootstrap_resultados.csv").set_index("modelo")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharex=True)
    for ax, modelo in zip(axes, ["beto", "bertin_roberta"]):
        datos = por_semilla[por_semilla["modelo"] == modelo].reset_index(drop=True)
        etiquetas = [f"s{s}" for s in datos["semilla"]]
        y = list(range(len(datos)))
        ax.errorbar(datos["diferencia_B_menos_A"], y,
                    xerr=[datos["diferencia_B_menos_A"] - datos["ci95_low"],
                          datos["ci95_high"] - datos["diferencia_B_menos_A"]],
                    fmt="o", color="#2F5597", capsize=3, label="Semilla (IC 95 % bootstrap pareado)")

        # Media multisemilla con IC del bootstrap de dos niveles.
        a = agregado.loc[modelo]
        y_media = len(datos) + 0.8
        ax.errorbar([a["media_dif"]], [y_media],
                    xerr=[[a["media_dif"] - a["ic95_low_2niveles"]], [a["ic95_high_2niveles"] - a["media_dif"]]],
                    fmt="D", color="#2F5597", mfc="white", capsize=3,
                    label="Media de 5 semillas (IC 95 % dos niveles)")

        # Corrida principal: se marca aparte, no entra en el promedio.
        p = principal.loc[modelo]
        y_principal = len(datos) + 2.0
        ax.errorbar([p["diferencia_B_menos_A"]], [y_principal],
                    xerr=[[p["diferencia_B_menos_A"] - p["ci95_low"]], [p["ci95_high"] - p["diferencia_B_menos_A"]]],
                    fmt="s", color="#C55A11", capsize=3, label="Corrida principal (referencia)")

        ax.axvline(0, color="black", linestyle="--", linewidth=1)
        ax.set_yticks(y + [y_media, y_principal])
        ax.set_yticklabels(etiquetas + ["media", "principal"])
        ax.set_title(f"{NOMBRES[modelo]}\nB > A en {int(a['semillas_B_mayor'])}/5 semillas; "
                     f"p dos niveles = {a['p_2niveles']:.3f} (Holm {a['p_2niveles_holm']:.3f})", fontsize=9)
        ax.set_xlabel("Diferencia F1-macro (B − A)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / "sensibilidad_semilla.png", dpi=150)
    plt.close(fig)
    print("[OK] Figura guardada: outputs/sensibilidad_semilla.png")


def tabla_calidad_estructural():
    """Exporta la comparación de calidad estructural A frente a B lista para el documento.

    Las métricas provienen de comparativa_calidad.csv (script 05, 2026-05-19), calculadas
    sobre corpus_final.csv antes de la imputación de fechas del 2026-08-31.
    """
    df = pd.read_csv(OUT / "comparativa_calidad.csv").set_index("dataset")
    fila_b = [i for i in df.index if "B" in i][0]
    fila_a = [i for i in df.index if "A" in i][0]
    metricas = ["completitud", "unicidad", "validez_fecha", "validez_canal", "trazabilidad"]
    tabla = pd.DataFrame({
        "metrica": metricas,
        "condicion_B_pct": [df.loc[fila_b, m] for m in metricas],
        "condicion_A_pct": [df.loc[fila_a, m] for m in metricas],
    })
    tabla["diferencia_B_menos_A_pp"] = (tabla["condicion_B_pct"] - tabla["condicion_A_pct"]).round(1)
    tabla["n_B"] = int(df.loc[fila_b, "n_registros"])
    tabla["n_A"] = int(df.loc[fila_a, "n_registros"])
    tabla.to_csv(OUT / "tabla_calidad_estructural.csv", index=False)
    print("[OK] Tabla guardada: outputs/tabla_calidad_estructural.csv")


def tabla_calidad_estructural_v2():
    """Exporta la tabla de calidad con completitud sobre campos comunes y origen de cada valor.

    No sobrescribe la tabla original. Agrega la completitud calculada sobre los campos
    presentes en ambas condiciones (text, num_sesion, fecha_real), porque la original usa 3
    campos en B y 4 en A. Marca como "por construcción" los valores que el script 05 asigna
    sin medir: validez de canal de B (B no tiene ese campo) y trazabilidad de A y B.
    condicion_A.csv se lee sin convertir "n/a" en nulo, para respetar el valor generado.
    """
    original = pd.read_csv(OUT / "comparativa_calidad.csv").set_index("dataset")
    fila_b = [i for i in original.index if "B" in i][0]
    fila_a = [i for i in original.index if "A" in i][0]
    b = pd.read_csv(OUT / "corpus_final.csv")
    a = pd.read_csv(OUT / "condicion_A.csv", keep_default_na=False, na_values=[""])

    def completitud(df):
        return round(sum(df[c].notna().sum() for c in CAMPOS_COMUNES) / (len(df) * len(CAMPOS_COMUNES)) * 100, 1)

    filas = [
        ("completitud (original: 3 campos en B, 4 en A)", original.loc[fila_b, "completitud"],
         original.loc[fila_a, "completitud"], "medida", "medida"),
        ("completitud (campos comunes: text, num_sesion, fecha_real)", completitud(b),
         completitud(a), "medida", "medida"),
        ("unicidad", original.loc[fila_b, "unicidad"], original.loc[fila_a, "unicidad"],
         "medida", "medida"),
        ("validez_fecha", original.loc[fila_b, "validez_fecha"], original.loc[fila_a, "validez_fecha"],
         "medida", "medida"),
        ("validez_canal", original.loc[fila_b, "validez_canal"], original.loc[fila_a, "validez_canal"],
         "por construcción", "medida"),
        ("trazabilidad", original.loc[fila_b, "trazabilidad"], original.loc[fila_a, "trazabilidad"],
         "por construcción", "por construcción"),
    ]
    tabla = pd.DataFrame(filas, columns=["metrica", "condicion_B_pct", "condicion_A_pct",
                                         "origen_valor_B", "origen_valor_A"])
    tabla["diferencia_B_menos_A_pp"] = (tabla["condicion_B_pct"] - tabla["condicion_A_pct"]).round(1)
    tabla["n_B"] = int(original.loc[fila_b, "n_registros"])
    tabla["n_A"] = int(original.loc[fila_a, "n_registros"])
    tabla.to_csv(OUT / "tabla_calidad_estructural_v2.csv", index=False)
    print("[OK] Tabla guardada: outputs/tabla_calidad_estructural_v2.csv")


def verificar_insumos_13b():
    """Comprueba que los insumos de 14 y 16 coinciden con los registrados por 13b.

    Returns:
        int: Número de insumos cuya huella no coincide con manifiesto_insumos.csv.
    """
    manifiesto = pd.read_csv(OUT / "manifiesto_insumos.csv").set_index("destino")["sha256"]
    discrepancias = 0
    for _, script, insumos in REGISTRO:
        if "17_" in script:
            continue
        for ruta in insumos:
            clave = f"outputs/{ruta.relative_to(OUT)}"
            if clave not in manifiesto.index or manifiesto[clave] != sha256(ruta):
                print(f"[ERROR] {clave} no coincide con manifiesto_insumos.csv")
                discrepancias += 1
    if not discrepancias:
        print("[OK] Insumos de 14 y 16 idénticos a los registrados por 13b")
    return discrepancias


def manifiesto_figuras():
    """Escribe outputs/manifiesto_figuras.csv con script, commit y huellas de cada salida."""
    filas = []
    for salida, script, insumos in REGISTRO:
        commit, sucio = commit_de(script)
        if sucio:
            print(f"[AVISO] {script} tiene cambios sin registrar: el commit no describe la salida")
        filas.append({
            "figura": salida, "script": script, "commit": commit,
            "script_sin_cambios": not sucio,
            "sha256_figura": sha256(OUT / salida),
            "insumos": ";".join(f"{ruta.relative_to(OUT)}:{sha256(ruta)}" for ruta in insumos),
        })
    pd.DataFrame(filas).to_csv(OUT / "manifiesto_figuras.csv", index=False)
    print(f"[OK] Manifiesto guardado: outputs/manifiesto_figuras.csv ({len(filas)} salidas)")


def main():
    """Genera la figura y la tabla nuevas y registra todas las salidas en el manifiesto."""
    figura_sensibilidad_semilla()
    tabla_calidad_estructural()
    tabla_calidad_estructural_v2()
    discrepancias = verificar_insumos_13b()
    manifiesto_figuras()
    sys.exit(1 if discrepancias else 0)


if __name__ == "__main__":
    main()
