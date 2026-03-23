# Plan de Implementación: Sistema de Análisis Inteligente Rappi
> Stack: Python · Pandas · Gemini 2.5 (Function Calling nativo) · Streamlit  
> IDE: Antigravity (vibe-coding con Gemini 2.5)  
> Tiempo objetivo: 2 días (~10 bloques de trabajo)  
> Versión: 3.0 — versión final lista para implementar

---

## 0. Contexto real de los datos (base para todo el plan)

### Dataset 1: `RAW_INPUT_METRICS` — 12,573 filas × 15 columnas
```
COUNTRY, CITY, ZONE, ZONE_TYPE, ZONE_PRIORITIZATION, METRIC,
L8W_ROLL, L7W_ROLL, L6W_ROLL, L5W_ROLL, L4W_ROLL, L3W_ROLL, L2W_ROLL, L1W_ROLL, L0W_ROLL
```
- **Columnas de semana:** `L8W_ROLL` (hace 8 semanas) → `L0W_ROLL` (semana actual)
- **13 métricas:** Retail SST > SS CVR, Restaurants SST > SS CVR, Gross Profit UE, Restaurants SS > ATC CVR, Non-Pro PTC > OP, % PRO Users Who Breakeven, Pro Adoption (Last Week Status), MLTV Top Verticals Adoption, % Restaurants Sessions With Optimal Assortment, Lead Penetration, Restaurants Markdowns / GMV, Perfect Orders, Turbo Adoption
- **9 países:** AR, BR, CL, CO, CR, EC, MX, PE, UY

### Dataset 2: `RAW_ORDERS` — 1,242 filas × 13 columnas
```
COUNTRY, CITY, ZONE, METRIC (siempre "Orders"),
L8W, L7W, L6W, L5W, L4W, L3W, L2W, L1W, L0W
```
- **⚠️ Diferencia crítica:** columnas SIN sufijo `_ROLL` (ej: `L0W` no `L0W_ROLL`)
- **Solución en data_loader:** renombrar estas columnas a `L8W_ROLL..L0W_ROLL`
  para unificar el esquema desde el inicio y evitar bugs silenciosos en tools.py

---

## 1. Arquitectura final (decisiones ya tomadas)

```
app.py  (Streamlit — 2 tabs)
├── Tab 1: Bot Conversacional
│   ├── bot.py          → Gemini 2.5 + Function Calling nativo
│   ├── tools.py        → 6 funciones analíticas en Pandas puro
│   └── context.py      → System prompt con vocabulario de negocio Rappi
└── Tab 2: Insights Automáticos
    ├── insights_engine.py  → 5 reglas deterministas en Pandas
    └── report_generator.py → Gemini redacta el reporte Markdown

data_loader.py     → Carga, normaliza, unifica esquema de semanas, hace pivot
demo_fallback.json → Plan B para demo en vivo si la API falla
test_tools.py      → 7 tests mínimos para validar funciones antes de la demo
```

### Decisiones de arquitectura fijas
| Decisión | Elección | Razón |
|---|---|---|
| LLM | Gemini 2.5 Pro | Única API disponible, excelente en function calling |
| Tool calling | Nativo de Gemini SDK | Sin frameworks, sin abstracción innecesaria |
| Multi-tool por turno | Soportado explícitamente | Gemini puede llamar varias tools en paralelo |
| Datos | En memoria (Pandas) | 12k filas caben fácil, cero latencia, cero setup |
| Insights | Reglas deterministas | Reproducibles, explicables, nunca fallan en demo |
| UI | Streamlit | `streamlit run app.py` y listo |
| Memoria conversacional | `st.session_state["chat_session"]` | Persiste entre re-renders de Streamlit |
| Plan B demo | `demo_fallback.json` | Respuestas pre-generadas si la API falla |

---

## 2. Estructura de carpetas del proyecto

```
rappi-ai-system/
├── app.py                  # Entry point Streamlit
├── bot.py                  # Orquestador conversacional
├── tools.py                # 6 funciones analíticas + helpers (fuzzy match, safe_result)
├── context.py              # System prompt y vocabulario de negocio
├── data_loader.py          # Carga, normalización y unificación de esquema
├── insights_engine.py      # Motor de 5 reglas deterministas
├── report_generator.py     # Generador de reporte Markdown con Gemini
├── visualizer.py           # Gráficas plotly para tendencias y comparaciones
├── demo_fallback.json      # Plan B: respuestas pre-generadas para la demo
├── test_tools.py           # 7 tests mínimos (5 min de trabajo, 30 min ahorrados)
├── data/
│   └── rappi_data.xlsx     # El Excel con los 3 sheets
├── requirements.txt        # Versiones fijas
├── .env                    # GEMINI_API_KEY=...
├── .env.example            # Plantilla pública sin secrets
└── README.md
```

---

## 3. Interfaces críticas (firmas exactas de funciones)

Estas son las 6 funciones que Gemini puede invocar. Los nombres y parámetros
deben coincidir exactamente con los `function_declarations` del SDK.

