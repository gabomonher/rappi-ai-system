import json
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# CONFIGURACIÓN INICIAL
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Rappi AI Analytics", page_icon="🛵", layout="wide")

# ---------------------------------------------------------------------------
# CARGA DE DATOS Y CONTEXTO
# ---------------------------------------------------------------------------
@st.cache_data
def get_data():
    from data_loader import load_data
    return load_data("data/rappi_data.xlsx")

try:
    df_metrics, df_orders, df_long = get_data()
    # Inyectar en tools como globals
    import tools
    tools.df_metrics = df_metrics
    tools.df_orders = df_orders
    tools.df_long = df_long
except Exception as e:
    st.error(f"Error cargando los datos: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# ESTADO DE LA SESIÓN (SESSION STATE)
# ---------------------------------------------------------------------------
if "chat_session" not in st.session_state:
    from bot import create_session
    try:
        st.session_state.chat_session = create_session()
    except Exception as e:
        st.error(f"Error al conectar con Gemini (¿Falta API KEY?): {e}")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "findings" not in st.session_state:
    st.session_state.findings = None

if "report" not in st.session_state:
    st.session_state.report = None

# ---------------------------------------------------------------------------
# FUNCIÓN CHAT CON FALLBACK
# ---------------------------------------------------------------------------
def chat_with_fallback(user_message: str, chat_session) -> tuple[str, list[str]]:
    """Intenta usar la API real de Gemini, si falla usa el JSON de fallback."""
    try:
        from bot import chat
        return chat(user_message, chat_session)
    except Exception as e:
        try:
            with open("demo_fallback.json", "r", encoding="utf-8") as f:
                fallback = json.load(f)
            # Buscar coincidencia parcial (hardcoded questions)
            for key, item in fallback.items():
                if item["pregunta"].lower() in user_message.lower():
                    st.warning("⚠️ Modo offline — respuesta pre-generada")
                    return item["respuesta"], ["fallback"]
        except Exception as fallback_error:
            pass
        
        st.error(f"Error de conexión: {str(e)}")
        return "", []

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🛵 Rappi AI Analytics")
    
    paises = ["Todos", "AR", "BR", "CL", "CO", "CR", "EC", "MX", "PE", "UY"]
    selected_country = st.selectbox("Filtro Global (País):", paises)
    
    if st.button("🗑️ Nueva conversación", use_container_width=True):
        st.session_state.messages = []
        from bot import create_session
        try:
            st.session_state.chat_session = create_session()
        except:
            pass
        st.rerun()
        
    st.divider()
    st.info("💡 **Tip**: Pregunta por las peores zonas en 'Perfect Orders' o analiza tendencias de 'Lead Penetration'.")
    st.caption("~$0.015 por query (Gemini 2.0 Flash / Pro)")

# ---------------------------------------------------------------------------
# MAIN LAYOUT — TABS
# ---------------------------------------------------------------------------
tab1, tab2 = st.tabs(["🤖 Bot Conversacional", "📊 Insights Automáticos"])

with tab1:
    st.header("Analista de Operaciones Rappi 💬")
    
    # Renderizar historial de mensajes
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "tools" in message and message["tools"]:
                tools_list = message["tools"]
                tool_names = [t.get("name", str(t)) if isinstance(t, dict) else t for t in tools_list]
                
                if "fallback" in tool_names:
                    st.warning("⚠️ Respuesta offline pre-generada.")
                else:
                    with st.expander(f"🔧 Debug — herramientas usadas: {tool_names}"):
                        st.caption("✅ Datos extraídos directamente de la base Pandas/Excel, NO son alucinaciones del LLM.")
                        
                    # Dibujar gráficos extra si hay DFs disponibles
                    for t in tools_list:
                        if isinstance(t, dict) and t.get("df") is not None and not t["df"].empty:
                            if "error" in t["df"].columns: continue # Saltar si hubo error
                            
                            if t["name"] == "trend_analysis":
                                from visualizer import create_trend_chart
                                metric = t["args"].get("metric", "Métrica")
                                label = t["args"].get("zone") or t["args"].get("city") or t["args"].get("country") or "Global"
                                fig = create_trend_chart(t["df"], metric, label)
                                st.plotly_chart(fig, use_container_width=True)
                            
                            elif t["name"] == "compare_segments":
                                from visualizer import create_bar_chart
                                metric = t["args"].get("metric", "Métrica")
                                group_col = t["args"].get("segment", "Segmento")
                                fig = create_bar_chart(t["df"], metric, group_col)
                                st.plotly_chart(fig, use_container_width=True)
    
    # Input de chat
    if prompt := st.chat_input("Pregúntame sobre las métricas de las zonas..."):
        # Mostrar mensaje del usuario inmediatamente
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Preparar mensaje para el LLM con el contexto del país si no es "Todos"
        llm_prompt = prompt
        if selected_country != "Todos":
            llm_prompt = f"[Contexto obligado: Filtra siempre por el país {selected_country}] {prompt}"
            
        # Añadir al historial
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Llamar al bot
        with st.chat_message("assistant"):
            if "chat_session" in st.session_state:
                with st.spinner("🔍 Analizando datos..."):
                    respuesta, tools_used = chat_with_fallback(llm_prompt, st.session_state.chat_session)
                
                if respuesta:
                    st.markdown(respuesta)
                    
                    if tools_used:
                        tool_names = [t.get("name", str(t)) if isinstance(t, dict) else t for t in tools_used]
                        if "fallback" in tool_names:
                            st.warning("⚠️ Respuesta offline pre-generada.")
                        else:
                            with st.expander(f"🔧 Debug — herramientas usadas: {tool_names}"):
                                st.caption("✅ Datos extraídos directamente de la base Pandas/Excel, NO son alucinaciones del LLM.")
                            
                            # Render charts immediately after receiving if applicable
                            for t in tools_used:
                                if isinstance(t, dict) and t.get("df") is not None and not t["df"].empty:
                                    if "error" in t["df"].columns: continue
                                    
                                    if t["name"] == "trend_analysis":
                                        from visualizer import create_trend_chart
                                        metric = t["args"].get("metric", "Métrica")
                                        label = t["args"].get("zone") or t["args"].get("city") or t["args"].get("country") or "Global"
                                        fig = create_trend_chart(t["df"], metric, label)
                                        st.plotly_chart(fig, use_container_width=True)
                                    
                                    elif t["name"] == "compare_segments":
                                        from visualizer import create_bar_chart
                                        metric = t["args"].get("metric", "Métrica")
                                        group_col = t["args"].get("segment", "Segmento")
                                        fig = create_bar_chart(t["df"], metric, group_col)
                                        st.plotly_chart(fig, use_container_width=True)
                    
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": respuesta,
                        "tools": tools_used
                    })
            else:
                st.error("No hay sesión de chat activa.")

