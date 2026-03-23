"""
tools.py — 6 funciones analíticas + 2 helpers de robustez.

Los DataFrames se inyectan como globals desde app.py:
    import tools
    tools.df_metrics = df_metrics
    tools.df_orders  = df_orders
    tools.df_long    = df_long
"""

import difflib
import pandas as pd

# ---------------------------------------------------------------------------
# DataFrames inyectados desde app.py — no acceder antes de inyectar
# ---------------------------------------------------------------------------
df_metrics: pd.DataFrame = None  # type: ignore
df_orders: pd.DataFrame = None   # type: ignore
df_long: pd.DataFrame = None     # type: ignore

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

VALID_METRICS = [
    "Retail SST > SS CVR", "Restaurants SST > SS CVR", "Gross Profit UE",
    "Restaurants SS > ATC CVR", "Non-Pro PTC > OP", "% PRO Users Who Breakeven",
    "Pro Adoption (Last Week Status)", "MLTV Top Verticals Adoption",
    "% Restaurants Sessions With Optimal Assortment", "Lead Penetration",
    "Restaurants Markdowns / GMV", "Perfect Orders", "Turbo Adoption",
]

WEEK_COLS = [
    "L8W_ROLL", "L7W_ROLL", "L6W_ROLL", "L5W_ROLL",
    "L4W_ROLL", "L3W_ROLL", "L2W_ROLL", "L1W_ROLL", "L0W_ROLL",
]

WEEK_LABEL_MAP = {
    "L8W_ROLL": "Sem -8", "L7W_ROLL": "Sem -7", "L6W_ROLL": "Sem -6",
    "L5W_ROLL": "Sem -5", "L4W_ROLL": "Sem -4", "L3W_ROLL": "Sem -3",
    "L2W_ROLL": "Sem -2", "L1W_ROLL": "Sem -1", "L0W_ROLL": "Sem 0",
}

COUNTRY_MAP = {
    "MEXICO": "MX", "MÉXICO": "MX",
    "COLOMBIA": "CO", "BRASIL": "BR", "BRAZIL": "BR",
    "ARGENTINA": "AR", "CHILE": "CL",
    "PERU": "PE", "PERÚ": "PE",
    "ECUADOR": "EC", "COSTA RICA": "CR", "URUGUAY": "UY",
}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def normalize_country(country: str) -> str:
    """Normaliza nombre de país a código de 2 letras (ej. 'México' → 'MX')."""
    if not country:
        return country
    c = country.upper().strip()
    return COUNTRY_MAP.get(c, c)

def fuzzy_match_metric(metric: str) -> str | None:
    """Corrige typos del LLM usando fuzzy matching. Retorna None si no hay match."""
    if metric in VALID_METRICS:
        return metric
    matches = difflib.get_close_matches(metric, VALID_METRICS, n=1, cutoff=0.6)
    return matches[0] if matches else None


def safe_result(df: pd.DataFrame, max_rows: int = 15) -> str:
    """Limita filas y convierte a markdown para no quemar tokens del LLM."""
    return df.head(max_rows).to_markdown(index=False)


def _error_df(msg: str) -> pd.DataFrame:
    """Helper interno para retornar un DataFrame con error descriptivo."""
    return pd.DataFrame({"error": [msg]})


# ---------------------------------------------------------------------------
# FUNCIÓN 1 — top_zones
# ---------------------------------------------------------------------------

