"""
bot.py — Orquestador conversacional con Gemini 2.5 Pro + Function Calling nativo.

Responsabilidades:
  - Definir TOOLS_DEFINITION con las 6 function_declarations
  - Crear sesión de chat con system prompt
  - Implementar loop multi-tool que recolecta TODAS las fn_calls del turno
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv

from tools import (
    top_zones, compare_segments, trend_analysis,
    find_zones, aggregate_by, explain_growth, safe_result,
)
from context import SYSTEM_PROMPT

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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
# TOOLS_DEFINITION — function_declarations para el SDK de Gemini
# Copiado exactamente de la sección 5 del plan
# ---------------------------------------------------------------------------

TOOLS_DEFINITION = [
    {
        "function_declarations": [
            {
                "name": "top_zones",
                "description": "Retorna las N zonas con mejor o peor desempeño en una métrica específica. Usar para preguntas de filtrado como '¿cuáles son las 5 peores zonas en Perfect Orders?'",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric":    {"type": "string", "description": "Nombre exacto de la métrica"},
                        "n":         {"type": "integer", "description": "Número de zonas a retornar (default: 5)"},
                        "country":   {"type": "string", "description": "Código de país (CO, MX, BR, etc.). Opcional."},
                        "city":      {"type": "string", "description": "Nombre de ciudad. Opcional."},
                        "ascending": {"type": "boolean", "description": "True para peores (menor valor), False para mejores (mayor valor)"},
                        "week":      {"type": "string", "description": "Semana de referencia. Default: L0W_ROLL"},
                    },
                    "required": ["metric"],
                },
            },
            {
                "name": "compare_segments",
                "description": "Compara el valor promedio de una métrica entre segmentos (Wealthy vs Non Wealthy, países, etc.). Usar para preguntas de comparación.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric":  {"type": "string"},
                        "segment": {"type": "string", "description": "ZONE_TYPE | ZONE_PRIORITIZATION | COUNTRY | CITY"},
                        "country": {"type": "string", "description": "Filtrar por país. Opcional."},
                        "week":    {"type": "string", "description": "Default: L0W_ROLL"},
                    },
                    "required": ["metric", "segment"],
                },
            },
            {
                "name": "trend_analysis",
                "description": "Muestra la evolución semana a semana de una métrica para una zona, ciudad o país. Usar para preguntas de tendencia temporal.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric":  {"type": "string"},
                        "zone":    {"type": "string", "description": "Nombre de zona. Opcional."},
                        "country": {"type": "string", "description": "Código de país. Opcional."},
                        "city":    {"type": "string", "description": "Nombre de ciudad. Opcional."},
                        "weeks":   {"type": "integer", "description": "Últimas N semanas (max 9). Default: 8"},
                    },
                    "required": ["metric"],
                },
            },
            {
                "name": "find_zones",
                "description": "Encuentra zonas que simultáneamente tienen métricas altas Y/O bajas. Usar para análisis multivariable como 'alto Lead Penetration pero bajo Perfect Order'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "high_metrics":    {"type": "array", "items": {"type": "string"}, "description": "Métricas donde la zona debe estar en el cuartil alto"},
                        "low_metrics":     {"type": "array", "items": {"type": "string"}, "description": "Métricas donde la zona debe estar en el cuartil bajo"},
                        "country":         {"type": "string", "description": "Opcional"},
                        "threshold_pct":   {"type": "number", "description": "Percentil para definir alto/bajo (default: 0.75)"},
                    },
                },
            },
            {
                "name": "aggregate_by",
                "description": "Calcula el promedio de una métrica agrupado por país, ciudad, tipo de zona o priorización. Usar para preguntas de agregación como '¿cuál es el promedio por país?'",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric":   {"type": "string"},
                        "group_by": {"type": "string", "description": "COUNTRY | CITY | ZONE_TYPE | ZONE_PRIORITIZATION"},
                        "country":  {"type": "string", "description": "Opcional"},
                        "week":     {"type": "string", "description": "Default: L0W_ROLL"},
                    },
                    "required": ["metric", "group_by"],
                },
            },
            {
                "name": "explain_growth",
                "description": "Identifica las zonas con mayor crecimiento en órdenes y retorna sus métricas operacionales para que el LLM pueda inferir qué explica el crecimiento.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "country": {"type": "string", "description": "Opcional"},
                        "top_n":   {"type": "integer", "description": "Cuántas zonas top retornar. Default: 5"},
                        "weeks":   {"type": "integer", "description": "Ventana de semanas para calcular crecimiento. Default: 5"},
                    },
                },
            },
        ]
    }
]

# ---------------------------------------------------------------------------
# SESIÓN DE CHAT
# ---------------------------------------------------------------------------

def create_session():
    """Crea un modelo + sesión de chat con tools y system prompt."""
    model = genai.GenerativeModel(
        model_name="gemini-2.5-pro",
        tools=TOOLS_DEFINITION,
        system_instruction=SYSTEM_PROMPT,
    )
    return model.start_chat()


# ---------------------------------------------------------------------------
# LOOP MULTI-TOOL
# ---------------------------------------------------------------------------

def chat(user_message: str, chat_session) -> tuple[str, list[str]]:
    """
    Envía un mensaje y procesa el loop multi-tool completo.

    Retorna (respuesta_texto, lista_de_tools_usadas).
    La lista permite a app.py mostrar debug info y decidir gráficos.
    """
    response = chat_session.send_message(user_message)
    tools_used = []

    # Loop: recolectar y ejecutar TODAS las tool calls del turno
    while True:
        fn_calls = [
            part.function_call
            for part in response.candidates[0].content.parts
            if hasattr(part, "function_call") and part.function_call.name
        ]

        if not fn_calls:
            break

        # Ejecutar TODAS y devolver todas las respuestas en un solo Content
        response_parts = []
        for fn_call in fn_calls:
            tools_used.append(fn_call.name)
            try:
                fn = TOOL_ROUTER[fn_call.name]
                params = dict(fn_call.args)
                result_df = fn(**params)
                result_str = safe_result(result_df)
            except Exception as e:
                result_str = f"Error ejecutando {fn_call.name}: {str(e)}"

            response_parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fn_call.name,
                        response={"result": result_str},
                    )
                )
            )

        response = chat_session.send_message(
            genai.protos.Content(parts=response_parts)
        )

    return response.text, tools_used


# ---------------------------------------------------------------------------
# TESTS — ejecutar directamente para validar
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tools as tools_module
    from data_loader import load_data

    # Cargar e inyectar datos
    df_metrics, df_orders, df_long = load_data("data/rappi_data.xlsx")
    tools_module.df_metrics = df_metrics
    tools_module.df_orders = df_orders
    tools_module.df_long = df_long

    SEP = "=" * 60

    # Crear sesión
    session = create_session()
    print(f"\n{SEP}")
    print("Sesión creada. Testeando 3 preguntas...")
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
            print(f"\n🔧 Tools usadas: {tools_used}")
            print(f"\n📝 Respuesta:\n{answer[:500]}...")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")

    print(f"\n{SEP}")
    print("✅ bot.py — tests completados")
    print(SEP)