### Helpers obligatorios (al inicio de tools.py):

```python
# tools.py — helpers
import difflib

VALID_METRICS = [
    "Retail SST > SS CVR", "Restaurants SST > SS CVR", "Gross Profit UE",
    "Restaurants SS > ATC CVR", "Non-Pro PTC > OP", "% PRO Users Who Breakeven",
    "Pro Adoption (Last Week Status)", "MLTV Top Verticals Adoption",
    "% Restaurants Sessions With Optimal Assortment", "Lead Penetration",
    "Restaurants Markdowns / GMV", "Perfect Orders", "Turbo Adoption"
]

def fuzzy_match_metric(metric: str) -> str:
    """Corrige typos del LLM usando fuzzy matching. Retorna None si no hay match."""
    if metric in VALID_METRICS:
        return metric
    matches = difflib.get_close_matches(metric, VALID_METRICS, n=1, cutoff=0.6)
    return matches[0] if matches else None

def safe_result(df: pd.DataFrame, max_rows: int = 15) -> str:
    """Limita el output para no quemar tokens innecesariamente."""
    if len(df) > max_rows:
        df = df.head(max_rows)
    return df.to_markdown(index=False)
```

### Firmas de las 6 tools:

```python
# tools.py — funciones analíticas
# IMPORTANTE: Cada función DEBE:
# 1. Llamar fuzzy_match_metric() para validar el nombre de métrica
# 2. Retornar pd.DataFrame({"error": ["mensaje"]}) si el parámetro es inválido
# 3. Envolver la lógica en try/except para no crashear el bot

def top_zones(
    metric: str,
    n: int = 5,
    country: str = None,
    city: str = None,
    ascending: bool = True,
    week: str = "L0W_ROLL"
) -> pd.DataFrame

def compare_segments(
    metric: str,
    segment: str,         # "ZONE_TYPE" | "ZONE_PRIORITIZATION" | "COUNTRY" | "CITY"
    country: str = None,
    week: str = "L0W_ROLL"
) -> pd.DataFrame

def trend_analysis(
    metric: str,
    zone: str = None,
    country: str = None,
    city: str = None,
    weeks: int = 8
) -> pd.DataFrame

def find_zones(
    high_metrics: list[str] = None,
    low_metrics: list[str] = None,
    country: str = None,
    threshold_pct: float = 0.75
) -> pd.DataFrame

def aggregate_by(
    metric: str,
    group_by: str = "COUNTRY",
    country: str = None,
    week: str = "L0W_ROLL"
) -> pd.DataFrame

def explain_growth(
    country: str = None,
    top_n: int = 5,
    weeks: int = 5
) -> pd.DataFrame
# Usa df_orders — cuyas columnas ya tienen sufijo _ROLL gracias a data_loader
```

---

## 4. El System Prompt (context.py)

```python
SYSTEM_PROMPT = """
Eres un analista de datos experto en operaciones de Rappi. 
Tu trabajo es ayudar a Ops Managers y analistas de SP&A a entender 
las métricas operacionales de las zonas geográficas donde opera Rappi.

## DATOS DISPONIBLES
Tienes acceso a métricas operacionales de 9 países (AR, BR, CL, CO, CR, EC, MX, PE, UY)
con datos de las últimas 9 semanas (L8W_ROLL = hace 8 semanas, L0W_ROLL = semana actual).

## MÉTRICAS DISPONIBLES (usa estos nombres EXACTOS al llamar funciones):
- "Perfect Orders" → Órdenes sin cancelaciones, defectos ni demoras / Total órdenes
- "Lead Penetration" → Tiendas habilitadas en Rappi / (prospectos + habilitadas + que salieron)
- "Gross Profit UE" → Margen bruto / Total órdenes
- "Turbo Adoption" → Usuarios que compran en Turbo / usuarios con Turbo disponible
- "Pro Adoption (Last Week Status)" → Usuarios Pro / Total usuarios
- "% PRO Users Who Breakeven" → Usuarios Pro que cubren costo membresía / Total Pro
- "MLTV Top Verticals Adoption" → Usuarios con órdenes en múltiples verticales / Total usuarios
- "Non-Pro PTC > OP" → Conversión No-Pro de Proceed to Checkout a Order Placed
- "% Restaurants Sessions With Optimal Assortment" → Sesiones con min 40 restaurantes / Total
- "Restaurants Markdowns / GMV" → Descuentos totales / GMV restaurantes
- "Restaurants SS > ATC CVR" → Conversión Select Store a Add to Cart en restaurantes
- "Restaurants SST > SS CVR" → % usuarios que seleccionan tienda de restaurantes de la lista
- "Retail SST > SS CVR" → % usuarios que seleccionan tienda de Supermercados de la lista

## SEGMENTACIONES DISPONIBLES:
- ZONE_TYPE: "Wealthy" | "Non Wealthy"
- ZONE_PRIORITIZATION: "High Priority" | "Prioritized" | "Not Prioritized"

## VOCABULARIO DE NEGOCIO:
- "zonas problemáticas" = zonas con métricas en deterioro (caída >10% o tendencia 3+ semanas)
- "zonas de oportunidad" = zonas con métricas creciendo o con gap positivo vs benchmark
- "esta semana" = columna L0W_ROLL (la más reciente)
- "semana pasada" = L1W_ROLL
- Si no especifican semana, usa L0W_ROLL

## CÓMO RESPONDER:
1. SIEMPRE llama al menos una función antes de dar números. Nunca inventes datos.
2. Presenta los resultados con los números exactos del dataset
3. Añade una interpretación de negocio (qué significa este resultado)
4. Da UNA recomendación accionable concreta
5. Sugiere 2-3 preguntas de seguimiento relevantes

## IMPORTANTE:
- NUNCA inventes números. Todos los datos deben venir de las funciones.
- Puedes llamar múltiples funciones en paralelo si la pregunta lo requiere.
- Si el usuario dice "peores zonas", significa ascending=True (menores valores primero).
- Si el usuario dice "mejores zonas", significa ascending=False.
- Los datos son anónimos y no representan un país/período real.
"""
```

