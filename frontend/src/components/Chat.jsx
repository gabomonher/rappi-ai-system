import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import Plot from 'react-plotly.js';
import './Chat.css';

const SUGGESTIONS = [
  { label: "Zonas problemáticas CO", query: "¿Cuáles son las 5 peores zonas en Perfect Orders en Colombia?" },
  { label: "Comparar GP UE MX vs CL", query: "Compara Gross Profit UE entre México y Chile" },
  { label: "Tendencia Lead Pen BR", query: "Muéstrame la tendencia de Lead Penetration en Brasil" },
  { label: "Top crecimiento órdenes", query: "¿Cuáles son las zonas que más crecen en órdenes?" }
];

export default function Chat({ initialQuery = null, onQueryConsumed = () => {} }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [country, setCountry] = useState('Todos');
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);
  const firedRef = useRef(false); // Prevent double-firing initialQuery
  
  // API base is proxied to :8000 via vite.config.js
  const apiBase = '/api';

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Auto-fire query coming from a Bento Card click in Insights tab
  useEffect(() => {
    if (initialQuery && !firedRef.current) {
      firedRef.current = true;
      handleSend(initialQuery);
      onQueryConsumed();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  const handleSend = async (text) => {
    if (!text.trim()) return;
    
    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await axios.post(`${apiBase}/chat`, {
        message: text,
        session_id: "demo-session",
        country: country
      });
      
      if (res.data.tools && res.data.tools.length > 0) {
        // Log tools exclusively for debugging in Chrome/Browser DevTools
        console.group("🔧 Herramientas usadas por Gemini");
        res.data.tools.forEach((t, i) => {
          console.log(`[${i + 1}] ${t.name}:`, t.data || t.args || t);
        });
        console.groupEnd();
      }

      const botMsg = {
        role: 'assistant',
        content: res.data.text,
        tools: res.data.tools
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'assistant', content: "⚠️ Error de conexión con el backend." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    setMessages([]);
    try {
      await axios.post(`${apiBase}/chat`, {
        message: "clear",
        clear_cache: true,
        session_id: "demo-session"
      });
    } catch (e) { console.error(e); }
  };

  // Eliminar el área interactiva de herramientas de datos a petición.

  return (
    <div className="chat-container">
      {/* Filtros */}
      <div className="chat-controls">
        <select value={country} onChange={(e) => setCountry(e.target.value)} className="country-select">
          <option value="Todos">País: Todos</option>
          {["AR", "BR", "CL", "CO", "CR", "EC", "MX", "PE", "UY"].map(c => (
            <option key={c} value={c}>País: {c}</option>
          ))}
        </select>
        <button onClick={handleClear} className="btn-secondary">Limpiar chat</button>
      </div>

      {/* Historial */}
      <div className="chat-history">
        {messages.length === 0 && (
          <div className="welcome-section">
            <div className="message message-assistant" style={{marginBottom: '24px'}}>
              <div className="message-bubble" style={{maxWidth: '80%', lineHeight: '1.6'}}>
                <h3>🤖 ¡Hola! Soy el AI Ops Assistant de Rappi.</h3>
                <p>Estoy conectado al motor de métricas y puedo analizar datos de <b>9 países</b> y más de <b>1,100 zonas</b> en tiempo real.</p>
                <p><b>¿Qué puedo hacer por ti?</b></p>
                <ul style={{marginTop: '8px', paddingLeft: '20px'}}>
                  <li>📊 Analizar tendencias semanales de métricas <i>(ej. Perfect Orders, Turbo Adoption)</i>.</li>
                  <li>🚨 Detectar caídas sostenidas y anomalías críticas operacionales.</li>
                  <li>🔍 Comparar el rendimiento (Gross Profit, CVR) entre países o zonas específicas.</li>
                </ul>
                <p style={{marginTop: '12px'}}>Selecciona una de las consultas sugeridas o escríbeme lo que necesites buscar.</p>
              </div>
            </div>
            <div className="suggestions">
              {SUGGESTIONS.map((s, i) => (
                <button key={i} className="suggestion-pill" onClick={() => handleSend(s.query)}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role === 'user' ? 'message-user' : 'message-assistant'}`}>
            <div className="message-bubble">
              <ReactMarkdown>{m.content}</ReactMarkdown>
            </div>
          </div>
        ))}

        {loading && (
          <div className="message message-assistant">
            <div className="message-bubble loading-bubble">Analizando datos...</div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="chat-input-area">
        <input 
          type="text" 
          placeholder="Escribe tu query sobre métricas operacionales o selecciona una sugerencia..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend(input)}
          disabled={loading}
        />
      </div>
    </div>
  );
}
