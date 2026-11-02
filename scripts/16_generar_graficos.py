"""Genera las figuras de métricas, matrices de confusión y curvas de validación cruzada.

Produce las figuras del reporte metodológico a partir de los resultados guardados
por los scripts de entrenamiento de cada modelo, organizados por el script 13b.

Entradas:
    outputs/graficos_input/<modelo>/: resultados_baseline.csv o resultado_{A,B}.csv,
    matriz_confusion_{A,B}.csv y, para BETO y BERTIN, kfold_epocas_{A,B}.csv.
Salidas:
    outputs/01_metricas_por_configuracion.png, outputs/02_matrices_confusion.png
    y outputs/03_curvas_kfold_epocas.png.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUTA_DATOS = Path("outputs/graficos_input")
RUTA_SALIDA = Path("outputs")
RUTA_SALIDA.mkdir(exist_ok=True)

AZUL_B = "#2F5496"      # Condición B (gobernada)
NARANJA_A = "#D9822B"   # Condición A (no gobernada)
ETIQUETAS = ["muy_positivo", "positivo", "levemente_positivo", "neutral", "negativo"]

plt.rcParams.update({
    "font.size": 11, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
})

# Nombre visible en los gráficos -> carpeta real en RUTA_DATOS
MODELOS = {
    "Baseline": "baseline",
    "BETO sin ajuste": "beto_sin_finetuning",
    "BETO con ajuste fino": "beto",
    "BERTIN": "roberta_es",
}
# Modelos que sí tienen curvas de k-fold (fine-tuning con transformers)
MODELOS_CON_KFOLD = {"BETO con ajuste fino": "beto", "BERTIN": "roberta_es"}


# --- 1. CARGA DE DATOS DESDE CSV REALES ---

def cargar_metricas(nombre_modelo, carpeta):
    """Carga las métricas de evaluación de un modelo desde sus archivos de resultados.

    Args:
        nombre_modelo (str): Nombre descriptivo del modelo.
        carpeta (str): Carpeta donde se encuentran los archivos de resultados del modelo.

    Returns:
        dict: Métricas de evaluación organizadas por condición experimental.
    """
    ruta = RUTA_DATOS / carpeta
    resultado = {}

    archivo_baseline = ruta / "resultados_baseline.csv"
    if archivo_baseline.exists():
        # Formato ancho: una sola fila con columnas *_B / *_A
        df = pd.read_csv(archivo_baseline)
        for cond in ["B", "A"]:
            resultado[cond] = {
                "f1_macro": df[f"f1_macro_{cond}"].iloc[0],
                "log_loss": df[f"log_loss_{cond}"].iloc[0],
                "pr_auc_macro": df[f"pr_auc_macro_{cond}"].iloc[0],
            }
        return resultado

    # Formato largo: un archivo por condición (resultado_A.csv / resultado_B.csv)
    for cond in ["B", "A"]:
        archivo = ruta / f"resultado_{cond}.csv"
        if not archivo.exists():
            print(f"No encontrado: {archivo} — se omite {nombre_modelo} ({cond})")
            continue
        df = pd.read_csv(archivo)
        resultado[cond] = {
            "f1_macro": df["f1_macro"].iloc[0],
            "log_loss": df["log_loss"].iloc[0],
            "pr_auc_macro": df["pr_auc_macro"].iloc[0],
        }
    return resultado


def cargar_matriz_confusion(carpeta, condicion):
    """Carga la matriz de confusión de un modelo para una condición dada.

    Args:
        carpeta (str): Carpeta donde se encuentran los archivos de resultados del modelo.
        condicion (str): Condición experimental a la que corresponde la matriz.

    Returns:
        numpy.ndarray or None: Matriz de confusión ordenada por etiqueta, o None si el archivo no existe.
    """
    archivo = RUTA_DATOS / carpeta / f"matriz_confusion_{condicion}.csv"
    if not archivo.exists():
        return None
    df = pd.read_csv(archivo, index_col=0)
    return df.loc[ETIQUETAS, ETIQUETAS].values  # fuerza el mismo orden en todos los modelos


def cargar_curvas_kfold(carpeta):
    """Carga las curvas de desempeño por época obtenidas mediante validación cruzada.

    Args:
        carpeta (str): Carpeta donde se encuentran los archivos de resultados del modelo.

    Returns:
        dict: Curvas de desempeño organizadas por condición experimental.
    """
    resultado = {}
    for cond in ["B", "A"]:
        archivo = RUTA_DATOS / carpeta / f"kfold_epocas_{cond}.csv"
        if not archivo.exists():
            print(f"No encontrado: {archivo}")
            continue
        resultado[cond] = pd.read_csv(archivo)  # columnas: epoca, f1_macro_promedio, f1_macro_std
    return resultado


# --- 2. GRÁFICO 1 — F1-macro / Log Loss / PR-AUC por configuración × condición ---

def graficar_metricas_por_configuracion():
    """Genera y guarda el gráfico comparativo de métricas por configuración y condición.

    Returns:
        None
    """
    filas = []
    for nombre, carpeta in MODELOS.items():
        metricas = cargar_metricas(nombre, carpeta)
        for cond, vals in metricas.items():
            filas.append({"modelo": nombre, "condicion": cond, **vals})

    if not filas:
        print("No se encontró ningún archivo de métricas — revisa RUTA_DATOS.")
        return
    df = pd.DataFrame(filas)

    modelos_presentes = [m for m in MODELOS if m in df["modelo"].unique()]
    x = np.arange(len(modelos_presentes))
    w = 0.35

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    specs = [("f1_macro", "F1-macro (mayor = mejor)"),
             ("log_loss", "Log Loss (menor = mejor)"),
             ("pr_auc_macro", "PR-AUC macro (mayor = mejor)")]

    for ax, (col, titulo) in zip(axes, specs):
        vals_b = [df[(df.modelo == m) & (df.condicion == "B")][col].values[0]
                  if not df[(df.modelo == m) & (df.condicion == "B")].empty else np.nan
                  for m in modelos_presentes]
        vals_a = [df[(df.modelo == m) & (df.condicion == "A")][col].values[0]
                  if not df[(df.modelo == m) & (df.condicion == "A")].empty else np.nan
                  for m in modelos_presentes]
        barras_b = ax.bar(x - w/2, vals_b, w, label="Condición B (gobernada)", color=AZUL_B)
        barras_a = ax.bar(x + w/2, vals_a, w, label="Condición A (no gobernada)", color=NARANJA_A)
        ax.set_title(titulo, pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(modelos_presentes, fontsize=9, rotation=20, ha="right")
        for barras in (barras_b, barras_a):
            for b in barras:
                h = b.get_height()
                if not np.isnan(h):
                    ax.annotate(f"{h:.3f}", (b.get_x() + b.get_width()/2, h),
                                ha="center", va="bottom", fontsize=7.5)
        ax.margins(y=0.18)

    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, 1.28), ncol=2, frameon=False, fontsize=10)
    plt.tight_layout(rect=[0, 0, 1, 0.90])
    ruta = RUTA_SALIDA / "01_metricas_por_configuracion.png"
    plt.savefig(ruta, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"[OK] Guardado: {ruta}")


# --- 3. GRÁFICO 2 — Matrices de confusión (heatmap), una fila por modelo disponible ---

def graficar_matrices_confusion():
    """Genera y guarda el gráfico de matrices de confusión por modelo disponible.

    Returns:
        None
    """
    modelos_disponibles = []
    for nombre, carpeta in MODELOS.items():
        mB = cargar_matriz_confusion(carpeta, "B")
        mA = cargar_matriz_confusion(carpeta, "A")
        if mB is not None and mA is not None:
            modelos_disponibles.append((nombre, mB, mA))

    if not modelos_disponibles:
        print("No se encontró ninguna matriz de confusión — revisa RUTA_DATOS.")
        return

    n = len(modelos_disponibles)
    fig, axes = plt.subplots(n, 2, figsize=(10, 4.3 * n))
    if n == 1:
        axes = axes.reshape(1, 2)

    etiquetas_cortas = ["muy_pos.", "positivo", "lev._pos.", "neutral", "negativo"]

    for fila, (nombre, mB, mA) in enumerate(modelos_disponibles):
        for col, (matriz, titulo_cond) in enumerate([(mB, "Condición B"), (mA, "Condición A")]):
            ax = axes[fila, col]
            im = ax.imshow(matriz, cmap="Blues")
            ax.set_xticks(range(5)); ax.set_xticklabels(etiquetas_cortas, rotation=40, ha="right", fontsize=7)
            ax.set_yticks(range(5)); ax.set_yticklabels(etiquetas_cortas, fontsize=7)
            # Filas: etiqueta real; columnas: etiqueta predicha (convención de
            # sklearn.metrics.confusion_matrix, con la que se guardaron las matrices).
            ax.set_ylabel("Etiqueta real", fontsize=8)
            ax.set_xlabel("Etiqueta predicha", fontsize=8)
            ax.set_title(f"{nombre} — {titulo_cond}", fontsize=10, fontweight="bold")
            vmax = matriz.max()
            for i in range(5):
                for j in range(5):
                    valor = int(matriz[i, j])
                    color = "white" if valor > vmax * 0.55 else "black"
                    ax.text(j, i, str(valor), ha="center", va="center", color=color,
                            fontsize=8, fontweight="bold" if i == j else "normal")

    plt.tight_layout()
    ruta = RUTA_SALIDA / "02_matrices_confusion.png"
    plt.savefig(ruta, dpi=170, bbox_inches="tight")
    plt.close()
    print(f"[OK] Guardado: {ruta}")


# --- 4. GRÁFICO 3 — Curvas de F1-macro por época (k-fold), BETO y BERTIN ---

def graficar_curvas_kfold():
    """Genera y guarda el gráfico de curvas de validación cruzada por modelo.

    Returns:
        None
    """
    modelos_disponibles = []
    for nombre, carpeta in MODELOS_CON_KFOLD.items():
        curvas = cargar_curvas_kfold(carpeta)
        if "B" in curvas and "A" in curvas:
            modelos_disponibles.append((nombre, curvas))

    if not modelos_disponibles:
        print("No se encontró ningún archivo kfold_epocas_*.csv — revisa RUTA_DATOS.")
        return

    n = len(modelos_disponibles)
    fig, axes = plt.subplots(1, n, figsize=(6.2 * n, 5), sharey=True)
    if n == 1:
        axes = [axes]

    for ax, (nombre, curvas) in zip(axes, modelos_disponibles):
        for cond, color, etiqueta in [("B", AZUL_B, "Condición B (gobernada)"),
                                        ("A", NARANJA_A, "Condición A (no gobernada)")]:
            df = curvas[cond]
            m = df["f1_macro_promedio"].values
            s = df["f1_macro_std"].values
            ep = df["epoca"].values
            ax.plot(ep, m, "-o", color=color, label=etiqueta, linewidth=2)
            ax.fill_between(ep, m - s, m + s, color=color, alpha=0.18)
        ax.set_title(f"{nombre} — F1-macro promedio (k-fold) ± 1 desv. est.")
        ax.set_xlabel("Época")
        ax.set_xticks(curvas["B"]["epoca"].values)

    axes[0].set_ylabel("F1-macro")
    axes[0].legend(loc="lower right", fontsize=9)
    plt.suptitle("Curva de validación cruzada usada para elegir el número de épocas",
                 fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    ruta = RUTA_SALIDA / "03_curvas_kfold_epocas.png"
    plt.savefig(ruta, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"[OK] Guardado: {ruta}")


# --- MAIN ---

if __name__ == "__main__":
    if not RUTA_DATOS.exists():
        print(f"No existe {RUTA_DATOS}. Crea la carpeta y coloca los CSV según la "
              f"estructura documentada en docs/guia_operativa_scripts.md.")
    else:
        print("Generando Gráfico 1 (métricas por configuración)...")
        graficar_metricas_por_configuracion()
        print("\nGenerando Gráfico 2 (matrices de confusión)...")
        graficar_matrices_confusion()
        print("\nGenerando Gráfico 3 (curvas k-fold)...")
        graficar_curvas_kfold()