# Rappi Ops Intelligence Hub

> An end-to-end AI-powered analytics platform for Operations teams — featuring a conversational data analyst, an autonomous insight engine, AI-generated executive reports, and interactive Bento Card deep-dives.

---

## Demo & Overview

| Feature | Description |
|---|---|
| 🤖 **AI Data Chat** | Ask operational questions in natural language. Gemini orchestrates deterministic Pandas tools to return real, traceable metrics. |
| 📊 **Auto-Insights Feed** | Autonomous statistical engine detects anomalies, sustained declines, and growth opportunities across 1,129 zones — without LLM involvement. |
| 📄 **AI Executive Reports** | One-click Markdown & PDF reports written by Gemini, with auto-generated trendline charts embedded. Saved with timestamps for historical access. |
| 🔍 **Bento Card Deep-Dives** | Click any insight card to instantly route it to the Chat for a deep analytical conversation. |

---

## Architecture

This project follows a **decoupled client-server** architecture, separating AI/data logic from presentation:

```
rappi-ai-system/
├── backend/                   # Python package — all server-side logic
│   ├── api.py                 # FastAPI REST API (entry point)
│   ├── bot.py                 # Gemini multi-tool orchestration loop
│   ├── tools.py               # Deterministic Pandas analytics functions (injected as Gemini tools)
│   ├── insights_engine.py     # Autonomous statistical insight engine (IQR, Pearson, WoW growth)
│   ├── report_generator.py    # AI executive report + PDF generation (fpdf2)
│   ├── report_graphics.py     # Matplotlib trendline chart generation
│   ├── data_loader.py         # Data cleaning & preprocessing pipeline
│   └── data_context.py        # Global data singleton + system prompt
├── frontend/                  # React + Vite application
│   └── src/
│       ├── App.jsx            # Root layout, tab routing, cross-component state
│       ├── components/
│       │   ├── Chat.jsx       # Conversational AI interface with Plotly chart rendering
│       │   └── Insights.jsx   # Insights feed, report generator, report history
├── data/                      # Source Excel dataset (gitignored)
├── reports/                   # Generated reports + chart images (persisted locally)
├── eda.py                     # Exploratory Data Analysis notebook-style script
└── requirements.txt
```

### Key Design Decisions

**1. Deterministic Tools Over Generative Code**  
All data computation uses hardcoded Pandas functions (`tools.py`) injected as Gemini Function Declarations. The LLM is *only* used for semantic understanding and text generation — it never writes or executes code. This guarantees **100% traceable, hallucination-free metrics** in a corporate context.

**2. Autonomous Insight Engine**  
`insights_engine.py` runs without any LLM involvement. It uses IQR-based anomaly detection, Pearson correlations, and week-over-week growth math to surface findings. The AI only enters the picture to *narrate* what the engine found.

**3. Multi-Tool Loop (Parallel Tool Calling)**  
`bot.py` implements a full `while True` loop that collects and executes **all function calls in a single turn** before returning to the model. This handles compound analytical queries (e.g., "compare X and show trend of Y") in one round trip.

**4. File-Relative Paths**  
All `pathlib.Path(__file__).resolve()` references mean the backend runs correctly from any working directory — critical after reorganizing into the `backend/` package.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **AI / LLM** | Google Gemini 2.5 Flash (`google-genai` SDK) |
| **Backend API** | FastAPI + Uvicorn |
| **Data Processing** | Pandas, NumPy |
| **PDF Generation** | fpdf2, python-markdown |
| **Chart Generation** | Matplotlib (headless `Agg` backend) |
| **Frontend** | React 18 + Vite |
| **Charts (UI)** | react-plotly.js |
| **Markdown Rendering** | react-markdown |

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- A [Google AI Studio](https://aistudio.google.com) API key (free tier works)

### 1. Clone & install backend dependencies

```bash
git clone <repo-url>
cd rappi-ai-system

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Open .env and set: GEMINI_API_KEY="your_key_here"
```

### 3. Start the backend

```bash
uvicorn backend.api:app --reload
# → API running on http://127.0.0.1:8000
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# → UI running on http://localhost:5173
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Conversational query with session state |
| `GET` | `/api/insights` | Pre-computed insights from the engine |
| `POST` | `/api/report/generate` | Generate AI executive report (with charts) |
| `GET` | `/api/report/md` | Download latest report as Markdown |
| `GET` | `/api/report/pdf` | Download latest report as branded PDF |
| `GET` | `/api/reports` | List all historical saved reports |
| `GET` | `/api/reports/{filename}` | Load a historical report |
| `GET` | `/api/reports/images/{filename}` | Serve generated chart images |

---

## Dataset Coverage

- **9 Countries:** AR, BR, CL, CO, CR, EC, MX, PE, UY
- **1,129 Zones** across all countries
- **13 Metrics:** Perfect Orders, Defect Rate, Turbo Adoption, Gross Profit UE, Lead Penetration, TTR, and more
- **Temporal granularity:** 9-week rolling windows (L0W to L8W)

---

## Cost Profile

The architecture intentionally pushes heavy computation to Pandas (CPU, free), only delegating semantic understanding to the LLM:

| Operation | Estimated Cost |
|---|---|
| Single analytical query | ~$0.01 |
| Complex multi-metric query | ~$0.02 |
| Full executive report generation | ~$0.05 |
| Typical 20-minute ops session | < $0.20 |

---

## Roadmap

1. **Production Data Integration** — Replace static Excel with Redshift / BigQuery connectors
2. **Forecasting** — Add Facebook Prophet for predictive weekly metric modeling
3. **User Authentication** — SSO integration for multi-user corporate deployment
4. **Containerization** — Docker + CI/CD pipeline for cloud deployment (AWS ECS / GCP Cloud Run)
5. **Alert System** — Automated Slack/email notifications when the insight engine detects critical anomalies
