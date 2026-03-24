"""
report_generator.py — Agente sintetizador de texto (sin tools).

Toma los hallazgos de insights_engine.py y redacta un reporte Markdown
ejecutivo usando Gemini (una única llamada).
Opcionalmente genera un PDF estilizado.
"""

import os
import io
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
import markdown
from fpdf import FPDF

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
# Reporte Semanal de Operaciones Rappi

## Resumen Ejecutivo
[Redacta 3 o 4 frases críticas sintetizando lo más importante de los hallazgos]

## Top 5 Hallazgos Críticos
[Para cada uno de los hallazgos más importantes, usa el siguiente formato]
### 1. [Título conciso del hallazgo] | [Tipo] | [Zona] | [Magnitud]
**Por qué importa:** [Explica el impacto de negocio de este hallazgo]
**Recomendación accionable:** [Qué debería hacer el equipo de operaciones al respecto]

[Repite para los top 5...]

## Métricas a Vigilar Esta Semana
[Menciona 2 o 3 métricas o zonas que quedaron fuera del top 5 pero que muestran comportamiento preocupante o correlaciones interesantes según la data provista]

REGLAS IMPORTANTES:
- NO uses emojis en el reporte
- Usa texto plano y profesional
- Las tablas deben usar formato Markdown estándar
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
    print(f"Reporte guardado exitosamente en: {path}")


# ---------------------------------------------------------------------------
# GENERACIÓN DE PDF ESTILIZADO CON fpdf2
# ---------------------------------------------------------------------------

class _RappiPDF(FPDF):
    """PDF personalizado con header y footer branded de Rappi en Dark Mode."""

    def header(self):
        # 1. Barra naranja-coral superior (brand Rappi)
        self.set_fill_color(250, 61, 34)  # #fa3d22
        self.rect(0, 0, self.w, 24, "F")
        
        # 3. Títulos en la barra
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(255, 255, 255)
        self.set_y(5)
        self.cell(0, 8, "Rappi Ops Intelligence Hub", align="C", new_x="LMARGIN", new_y="NEXT")
        
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(255, 230, 230)
        self.cell(0, 5, "Reporte Ejecutivo Automatizado con IA", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Rappi Confidential  |  Página {self.page_no()}/{{nb}}", align="C")


def generate_pdf(report_md: str) -> bytes:
    """
    Convierte el reporte Markdown a HTML y usa fpdf2 para generar un PDF
    con un diseño Premium Dark Mode idéntico a la app web.
    """
    import re
    # Limpiar emojis (fpdf2 sufre renderizándolos sin fuentes especiales)
    clean_md = re.sub(
        r'[\U0001F600-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
        r'\u2600-\u26FF\u2700-\u27BF\u2B50\u2B55\u231A\u23F0-\u23FF'
        r'\u2934\u2935\u25AA\u25AB\u25FB-\u25FE\u2614\u2615'
        r'\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF]',
        '', report_md
    )

    # Markdown → HTML
    html_body = markdown.markdown(
        clean_md,
        extensions=["tables", "fenced_code"],
    )

    pdf = _RappiPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Reemplazo manual de etiquetas HTML para inyectar colores Light Mode.
    styled_html = html_body
    
    # Arreglar la ruta de la imagen generada dinámicamente:
    # El LLM devuelve: ![Alt](/api/reports/images/file.png)
    # Pero para que fpdf2 lo vea, la ruta debe ser local al servidor: 'reports/images/file.png'
    # Así fpdf2 lee el binario real e imprime la foto.
    styled_html = styled_html.replace('src="/api/', 'src="')
    
    styled_html = styled_html.replace("<h1>", '<h1 style="color: #fa3d22;">')
    styled_html = styled_html.replace("<h2>", '<h2 style="color: #222222;">')
    styled_html = styled_html.replace("<h3>", '<h3 style="color: #fa3d22;">')
    styled_html = styled_html.replace("<strong>", '<b style="color: #000000;">')
    styled_html = styled_html.replace("</strong>", '</b>')
    styled_html = styled_html.replace("<table>", '<table width="100%" border="1" bordercolor="#cccccc">')
    styled_html = styled_html.replace("<th>", '<th align="left" bgcolor="#fa3d22"><font color="#ffffff">')
    styled_html = styled_html.replace("</th>", '</font></th>')
    styled_html = styled_html.replace("<td>", '<td bgcolor="#ffffff"><font color="#333333">')
    styled_html = styled_html.replace("</td>", '</font></td>')

    # Color de texto base para párrafos y listas (Gris oscuro)
    pdf.set_text_color(51, 51, 51) 
    pdf.set_font("Helvetica", "", 10)
    pdf.write_html(styled_html)

    return bytes(pdf.output())

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
