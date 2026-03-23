"""
insights_engine.py — Motor de insights determinísticos (sin LLM).

5 funciones de detección + 1 orquestadora.
Cada hallazgo es un dict con:
  {type, zone, city, country, metric, magnitude, direction, description, data}
"""

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

WEEK_COLS = [
    "L8W_ROLL", "L7W_ROLL", "L6W_ROLL", "L5W_ROLL",
    "L4W_ROLL", "L3W_ROLL", "L2W_ROLL", "L1W_ROLL", "L0W_ROLL",
]

BUSINESS_PAIRS = [
    ("Lead Penetration", "Perfect Orders"),
    ("Pro Adoption (Last Week Status)", "% PRO Users Who Breakeven"),
    ("Restaurants SST > SS CVR", "Restaurants SS > ATC CVR"),
    ("% Restaurants Sessions With Optimal Assortment", "Restaurants SS > ATC CVR"),
    ("Turbo Adoption", "MLTV Top Verticals Adoption"),
    ("Non-Pro PTC > OP", "Gross Profit UE"),
    ("Lead Penetration", "Restaurants Markdowns / GMV"),
]


# ---------------------------------------------------------------------------
# 1. detect_anomalies
# ---------------------------------------------------------------------------

def detect_anomalies(df_long: pd.DataFrame, threshold: float = 0.10) -> list[dict]:
    """
    Compara L0W_ROLL vs L1W_ROLL por (zone, metric).
    Si abs(pct_change) > threshold → anomalía.
    Si <3 resultados: reintentar con threshold=0.05.
    Retorna top 10 por magnitud absoluta.
    """
    try:
        # Pivotar: filas = (zone, metric, country, city), columnas = week
        curr = df_long[df_long["week"] == "L0W_ROLL"][["COUNTRY", "CITY", "ZONE", "METRIC", "value"]].copy()
        prev = df_long[df_long["week"] == "L1W_ROLL"][["COUNTRY", "CITY", "ZONE", "METRIC", "value"]].copy()

        merged = curr.merge(prev, on=["COUNTRY", "CITY", "ZONE", "METRIC"], suffixes=("_L0", "_L1"))
        merged = merged.dropna(subset=["value_L0", "value_L1"])
        merged = merged[merged["value_L1"] != 0]  # evitar división por cero

        merged["pct_change"] = (merged["value_L0"] - merged["value_L1"]) / merged["value_L1"]

        def _filter(df, thresh):
            return df[df["pct_change"].abs() > thresh].copy()

        anomalies = _filter(merged, threshold)

        # Reintentar con threshold reducido si pocos resultados
        if len(anomalies) < 3 and threshold > 0.05:
            anomalies = _filter(merged, 0.05)

        anomalies["abs_change"] = anomalies["pct_change"].abs()
        anomalies = anomalies.nlargest(10, "abs_change")

        findings = []
        for _, row in anomalies.iterrows():
            direction = "subió" if row["pct_change"] > 0 else "cayó"
            findings.append({
                "type": "anomaly",
                "zone": row["ZONE"],
                "city": row["CITY"],
                "country": row["COUNTRY"],
                "metric": row["METRIC"],
                "magnitude": round(row["pct_change"] * 100, 2),
                "direction": direction,
                "description": f"{row['METRIC']} {direction} {abs(row['pct_change'])*100:.1f}% en {row['ZONE']} ({row['COUNTRY']})",
                "data": {"L0W": round(row["value_L0"], 4), "L1W": round(row["value_L1"], 4)},
            })

        return findings
    except Exception as e:
        print(f"⚠️ Error en detect_anomalies: {e}")
        return []


# ---------------------------------------------------------------------------
# 2. detect_sustained_decline
# ---------------------------------------------------------------------------

def detect_sustained_decline(df_long: pd.DataFrame, n_weeks: int = 3) -> list[dict]:
    """
    Verifica si los últimos n_weeks valores son consecutivamente decrecientes.
    Calcula caída total % desde inicio de la tendencia.
    """
    try:
        # Usar las últimas n_weeks+1 semanas (necesitamos n_weeks comparaciones)
        last_weeks = WEEK_COLS[-(n_weeks + 1):]

        df = df_long[df_long["week"].isin(last_weeks)].copy()

        # Pivotar: filas = (zone, metric, country, city), columnas = week
        pivot = df.pivot_table(
            index=["COUNTRY", "CITY", "ZONE", "METRIC"],
            columns="week",
            values="value",
        ).reset_index()

        # Solo conservar filas con datos en todas las semanas relevantes
        pivot = pivot.dropna(subset=last_weeks)

        if pivot.empty:
            return []

        findings = []
        for _, row in pivot.iterrows():
            values = [row[w] for w in last_weeks]

            # Verificar si es consecutivamente decreciente
            is_declining = all(values[i] > values[i + 1] for i in range(len(values) - 1))

            if is_declining and values[0] != 0:
                total_decline = (values[-1] - values[0]) / values[0]
                findings.append({
                    "type": "sustained_decline",
                    "zone": row["ZONE"],
                    "city": row["CITY"],
                    "country": row["COUNTRY"],
                    "metric": row["METRIC"],
                    "magnitude": round(total_decline * 100, 2),
                    "direction": "cayó",
                    "description": f"{row['METRIC']} cayó {abs(total_decline)*100:.1f}% en {n_weeks} semanas consecutivas en {row['ZONE']} ({row['COUNTRY']})",
                    "data": {w: round(v, 4) for w, v in zip(last_weeks, values)},
                })

        # Top 10 por magnitud absoluta
        findings.sort(key=lambda x: abs(x["magnitude"]), reverse=True)
        return findings[:10]
    except Exception as e:
        print(f"⚠️ Error en detect_sustained_decline: {e}")
        return []