---

## 5. Definición de las Tools para Gemini SDK

```python
# bot.py — definición de tools para el SDK de Gemini

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
                        "week":      {"type": "string", "description": "Semana de referencia. Default: L0W_ROLL"}
                    },
                    "required": ["metric"]
                }
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
                        "week":    {"type": "string", "description": "Default: L0W_ROLL"}
                    },
                    "required": ["metric", "segment"]
                }
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
                        "weeks":   {"type": "integer", "description": "Últimas N semanas (max 9). Default: 8"}
                    },
                    "required": ["metric"]
                }
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
                        "threshold_pct":   {"type": "number", "description": "Percentil para definir alto/bajo (default: 0.75)"}
                    }
                }
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
                        "week":     {"type": "string", "description": "Default: L0W_ROLL"}
                    },
                    "required": ["metric", "group_by"]
                }
            },
            {
                "name": "explain_growth",
                "description": "Identifica las zonas con mayor crecimiento en órdenes y retorna sus métricas operacionales para que el LLM pueda inferir qué explica el crecimiento.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "country": {"type": "string", "description": "Opcional"},
                        "top_n":   {"type": "integer", "description": "Cuántas zonas top retornar. Default: 5"},
                        "weeks":   {"type": "integer", "description": "Ventana de semanas para calcular crecimiento. Default: 5"}
                    }
                }
            }
        ]
    }
]
```

---

## 6. Loop de conversación completo (bot.py)

```python
import google.generativeai as genai
from tools import top_zones, compare_segments, trend_analysis, find_zones, aggregate_by, explain_growth, safe_result
from context import SYSTEM_PROMPT
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

TOOL_ROUTER = {
    "top_zones": top_zones,
    "compare_segments": compare_segments,
    "trend_analysis": trend_analysis,
    "find_zones": find_zones,
    "aggregate_by": aggregate_by,
    "explain_growth": explain_growth,
}

def create_session():
    model = genai.GenerativeModel(
        model_name="gemini-2.5-pro",
        tools=TOOLS_DEFINITION,
        system_instruction=SYSTEM_PROMPT
    )
    return model.start_chat()

def chat(user_message: str, chat_session) -> tuple[str, list[str]]:
    """
    Retorna (respuesta_texto, lista_de_tools_usadas).
    La lista permite a app.py mostrar debug info y gráficos.
    """
    response = chat_session.send_message(user_message)
    tools_used = []

    # Loop multi-tool: recolectar y ejecutar TODAS las tool calls del turno
    while True:
        fn_calls = [
            part.function_call
            for part in response.candidates[0].content.parts
            if hasattr(part, 'function_call') and part.function_call
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
                        response={"result": result_str}
                    )
                )
            )

        response = chat_session.send_message(
            genai.protos.Content(parts=response_parts)
        )

    return response.text, tools_used
```

---

## 7. Motor de Insights (insights_engine.py)

