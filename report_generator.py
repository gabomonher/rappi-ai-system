"""
report_generator.py — Agente sintetizador de texto (sin tools).

Toma los hallazgos de insights_engine.py y redacta un reporte Markdown
ejecutivo usando Gemini (una única llamada).
"""

import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Igual que en bot.py, usamos flash-lite/flash para dev, luego se puede subir a pro
MODEL = "gemini-2.5-flash-lite"

def format_findings_for_llm(findings: list[dict]) -> str:
    """Convierte la lista de diccionarios a un formato de texto estructurado para el prompt."""
    if not findings:
        return "No se detectaron hallazgos significativos esta semana."
    
    text_blocks = []
    for i, f in enumerate(findings, 1):
        block = f"[{i}] TIPO: {f['type'].upper()} | MAGNITUD: {f['magnitude']}%\n"
        block += f"    ZONA: {f['zone']} ({f['city']}, {f['country']})\n"
        block += f"    METRICA: {f['metric']}\n"
        block += f"    DESCRIPCION: {f['description']}\n"
        block += f"    DATA: {json.dumps(f['data'])}\n"
        text_blocks.append(block)
    
    return "\n".join(text_blocks)

def generate_report(findings: list[dict]) -> str:
    """
    Hace UNA sola llamada a Gemini para redactar el reporte ejecutivo.
    No usa herramientas (tools).
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    system_instruction = "Eres un analista ejecutivo de operaciones de Rappi. Redacta reportes claros, directos y accionables orientados a Ops Managers y City Managers."
    
    formatted_data = format_findings_for_llm(findings)
    
    prompt = f"""
Basado en los siguientes hallazgos de datos generados por nuestro motor de insights, redacta un reporte ejecutivo en Markdown.

HALLAZGOS DETECTADOS:
{formatted_data}

ESTRUCTURA OBLIGATORIA DEL REPORTE:
# 🚨 Reporte Semanal de Operaciones Rappi

## Resumen Ejecutivo
[Redacta 3 o 4 frases críticas sintetizando lo más importante de los hallazgos]

## Top 5 Hallazgos Críticos
[Para cada uno de los hallazgos más importantes, usa el siguiente formato]
### 1. [Título conciso del hallazgo] | [Tipo] | [Zona] | [Magnitud]
**Por qué importa:** [Explica el impacto de negocio de este hallazgo]
**Recomendación accionable:** [Qué debería hacer el equipo de operaciones al respecto]

[Repite para los top 5...]

## ⚠️ Métricas a Vigilar Esta Semana
[Menciona 2 o 3 métricas o zonas que quedaron fuera del top 5 pero que muestran comportamiento preocupante o correlaciones interesantes según la data provista]
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3, # Baja temperatura para que sea analítico y consistente
        ),
    )
    
    return response.text

def save_report(report_text: str, path: str = "reporte_insights.md"):
    """Guarda el texto del reporte en un archivo Markdown."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"✅ Reporte guardado exitosamente en: {path}")

# ---------------------------------------------------------------------------
# BLOQUE MAIN (Prueba de integración)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from data_loader import load_data
    from insights_engine import run_all_insights
    
    SEP = "=" * 60
    print(f"\n{SEP}")
    print("🚀 Iniciando Pipeline de Reporte Automático...")
    print(SEP)
    
    print("1. Cargando datos...")
    df_metrics, df_orders, df_long = load_data("data/rappi_data.xlsx")
    
    print("2. Ejecutando motor de insights...")
    findings = run_all_insights(df_metrics, df_long, df_orders)
    print(f"   ✓ {len(findings)} hallazgos detectados.")
    
    print(f"3. Generando reporte ejecutivo con {MODEL}...")
    report_md = generate_report(findings)
    
    print("4. Guardando archivo...")
    save_report(report_md)
    
    print(f"\n{SEP}")
    print("📊 VISTA PREVIA DEL REPORTE:")
    print(SEP)
    # Mostramos los primeros 800 caracteres como vista previa
    print(report_md[:800] + "\n...\n[REPORTE TRUNCADO PARA VISTA PREVIA]")
    print(SEP)