# ---------------------------------------------------------------------------
# 3. detect_benchmarking_gaps
# ---------------------------------------------------------------------------

def detect_benchmarking_gaps(df_metrics: pd.DataFrame, week: str = "L0W_ROLL") -> list[dict]:
    """
    Agrupa por (COUNTRY, ZONE_TYPE, METRIC).
    Zonas >1.5 IQR por debajo de la mediana = outlier negativo.
    """
    try:
        df = df_metrics.dropna(subset=[week]).copy()

        findings = []
        grouped = df.groupby(["COUNTRY", "ZONE_TYPE", "METRIC"])

        for (country, zone_type, metric), group in grouped:
            if len(group) < 4:  # necesitamos suficientes datos para IQR
                continue

            q1 = group[week].quantile(0.25)
            q3 = group[week].quantile(0.75)
            iqr = q3 - q1
            median = group[week].median()
            lower_bound = median - 1.5 * iqr

            outliers = group[group[week] < lower_bound]

            for _, row in outliers.iterrows():
                gap = row[week] - median
                gap_pct = (gap / median * 100) if median != 0 else 0

                findings.append({
                    "type": "benchmarking_gap",
                    "zone": row["ZONE"],
                    "city": row["CITY"],
                    "country": country,
                    "metric": metric,
                    "magnitude": round(gap_pct, 2),
                    "direction": "bajo",
                    "description": f"{row['ZONE']} está {abs(gap_pct):.1f}% por debajo de la mediana en {metric} ({country}, {zone_type})",
                    "data": {"valor": round(row[week], 4), "mediana": round(median, 4), "lower_bound": round(lower_bound, 4)},
                })

        findings.sort(key=lambda x: abs(x["magnitude"]), reverse=True)
        return findings[:10]
    except Exception as e:
        print(f"⚠️ Error en detect_benchmarking_gaps: {e}")
        return []


# ---------------------------------------------------------------------------
# 4. detect_correlations
# ---------------------------------------------------------------------------

def detect_correlations(df_metrics: pd.DataFrame, week: str = "L0W_ROLL", min_corr: float = 0.65) -> list[dict]:
    """
    Solo evalúa los pares en BUSINESS_PAIRS.
    No calcula todas las combinaciones posibles.
    """
    try:
        df = df_metrics.dropna(subset=[week]).copy()

        # Pivotar: filas = zona, columnas = metric, valores = week
        pivot = df.pivot_table(
            index=["COUNTRY", "CITY", "ZONE"],
            columns="METRIC",
            values=week,
        ).reset_index()

        findings = []
        for metric_a, metric_b in BUSINESS_PAIRS:
            if metric_a not in pivot.columns or metric_b not in pivot.columns:
                continue

            pair_data = pivot[[metric_a, metric_b]].dropna()
            if len(pair_data) < 10:
                continue

            corr = pair_data[metric_a].corr(pair_data[metric_b])

            if abs(corr) >= min_corr:
                direction = "positiva" if corr > 0 else "negativa"
                findings.append({
                    "type": "correlation",
                    "zone": "Global",
                    "city": "N/A",
                    "country": "ALL",
                    "metric": f"{metric_a} ↔ {metric_b}",
                    "magnitude": round(corr * 100, 2),
                    "direction": direction,
                    "description": f"Correlación {direction} ({corr:.2f}) entre {metric_a} y {metric_b}",
                    "data": {"metric_a": metric_a, "metric_b": metric_b, "correlation": round(corr, 4)},
                })

        findings.sort(key=lambda x: abs(x["magnitude"]), reverse=True)
        return findings
    except Exception as e:
        print(f"⚠️ Error en detect_correlations: {e}")
        return []


# ---------------------------------------------------------------------------
# 5. detect_opportunities
# ---------------------------------------------------------------------------

