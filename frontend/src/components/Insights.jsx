import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import './Insights.css';

export default function Insights({ onAnalyzeCard = null }) {
  const [findings, setFindings] = useState([]);
  const [report, setReport] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [loading, setLoading] = useState(true);
  const [savedReports, setSavedReports] = useState([]);

  const apiBase = '/api';

  useEffect(() => {
    fetchInsights();
    fetchReports();
  }, []);

  const fetchReports = async () => {
    try {
      const res = await axios.get(`${apiBase}/reports`);
      setSavedReports(res.data.reports || []);
    } catch (e) {
      console.error("Error fetching historical reports", e);
    }
  };

  const loadReport = async (filename) => {
    try {
      const res = await axios.get(`${apiBase}/reports/${filename}`);
      setReport(res.data.report_md);
      setShowReport(true);
    } catch (e) {
      console.error(e);
      alert("Error al cargar reporte del historial");
    }
  };

  const fetchInsights = async () => {
    try {
      const res = await axios.get(`${apiBase}/insights`);
      setFindings(res.data.findings || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const generateReport = async () => {
    setGenerating(true);
    try {
      const res = await axios.post(`${apiBase}/report/generate`);
      setReport(res.data.report_md);
      setShowReport(true);
      fetchReports(); // Refresh history
    } catch (e) {
      console.error(e);
      alert("Error al generar reporte");
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadMd = () => {
    window.location.href = `${apiBase}/report/md`;
  };

  const handleDownloadPdf = () => {
    window.location.href = `${apiBase}/report/pdf`;
  };

  if (loading) {
    return <div className="loading-state">Cargando insights precalculados...</div>;
  }

  // Count distinct types
  const anomalies = findings.filter(f => f.type === 'anomaly').length;
  const declines = findings.filter(f => f.type === 'sustained_decline').length;
  const opps = findings.filter(f => f.type === 'opportunity').length;
  const gaps = findings.filter(f => f.type === 'benchmarking_gap').length;

  const getStyleForType = (type) => {
    switch (type) {
      case 'anomaly': return { label: 'CRÍTICO · ANOMALÍA', colorClass: 'critical' };
      case 'sustained_decline': return { label: 'ALERTA · CAÍDA SOSTENIDA', colorClass: 'critical' };
      case 'opportunity': return { label: 'OPORTUNIDAD', colorClass: 'success' };
      case 'benchmarking_gap': return { label: 'GAP VS BENCHMARK', colorClass: 'info' };
      default: return { label: 'INSIGHT', colorClass: 'info' };
    }
  };

  // Sort top 8 by highest magnitude magnitude
  const sortedFindings = [...findings].sort((a, b) => Math.abs(b.magnitude || 0) - Math.abs(a.magnitude || 0));
  const topFindings = sortedFindings.slice(0, 8);
  const detailsFindings = sortedFindings.slice(8);

  return (
    <div className="insights-container">
      {/* Metrics Row */}
      <div className="stat-row">
        <div className="stat-box">
          <div className="stat-value text-accent">{anomalies}</div>
          <div className="stat-label">Anomalías</div>
        </div>
        <div className="stat-box">
          <div className="stat-value">{declines}</div>
          <div className="stat-label">Caídas</div>
        </div>
        <div className="stat-box">
          <div className="stat-value">{opps}</div>
          <div className="stat-label">Oportunidades</div>
        </div>
        <div className="stat-box">
          <div className="stat-value">{gaps}</div>
          <div className="stat-label">Gaps</div>
        </div>
      </div>

      {/* Report Section */}
      <div className="section-label" style={{marginTop: 32, marginBottom: 16}}>Reporte Ejecutivo Automático</div>
      
      <div style={{display: 'flex', gap: '20px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 32}}>
        
        {/* Layout Left: Generador */}
        <div style={{flex: '2', minWidth: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(255,255,255,0.02)', padding: '24px', borderRadius: '12px'}}>
          {!report && (
             <div style={{display: 'flex', justifyContent: 'center', width: '100%'}}>
               <button className="btn-primary" onClick={generateReport} disabled={generating}>
                  {generating ? "Redactando con Gemini..." : "✨ Generar reporte con IA"}
               </button>
             </div>
          )}

          {report && !showReport && (
             <div style={{display: 'flex', justifyContent: 'center', gap: '16px', width: '100%'}}>
               <button className="btn-primary" onClick={() => setShowReport(true)}>
                  👁️ Abrir Reporte Actual
               </button>
               <button className="btn-secondary" style={{padding: '12px 28px', fontSize: '15px'}} onClick={generateReport} disabled={generating}>
                  {generating ? "Redactando..." : "↻ Nuevo Reporte"}
               </button>
             </div>
          )}
          
          {report && showReport && (
            <div style={{display: 'flex', justifyContent: 'center', width: '100%'}}>
              <span style={{color: '#d4d4d8', fontSize: '14px', fontStyle: 'italic'}}>El reporte está expandido abajo.</span>
            </div>
          )}
        </div>

        {/* Layout Right: Historial */}
        <div style={{flex: '1', minWidth: '300px', background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)'}}>
          <h4 style={{marginTop: 0, marginBottom: '12px', color: '#d4d4d8', fontSize: '15px'}}>Historial de Reportes</h4>
          {savedReports.length === 0 ? (
            <p style={{color: '#888', fontSize: '13px', margin: 0}}>No hay reportes guardados aún.</p>
          ) : (
            <div className="reports-history-list" style={{display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto', paddingRight: '8px'}}>
              {savedReports.map(r => (
                <button 
                  key={r.filename} 
                  className="btn-secondary" 
                  style={{textAlign: 'left', padding: '8px 12px', fontSize: '13px', border: '1px solid rgba(255,255,255,0.1)'}}
                  onClick={() => loadReport(r.filename)}
                >
                  📄 Reporte del {r.date.split(' ')[0]} <span style={{opacity: 0.5, marginLeft: '4px'}}>{r.date.split(' ')[1]}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {report && showReport && (
        <div className="report-box" style={{marginBottom: 32}}>
          <ReactMarkdown>{report}</ReactMarkdown>
          
          <div className="report-actions">
            <button className="btn-secondary" onClick={handleDownloadMd}>Descargar Markdown</button>
            <button className="btn-secondary" onClick={handleDownloadPdf}>Descargar PDF</button>
            <button className="btn-secondary" onClick={() => setShowReport(false)}>Ocultar Reporte</button>
          </div>
        </div>
      )}

      {/* Bento Cards */}
      <div className="section-label" style={{marginTop: 16}}>Hallazgos Top <span style={{fontSize: '12px', color: '#888', fontWeight: 'normal', marginLeft: '8px'}}>{onAnalyzeCard ? '— Haz clic en una tarjeta para analizarla en profundidad' : ''}</span></div>
      <div className="bento-grid">
        {topFindings.map((f, i) => {
          const style = getStyleForType(f.type);
          return (
            <div 
              key={i} 
              className={`bento-card bento-card-${style.colorClass}`}
              style={onAnalyzeCard ? {cursor: 'pointer', transition: 'transform 0.15s, box-shadow 0.15s'} : {}}
              onClick={() => onAnalyzeCard && onAnalyzeCard(f)}
              title={onAnalyzeCard ? 'Clic para analizar en el chat' : ''}
            >
              <div className={`card-type card-type-${style.colorClass}`}>{style.label} {onAnalyzeCard ? <span style={{float:'right', opacity: 0.5, fontSize: '10px'}}>🔍 Analizar</span> : ''}</div>
              <div className="card-title">{f.metric} · {f.zone}</div>
              <div className="card-meta">{f.city}, {f.country} · Magnitud: {f.magnitude}%</div>
              <div className="card-desc">{f.description}</div>
            </div>
          );
        })}
      </div>

      {detailsFindings.length > 0 && (
        <details className="tools-expander" style={{marginTop: 16}}>
          <summary>Ver {detailsFindings.length} hallazgos más</summary>
          <div className="tools-content">
             {detailsFindings.map((f, i) => {
                const style = getStyleForType(f.type);
                return (
                  <div 
                    key={i} 
                    className={`bento-card bento-card-${style.colorClass}`} 
                    style={{marginTop: 10, cursor: onAnalyzeCard ? 'pointer' : 'default'}}
                    onClick={() => onAnalyzeCard && onAnalyzeCard(f)}
                    title={onAnalyzeCard ? 'Clic para analizar en el chat' : ''}
                  >
                    <div className={`card-type card-type-${style.colorClass}`}>{style.label}</div>
                    <div className="card-title">{f.metric} · {f.zone}</div>
                    <div className="card-meta">{f.city}, {f.country} · Magnitud: {f.magnitude}%</div>
                    <div className="card-desc">{f.description}</div>
                  </div>
                );
             })}
          </div>
        </details>
      )}
    </div>
  );
}