```python
# Las 5 reglas deterministas — sin LLM, solo Pandas

def detect_anomalies(df_long, threshold=0.10):
    """Zonas con cambio >10% entre L1W_ROLL y L0W_ROLL.
    Si <3 resultados con 0.10, reintentar automáticamente con 0.05."""

def detect_sustained_decline(df_long, n_weeks=3):
    """Métricas con deterioro en 3+ semanas consecutivas."""

def detect_benchmarking_gaps(df_metrics, week="L0W_ROLL"):
    """Zonas >1.5 IQR por debajo de la mediana de su grupo (COUNTRY, ZONE_TYPE, METRIC)."""

def detect_correlations(df_metrics, week="L0W_ROLL", min_corr=0.65):
    """Pares de métricas con alta correlación. Solo evaluar BUSINESS_PAIRS predefinidos:"""
    BUSINESS_PAIRS = [
        ("Lead Penetration", "Perfect Orders"),
        ("Pro Adoption (Last Week Status)", "% PRO Users Who Breakeven"),
        ("Restaurants SST > SS CVR", "Restaurants SS > ATC CVR"),
        ("% Restaurants Sessions With Optimal Assortment", "Restaurants SS > ATC CVR"),
        ("Turbo Adoption", "MLTV Top Verticals Adoption"),
        ("Non-Pro PTC > OP", "Gross Profit UE"),
        ("Lead Penetration", "Restaurants Markdowns / GMV"),
    ]

def detect_opportunities(df_metrics, df_orders, week="L0W_ROLL"):
    """Zonas con orders creciendo >5% PERO con ≥2 métricas bajo el promedio de su país."""

def run_all_insights(df_metrics, df_long, df_orders):
    findings = []
    findings.extend(detect_anomalies(df_long))
    findings.extend(detect_sustained_decline(df_long))
    findings.extend(detect_benchmarking_gaps(df_metrics))
    findings.extend(detect_correlations(df_metrics))
    findings.extend(detect_opportunities(df_metrics, df_orders))
    return sorted(findings, key=lambda x: abs(x.get('magnitude', 0)), reverse=True)[:10]
```

---

## 8. Plan de 2 días — Bloques de trabajo

### DÍA 1: Bot conversacional funcionando end-to-end

#### Bloque 1 · 1.5h · Setup del proyecto
**Objetivo:** Entorno listo, datos validados, esquema unificado  
**Resultado esperado:** `data_loader.py` completo retornando 3 DataFrames con columnas normalizadas

**Prompt para Antigravity:**
```
Crea data_loader.py que:
1. Cargue el archivo Excel en data/rappi_data.xlsx
2. Lea el sheet RAW_INPUT_METRICS (columnas de semana: L8W_ROLL a L0W_ROLL, con sufijo _ROLL)
3. Lea el sheet RAW_ORDERS (columnas de semana: L8W a L0W, SIN sufijo _ROLL)

4. ⚠️ PASO CRÍTICO — Unificar esquema de df_orders renombrando columnas de semana:
   df_orders.rename(columns={
       "L8W": "L8W_ROLL", "L7W": "L7W_ROLL", "L6W": "L6W_ROLL", "L5W": "L5W_ROLL",
       "L4W": "L4W_ROLL", "L3W": "L3W_ROLL", "L2W": "L2W_ROLL", "L1W": "L1W_ROLL", "L0W": "L0W_ROLL"
   }, inplace=True)
   Sin este paso, explain_growth fallará silenciosamente buscando columnas que no existen.

5. Normalice nombres de zona y ciudad en ambos DataFrames:
   df["ZONE"] = df["ZONE"].str.strip().str.title()
   df["CITY"] = df["CITY"].str.strip().str.title()

6. Cree df_long haciendo melt de df_metrics:
   - id_vars: [COUNTRY, CITY, ZONE, ZONE_TYPE, ZONE_PRIORITIZATION, METRIC]
   - value_vars: [L8W_ROLL, L7W_ROLL, L6W_ROLL, L5W_ROLL, L4W_ROLL, L3W_ROLL, L2W_ROLL, L1W_ROLL, L0W_ROLL]
   - var_name: "week", value_name: "value"

7. Retorne tuple: (df_metrics, df_orders, df_long)
8. Al final: print de .shape y .head(2) de cada DataFrame para validación

Usa pandas y openpyxl. El archivo Excel tiene 3 sheets: RAW_INPUT_METRICS, RAW_ORDERS, RAW_SUMMARY.
```

---

#### Bloque 2 · 2.5h · Las 6 funciones analíticas
**Objetivo:** `tools.py` completo y testeado con datos reales  
**Resultado esperado:** Cada función retorna un DataFrame correcto cuando se corre en terminal

