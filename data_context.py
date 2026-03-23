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
