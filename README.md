# 🛵 Rappi AI Analytics System

*Un copiloto analítico conversacional para Operaciones de Rappi, impulsado por Gemini 2.5 y Function Calling determinista.*

---

## 🚀 Resumen del Proyecto
El **Rappi AI Analytics System** está diseñado para revolucionar la manera en que los Ops Managers y City Managers interactúan con la información. A través de una interfaz conversacional en lenguaje natural, permite analizar el desempeño operativo de las distintas zonas sin necesidad de escribir código o consultas SQL complejas.

Para garantizar la integridad y precisión de los datos corporativos, el sistema utiliza inteligencia artificial **únicamente para orquestación semántica y generación de texto**, mientras que todos los cálculos matemáticos, filtrados y cruces de datos se ejecutan en Python (Pandas) bajo reglas estrictas de negocio. El resultado: **100% trazabilidad operativa y 0% de alucinaciones en las métricas.**

---

## 🛠️ Cómo Inicializar el Proyecto Localmente

Para desplegar el sistema en un entorno de desarrollo local, sigue estos 4 sencillos pasos:

1. **Clonar el repositorio y entrar al directorio:**
   ```bash
   git clone <repo-url>
   cd rappi-ai-system
   ```

2. **Instalar las dependencias requeridas:**
   Se recomienda usar un entorno virtual (`venv` o `conda`).
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar las credenciales de entorno:**
   Copia el archivo de ejemplo y agrega tu API Key de Google Gemini.
   ```bash
   cp .env.example .env
   ```
   *(Abre `.env` en tu editor principal y define `GEMINI_API_KEY="tu_clave_aqui"`, generada en Google AI Studio)*

4. **Lanzar la aplicación interactiva:**
   ```bash
   streamlit run app.py
   ```
   La interfaz gráfica estará disponible en http://localhost:8501.

---

## 🏗️ Arquitectura de la Solución

El proyecto sigue una arquitectura modular y escalable en la cual cada archivo tiene una única responsabilidad claramente definida:

| Archivo | Responsabilidad Principal |
|---------|---------------------------|
| **`app.py`** | Controlador Front-End (Streamlit). Gestiona la interfaz del bot conversacional, estado de sesión y visualización de insights automáticos. |
| **`bot.py`** | Orquestador de la Inteligencia Artificial. Maneja el loop *multi-tool* para ejecutar múltiples funciones en un solo turno usando el robusto SDK `google-genai`. |
| **`tools.py`** | Colección de funciones analíticas deterministas de Pandas inyectadas como *tools* dentro de Gemini. Son el "cerebro lógico" de las respuestas. |
| **`insights_engine.py`** | Motor estadístico offline capaz de detectar de forma autónoma anomalías, brechas e impacto sin intervención de LLMs. |
| **`report_generator.py`** | Sintetizador de reportes ejecutivos. Toma resultados del `insights_engine` y redacta un entregable estructurado en Markdown legible por perfiles de management. |
| **`context.py`** | Contiene el `SYSTEM_PROMPT` con el comportamiento corporativo y directrices exactas de nuestro analista conversacional. |
| **`data_loader.py`** | Módulo de pre-procesamiento de datos. Se encarga de la limpieza de datos (deduplicación, imputación) garantizando la calidad antes de llegar al sistema. |

---

## 🧠 Decisiones Técnicas y de Diseño

Durante el desarrollo e ideación, prioricé la **fiabilidad**, la **transparencia organizativa** y la **velocidad de iteración**:

1. **Function Calling Nativo vs Data Agents Genéricos (PandasAI):** 
   Elegí implementar *Function Calling* estructurado y restrictivo de Gemini por sobre bibliotecas donde la IA genera consultas "ad-hoc". En un entorno corporativo real, la seguridad y predecibilidad de usar reglas de negocio sólidas y *hardcodeadas* supera ampliamente la flexibilidad insegura de que un modelo escriba código arbitrario al vuelo.
   
2. **Insights Deterministas Completamente Explicables:** 
   El motor que detecta y propone insights se apoya en operaciones matemáticas claras (Rango Intercuartilíco, correlaciones de Pearson predefinidas y *week-over-week growth*). Esto lo hace 100% transparente, reproducible y explicable para los equipos de operaciones y finanzas.
   
3. **Data Estructurada y Vectorizada en RAM:** 
   Para los fines de este POC (Proof of Concept), más de 100k registros son manipulados de forma asíncrona pero eficiente en RAM a través del motor optimizado de Pandas (sin for-loops nativos en su procesamiento de series), garantizando latencias y tiempos de respuesta extremadamente competitivos.

---

## 💸 Factibilidad Operacional y Costos Estimados

El balanceo lógico de las responsabilidades, dejando el cómputo masivo local en Pandas y delegando tan solo la inferencia semántica a la API, permite un esquema de costos predecible y minúsculo usando los modelos ligeros de estado del arte (`Flash-Lite / Flash`):

- **Query Simple:** ~$0.01 por turno analítico.
- **Query Estructural Complejo:** ~$0.02 (involucrando múltiples extracciones y *tool calls* en cascada).
- **Generación del Reporte Semanal Integral:** ~$0.05.
- **Sesión Operativa Típica Continuada (~20 min):** Usualmente por debajo de $0.20 por usuario activo total.

---

## 🚀 Limitaciones y Siguientes Pasos Evolutivos

Si dispusiera de recursos adicionales de ingeniería y tiempo para expandir esta iniciativa iterativamente, priorizaría lo siguiente en el roadmap:

1. **Integración con Data Warehouses Corporativos:** Desacoplar `data_loader.py` de archivos estáticos y conectarlo eficientemente a repositorios de producción (AWS Redshift / Snowflake / BigQuery) utilizando conectores nativos y cachés en la nube.
2. **Modelos Empíricos Avanzados:** Introducir un pipeline con Facebook Prophet o modelos ARIMA para no solo medir la caída en retención, sino también hacer un *forecasting* de volumetría y *churn rate* semanas antes de que suceda.
3. **Despliegue y Autenticación Corporativa:** Empaquetar la aplicación en contenedores (Docker) y desplegarla en un entorno administrado (Streamlit Cloud o AWS ECS) habilitando SSO (Single Sign-On) estricto.