def top_zones(
    metric: str,
    n: int = 5,
    country: str = None,
    city: str = None,
    ascending: bool = True,
    week: str = "L0W_ROLL",
) -> pd.DataFrame:
    """Retorna las N zonas con mejor o peor desempeño en una métrica."""
    metric = fuzzy_match_metric(metric)
    if metric is None:
        return _error_df(f"Métrica no reconocida. Válidas: {VALID_METRICS}")
    try:
        df = df_metrics[df_metrics["METRIC"] == metric].copy()
        if country:
            df = df[df["COUNTRY"] == normalize_country(country)]
        if city:
            df = df[df["CITY"] == city.title()]

        df = df.dropna(subset=[week])

        if df.empty:
            return _error_df(f"Sin datos para {metric} con los filtros aplicados.")

        df = df.sort_values(week, ascending=ascending).head(n)
        cols = ["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "ZONE_PRIORITIZATION", week]
        return df[cols].reset_index(drop=True)
    except Exception as e:
        return _error_df(f"Error en top_zones: {str(e)}")


# ---------------------------------------------------------------------------
# FUNCIÓN 2 — compare_segments
# ---------------------------------------------------------------------------

def compare_segments(
    metric: str,
    segment: str,
    country: str = None,
    week: str = "L0W_ROLL",
) -> pd.DataFrame:
    """Compara el valor promedio de una métrica entre segmentos."""
    metric = fuzzy_match_metric(metric)
    if metric is None:
        return _error_df(f"Métrica no reconocida. Válidas: {VALID_METRICS}")
    try:
        valid_segments = ["ZONE_TYPE", "ZONE_PRIORITIZATION", "COUNTRY", "CITY"]
        if segment not in valid_segments:
            return _error_df(f"Segmento inválido '{segment}'. Válidos: {valid_segments}")

        df = df_metrics[df_metrics["METRIC"] == metric].copy()
        if country:
            df = df[df["COUNTRY"] == normalize_country(country)]

        df = df.dropna(subset=[week])

        if df.empty:
            return _error_df(f"Sin datos para {metric} con los filtros aplicados.")

        result = (
            df.groupby(segment)[week]
            .agg(["mean", "min", "max", "count"])
            .reset_index()
        )
        result.columns = [segment, "Promedio", "Mínimo", "Máximo", "Zonas"]
        result = result.sort_values("Promedio", ascending=False)
        result[["Promedio", "Mínimo", "Máximo"]] = result[["Promedio", "Mínimo", "Máximo"]].round(4)
        return result.reset_index(drop=True)
    except Exception as e:
        return _error_df(f"Error en compare_segments: {str(e)}")


# ---------------------------------------------------------------------------
# FUNCIÓN 3 — trend_analysis
# ---------------------------------------------------------------------------

def trend_analysis(
    metric: str,
    zone: str = None,
    country: str = None,
    city: str = None,
    weeks: int = 8,
) -> pd.DataFrame:
    """Muestra la evolución semana a semana de una métrica."""
    metric = fuzzy_match_metric(metric)
    if metric is None:
        return _error_df(f"Métrica no reconocida. Válidas: {VALID_METRICS}")
    try:
        df = df_long[df_long["METRIC"] == metric].copy()
        if zone:
            df = df[df["ZONE"] == zone.title()]
        if country:
            df = df[df["COUNTRY"] == normalize_country(country)]
        if city:
            df = df[df["CITY"] == city.title()]

        if df.empty:
            return _error_df(f"Sin datos para {metric} con los filtros aplicados.")

        # Zona específica vs promedio grupal
        if zone:
            result = df[["week", "value"]].copy()
            result = result.groupby("week")["value"].mean().reset_index()  # por si hay duplicados residuales
        else:
            result = df.groupby("week")["value"].mean().reset_index()

        # Mantener solo las últimas `weeks` semanas en orden cronológico
        week_order = WEEK_COLS  # L8W_ROLL (más vieja) → L0W_ROLL (más reciente)
        last_n = week_order[-weeks:] if weeks < len(week_order) else week_order
        result = result[result["week"].isin(last_n)]
        result["_order"] = result["week"].map({w: i for i, w in enumerate(week_order)})
        result = result.sort_values("_order").drop(columns="_order")

        # Agregar labels legibles y % cambio
        result["week_label"] = result["week"].map(WEEK_LABEL_MAP)
        result["value"] = result["value"].round(4)
        result["pct_change_vs_prev"] = result["value"].pct_change().round(4)

        return result[["week", "week_label", "value", "pct_change_vs_prev"]].reset_index(drop=True)
    except Exception as e:
        return _error_df(f"Error en trend_analysis: {str(e)}")


# ---------------------------------------------------------------------------
# FUNCIÓN 4 — find_zones
# ---------------------------------------------------------------------------

def find_zones(
    high_metrics: list[str] = None,
    low_metrics: list[str] = None,
    country: str = None,
    threshold_pct: float = 0.75,
) -> pd.DataFrame:
    """Encuentra zonas con métricas simultáneamente altas Y/O bajas."""
    try:
        # Validar métricas con fuzzy matching
        all_metrics = []
        resolved_high, resolved_low = [], []

        for m in (high_metrics or []):
            matched = fuzzy_match_metric(m)
            if matched is None:
                return _error_df(f"Métrica no reconocida: '{m}'. Válidas: {VALID_METRICS}")
            resolved_high.append(matched)
            all_metrics.append(matched)

        for m in (low_metrics or []):
            matched = fuzzy_match_metric(m)
            if matched is None:
                return _error_df(f"Métrica no reconocida: '{m}'. Válidas: {VALID_METRICS}")
            resolved_low.append(matched)
            all_metrics.append(matched)

        if not all_metrics:
            return _error_df("Debes especificar al menos una métrica en high_metrics o low_metrics.")

        df = df_metrics[df_metrics["METRIC"].isin(all_metrics)].copy()
        if country:
            df = df[df["COUNTRY"] == normalize_country(country)]

        pivot = df.pivot_table(
            index=["COUNTRY", "CITY", "ZONE"],
            columns="METRIC",
            values="L0W_ROLL",
        ).reset_index()

        if pivot.empty:
            return _error_df("Sin datos para las métricas y filtros indicados.")

        def _apply_filters(pv, thresh):
            mask = pd.Series(True, index=pv.index)
            for m in resolved_high:
                if m in pv.columns:
                    cutoff = pv[m].quantile(thresh)
                    mask &= pv[m] >= cutoff
            for m in resolved_low:
                if m in pv.columns:
                    cutoff = pv[m].quantile(1 - thresh)
                    mask &= pv[m] <= cutoff
            return pv[mask]

        result = _apply_filters(pivot, threshold_pct)

        # Si vacío, reintentar con threshold reducido
        nota = None
        if result.empty and threshold_pct > 0.60:
            result = _apply_filters(pivot, 0.60)
            nota = "Se usó threshold reducido (0.60) porque no hubo resultados con 0.75"

        if result.empty:
            return _error_df("No se encontraron zonas que cumplan todas las condiciones.")

        cols = ["COUNTRY", "CITY", "ZONE"] + [m for m in all_metrics if m in result.columns]
        result = result[cols].reset_index(drop=True)

        # Redondear valores numéricos
        for m in all_metrics:
            if m in result.columns:
                result[m] = result[m].round(4)

        if nota:
            result["nota"] = nota

        return result
    except Exception as e:
        return _error_df(f"Error en find_zones: {str(e)}")


# ---------------------------------------------------------------------------
# FUNCIÓN 5 — aggregate_by
# ---------------------------------------------------------------------------

def aggregate_by(
    metric: str,
    group_by: str = "COUNTRY",
    country: str = None,
    week: str = "L0W_ROLL",
) -> pd.DataFrame:
    """Calcula el promedio de una métrica agrupado por una dimensión."""
    metric = fuzzy_match_metric(metric)
    if metric is None:
        return _error_df(f"Métrica no reconocida. Válidas: {VALID_METRICS}")
    try:
        valid_groups = ["COUNTRY", "CITY", "ZONE_TYPE", "ZONE_PRIORITIZATION"]
        if group_by not in valid_groups:
            return _error_df(f"group_by inválido '{group_by}'. Válidos: {valid_groups}")

        df = df_metrics[df_metrics["METRIC"] == metric].copy()
        if country:
            df = df[df["COUNTRY"] == normalize_country(country)]

        df = df.dropna(subset=[week])

        if df.empty:
            return _error_df(f"Sin datos para {metric} con los filtros aplicados.")

        result = (
            df.groupby(group_by)[week]
            .agg(["mean", "min", "max", "count"])
            .reset_index()
        )
        result.columns = [group_by, "Promedio", "Mínimo", "Máximo", "Zonas"]
        result = result.sort_values("Promedio", ascending=False)
        result[["Promedio", "Mínimo", "Máximo"]] = result[["Promedio", "Mínimo", "Máximo"]].round(4)
        return result.reset_index(drop=True)
    except Exception as e:
        return _error_df(f"Error en aggregate_by: {str(e)}")


# ---------------------------------------------------------------------------
# FUNCIÓN 6 — explain_growth
# ---------------------------------------------------------------------------

def explain_growth(
    country: str = None,
    top_n: int = 5,
    weeks: int = 5,
) -> pd.DataFrame:
    """Identifica zonas con mayor crecimiento en órdenes y sus métricas."""
    try:
        start_week = f"L{weeks}W_ROLL"
        if start_week not in WEEK_COLS:
            return _error_df(f"Semana {start_week} no existe. weeks debe ser 1-8.")

        # Filtrar órdenes con datos válidos en ambas puntas
        df_o = df_orders.dropna(subset=[start_week, "L0W_ROLL"]).copy()
        if country:
            df_o = df_o[df_o["COUNTRY"] == normalize_country(country)]

        if df_o.empty:
            return _error_df("Sin datos de órdenes para calcular crecimiento.")

        # Calcular % crecimiento
        df_o["orders_growth_pct"] = (
            (df_o["L0W_ROLL"] - df_o[start_week]) / df_o[start_week] * 100
        ).round(2)

        # Top N con mayor crecimiento positivo
        top = df_o.nlargest(top_n, "orders_growth_pct")[
            ["COUNTRY", "CITY", "ZONE", "orders_growth_pct"]
        ]

        if top.empty:
            return _error_df("No se encontraron zonas con crecimiento positivo.")

        # Extraer métricas de esas zonas
        metrics_pivot = df_metrics.pivot_table(
            index=["COUNTRY", "CITY", "ZONE"],
            columns="METRIC",
            values="L0W_ROLL",
        ).reset_index()

        result = top.merge(metrics_pivot, on=["COUNTRY", "CITY", "ZONE"], how="left")

        # Eliminar zonas sin métricas (226 zonas en orders no tienen métricas — EDA)
        metric_cols = [c for c in result.columns if c not in ["COUNTRY", "CITY", "ZONE", "orders_growth_pct"]]
        result = result.dropna(subset=metric_cols, thresh=max(1, len(metric_cols) // 2))

        if result.empty:
            return _error_df("Las zonas con mayor crecimiento no tienen métricas disponibles.")

        # Redondear columnas de métricas (reutiliza metric_cols definido arriba)
        for col in metric_cols:
            result[col] = result[col].round(4)

        return result.reset_index(drop=True)
    except Exception as e:
        return _error_df(f"Error en explain_growth: {str(e)}")


# ---------------------------------------------------------------------------
# TESTS — ejecutar directamente para validar
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from data_loader import load_data

    # Inyectar DataFrames como globals
    _df_m, _df_o, _df_l = load_data("data/rappi_data.xlsx")

    # Inyectar en el módulo (NO como variables locales)
    import tools as _self
    _self.df_metrics = _df_m
    _self.df_orders  = _df_o
    _self.df_long    = _df_l

    SEP = "=" * 60

    def run_test(name, fn, *args, **kwargs):
        print(f"\n{SEP}")
        print(f"TEST: {name}")
        print(SEP)
        result = fn(*args, **kwargs)
        print(f"  Shape: {result.shape}")
        print(f"  Columnas: {list(result.columns)}")
        print(result.head(3).to_markdown(index=False))
        return result

    # Test 1: top_zones con nombre correcto
    r1 = run_test(
        "top_zones('Perfect Orders', country='CO', n=5)",
        _self.top_zones, "Perfect Orders", n=5, country="CO",
    )

    # Test 2: top_zones con typo — fuzzy match debe funcionar
    r2 = run_test(
        "top_zones('perfect orders', country='CO', n=5)  ← TYPO",
        _self.top_zones, "perfect orders", n=5, country="CO",
    )

    # Verificar que fuzzy match produce el mismo resultado
    print(f"\n{'─' * 60}")
    if "error" not in r2.columns and r1.shape == r2.shape:
        print("✅ Fuzzy match funciona: 'perfect orders' → 'Perfect Orders'")
    else:
        print("❌ Fuzzy match falló — r1 y r2 no coinciden")

    # Test 3: compare_segments
    run_test(
        "compare_segments('Lead Penetration', 'ZONE_TYPE', country='MX')",
        _self.compare_segments, "Lead Penetration", "ZONE_TYPE", country="MX",
    )

    # Test 4: trend_analysis
    r4 = run_test(
        "trend_analysis('Gross Profit UE', country='BR', weeks=8)",
        _self.trend_analysis, "Gross Profit UE", country="BR", weeks=8,
    )
    if "week_label" in r4.columns:
        print("✅ Columna week_label presente")
    else:
        print("❌ Falta columna week_label")

    # Test 5: find_zones multivariable
    run_test(
        "find_zones(high=['Lead Penetration'], low=['Perfect Orders'], country='AR')",
        _self.find_zones,
        high_metrics=["Lead Penetration"],
        low_metrics=["Perfect Orders"],
        country="AR",
    )

    # Test 6: aggregate_by
    r6 = run_test(
        "aggregate_by('Turbo Adoption', group_by='COUNTRY')",
        _self.aggregate_by, "Turbo Adoption", group_by="COUNTRY",
    )

    # Test 7: explain_growth
    r7 = run_test(
        "explain_growth(top_n=5, weeks=5)",
        _self.explain_growth, top_n=5, weeks=5,
    )
    # Verificar que no hay zonas con todo NaN en métricas
    if "error" not in r7.columns:
        metric_cols = [c for c in r7.columns if c not in ["COUNTRY", "CITY", "ZONE", "orders_growth_pct"]]
        all_nan_rows = r7[metric_cols].isnull().all(axis=1).sum()
        if all_nan_rows == 0:
            print("✅ explain_growth: 0 zonas con todas las métricas NaN")
        else:
            print(f"❌ explain_growth: {all_nan_rows} zonas con todas las métricas NaN")

    print(f"\n{SEP}")
    print("🎉 Todos los tests ejecutados. Verifica los resultados arriba.")
    print(SEP)
