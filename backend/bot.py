"""
bot.py — Orquestador conversacional con Gemini 2.0 Flash + Function Calling nativo.

SDK: google-genai (nuevo) — NO google-generativeai (deprecado)

Responsabilidades:
  - Definir TOOLS con types.Tool / types.FunctionDeclaration
  - Crear sesión de chat con client.chats.create()
  - Implementar loop multi-tool que recolecta TODAS las fn_calls del turno
"""

import os
import time
import hashlib
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

from .tools import (
    top_zones, compare_segments, trend_analysis,
    find_zones, aggregate_by, explain_growth, safe_result,
)
from .data_context import SYSTEM_PROMPT

load_dotenv()

# ---------------------------------------------------------------------------
# MODELO — cambiar a "gemini-2.5-pro" cuando tengas billing activado
# ---------------------------------------------------------------------------
MODEL = "gemini-2.5-flash-lite"

# ---------------------------------------------------------------------------
# CLIENT — a nivel de módulo para que persista durante toda la vida del proceso
# Si se crea dentro de create_session() como variable local, se destruye
# al salir de la función y la sesión de chat queda sin cliente activo.
# ---------------------------------------------------------------------------
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ---------------------------------------------------------------------------
# TOOL ROUTER — mapea nombre de función → función real de tools.py
# ---------------------------------------------------------------------------

TOOL_ROUTER = {
    "top_zones": top_zones,
    "compare_segments": compare_segments,
    "trend_analysis": trend_analysis,
    "find_zones": find_zones,
    "aggregate_by": aggregate_by,
    "explain_growth": explain_growth,
}

# ---------------------------------------------------------------------------
# RESPONSE CACHE — evita llamadas duplicadas a la API con el mismo mensaje
# ---------------------------------------------------------------------------
_response_cache: dict[str, tuple[str, list]] = {}

logger = logging.getLogger(__name__)


def clear_cache() -> None:
    """Limpia el caché de respuestas. Llamar al iniciar nueva conversación."""
    _response_cache.clear()

# ---------------------------------------------------------------------------
# TOOLS — function_declarations con types.Tool del nuevo SDK
# ---------------------------------------------------------------------------

TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="top_zones",
            description="Retorna las N zonas con mejor o peor desempeño en una métrica específica. Usar para preguntas de filtrado como '¿cuáles son las 5 peores zonas en Perfect Orders?'",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "metric": types.Schema(type=types.Type.STRING, description="Nombre exacto de la métrica"),
                    "n": types.Schema(type=types.Type.INTEGER, description="Número de zonas a retornar (default: 5)"),
                    "country": types.Schema(type=types.Type.STRING, description="Código de país (CO, MX, BR, etc.). Opcional."),
                    "city": types.Schema(type=types.Type.STRING, description="Nombre de ciudad. Opcional."),
                    "ascending": types.Schema(type=types.Type.BOOLEAN, description="True para peores (menor valor), False para mejores (mayor valor)"),
                    "week": types.Schema(type=types.Type.STRING, description="Semana de referencia. Default: L0W_ROLL"),
                },
                required=["metric"],
            ),
        ),
        types.FunctionDeclaration(
            name="compare_segments",
            description="Compara el valor promedio de una métrica entre segmentos (Wealthy vs Non Wealthy, países, etc.). Usar para preguntas de comparación.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "metric": types.Schema(type=types.Type.STRING, description="Nombre exacto de la métrica"),
                    "segment": types.Schema(type=types.Type.STRING, description="ZONE_TYPE | ZONE_PRIORITIZATION | COUNTRY | CITY"),
                    "country": types.Schema(type=types.Type.STRING, description="Filtrar por país. Opcional."),
                    "week": types.Schema(type=types.Type.STRING, description="Default: L0W_ROLL"),
                },
                required=["metric", "segment"],
            ),
        ),
        types.FunctionDeclaration(
            name="trend_analysis",
            description="Muestra la evolución semana a semana de una métrica para una zona, ciudad o país. Usar para preguntas de tendencia temporal.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "metric": types.Schema(type=types.Type.STRING, description="Nombre exacto de la métrica"),
                    "zone": types.Schema(type=types.Type.STRING, description="Nombre de zona. Opcional."),
                    "country": types.Schema(type=types.Type.STRING, description="Código de país. Opcional."),
                    "city": types.Schema(type=types.Type.STRING, description="Nombre de ciudad. Opcional."),
                    "weeks": types.Schema(type=types.Type.INTEGER, description="Últimas N semanas (max 9). Default: 8"),
                },
                required=["metric"],
            ),
        ),
        types.FunctionDeclaration(
            name="find_zones",
            description="Encuentra zonas que simultáneamente tienen métricas altas Y/O bajas. Usar para análisis multivariable como 'alto Lead Penetration pero bajo Perfect Order'.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "high_metrics": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="Métricas donde la zona debe estar en el cuartil alto"),
                    "low_metrics": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="Métricas donde la zona debe estar en el cuartil bajo"),
                    "country": types.Schema(type=types.Type.STRING, description="Opcional"),
                    "threshold_pct": types.Schema(type=types.Type.NUMBER, description="Percentil para definir alto/bajo (default: 0.75)"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="aggregate_by",
            description="Calcula el promedio de una métrica agrupado por país, ciudad, tipo de zona o priorización. Usar para preguntas de agregación como '¿cuál es el promedio por país?'",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "metric": types.Schema(type=types.Type.STRING, description="Nombre exacto de la métrica"),
                    "group_by": types.Schema(type=types.Type.STRING, description="COUNTRY | CITY | ZONE_TYPE | ZONE_PRIORITIZATION"),
                    "country": types.Schema(type=types.Type.STRING, description="Opcional"),
                    "week": types.Schema(type=types.Type.STRING, description="Default: L0W_ROLL"),
                },
                required=["metric", "group_by"],
            ),
        ),
        types.FunctionDeclaration(
            name="explain_growth",
            description="Identifica las zonas con mayor crecimiento en órdenes y retorna sus métricas operacionales para que el LLM pueda inferir qué explica el crecimiento.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "country": types.Schema(type=types.Type.STRING, description="Opcional"),
                    "top_n": types.Schema(type=types.Type.INTEGER, description="Cuántas zonas top retornar. Default: 5"),
                    "weeks": types.Schema(type=types.Type.INTEGER, description="Ventana de semanas para calcular crecimiento. Default: 5"),
                },
            ),
        ),
    ]
)