**Prompt para Antigravity:**
```
Crea tools.py con 6 funciones analíticas + 2 helpers de robustez.
Usa solo Pandas. Los DataFrames (df_metrics, df_orders, df_long) son variables globales
que se inyectan desde app.py antes del primer uso.

HELPERS OBLIGATORIOS (al inicio del archivo):
- VALID_METRICS: lista con los 13 nombres exactos de métricas
- fuzzy_match_metric(metric) -> str: usa difflib.get_close_matches para corregir 
  typos del LLM. Si no hay match con cutoff=0.6, retorna None.
- safe_result(df, max_rows=15) -> str: trunca a max_rows filas y retorna 
  df.to_markdown(index=False) para limitar tokens enviados al LLM.

REGLA PARA CADA FUNCIÓN: 
- Al inicio, validar metric con fuzzy_match_metric(). Si retorna None, 
  retornar pd.DataFrame({"error": [f"Métrica '{metric}' no encontrada. Disponibles: {VALID_METRICS}"]})
- Envolver toda la lógica en try/except que retorne DataFrame con error descriptivo.

FUNCIONES:

1. top_zones(metric, n=5, country=None, city=None, ascending=True, week="L0W_ROLL"):
   - Filtra df_metrics por metric (y opcionalmente country/city)
   - Retorna las n zonas ordenadas por el valor de la semana `week`
   - Columnas: COUNTRY, CITY, ZONE, ZONE_TYPE, valor de la semana

2. compare_segments(metric, segment, country=None, week="L0W_ROLL"):
   - segment: ZONE_TYPE, ZONE_PRIORITIZATION, COUNTRY, CITY
   - groupby(segment)[week].agg(["mean","min","max","count"])
   - Ordena por mean descendente

3. trend_analysis(metric, zone=None, country=None, city=None, weeks=8):
   - Usa df_long filtrado por metric (y opcionalmente zone/country/city)
   - Si zone=None: promedio grupal por semana
   - week_label: convierte "L8W_ROLL" → "Sem -8", "L0W_ROLL" → "Sem 0"
   - Calcula pct_change_vs_prev entre semanas

4. find_zones(high_metrics=None, low_metrics=None, country=None, threshold_pct=0.75):
   - Para cada métrica en high_metrics: zonas en percentil >= threshold_pct
   - Para cada métrica en low_metrics: zonas en percentil <= (1-threshold_pct)
   - Retorna intersección + valores de todas las métricas relevantes

5. aggregate_by(metric, group_by="COUNTRY", country=None, week="L0W_ROLL"):
   - groupby(group_by)[week].agg(["mean","min","max","count"])
   - Ordena por mean descendente

6. explain_growth(country=None, top_n=5, weeks=5):
   - En df_orders (columnas ya son L8W_ROLL..L0W_ROLL gracias a data_loader):
     calcula % cambio entre f"L{weeks}W_ROLL" y "L0W_ROLL" por zona
   - Toma top_n zonas con mayor crecimiento
   - Extrae todas sus métricas de df_metrics en L0W_ROLL
   - Retorna: ZONE, COUNTRY, CITY, orders_growth_pct + columna por métrica

Añade al final un bloque if __name__ == "__main__" que:
- Cargue los datos con data_loader
- Inyecte los DataFrames como globals
- Testee las 6 funciones con ejemplos concretos
- Incluya un test con nombre de métrica con typo ("perfect orders") para validar fuzzy matching
```

---

#### Bloque 3 · 2h · Bot con function calling
**Objetivo:** `bot.py` + `context.py` funcionando — responde preguntas en terminal  
**Resultado esperado:** 3 preguntas respondidas con números reales del CSV

**Prompt para Antigravity:**
```
Crea context.py con la constante SYSTEM_PROMPT (copiar exactamente de la sección 4 del plan).

Crea bot.py con:
1. TOOLS_DEFINITION: lista de function_declarations para las 6 funciones
   (copiar exactamente de la sección 5 del plan)
2. TOOL_ROUTER: dict nombre_función → función real de tools.py
3. create_session(): GenerativeModel("gemini-2.5-pro", tools, system_instruction) → start_chat()
4. chat(user_message, chat_session) -> tuple[str, list[str]]:
   Implementar el loop multi-tool de la sección 6 del plan:
   - Recolectar TODAS las fn_calls del turno (no solo la primera)
   - Ejecutar cada una con try/except individual usando safe_result()
   - Devolver TODAS las respuestas en un solo Content con múltiples Parts
   - Retornar (response.text, tools_used)
5. Bloque main: crear sesión, testear 3 preguntas, imprimir tools_used y respuesta.
```

---

#### Bloque 4 · 2h · Streamlit Tab 1 (Chat)
**Objetivo:** UI del bot funcionando en el browser  
**Resultado esperado:** Chat completo con memoria persistente

**Prompt para Antigravity:**
```
Crea app.py con Streamlit. Implementa Tab 1 completo.

CONFIGURACIÓN INICIAL:
st.set_page_config(page_title="Rappi AI Analytics", page_icon="🛵", layout="wide")

CARGA DE DATOS (una sola vez, cacheado):
@st.cache_data
def get_data():
    from data_loader import load_data
    return load_data("data/rappi_data.xlsx")

df_metrics, df_orders, df_long = get_data()

# Inyectar en tools como globals
import tools
tools.df_metrics = df_metrics
tools.df_orders = df_orders
tools.df_long = df_long

# ⚠️ CRÍTICO — Sin este patrón, la memoria se pierde en cada interacción:
if "chat_session" not in st.session_state:
    from bot import create_session
    st.session_state.chat_session = create_session()
if "messages" not in st.session_state:
    st.session_state.messages = []

SIDEBAR:
- st.title("🛵 Rappi AI Analytics")
- Selectbox país: ["Todos","AR","BR","CL","CO","CR","EC","MX","PE","UY"]
- Botón "🗑️ Nueva conversación": limpiar messages + reiniciar chat_session + st.rerun()
- st.info("~$0.015 por query")

TAB 1 "🤖 Bot Conversacional":
- Renderizar historial con st.chat_message
- user_input = st.chat_input(...)
- Al recibir input:
  1. Si país != "Todos": prepend contexto al mensaje
  2. with st.spinner("🔍 Analizando datos..."): respuesta, tools_used = chat_with_fallback(...)
  3. Agregar a messages y renderizar con st.markdown
  4. Mostrar expander "🔧 Debug — herramientas usadas: {tools_used}"
     (demuestra al jurado que los datos vienen del CSV)

FUNCIÓN chat_with_fallback (plan B):
import json
def chat_with_fallback(user_message, chat_session):
    try:
        from bot import chat
        return chat(user_message, chat_session)
    except Exception as e:
        try:
            with open("demo_fallback.json", "r", encoding="utf-8") as f:
                fallback = json.load(f)
            for key, item in fallback.items():
                if item["pregunta"].lower() in user_message.lower():
                    st.warning("⚠️ Modo offline — respuesta pre-generada")
                    return item["respuesta"], ["fallback"]
        except:
            pass
        st.error(f"Error de conexión: {str(e)}")
        return "", []

from dotenv import load_dotenv; load_dotenv()
```