with tab2:
    st.header("📊 Insights Automáticos")
    st.write("Detección determinista de hallazgos críticos sin escribir queries.")
    
    # Calcular insights la primera vez
    if st.session_state.findings is None:
        with st.spinner("Calculando insights sobre la data actualizada..."):
            from insights_engine import run_all_insights
            import tools
            
            try:
                st.session_state.findings = run_all_insights(
                    tools.df_metrics, tools.df_long, tools.df_orders
                )
            except Exception as e:
                st.error(f"Error procesando insights: {e}")
                st.session_state.findings = []
    
    findings = st.session_state.findings
    
    if findings:
        # Contadores por tipo
        counts = {"anomaly": 0, "sustained_decline": 0, "opportunity": 0, "benchmarking_gap": 0, "correlation": 0}
        for f in findings:
            counts[f["type"]] = counts.get(f["type"], 0) + 1
            
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🚨 Anomalías (Spikes/Drops)", counts.get("anomaly", 0))
        with col2:
            st.metric("📉 Caídas Sostenidas", counts.get("sustained_decline", 0))
        with col3:
            st.metric("💡 Oportunidades", counts.get("opportunity", 0))
            
        st.divider()
        
        # Generar Reporte
        st.subheader("📝 Reporte Ejecutivo")
        
        if st.session_state.report is None:
            if st.button("🔍 Generar Reporte Ejecutivo con IA", type="primary"):
                with st.spinner("Redactando reporte con Gemini 2.5 Flash Lite..."):
                    from report_generator import generate_report
                    try:
                        report_md = generate_report(findings)
                        st.session_state.report = report_md
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error generando reporte: {e}")
        else:
            # Mostrar el reporte generado
            st.markdown(st.session_state.report)
            
            # Botón de descarga
            st.download_button(
                label="📥 Descargar Reporte (Markdown)",
                data=st.session_state.report,
                file_name="reporte_insights.md",
                mime="text/markdown"
            )
            
            if st.button("🔄 Regenerar Reporte"):
                st.session_state.report = None
                st.rerun()
    else:
        st.info("No se encontraron hallazgos significativos en la base de datos.")