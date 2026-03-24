import os
import uuid
import matplotlib
matplotlib.use('Agg')  # Headless backend (no GUI required)
import matplotlib.pyplot as plt
from pathlib import Path

# Directorio base para imágenes — siempre relativo al proyecto
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_IMG_DIR = str(_PROJECT_ROOT / "reports" / "images")
os.makedirs(REPORTS_IMG_DIR, exist_ok=True)

def generate_charts(findings: list[dict], max_charts: int = 2) -> list[dict]:
    chart_urls = []
    
    # Filtramos hallazgos que tengan historial temporal en data (más de 2 datapoints)
    valid_findings = [
        f for f in findings 
        if isinstance(f.get("data"), dict) and len(f["data"]) > 1
    ]
    
    # Priorizar caídas o anomalías sobre oportunidades
    valid_findings.sort(key=lambda x: 1 if x.get("direction") == "cayó" else 2)
        
    for f in valid_findings[:max_charts]:
        metric = f["metric"]
        zone = f["zone"]
        data_dict = f["data"]  # Ej: {"L2W_ROLL": 0.5, "L1W_ROLL": 0.4, "L0W_ROLL": 0.3}
        
        # Ordenar cronológicamente asumiendo formato temporal (ej: L0W_ROLL, L1W_ROLL...)
        # Nota: L0W_ROLL significa Última Semana, por lo que históricamente el número cae
        keys = list(data_dict.keys())
        
        # Intentamos ordenar los X (tiempo) para que vayan de lo viejo a lo nuevo
        def get_week_num(k):
            try:
                # "L4W_ROLL" -> 4. A mayor número, más vieja.
                num = ''.join(c for c in k if c.isdigit())
                return int(num) if num else -1
            except:
                return -1
                
        sorted_keys = sorted(keys, key=get_week_num, reverse=True)
        # Extraer labels e values ordenados (de la semana más vieja a la más nueva)
        x_labels = [k.replace("_ROLL", "").replace("W", "") for k in sorted_keys]
        y_values = [data_dict[k] for k in sorted_keys]
            
        filename = f"chart_{uuid.uuid4().hex[:8]}.png"
        filepath = os.path.join(REPORTS_IMG_DIR, filename)
        
        # Estilos modernos de gráfico (Light Theme para fondo blanco del PDF)
        plt.figure(figsize=(6, 4))
        ax = plt.axes()
        
        # Ocultar bordes innecesarios
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cccccc')
        ax.spines['bottom'].set_color('#cccccc')
        
        # Color primario de Rappi (cayó = coral alert, subió = verde positive)
        color = '#fa3d22' if f.get("direction") == "cayó" else '#00cc66'
        
        # Trazar línea
        plt.plot(x_labels, y_values, marker='o', color=color, linewidth=2.5, markersize=8)
        
        # Rellenar bajo la curva sutilmente
        plt.fill_between(x_labels, y_values, color=color, alpha=0.1)
        
        # Etiquetas en los puntos para dar precisión en el resumen
        for idx, (x, y) in enumerate(zip(x_labels, y_values)):
            text = f"{y:.2g}"
            # Colocar texto sutilmente arriba del punto (y desplazar un poco)
            plt.annotate(text, (x, y), textcoords="offset points", xytext=(0,10), ha='center', fontsize=8, color='#555555')
        
        # Grid sutil horizontal
        plt.grid(True, axis='y', linestyle='--', alpha=0.5)
        
        # Styling y márgenes
        plt.title(f"{metric} - {zone}", fontsize=12, fontweight='bold', color='#333333', pad=15)
        plt.xticks(fontsize=9, color='#666666')
        plt.yticks(fontsize=9, color='#666666')
        plt.tight_layout()
        
        # Exportar y no mostrar
        plt.savefig(filepath, format="png", dpi=150, bbox_inches="tight")
        plt.close()
        
        # Guardamos la url pública
        url_path = f"/api/reports/images/{filename}"
        chart_urls.append({
            "metric": metric,
            "zone": zone,
            "url": url_path,
            "local_path": filepath
        })
        
    return chart_urls