---

### DÍA 2: Insights engine + reporte + integración final

#### Bloque 5 · 2h · Motor de insights
**Objetivo:** `insights_engine.py` detectando hallazgos reales  
**Resultado esperado:** `python insights_engine.py` imprime mínimo 5 hallazgos distintos

**Prompt para Antigravity:**
```
Crea insights_engine.py con 5 funciones de detección y una orquestadora.
Usa solo Pandas, sin LLMs. Cada hallazgo es un dict:
{type, zone, city, country, metric, magnitude, direction, description, data}

1. detect_anomalies(df_long, threshold=0.10):
   Compara L0W_ROLL vs L1W_ROLL por (zone, metric).
   Si abs(pct_change) > threshold → anomalía.
   Si <3 resultados: reintentar con threshold=0.05.
   Retorna top 10 por magnitud absoluta.

2. detect_sustained_decline(df_long, n_weeks=3):
   Verifica si los últimos n_weeks valores son consecutivamente decrecientes.
   Calcula caída total % desde inicio de la tendencia.

3. detect_benchmarking_gaps(df_metrics, week="L0W_ROLL"):
   Agrupa por (COUNTRY, ZONE_TYPE, METRIC).
   Zonas >1.5 IQR por debajo de la mediana = outlier negativo.

4. detect_correlations(df_metrics, week="L0W_ROLL", min_corr=0.65):
   Solo evaluar los pares en BUSINESS_PAIRS (ver sección 7 del plan).
   No calcular todas las combinaciones posibles.

5. detect_opportunities(df_metrics, df_orders, week="L0W_ROLL"):
   Zonas con orders creciendo >5% (L4W_ROLL vs L0W_ROLL) Y ≥2 métricas bajo promedio.

6. run_all_insights(df_metrics, df_long, df_orders) -> list[dict]:
   Ejecuta las 5, combina, ordena por abs(magnitude), retorna top 10.

Bloque main: cargar datos, correr run_all_insights, imprimir cada hallazgo.
```

---

#### Bloque 6 · 1.5h · Generador de reporte
**Objetivo:** `report_generator.py` produciendo Markdown ejecutivo  
**Resultado esperado:** `reporte_insights.md` legible por un Ops Manager

**Prompt para Antigravity:**
```
Crea report_generator.py con:

1. format_findings_for_llm(findings: list[dict]) -> str:
   Convierte hallazgos a texto estructurado para el LLM.

2. generate_report(findings: list[dict]) -> str:
   UNA sola llamada a Gemini 2.5 Pro (sin tools).
   System: "Eres un analista ejecutivo de Rappi. Redacta reportes claros y accionables."
   Pide reporte Markdown con estructura:
   # 🚨 Reporte Semanal de Operaciones Rappi
   ## Resumen Ejecutivo [3-4 frases críticas]
   ## Top 5 Hallazgos Críticos
   ### 1. [Título] | Tipo | Zona | Magnitud | Por qué importa | Recomendación accionable
   ## ⚠️ Métricas a Vigilar Esta Semana

3. save_report(report_text, path="reporte_insights.md"):
   Guarda con encoding UTF-8.

Bloque main: load_data → run_all_insights → generate_report → save_report → print.
```

---

#### Bloque 7 · 1.5h · Streamlit Tab 2 + integración final
**Objetivo:** App completa, demo-ready  
**Resultado esperado:** Ambas tabs funcionando en browser

**Prompt para Antigravity:**
```
Actualiza app.py para agregar Tab 2.

TAB 2 "📊 Insights Automáticos":
- 3 columnas st.metric: anomalías / tendencias negativas / oportunidades
  (precalcular con run_all_insights y guardar en st.session_state["findings"])
- Botón "🔍 Generar Reporte Ejecutivo"
- Spinner → generate_report → mostrar con st.markdown
- st.download_button para descargar el .md
- Guardar reporte en st.session_state["report"] para no regenerar

MEJORA TAB 1:
- El expander de debug muestra: tools usadas + "✅ Datos vienen del CSV, no generados por el LLM"
- Si tools_used contiene "fallback": mostrar st.warning en lugar del expander normal

Manejo de errores general: envolver todo en try/except con st.error amigable.
```

