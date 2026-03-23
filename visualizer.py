import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def create_trend_chart(df: pd.DataFrame, metric: str, label: str) -> go.Figure:
    """
    Gráfico de líneas para trend_analysis.
    df contiene: 'week', 'week_label', 'value', 'pct_change_vs_prev'.
    """
    if df.empty or "value" not in df.columns or "week_label" not in df.columns:
        return px.line(title="Datos insuficientes para la tendencia")

    fig = px.line(
        df, 
        x="week_label", 
        y="value", 
        title=f"Tendencia: {metric} ({label})",
        markers=True,
    )
    
    # Customización estética según los guidelines de marca/plan
    fig.update_traces(line_color="#FF6B6B", line_width=3, marker=dict(size=8, color="#FF6B6B"))
    
    # Encontrar el min y el max
    min_val = df["value"].min()
    max_val = df["value"].max()
    
    min_row = df[df["value"] == min_val].iloc[0]
    max_row = df[df["value"] == max_val].iloc[0]
    
    # Anotación del punto más bajo
    fig.add_annotation(
        x=min_row["week_label"], y=min_val,
        text="⚠️ Menor valor", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor="#636363",
        ax=0, ay=40, font=dict(color="#d62728")
    )
    
    # Anotación del punto más alto
    fig.add_annotation(
        x=max_row["week_label"], y=max_val,
        text="✅ Mayor valor", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor="#636363",
        ax=0, ay=-40, font=dict(color="#2ca02c")
    )
    
    fig.update_layout(
        xaxis_title="",
        yaxis_title=metric,
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
    )
    fig.update_yaxes(gridcolor="lightgrey")
    
    return fig

def create_bar_chart(df: pd.DataFrame, metric: str, group_col: str) -> go.Figure:
    """
    Gráfico de barras horizontales para compare_segments.
    df contiene: group_col, "Promedio", "Mínimo", "Máximo", "Zonas".
    """
    if df.empty or "Promedio" not in df.columns or group_col not in df.columns:
        return px.bar(title="Datos insuficientes para la comparativa")

    # Ordenar por el Promedio para que el más alto quede arriba
    df_sorted = df.sort_values(by="Promedio", ascending=True)

    fig = px.bar(
        df_sorted,
        x="Promedio",
        y=group_col,
        orientation="h",
        title=f"Comparativa: {metric} por {group_col}",
        color="Promedio",
        color_continuous_scale="Reds",
        text="Promedio"
    )
    
    fig.update_traces(texttemplate="%{text:.4f}", textposition="auto")
    fig.update_layout(
        xaxis_title=f"Promedio de {metric}",
        yaxis_title="",
        coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
    )
    fig.update_xaxes(gridcolor="lightgrey")
    
    return fig
