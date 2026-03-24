import React, { useState, useEffect } from 'react';
import Chat from './components/Chat';
import Insights from './components/Insights';
import axios from 'axios';

function App() {
  const [metrics, setMetrics] = useState({ zones: 0, countries: 0 });
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' or 'insights'
  const [showInfo, setShowInfo] = useState(false);
  const [pendingQuery, setPendingQuery] = useState(null);
  
  useEffect(() => {
    setMetrics({ zones: 1129, countries: 9 });
  }, []);

  // Called when user clicks a Bento Card in Insights:
  // builds an analytical query and routes the user to the Chat tab.
  const handleAnalyzeCard = (finding) => {
    const q = `Anomalía detectada por el motor de insights:
- Métrica: ${finding.metric}
- Zona: ${finding.zone} (${finding.city}, ${finding.country})
- Tipo: ${finding.type} | Magnitud: ${finding.magnitude}%
- Descripción: ${finding.description}

Usa tus herramientas para obtener el contexto de datos y haz un análisis profundo: causas, impacto operacional y acciones concretas para el equipo de Ops.`;
    setPendingQuery(q);
    setActiveTab('chat');
  };

  return (
    <div className="app-container">
      {/* Top Nav */}
      <header className="top-nav">
        <div className="top-nav-left">
          <div className="nav-logo">R</div>
          <span className="nav-title">Ops Intelligence Hub</span>
          <span className="nav-badge">{metrics.zones} zonas · {metrics.countries} países</span>
        </div>
        
        {/* Tab System in Center/Right */}
        <div className="nav-tabs">
          <button 
            className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            🤖 AI Data Chat
          </button>
          <button 
            className={`nav-tab ${activeTab === 'insights' ? 'active' : ''}`}
            onClick={() => setActiveTab('insights')}
          >
            📊 Auto-Insights Feed
          </button>
        </div>

        <div className="top-nav-right">
          <button 
            className="nav-badge role-badge" 
            onClick={() => setShowInfo(true)}
            style={{cursor: 'pointer', border: 'none', background: 'rgba(250, 61, 34, 0.1)', color: '#fa3d22', padding: '6px 14px'}}
          >
            📊 Info Dataset
          </button>
        </div>
      </header>

      {/* Main Layout */}
      <main className="main-layout single-view">
        {activeTab === 'chat' && (
          <section className="view-container">
            <Chat initialQuery={pendingQuery} onQueryConsumed={() => setPendingQuery(null)} />
          </section>
        )}
        
        {activeTab === 'insights' && (
          <section className="view-container">
            <Insights onAnalyzeCard={handleAnalyzeCard} />
          </section>
        )}
      </main>

      {/* Info Modal */}
      {showInfo && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', 
          backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 9999,
          display: 'flex', justifyContent: 'center', alignItems: 'center'
        }}>
          <div style={{
            background: '#1f1f22', border: '1px solid #3f3f46', borderRadius: '12px',
            padding: '24px', maxWidth: '500px', width: '90%', color: '#d4d4d8',
            boxShadow: '0 10px 25px rgba(0,0,0,0.5)'
          }}>
            <h2 style={{marginTop: 0, color: '#ffffff', fontSize: '18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              Información del Dataset Analítico
              <button 
                onClick={() => setShowInfo(false)} 
                style={{background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: '20px'}}
              >
                ×
              </button>
            </h2>
            <div style={{lineHeight: '1.6', fontSize: '14px'}}>
              <p>Este hub está conectado a la base de datos de <b>Operaciones y SP&A</b>, abarcando <span style={{color: '#fa3d22', fontWeight: 'bold'}}>{metrics.zones}</span> zonas a nivel global.</p>
              
              <h4 style={{color: '#ffffff', marginBottom: '8px', marginTop: '16px'}}>🌎 Cobertura (9 Países)</h4>
              <p>Argentina (AR), Brasil (BR), Chile (CL), Colombia (CO), Costa Rica (CR), Ecuador (EC), México (MX), Perú (PE), Uruguay (UY).</p>

              <h4 style={{color: '#ffffff', marginBottom: '8px', marginTop: '16px'}}>📈 Métricas Clave Monitoreadas</h4>
              <ul style={{paddingLeft: '20px', margin: 0}}>
                <li><b>Perfect Orders:</b> % de órdenes entregadas sin defectos.</li>
                <li><b>Defect Rate:</b> Tasa general de defectos.</li>
                <li><b>Turbo Adoption:</b> Penetracion del formato Turbo.</li>
                <li><b>Gross Profit UE (USD):</b> Rentabilidad Unitaria bruta.</li>
                <li><b>Lead Penetration:</b> Participación de mercado por zona.</li>
                <li><b>TTR:</b> Time To Resolution (Soporte).</li>
              </ul>

              <h4 style={{color: '#ffffff', marginBottom: '8px', marginTop: '16px'}}>📅 Granularidad Temporal</h4>
              <p>Análisis en ventanas móviles de 9 semanas (L0W = Actual hasta L8W = Histórica).</p>
            </div>
            <div style={{marginTop: '24px', textAlign: 'right'}}>
              <button className="btn-primary" onClick={() => setShowInfo(false)}>Entendido</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