---

#### Bloque 8 · 1h · Tests + pruebas de demo + fallback JSON
**Objetivo:** Todo funciona, plan B listo con respuestas reales

**Prompt para Antigravity — crear tests:**
```
Crea test_tools.py que:
1. Cargue datos con data_loader.load_data("data/rappi_data.xlsx")
2. Inyecte los DataFrames en tools como globals
3. Ejecute estos 7 tests con assert:
   - top_zones("Perfect Orders", country="CO", n=5) → no vacío, ≤5 filas, columna ZONE existe
   - compare_segments("Lead Penetration", "ZONE_TYPE", country="MX") → no vacío
   - trend_analysis("Gross Profit UE", country="BR", weeks=8) → columna week_label existe
   - find_zones(high_metrics=["Lead Penetration"], low_metrics=["Perfect Orders"]) → no crashea
   - aggregate_by("Turbo Adoption", group_by="COUNTRY") → len > 0
   - explain_growth(top_n=5, weeks=5) → columna orders_growth_pct existe
   - top_zones("perfect orders") → fuzzy match funciona, NO retorna columna "error"
4. Imprime ✅ por cada test que pasa
5. Imprime 🎉 al final si todos pasan

Córrelo: python test_tools.py
Si algún test falla, muéstrame el error antes de continuar al Bloque 8.
```

**Las 5 preguntas de demo (ordenadas de menor a mayor dificultad):**

1. *(Filtrado)* "¿Cuáles son las 5 peores zonas en Perfect Orders en Colombia?"
2. *(Comparación)* "Compara Lead Penetration entre zonas Wealthy y Non Wealthy en México"
3. *(Tendencia)* "¿Cómo ha evolucionado el Gross Profit UE en las últimas 8 semanas en Brasil?"
4. *(Multivariable)* "¿Qué zonas tienen alto Lead Penetration pero bajo Perfect Order en Argentina?"
5. *(Inferencia)* "¿Cuáles son las zonas que más crecen en órdenes en las últimas 5 semanas y qué podría explicar ese crecimiento?"

**Para cada pregunta verificar:**
- [ ] El expander muestra tools_used (confirma que no alucina)
- [ ] Incluye interpretación de negocio + recomendación + follow-ups
- [ ] La memoria funciona: después de pregunta 1, hacer "¿Y en México?" y verificar contexto

**Después de verificar las 5 preguntas — crear el plan B:**
```
Crea demo_fallback.json con esta estructura y pega las respuestas reales
que acabas de obtener del bot:
{
  "pregunta_1": {
    "pregunta": "¿Cuáles son las 5 peores zonas en Perfect Orders en Colombia?",
    "respuesta": "[PEGAR AQUÍ la respuesta completa del bot]"
  },
  "pregunta_2": {
    "pregunta": "Compara Lead Penetration entre zonas Wealthy y Non Wealthy en México",
    "respuesta": "[PEGAR AQUÍ]"
  },
  "pregunta_3": {
    "pregunta": "¿Cómo ha evolucionado el Gross Profit UE en las últimas 8 semanas en Brasil?",
    "respuesta": "[PEGAR AQUÍ]"
  },
  "pregunta_4": {
    "pregunta": "¿Qué zonas tienen alto Lead Penetration pero bajo Perfect Order en Argentina?",
    "respuesta": "[PEGAR AQUÍ]"
  },
  "pregunta_5": {
    "pregunta": "¿Cuáles son las zonas que más crecen en órdenes en las últimas 5 semanas?",
    "respuesta": "[PEGAR AQUÍ]"
  }
}
```

---

#### Bloque 9 · 1h · README + documentación
**Objetivo:** Repo ejecutable por cualquier persona de Rappi

**Prompt para Antigravity:**
```
Crea README.md con:

# 🛵 Rappi AI Analytics System

## ¿Qué hace?
Bot conversacional + insights automáticos para operaciones de Rappi.
Ops Managers hacen preguntas en lenguaje natural y obtienen análisis
basados en datos reales sin saber SQL ni Python.

## Cómo correrlo (3 pasos)
git clone <repo>
cd rappi-ai-system
pip install -r requirements.txt
cp .env.example .env   # Editar con tu GEMINI_API_KEY
streamlit run app.py

## Arquitectura
Tabla con los 9 archivos y su responsabilidad.

## Costos estimados
Query simple ~$0.01 | Query complejo ~$0.02 | Reporte insights ~$0.05 | Sesión típica ~$0.20

## Decisiones técnicas clave
- Gemini 2.5 Pro + function calling nativo (sin LangChain): control total, 0 alucinaciones
- Insights deterministas (sin ML): reproducibles, explicables, predecibles en demo
- Datos en memoria (Pandas): 12k filas, latencia <100ms, cero infraestructura

## Limitaciones y próximos pasos
- Datos snapshot estático; en producción conectaría a BigQuery/Redshift
- ML para forecasting (Prophet) y clustering de zonas con tiempo adicional
- Deployment en Streamlit Cloud con autenticación corporativa

Crea también:
- .env.example con: GEMINI_API_KEY=your_gemini_api_key_here
- requirements.txt con versiones fijas:
  streamlit==1.44.0
  pandas==2.2.3
  google-generativeai==0.8.5
  python-dotenv==1.1.0
  openpyxl==3.1.5
  tabulate==0.9.0
  plotly==5.22.0
```