# ---------------------------------------------------------------------------
# SESIÓN DE CHAT
# ---------------------------------------------------------------------------

def create_session():
    """Crea una sesión de chat usando el client a nivel de módulo."""
    session = _client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[TOOLS],
        ),
    )
    return session


# ---------------------------------------------------------------------------
# LOOP MULTI-TOOL
# ---------------------------------------------------------------------------

def chat(user_message: str, chat_session, retry_callback=None) -> tuple[str, list[str]]:
    """
    Envía un mensaje y procesa el loop multi-tool completo.

    Retorna (respuesta_texto, lista_de_tools_usadas).
    La lista permite a app.py mostrar debug info y renderizar gráficos.

    Args:
        retry_callback: función opcional para mostrar reintentos en la UI
                        (ej: st.warning). Si es None, usa logging.
    """
    # Cache: si el mismo mensaje ya fue procesado, retornar respuesta anterior
    cache_key = hashlib.sha256(user_message.encode()).hexdigest()
    if cache_key in _response_cache:
        logger.info("Cache hit para: %s", user_message[:50])
        return _response_cache[cache_key]

    # Retry hasta 3 veces con espera entre intentos
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = chat_session.send_message(user_message)
            break
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                wait = (attempt + 1) * 5  # 5s, 10s, 15s (más corto que antes)
                msg = f"⚠️  Servidor ocupado, reintentando en {wait}s... (intento {attempt + 2}/{max_retries})"
                if retry_callback:
                    retry_callback(msg)
                else:
                    logger.warning(msg)
                time.sleep(wait)
            else:
                raise

    tools_used = []

    # Loop: recolectar y ejecutar TODAS las tool calls del turno
    while True:
        fn_calls = [
            part.function_call
            for part in response.candidates[0].content.parts
            if hasattr(part, "function_call") and part.function_call is not None
        ]

        if not fn_calls:
            break

        # Ejecutar TODAS y devolver todas las respuestas en un solo mensaje
        response_parts = []
        for fc in fn_calls:
            try:
                result_df = TOOL_ROUTER[fc.name](**dict(fc.args))
                tools_used.append({
                    "name": fc.name,
                    "df": result_df,
                    "args": dict(fc.args)
                })
                result_str = safe_result(result_df)
            except Exception as e:
                tools_used.append({"name": fc.name, "error": str(e)})
                result_str = f"Error ejecutando {fc.name}: {str(e)}"

            response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": result_str},
                    )
                )
            )

        response = chat_session.send_message(response_parts)

    result = (response.text, tools_used)
    _response_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# TESTS — ejecutar directamente para validar
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from data_loader import load_data
    from data_context import set_context

    # Cargar e inicializar contexto de datos
    df_metrics, df_orders, df_long = load_data("data/rappi_data.xlsx")
    set_context(df_metrics, df_orders, df_long)

    SEP = "=" * 60

    # Crear sesión
    session = create_session()
    print(f"\n{SEP}")
    print(f"Sesión creada con modelo: {MODEL}")
    print("Testeando 3 preguntas...")
    print(SEP)

    test_questions = [
        "¿Cuáles son las 5 peores zonas en Perfect Orders en Colombia?",
        "Compara Lead Penetration entre zonas Wealthy y Non Wealthy en México",
        "¿Cuáles son las zonas que más crecen en órdenes en las últimas 5 semanas?",
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n{'─' * 60}")
        print(f"PREGUNTA {i}: {question}")
        print("─" * 60)

        try:
            answer, tools_used = chat(question, session)
            nombres = [t.get("name", str(t)) if isinstance(t, dict) else t for t in tools_used]
            print(f"\n🔧 Tools usadas: {nombres}")
            print(f"\n📝 Respuesta:\n{answer[:500]}...")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")

    print(f"\n{SEP}")
    print("✅ bot.py — tests completados")
    print(SEP)
