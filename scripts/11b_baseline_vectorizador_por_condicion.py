"""Sensibilidad del baseline TF-IDF al vectorizador: un vectorizador ajustado por condición.

El script 11 ajusta un único TfidfVectorizer sobre el entrenamiento de B y lo aplica a
ambas condiciones, lo que puede favorecer a B (el vocabulario es el de B). Este script
repite el baseline con un vectorizador independiente por condición, ajustado sobre el
entrenamiento de esa condición, y estima Δ = F1-macro(B) − F1-macro(A) con el mismo
bootstrap pareado del script 14 (por segmento y por entrevista). Es un análisis de
sensibilidad (plan del 2026-11-02): el resultado principal del baseline sigue siendo el
del script 11. Reutiliza sin cambios la carga, la construcción de conjuntos, el modelo y
el conjunto comparable del script 11; solo cambia dónde se ajusta el vectorizador.

En --modo preview, antes de calcular nada nuevo, verifica que con el vectorizador único
se reproducen exactamente las predicciones originales (outputs/bootstrap_input/), y no
escribe archivos.

Entradas:
    Tablas split_asignacion, segmento_retroalimentacion, segmento_condicion_a,
    augmentation_segmentos, retroalimentacion (solo lectura) y
    outputs/bootstrap_input/baseline_predicciones_{A,B}.csv (verificación).
Salidas (modo completo, outputs/sensibilidad_vectorizador/):
    predicciones_{A,B}_baseline.csv, bootstrap_resultados.csv.
"""

import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

OUT_DIR = Path("outputs/sensibilidad_vectorizador")
REFERENCIA = Path("outputs/bootstrap_input")


def cargar_script(nombre):
    """Importa un script del pipeline como módulo, para reutilizar sus funciones sin copiarlas.

    Args:
        nombre (str): Nombre del archivo en scripts/.

    Returns:
        module: Módulo importado.
    """
    ruta = Path(__file__).resolve().parent / nombre
    spec = importlib.util.spec_from_file_location(ruta.stem.replace("-", "_"), ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def predecir(s11, df_b, df_a, por_condicion):
    """Entrena el baseline en ambas condiciones y predice el conjunto comparable.

    Replica la lógica de entrenar_y_evaluar() del script 11 (mismos hiperparámetros, mismo
    tratamiento de nulo_texto y mismo conjunto comparable), sin escribir archivos.

    Args:
        s11 (module): Script 11 importado.
        df_b (pandas.DataFrame): Conjunto de la condición gobernada.
        df_a (pandas.DataFrame): Conjunto de la condición cruda.
        por_condicion (bool): True, un vectorizador por condición; False, el único de B (script 11).

    Returns:
        dict: Predicciones por condición, con id_segmento, y_true, y_pred y probabilidades.
    """
    train_b = df_b[df_b["split"] == "train"].copy()
    train_a = df_a[df_a["split"] == "train"].copy()
    train_b["texto"] = train_b["texto"].fillna("")
    train_a["texto"] = train_a["texto"].fillna("")  # nulo_texto -> "" en train, como en el 11

    nuevo_vec = lambda: TfidfVectorizer(max_features=5000, ngram_range=(1, 2), min_df=2)
    vec_b = nuevo_vec()
    Xtr_b = vec_b.fit_transform(train_b["texto"])
    if por_condicion:
        vec_a = nuevo_vec()
        Xtr_a = vec_a.fit_transform(train_a["texto"])
    else:
        vec_a = vec_b
        Xtr_a = vec_a.transform(train_a["texto"])

    clf_b = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42).fit(Xtr_b, train_b["etiqueta"])
    clf_a = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42).fit(Xtr_a, train_a["etiqueta"])

    # Conjunto comparable: se excluyen en ambas condiciones los casos con nulo_texto en A
    test_a = df_a[df_a["split"] == "test"].copy()
    nulos = set(test_a[test_a["tipo_error"].apply(s11.es_nulo_texto)]["id_segmento"])
    test_a = test_a[~test_a["id_segmento"].isin(nulos)].copy()
    test_b = df_b[(df_b["split"] == "test") & df_b["id_segmento"].isin(set(test_a["id_segmento"]))].copy()
    test_a["texto"] = test_a["texto"].fillna("")
    test_b["texto"] = test_b["texto"].fillna("")

    salida = {}
    for cond, test, vec, clf in (("A", test_a, vec_a, clf_a), ("B", test_b, vec_b, clf_b)):
        X = vec.transform(test["texto"])
        probs = s11.reordenar_probs(clf, clf.predict_proba(X))
        df = test[["id_segmento"]].copy()
        df["y_true"] = test["etiqueta"].values
        df["y_pred"] = clf.predict(X)
        for i, et in enumerate(s11.ETIQUETAS):
            df[f"prob_{et}"] = probs[:, i]
        salida[cond] = df.reset_index(drop=True)
    return salida