---

#### Bloque 10 · 1h · Buffer / Bonus
**Objetivo:** Gráficos de tendencia en el chat (solo si bloques 1-9 están sólidos)

**Prompt para Antigravity:**
```
Crea visualizer.py con:

1. create_trend_chart(df, metric, label) -> plotly.Figure:
   Líneas. X: week_label, Y: value. Color coral (#FF6B6B), markers.
   Anotación en punto más bajo (⚠️) y más alto (✅).

2. create_bar_chart(df, metric, group_col) -> plotly.Figure:
   Barras horizontales ordenadas por valor desc. Para compare_segments.

Integra en app.py Tab 1:
- Si "trend_analysis" in tools_used: st.plotly_chart(create_trend_chart(...))
- Si "compare_segments" in tools_used: st.plotly_chart(create_bar_chart(...))
```

---

## 9. Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación | ¿Implementada? |
|---|---|---|---|
| Gemini invoca tool con nombre de métrica con typo | Media | `fuzzy_match_metric()` con `difflib.get_close_matches(cutoff=0.6)` | ✅ tools.py helpers |
| Zona no encontrada por capitalización distinta | Alta | `.str.strip().str.title()` en data_loader | ✅ data_loader.py |
| Columnas de df_orders sin _ROLL → bug silencioso | Alta | Renombrar en data_loader al cargar | ✅ Bloque 1 prompt |
| Gemini emite múltiples tool calls en un turno | Media | Loop multi-tool recolecta TODAS las fn_calls | ✅ bot.py |
| Gemini no llama ninguna tool y alucina | Baja | System prompt: "SIEMPRE llama función antes de dar números" | ✅ context.py |
| Crash en demo por fallo de API | Baja | demo_fallback.json + chat_with_fallback() | ✅ Bloque 8 + app.py |
| Streamlit pierde la sesión del chat | Alta | Guard `if "chat_session" not in st.session_state` | ✅ app.py |
| Output de tools demasiado grande | Media | `safe_result()` limita a 15 filas + `.to_markdown()` | ✅ tools.py helpers |
| Insights engine no encuentra anomalías | Media | Threshold adaptativo: 0.10 → 0.05 si <3 resultados | ✅ insights_engine.py |

---

## 10. Checklist final pre-demo

### Código
- [ ] `python test_tools.py` → "🎉 Todos los tests pasaron"
- [ ] `streamlit run app.py` arranca sin errores desde entorno limpio
- [ ] `demo_fallback.json` tiene las 5 respuestas reales copiadas

### Bot
- [ ] Las 5 preguntas de demo funcionan sin errores
- [ ] El expander de debug muestra tools_used en cada respuesta
- [ ] La memoria funciona: "¿Y en México?" entiende el contexto previo
- [ ] Cada respuesta: datos + interpretación + recomendación + follow-ups

### Insights
- [ ] Reporte tiene ≥5 hallazgos de distintos tipos
- [ ] Cada hallazgo tiene recomendación accionable
- [ ] Markdown se renderiza correctamente en Streamlit

### Infraestructura
- [ ] `.env.example` en el repo
- [ ] `requirements.txt` con versiones fijas
- [ ] README: instrucciones de 3 pasos que funcionan

### Demo en vivo
- [ ] 5 preguntas probadas ≥10 veces
- [ ] Saber dónde está demo_fallback.json y cómo activarlo
- [ ] App corriendo 10 minutos antes de empezar

---

## 11. Estructura de la presentación (30 min)

| Segmento | Tiempo | Qué mostrar |
|---|---|---|
| Contexto y approach | 3 min | Problema, decisiones de priorización, por qué este stack |
| Demo Bot — 5 preguntas | 10 min | Orden de dificultad creciente, mostrar debug expander en ≥1 |
| Demo Insights | 5 min | Generar reporte en vivo, explicar 2-3 hallazgos concretos |
| Decisiones técnicas | 5 min | Gemini + function calling vs alternativas, trade-offs honestos |
| Limitaciones / Next Steps | 2 min | Qué sacrificaste, qué harías con 5 días |
| Q&A | 5 min | — |

**Frases clave para la presentación:**
- *"El debug expander muestra exactamente qué función se llamó — los números nunca son inventados"*
- *"Elegí function calling propio sobre PandasAI porque en demo en vivo la confiabilidad vale más que la velocidad de desarrollo"*
- *"Los insights son deterministas — no son magia de ML, son reglas de negocio explicables"*
- *"Si la API falla en demo, tengo un plan B con respuestas pre-generadas. No confío en el WiFi de la sala"*
- *"El loop multi-tool permite que Gemini compare dos métricas en paralelo en un solo turno"*