def detect_opportunities(df_metrics: pd.DataFrame, df_orders: pd.DataFrame, week: str = "L0W_ROLL") -> list[dict]:
    """
    Zonas con orders creciendo >5% (L4W_ROLL vs L0W_ROLL) Y ≥2 métricas bajo promedio.
    """
    try:
        # Calcular crecimiento de órdenes
        df_o = df_orders.dropna(subset=["L4W_ROLL", "L0W_ROLL"]).copy()
        df_o = df_o[df_o["L4W_ROLL"] != 0]
        df_o["orders_growth"] = (df_o["L0W_ROLL"] - df_o["L4W_ROLL"]) / df_o["L4W_ROLL"]
        growing = df_o[df_o["orders_growth"] > 0.05][["COUNTRY", "CITY", "ZONE", "orders_growth"]]

        if growing.empty:
            return []

        # Pivotar métricas
        df_m = df_metrics.dropna(subset=[week]).copy()
        pivot = df_m.pivot_table(
            index=["COUNTRY", "CITY", "ZONE"],
            columns="METRIC",
            values=week,
        ).reset_index()

        # Promedios por país para comparación
        country_means = df_m.groupby(["COUNTRY", "METRIC"])[week].mean()

        # Merge zonas con crecimiento + sus métricas
        merged = growing.merge(pivot, on=["COUNTRY", "CITY", "ZONE"], how="inner")

        if merged.empty:
            return []

        metric_cols = [c for c in merged.columns if c not in ["COUNTRY", "CITY", "ZONE", "orders_growth"]]

        findings = []
        for _, row in merged.iterrows():
            below_avg_count = 0
            below_metrics = []

            for m in metric_cols:
                if pd.isna(row[m]):
                    continue
                try:
                    avg = country_means.loc[(row["COUNTRY"], m)]
                    if row[m] < avg:
                        below_avg_count += 1
                        below_metrics.append(m)
                except KeyError:
                    continue

            if below_avg_count >= 2:
                findings.append({
                    "type": "opportunity",
                    "zone": row["ZONE"],
                    "city": row["CITY"],
                    "country": row["COUNTRY"],
                    "metric": ", ".join(below_metrics[:3]),
                    "magnitude": round(row["orders_growth"] * 100, 2),
                    "direction": "subió",
                    "description": f"{row['ZONE']} ({row['COUNTRY']}) crece {row['orders_growth']*100:.1f}% en órdenes pero tiene {below_avg_count} métricas bajo promedio",
                    "data": {"orders_growth_pct": round(row["orders_growth"] * 100, 2), "below_avg_metrics": below_metrics[:5]},
                })

        findings.sort(key=lambda x: abs(x["magnitude"]), reverse=True)
        return findings[:10]
    except Exception as e:
        print(f"⚠️ Error en detect_opportunities: {e}")
        return []


# ---------------------------------------------------------------------------
# 6. run_all_insights — orquestadora
# ---------------------------------------------------------------------------

def run_all_insights(df_metrics: pd.DataFrame, df_long: pd.DataFrame, df_orders: pd.DataFrame) -> list[dict]:
    """
    Ejecuta las 5 funciones de detección, combina, ordena por magnitud absoluta.
    Retorna top 10 hallazgos.
    """
    findings = []
    findings.extend(detect_anomalies(df_long))
    findings.extend(detect_sustained_decline(df_long))
    findings.extend(detect_benchmarking_gaps(df_metrics))
    findings.extend(detect_correlations(df_metrics))
    findings.extend(detect_opportunities(df_metrics, df_orders))

    # Ordenar por magnitud absoluta descendente y retornar top 10
    return sorted(findings, key=lambda x: abs(x.get("magnitude", 0)), reverse=True)[:10]


# ---------------------------------------------------------------------------
# TESTS — ejecutar directamente para validar
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from data_loader import load_data

    df_metrics, df_orders, df_long = load_data("data/rappi_data.xlsx")

    SEP = "=" * 60

    print(f"\n{SEP}")
    print("🔍 Ejecutando motor de insights...")
    print(SEP)

    # Ejecutar cada detector individualmente para ver conteo
    anomalies = detect_anomalies(df_long)
    print(f"\n1. detect_anomalies:        {len(anomalies)} hallazgos")

    declines = detect_sustained_decline(df_long)
    print(f"2. detect_sustained_decline: {len(declines)} hallazgos")

    gaps = detect_benchmarking_gaps(df_metrics)
    print(f"3. detect_benchmarking_gaps: {len(gaps)} hallazgos")

    corrs = detect_correlations(df_metrics)
    print(f"4. detect_correlations:      {len(corrs)} hallazgos")

    opps = detect_opportunities(df_metrics, df_orders)
    print(f"5. detect_opportunities:     {len(opps)} hallazgos")

    total = len(anomalies) + len(declines) + len(gaps) + len(corrs) + len(opps)
    print(f"\n   Total bruto: {total} hallazgos")

    # Ejecutar orquestadora
    print(f"\n{SEP}")
    print("📊 run_all_insights → Top 10")
    print(SEP)

    top_findings = run_all_insights(df_metrics, df_long, df_orders)

    for i, f in enumerate(top_findings, 1):
        print(f"\n{'─' * 60}")
        print(f"#{i} [{f['type'].upper()}] | Magnitud: {f['magnitude']}%")
        print(f"   Zona: {f['zone']} ({f['country']})")
        print(f"   Métrica: {f['metric']}")
        print(f"   📝 {f['description']}")
        print(f"   📦 Data: {f['data']}")

    print(f"\n{SEP}")
    if len(top_findings) >= 5:
        print(f"✅ insights_engine.py — {len(top_findings)} hallazgos generados (≥5 requeridos)")
    else:
        print(f"⚠️ insights_engine.py — solo {len(top_findings)} hallazgos (se esperaban ≥5)")
    print(SEP)
