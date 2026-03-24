import os
import json
import glob
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from . import bot
from .data_context import set_context, get_context
from .data_loader import load_data
from .insights_engine import run_all_insights
from .report_generator import generate_report, generate_pdf

load_dotenv()

# Paths resolved from file location so they hold in any CWD
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = str(_PROJECT_ROOT / "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)
# Global state for API
app_state = {
    "findings": [],
    "report_md": None,
    "chat_sessions": {}  # Simple session storage in memory
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load data, set context, and pre-compute insights
    try:
        print("🔄 Loading data...")
        df_metrics, df_orders, df_long = load_data()  # uses __file__-relative path
        set_context(df_metrics, df_orders, df_long)
        
        print("🔄 Computing insights...")
        ctx = get_context()
        app_state["findings"] = run_all_insights(ctx.df_metrics, ctx.df_long, ctx.df_orders)
        print(f"✅ Startup complete. Found {len(app_state['findings'])} insights.")
    except Exception as e:
        print(f"❌ Error during startup: {e}")
    yield
    # Shutdown
    print("🛑 Shutting down.")

app = FastAPI(title="Rappi Ops Intelligence API", lifespan=lifespan)

# Allow React frontend (default Vite port is 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    country: str = "Todos"
    clear_cache: bool = False

class ChatResponse(BaseModel):
    text: str
    tools: List[Dict[str, Any]]

# --- API Routes ---

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    session_id = request.session_id
    
    if request.clear_cache:
        bot.clear_cache()
        if session_id in app_state["chat_sessions"]:
            del app_state["chat_sessions"][session_id]

    # Get or create session
    if session_id not in app_state["chat_sessions"]:
        try:
            app_state["chat_sessions"][session_id] = bot.create_session()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gemini connection error: {e}")
            
    chat_session = app_state["chat_sessions"][session_id]
    
    # Format prompt with country context if selected
    llm_prompt = request.message
    if request.country != "Todos":
        llm_prompt = f"[Contexto obligado: Filtra siempre por el país {request.country}] {request.message}"
        
    # Attempt to chat
    try:
        # We don't use the Streamlit warning here, just a simple print callback or None
        respuesta, tools_used = bot.chat(
            llm_prompt, 
            chat_session, 
            retry_callback=lambda msg: print(f"Retry: {msg}")
        )
        
        # Clean DataFrames from tools_used for JSON serialization
        # We convert DataFrames to dicts so frontend can render them
        cleaned_tools = []
        for t in tools_used:
            if isinstance(t, dict):
                clean_t = {k: v for k, v in t.items() if k != 'df'}
                if 'df' in t and t['df'] is not None and not t['df'].empty:
                    if 'error' not in t['df'].columns:
                        clean_t['data'] = t['df'].to_dict(orient='records')
                cleaned_tools.append(clean_t)
            else:
                cleaned_tools.append({"name": str(t)})
                
        return ChatResponse(text=respuesta, tools=cleaned_tools)
        
    except Exception as e:
        # Fallback mechanism
        try:
            with open("demo_fallback.json", "r", encoding="utf-8") as f:
                fallback = json.load(f)
            for key, item in fallback.items():
                if item["pregunta"].lower() in request.message.lower():
                    return ChatResponse(
                        text=item["respuesta"], 
                        tools=[{"name": "fallback", "warning": "Modo offline — respuesta pre-generada"}]
                    )
        except:
            pass
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@app.get("/api/insights")
def get_insights():
    """Return pre-computed insights."""
    return {"findings": app_state["findings"]}

@app.post("/api/report/generate")
def generate_exec_report():
    """Generate the executive report using LLM."""
    if not app_state["findings"]:
        raise HTTPException(status_code=400, detail="No findings available to generate report.")
        
    try:
        report_md = generate_report(app_state["findings"])
        app_state["report_md"] = report_md
        
        # Guardar en disco con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.md"
        filepath = os.path.join(REPORTS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_md)
            
        return {"status": "success", "report_md": report_md, "filename": filename}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating report: {e}")

@app.get("/api/reports")
def list_reports():
    """List historical generated reports."""
    files = glob.glob(os.path.join(REPORTS_DIR, "*.md"))
    reports = []
    for f in files:
        filename = os.path.basename(f)
        try:
            # Parse timestamp report_YYYYMMDD_HHMMSS.md
            ts_str = filename.replace("report_", "").replace(".md", "")
            dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            formatted_date = dt.strftime("%d/%m/%Y %H:%M:%S")
        except:
            formatted_date = filename
            
        reports.append({
            "filename": filename,
            "date": formatted_date,
            "sort_key": os.path.getmtime(f)
        })
    # Sort newest first
    reports.sort(key=lambda x: x["sort_key"], reverse=True)
    return {"reports": reports}

@app.get("/api/reports/{filename}")
def get_historical_report(filename: str):
    """Retrieve an older report and set it as active."""
    filepath = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Report not found")
        
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    app_state["report_md"] = content
    return {"report_md": content}

@app.get("/api/reports/images/{filename}")
def get_report_image(filename: str):
    """Serve dynamically generated report chart images."""
    filepath = os.path.join(REPORTS_DIR, "images", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(filepath)

@app.get("/api/report/md")
def download_report_md():
    if not app_state["report_md"]:
        raise HTTPException(status_code=404, detail="Report not generated yet.")
    
    return Response(
        content=app_state["report_md"],
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="reporte_insights.md"'}
    )

@app.get("/api/report/pdf")
def download_report_pdf():
    if not app_state["report_md"]:
        raise HTTPException(status_code=404, detail="Report not generated yet.")
        
    try:
        pdf_bytes = generate_pdf(app_state["report_md"])
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="reporte_insights.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