def verificar_reproduccion(pred):
    """Compara las predicciones con vectorizador único contra las originales del script 11.

    Args:
        pred (dict): Predicciones A y B con el vectorizador único.

    Returns:
        bool: True si y_pred coincide en todos los casos y las probabilidades difieren menos de 1e-9.
    """
    ok = True
    for cond in ("A", "B"):
        ref = pd.read_csv(REFERENCIA / f"baseline_predicciones_{cond}.csv").set_index("id_segmento").sort_index()
        nueva = pred[cond].set_index("id_segmento").sort_index()
        iguales = ref.index.equals(nueva.index) and (ref["y_pred"] == nueva["y_pred"]).all()
        cols = [c for c in ref.columns if c.startswith("prob_")]
        dif = float(np.abs(ref[cols].to_numpy() - nueva[cols].to_numpy()).max()) if iguales else np.inf
        print(f"  Condición {cond}: y_pred idénticas {iguales} | máx. diferencia de probabilidad {dif:.1e}")
        ok &= iguales and dif < 1e-9
    return ok


def main():
    """Verifica la reproducción del script 11 y estima la sensibilidad al vectorizador."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--modo", choices=["preview", "completo"], default="preview")
    args = parser.parse_args()

    s11 = cargar_script("11_entrenar_baseline.py")
    s14 = cargar_script("14_bootstrap_pareado.py")
    split, real_b, cond_a_primaria, cond_a_dup_extra, aug = s11.cargar_datos()
    df_b = s11.construir_conjunto(split, real_b, cond_a_primaria, cond_a_dup_extra, aug, "B")
    df_a = s11.construir_conjunto(split, real_b, cond_a_primaria, cond_a_dup_extra, aug, "A")

    print("Verificación: vectorizador único (script 11) frente a las predicciones originales")
    if not verificar_reproduccion(predecir(s11, df_b, df_a, por_condicion=False)):
        raise SystemExit("[ERROR] No se reproducen las predicciones originales; no se continúa.")

    pred = predecir(s11, df_b, df_a, por_condicion=True)
    grupos = s14.grupos_por_entrevista(pred["A"]["id_segmento"])
    filas = []
    for unidad, g in (("segmento", None), ("entrevista", grupos)):
        for excluir in (False, True):
            conservar = ~pred["A"]["id_segmento"].isin(s14.IDS_FUGA).to_numpy() if excluir \
                else np.ones(len(pred["A"]), dtype=bool)
            a = pred["A"][conservar].reset_index(drop=True)
            b = pred["B"][conservar].reset_index(drop=True)
            r, _ = s14.bootstrap_pareado(a, b, grupos=None if g is None else g[conservar])
            filas.append({"vectorizador": "por_condicion", "remuestreo": unidad,
                          "conjunto": "sin_fuga" if excluir else "comparable", **r,
                          "n_entrevistas": len(np.unique(g[conservar])) if g is not None else np.nan})
    tabla = pd.DataFrame(filas)[["vectorizador", "remuestreo", "conjunto", "f1_macro_B", "f1_macro_A",
                                 "diferencia_B_menos_A", "ci95_low", "ci95_high", "p_valor_aprox",
                                 "ee_bootstrap", "emd_80", "n_pares", "n_entrevistas"]]
    print("\nBaseline con vectorizador por condición:")
    print(tabla.to_string(index=False))

    if args.modo == "preview":
        print("\n[preview] No se escribió nada. Ejecutar con --modo completo para guardar las salidas.")
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for cond in ("A", "B"):
        pred[cond].to_csv(OUT_DIR / f"predicciones_{cond}_baseline.csv", index=False)
    tabla.to_csv(OUT_DIR / "bootstrap_resultados.csv", index=False)
    print(f"\n[OK] Salidas en {OUT_DIR}/")


if __name__ == "__main__":
    main()
