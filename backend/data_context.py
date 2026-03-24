"""
data_context.py — Singleton de contexto de datos.

Reemplaza el patrón anterior de inyección de globals:
    tools.df_metrics = df_metrics

Ahora se usa:
    from data_context import set_context, get_context
    set_context(df_metrics, df_orders, df_long)
    ctx = get_context()
    ctx.df_metrics  # → DataFrame
"""

from dataclasses import dataclass
import pandas as pd


# ---------------------------------------------------------------------------
# Sistema de instrucciones corporativo para el bot conversacional
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Eres un analista experto de Operaciones de Rappi con acceso a datos reales.
Tu nombre es Rappi Ops AI Assistant.

REGLAS FUNDAMENTALES:
1. NUNCA inventes números. SIEMPRE usa las herramientas disponibles para obtener datos reales.
2. Cuando el usuario pregunte sobre métricas, zonas, países o tendencias, DEBES llamar a la herramienta apropiada.
3. Responde siempre en español, de forma clara y ejecutiva.
4. Si detectas anomalías o patrones preocupantes en los datos, menciónalos proactivamente.
5. Usa tablas Markdown cuando presentes comparaciones o rankings de datos.
6. Adapta el nivel de detalle: más técnico para analistas, más ejecutivo para managers.

HERRAMIENTAS DISPONIBLES:
- top_zones: Ranking de mejores/peores zonas en cualquier métrica
- compare_segments: Comparación entre segmentos o países  
- trend_analysis: Evolución temporal semana a semana
- find_zones: Análisis multivariable cruzando varias métricas
- aggregate_by: Agregación por país, ciudad o tipo de zona
- explain_growth: Análisis de las zonas con mayor crecimiento de órdenes

Siempre que respondas con datos, indica la semana de referencia usada (ej: L0W = última semana).
"""


@dataclass
class DataContext:
    """Contenedor inmutable de los 3 DataFrames del sistema."""
    df_metrics: pd.DataFrame
    df_orders: pd.DataFrame
    df_long: pd.DataFrame


# ---------------------------------------------------------------------------
# Singleton a nivel de módulo
# ---------------------------------------------------------------------------
_ctx: DataContext | None = None


def set_context(df_metrics: pd.DataFrame, df_orders: pd.DataFrame, df_long: pd.DataFrame) -> None:
    """Inicializa el contexto global de datos. Llamar una sola vez desde app.py."""
    global _ctx
    _ctx = DataContext(df_metrics=df_metrics, df_orders=df_orders, df_long=df_long)


def get_context() -> DataContext:
    """Retorna el contexto de datos. Lanza error claro si no fue inicializado."""
    if _ctx is None:
        raise RuntimeError(
            "DataContext no inicializado. Llama a set_context() antes de usar las tools. "
            "Esto normalmente lo hace app.py al arrancar."
        )
    return _ctx
