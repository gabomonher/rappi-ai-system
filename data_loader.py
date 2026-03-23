"""
data_loader.py — Carga, limpieza y unificación de esquema.

Hallazgos del EDA que justifican cada paso:
  - 963 filas exactamente duplicadas en RAW_INPUT_METRICS (~15%)
  - Lead Penetration con valores hasta 393.9 (definición: ratio [0,1])
  - 113 zonas fantasma en RAW_ORDERS (sin absolutamente ningún valor)
  - 131 zonas sin L0W_ROLL pero con historial — NO eliminar aquí;
    son zonas que dejaron de operar gradualmente y son útiles para
    detect_sustained_decline y trend_analysis en insights_engine.py
  - RAW_ORDERS tiene columnas L8W..L0W (sin _ROLL) → unificar esquema
"""

import pandas as pd

# ---------------------------------------------------------------------------
# Constantes exportadas — usadas también por tools.py, insights_engine.py
# ---------------------------------------------------------------------------

WEEK_COLS = [
    "L8W_ROLL", "L7W_ROLL", "L6W_ROLL", "L5W_ROLL",
    "L4W_ROLL", "L3W_ROLL", "L2W_ROLL", "L1W_ROLL", "L0W_ROLL",
]

_ID_VARS = ["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "ZONE_PRIORITIZATION", "METRIC"]

_ORDERS_RENAME = {
    "L8W": "L8W_ROLL", "L7W": "L7W_ROLL", "L6W": "L6W_ROLL",
    "L5W": "L5W_ROLL", "L4W": "L4W_ROLL", "L3W": "L3W_ROLL",
    "L2W": "L2W_ROLL", "L1W": "L1W_ROLL", "L0W": "L0W_ROLL",
}


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def load_data(file_path: str = "data/rappi_data.xlsx") -> tuple:
    """
    Carga y limpia RAW_INPUT_METRICS y RAW_ORDERS del Excel de Rappi.

    Returns
    -------
    (df_metrics, df_orders, df_long)
        df_metrics : RAW_INPUT_METRICS limpio (post-dedup + clip Lead Penetration)
        df_orders  : RAW_ORDERS con esquema _ROLL, sin zonas fantasma
                     ⚠️ Mantiene zonas sin L0W_ROLL (historial útil)
        df_long    : melt de df_metrics, filas con value=NaN eliminadas
    """

    # ══════════════════════════════════════════════════════════
    # BLOQUE A — df_metrics (RAW_INPUT_METRICS)
    # ══════════════════════════════════════════════════════════

    # A1. Cargar
    df_metrics = pd.read_excel(file_path, sheet_name="RAW_INPUT_METRICS", engine="openpyxl")

    # A2. Eliminar duplicados exactos ANTES del melt
    #     EDA: 963 filas (~15%) exactamente iguales — artefacto de exportación
    #     Hacerlo antes del melt evita multiplicar el problema por 9
    df_metrics = df_metrics.drop_duplicates()

    # A3. Corregir outliers de Lead Penetration
    #     EDA: valores hasta 393.9; definición de métrica es ratio [0, 1]
    mask_lp = df_metrics["METRIC"] == "Lead Penetration"
    df_metrics.loc[mask_lp, WEEK_COLS] = (
        df_metrics.loc[mask_lp, WEEK_COLS].clip(upper=1.0)
    )

    # A4. Normalizar nombres de zona y ciudad
    df_metrics["ZONE"] = df_metrics["ZONE"].str.strip().str.title()
    df_metrics["CITY"] = df_metrics["CITY"].str.strip().str.title()

    # A5. Crear df_long (formato largo para análisis temporal)
    df_long = df_metrics.melt(
        id_vars=_ID_VARS,
        value_vars=WEEK_COLS,
        var_name="week",
        value_name="value",
    )
    df_long = df_long.dropna(subset=["value"])

    # ══════════════════════════════════════════════════════════
    # BLOQUE B — df_orders (RAW_ORDERS)
    # ══════════════════════════════════════════════════════════

    # B1. Cargar
    df_orders = pd.read_excel(file_path, sheet_name="RAW_ORDERS", engine="openpyxl")

    # B2. Unificar esquema: L8W..L0W → L8W_ROLL..L0W_ROLL
    #     CRÍTICO: sin este paso explain_growth falla silenciosamente
    df_orders.rename(columns=_ORDERS_RENAME, inplace=True)

    # B3. Eliminar SOLO las zonas fantasma (sin ningún valor en ninguna semana)
    #     EDA: 113 zonas existen en el dataset pero con todas las semanas NaN
    df_orders = df_orders.dropna(how="all", subset=WEEK_COLS)

    # B4. ⚠️ NO eliminar zonas sin L0W_ROLL
    #     EDA: 131 zonas sin L0W_ROLL tienen historial útil (53 con ≥3 semanas)
    #     → útiles para detect_sustained_decline y trend_analysis
    #     → cada función que necesite solo zonas activas filtra L0W_ROLL internamente

    # B5. Normalizar nombres de zona y ciudad
    df_orders["ZONE"] = df_orders["ZONE"].str.strip().str.title()
    df_orders["CITY"] = df_orders["CITY"].str.strip().str.title()

    # ══════════════════════════════════════════════════════════
    # VALIDACIÓN FINAL
    # ══════════════════════════════════════════════════════════
    print(f"df_metrics : {df_metrics.shape}  — esperado: ~(11610, 15)")
    print(f"df_orders  : {df_orders.shape}   — esperado: ~(1129, 13)")
    print(f"df_long    : {df_long.shape}     — esperado: ~(103863, 8)")
    print(f"Métricas únicas     : {df_metrics['METRIC'].nunique()}  — esperado: 13")
    print(f"Países únicos       : {df_metrics['COUNTRY'].nunique()} — esperado: 9")
    lp_max = df_metrics.loc[mask_lp, "L0W_ROLL"].max()
    print(f"Lead Penetration máx: {lp_max:.4f} — esperado: ≤1.0")
    print(f"Zonas activas en orders (con L0W_ROLL): {df_orders['L0W_ROLL'].notnull().sum()} — esperado: ~998")
    print(f"Zonas sin L0W_ROLL pero con historial : {df_orders['L0W_ROLL'].isnull().sum()} — esperado: ~131")

    return df_metrics, df_orders, df_long


# ---------------------------------------------------------------------------
# Ejecutar directamente para validación
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Cargando y limpiando datos...")
    print("=" * 60)
    df_metrics, df_orders, df_long = load_data()
    print("\n✅ data_loader.py — carga y limpieza completa")
