# ==============================================================================
# EDA COMPLETO — Sistema de Análisis Inteligente para Operaciones Rappi
# ==============================================================================
# Cubre todos los hallazgos de la sesión de análisis:
#   1. Nulos
#   2. Consistencia de nombres y catálogos
#   3. Rangos de valores por métrica
#   4. Duplicados (Escenario A vs B)
#   5. Outliers e inactividad en órdenes
#   6. Cobertura temporal
#   7. Análisis de zonas sin L0W_ROLL (¿su historial es útil?)
#   8. Decisiones de limpieza documentadas
# ==============================================================================

import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
FILE_PATH = 'data/rappi_data.xlsx'

WEEK_COLS_METRICS = [
    'L8W_ROLL', 'L7W_ROLL', 'L6W_ROLL', 'L5W_ROLL',
    'L4W_ROLL', 'L3W_ROLL', 'L2W_ROLL', 'L1W_ROLL', 'L0W_ROLL'
]
WEEK_COLS_ORDERS_RAW  = ['L8W','L7W','L6W','L5W','L4W','L3W','L2W','L1W','L0W']
WEEK_COLS_ORDERS_ROLL = ['L8W_ROLL','L7W_ROLL','L6W_ROLL','L5W_ROLL',
                         'L4W_ROLL','L3W_ROLL','L2W_ROLL','L1W_ROLL','L0W_ROLL']

VALID_METRICS = [
    'Retail SST > SS CVR', 'Restaurants SST > SS CVR', 'Gross Profit UE',
    'Restaurants SS > ATC CVR', 'Non-Pro PTC > OP', '% PRO Users Who Breakeven',
    'Pro Adoption (Last Week Status)', 'MLTV Top Verticals Adoption',
    '% Restaurants Sessions With Optimal Assortment', 'Lead Penetration',
    'Restaurants Markdowns / GMV', 'Perfect Orders', 'Turbo Adoption'
]
VALID_COUNTRIES  = ['AR', 'BR', 'CL', 'CO', 'CR', 'EC', 'MX', 'PE', 'UY']
VALID_ZONE_TYPES = ['Wealthy', 'Non Wealthy']
VALID_PRIORITIES = ['High Priority', 'Prioritized', 'Not Prioritized']

SEP  = '=' * 70
SEP2 = '-' * 70

def sep(title=''):
    print(f'\n{SEP}')
    if title:
        print(f'  {title}')
        print(SEP)

# ==============================================================================
# CARGA DE DATOS
# ==============================================================================
sep('CARGA DE DATOS')
print(f'\nLeyendo: {FILE_PATH}')
df_orders  = pd.read_excel(FILE_PATH, sheet_name='RAW_ORDERS')
df_metrics = pd.read_excel(FILE_PATH, sheet_name='RAW_INPUT_METRICS')

# Renombrar columnas de orders para análisis unificado
df_orders.rename(columns={
    'L8W':'L8W_ROLL','L7W':'L7W_ROLL','L6W':'L6W_ROLL','L5W':'L5W_ROLL',
    'L4W':'L4W_ROLL','L3W':'L3W_ROLL','L2W':'L2W_ROLL','L1W':'L1W_ROLL','L0W':'L0W_ROLL'
}, inplace=True)

print('Datos cargados y esquema de orders unificado a _ROLL.')

# ==============================================================================
# A. TAMAÑO Y ESTRUCTURA
# ==============================================================================
sep('A. TAMAÑO Y ESTRUCTURA')
print(f'\n-> RAW_ORDERS  : {df_orders.shape[0]:,} filas x {df_orders.shape[1]} columnas')
print(f'-> RAW_METRICS : {df_metrics.shape[0]:,} filas x {df_metrics.shape[1]} columnas')
print(f'-> Países      : {df_orders["COUNTRY"].nunique()}')
print(f'-> Ciudades    : {df_orders["CITY"].nunique()}')
print(f'-> Zonas únicas (Orders) : {df_orders["ZONE"].nunique()}')
print(f'-> Zonas únicas (Metrics): {df_metrics["ZONE"].nunique()}')
print(f'-> Métricas únicas       : {df_metrics["METRIC"].nunique()}')

# ==============================================================================
# ANÁLISIS 1 — NULOS
# ==============================================================================
sep('ANÁLISIS 1: Nulos')

print('\n[RAW_INPUT_METRICS] Nulos por columna de semana:')
print(df_metrics[WEEK_COLS_METRICS].isnull().sum().to_string())

print('\n[RAW_ORDERS] Nulos por columna de semana (ya con _ROLL):')
print(df_orders[WEEK_COLS_ORDERS_ROLL].isnull().sum().to_string())

pct_null_met = (df_metrics[WEEK_COLS_METRICS].isnull().any(axis=1).sum() / len(df_metrics)) * 100
pct_null_ord = (df_orders[WEEK_COLS_ORDERS_ROLL].isnull().any(axis=1).sum() / len(df_orders)) * 100
print(f'\n% filas con ≥1 nulo en semanas (Metrics): {pct_null_met:.2f}%')
print(f'% filas con ≥1 nulo en semanas (Orders) : {pct_null_ord:.2f}%')

zonas_todo_nulo_met = df_metrics[df_metrics[WEEK_COLS_METRICS].isnull().all(axis=1)]['ZONE'].nunique()
zonas_todo_nulo_ord = df_orders[df_orders[WEEK_COLS_ORDERS_ROLL].isnull().all(axis=1)]['ZONE'].nunique()
print(f'\nZonas sin NINGÚN dato en ninguna semana (Metrics): {zonas_todo_nulo_met}')
print(f'Zonas sin NINGÚN dato en ninguna semana (Orders) : {zonas_todo_nulo_ord}')

zonas_fantasma = df_orders[df_orders[WEEK_COLS_ORDERS_ROLL].isnull().all(axis=1)][['COUNTRY','CITY','ZONE']]
if len(zonas_fantasma) > 0:
    print(f'\n  Ejemplos zonas fantasma en Orders (primeras 5):')
    print(zonas_fantasma.head(5).to_string(index=False))

print('\n⚠️  DECISIÓN: df_orders.dropna(how="all", subset=WEEK_COLS) — elimina zonas fantasma')

# ==============================================================================
# ANÁLISIS 2 — CONSISTENCIA DE NOMBRES Y CATÁLOGOS
# ==============================================================================
sep('ANÁLISIS 2: Consistencia de Nombres y Catálogos')

paises_encontrados = sorted(df_metrics['COUNTRY'].unique().tolist())
paises_inesperados = [p for p in paises_encontrados if p not in VALID_COUNTRIES]
print(f'\nPaíses encontrados ({len(paises_encontrados)}): {paises_encontrados}')
print(f'Países inesperados: {paises_inesperados if paises_inesperados else "Ninguno ✅"}')

metricas_encontradas = sorted(df_metrics['METRIC'].unique().tolist())
metricas_inesperadas = [m for m in metricas_encontradas if m not in VALID_METRICS]
print(f'\nMétricas encontradas ({len(metricas_encontradas)}): OK')
print(f'Métricas inesperadas: {metricas_inesperadas if metricas_inesperadas else "Ninguna ✅"}')
print('\nConteo por métrica:')
print(df_metrics['METRIC'].value_counts().to_string())

print(f'\nZONE_TYPE     : {df_metrics["ZONE_TYPE"].value_counts().to_dict()}')
tipos_inesperados = [t for t in df_metrics['ZONE_TYPE'].unique() if t not in VALID_ZONE_TYPES]
print(f'  Inesperados: {tipos_inesperados if tipos_inesperados else "Ninguno ✅"}')

print(f'\nZONE_PRIORITIZATION: {df_metrics["ZONE_PRIORITIZATION"].value_counts().to_dict()}')
prio_inesperadas = [p for p in df_metrics['ZONE_PRIORITIZATION'].unique() if p not in VALID_PRIORITIES]
print(f'  Inesperadas: {prio_inesperadas if prio_inesperadas else "Ninguna ✅"}')

zonas_ord = set(df_orders['ZONE'].dropna().unique())
zonas_met = set(df_metrics['ZONE'].dropna().unique())
solo_en_orders  = zonas_ord - zonas_met
solo_en_metrics = zonas_met - zonas_ord
print(f'\nZonas en Orders que NO están en Metrics: {len(solo_en_orders)}')
if solo_en_orders:
    print(f'  Ejemplos: {list(solo_en_orders)[:5]}')
print(f'Zonas en Metrics que NO están en Orders: {len(solo_en_metrics)}')
if solo_en_metrics:
    print(f'  Ejemplos: {list(solo_en_metrics)[:5]}')

print('\n⚠️  DECISIÓN: en explain_growth hacer dropna después del merge — zonas sin métricas devuelven NaN')

# ==============================================================================
# ANÁLISIS 3 — RANGOS DE VALORES POR MÉTRICA
# ==============================================================================
sep('ANÁLISIS 3: Rangos de Valores por Métrica')

metrics_melt = df_metrics.melt(
    id_vars=['METRIC'],
    value_vars=WEEK_COLS_METRICS,
    value_name='VAL'
).dropna()

print(f'\n{"MÉTRICA":<50} {"MIN":>10} {"MAX":>10} {"MEDIA":>8} {"% FUERA[0,1]":>14} {"=0":>6} {"=1":>6}')
print('-' * 106)

alertas = []
for met in VALID_METRICS:
    datos = metrics_melt[metrics_melt['METRIC'] == met]['VAL']
    if len(datos) == 0:
        continue
    val_min  = datos.min()
    val_max  = datos.max()
    val_mean = datos.mean()
    fuera    = ((datos < 0) | (datos > 1)).mean() * 100
    ceros    = (datos == 0).sum()
    unos     = (datos == 1).sum()

    flag = ''
    if fuera > 5:
        flag = '  ⚠️'
        alertas.append((met, val_min, val_max, fuera))
    print(f'{met:<50} {val_min:>10.3f} {val_max:>10.3f} {val_mean:>8.3f} {fuera:>13.1f}% {ceros:>6} {unos:>6}{flag}')

if alertas:
    print('\n⚠️  MÉTRICAS CON VALORES FUERA DE [0,1]:')
    for met, mn, mx, pct in alertas:
        print(f'   {met}: min={mn:.3f}, max={mx:.3f}, {pct:.1f}% fuera de rango')

print('\n⚠️  DECISIÓN: Lead Penetration → clip(upper=1.0) en data_loader')
print('⚠️  DECISIÓN: Gross Profit UE puede ser negativo — es margen, no ratio.')
print('             Agregar nota en system prompt de context.py')

# ==============================================================================
# ANÁLISIS 4 — DUPLICADOS
# ==============================================================================
sep('ANÁLISIS 4: Duplicados')

KEY_COLS = ['COUNTRY','CITY','ZONE','ZONE_TYPE','ZONE_PRIORITIZATION','METRIC']

total_dupes = df_metrics.duplicated().sum()
key_dupes   = df_metrics.duplicated(subset=KEY_COLS).sum()

print(f'\nDuplicados totales (todas las columnas iguales): {total_dupes}')
print(f'Duplicados por clave (zona + métrica)          : {key_dupes}')

if total_dupes == key_dupes:
    print(f'\n✅ Escenario A confirmado: todos los duplicados son filas exactamente iguales.')
    print(f'   Solución: df_metrics.drop_duplicates()')
    print(f'   Filas esperadas después de deduplicar: {len(df_metrics) - total_dupes:,}')
else:
    print(f'\n⚠️  Escenario B detectado: hay duplicados de clave con valores distintos.')
    conflictos = df_metrics[df_metrics.duplicated(subset=KEY_COLS, keep=False)]
    print(conflictos.sort_values(KEY_COLS)[KEY_COLS + ['L0W_ROLL','L1W_ROLL']].head(10).to_string(index=False))

if total_dupes > 0:
    ejemplo = df_metrics[df_metrics.duplicated(keep=False)].sort_values(KEY_COLS).head(4)
    print(f'\nEjemplo de filas duplicadas:')
    print(ejemplo[KEY_COLS + ['L0W_ROLL']].to_string(index=False))

print('\n⚠️  DECISIÓN: df_metrics.drop_duplicates() — ANTES del melt en data_loader')

# ==============================================================================
# ANÁLISIS 5 — OUTLIERS E INACTIVIDAD EN ÓRDENES
# ==============================================================================
sep('ANÁLISIS 5: Outliers e Inactividad en Órdenes (semana L0W_ROLL)')

l0w = df_orders['L0W_ROLL'].dropna()
print(f'\nDistribución de órdenes en L0W_ROLL:')
print(l0w.describe().round(2).to_string())

zonas_cero = (l0w == 0).sum()
print(f'\nZonas con 0 órdenes en L0W_ROLL: {zonas_cero}')

media  = l0w.mean()
std    = l0w.std()
umbral = media + 3 * std
outliers = df_orders[df_orders['L0W_ROLL'] > umbral][['COUNTRY','CITY','ZONE','L0W_ROLL']]\
           .sort_values('L0W_ROLL', ascending=False)

print(f'\nUmbral outlier (media + 3σ): {umbral:,.0f} órdenes')
print(f'Zonas con órdenes > umbral : {len(outliers)}')
if len(outliers) > 0:
    print(f'\nTop zonas con mayor volumen:')
    print(outliers.head(10).to_string(index=False))
    print('\n  Nota: zonas reales de alto volumen, NO errores de datos.')
    print('  DECISIÓN: NO filtrar — explain_growth usa % de crecimiento, no valor absoluto.')

# ==============================================================================
# ANÁLISIS 6 — COBERTURA TEMPORAL
# ==============================================================================
sep('ANÁLISIS 6: Cobertura Temporal')

cobertura_met = df_metrics.dropna(subset=WEEK_COLS_METRICS).shape[0]
cobertura_ord = df_orders.dropna(subset=WEEK_COLS_ORDERS_ROLL).shape[0]
print(f'\n[Metrics] Filas con datos en las 9 semanas: {cobertura_met:,} ({cobertura_met/len(df_metrics)*100:.1f}%)')
print(f'[Orders]  Filas con datos en las 9 semanas: {cobertura_ord:,} ({cobertura_ord/len(df_orders)*100:.1f}%)')

cols_pasadas_ord = [c for c in WEEK_COLS_ORDERS_ROLL if c != 'L0W_ROLL']
zonas_recientes_ord = df_orders[
    df_orders['L0W_ROLL'].notnull() &
    df_orders[cols_pasadas_ord].isnull().all(axis=1)
]
print(f'\nZonas de reciente apertura en Orders (solo L0W_ROLL): {len(zonas_recientes_ord)}')
if len(zonas_recientes_ord) > 0:
    print(f'  Ejemplos: {zonas_recientes_ord["ZONE"].tolist()[:5]}')

cols_pasadas_met = [c for c in WEEK_COLS_METRICS if c != 'L0W_ROLL']
zonas_recientes_met = df_metrics[
    df_metrics['L0W_ROLL'].notnull() &
    df_metrics[cols_pasadas_met].isnull().all(axis=1)
]['ZONE'].nunique()
print(f'Zonas de reciente apertura en Metrics (solo L0W_ROLL): {zonas_recientes_met}')

# ==============================================================================
# ANÁLISIS 7 — ZONAS SIN L0W_ROLL: ¿SU HISTORIAL ES ÚTIL?
# ==============================================================================
sep('ANÁLISIS 7: Zonas sin L0W_ROLL — ¿su historial es útil?')

# Separar los 3 grupos
fantasmas  = df_orders[df_orders[WEEK_COLS_ORDERS_ROLL].isnull().all(axis=1)]
sin_l0w    = df_orders[
    df_orders['L0W_ROLL'].isnull() &
    ~df_orders[WEEK_COLS_ORDERS_ROLL].isnull().all(axis=1)
]
activas    = df_orders[df_orders['L0W_ROLL'].notnull()]

print(f'\nTotal zonas en df_orders         : {len(df_orders):,}')
print(f'  Grupo A — Fantasmas (todo NaN) : {len(fantasmas)}  → eliminar en data_loader')
print(f'  Grupo B — Sin L0W, con historial: {len(sin_l0w)}  → analizar abajo')
print(f'  Grupo C — Activas (tienen L0W) : {len(activas):,}  → usar siempre')

# Análisis del Grupo B
semanas_con_dato = sin_l0w[WEEK_COLS_ORDERS_ROLL].notnull().sum(axis=1)
util_tendencias  = (semanas_con_dato >= 3).sum()
poco_util        = (semanas_con_dato < 3).sum()

print(f'\n--- Grupo B: {len(sin_l0w)} zonas sin L0W_ROLL pero con historial ---')
print(f'Semanas con dato promedio : {semanas_con_dato.mean():.1f}')
print(f'Distribución de semanas con dato:')
print(semanas_con_dato.value_counts().sort_index().to_string())
print(f'\nZonas con ≥3 semanas (útiles para detect_sustained_decline): {util_tendencias}')
print(f'Zonas con <3 semanas (poco útiles para cualquier análisis)  : {poco_util}')

# Patrón de los nulos — ¿se caen hacia semanas recientes?
print(f'\nNulos por semana en Grupo B (patrón de abandono):')
nulos_por_semana = sin_l0w[WEEK_COLS_ORDERS_ROLL].isnull().sum()
print(nulos_por_semana.to_string())
if nulos_por_semana['L1W_ROLL'] > nulos_por_semana['L8W_ROLL']:
    print('\n  → Patrón confirmado: los nulos aumentan hacia semanas recientes.')
    print('    Son zonas que dejaron de operar gradualmente, no errores de datos.')

print(f'\nEjemplos de zonas del Grupo B:')
print(sin_l0w[['COUNTRY','CITY','ZONE'] + WEEK_COLS_ORDERS_ROLL].head(5).to_string(index=False))

# Conclusión
print(f"""
┌─────────────────────────────────────────────────────────────────┐
│  CONCLUSIÓN ANÁLISIS 7                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Las {len(sin_l0w)} zonas sin L0W_ROLL NO se eliminan en data_loader.  │
│  Su historial es valioso para:                                  │
│                                                                 │
│  ✅ detect_sustained_decline — {util_tendencias} zonas con ≥3 semanas          │
│     muestran caída y desaparición gradual = insight real        │
│  ✅ trend_analysis — cualquier zona con ≥2 semanas tiene        │
│     una tendencia que mostrar                                   │
│                                                                 │
│  ❌ top_zones, compare_segments, aggregate_by, find_zones       │
│     — estas funciones filtran internamente por L0W_ROLL         │
│     (Pandas ignora NaN al ordenar/agrupar)                      │
│  ❌ explain_growth — filtra explícitamente con:                 │
│     dropna(subset=[start_week, "L0W_ROLL"])                     │
│                                                                 │
│  DECISIÓN FINAL:                                                │
│  data_loader → solo eliminar Grupo A (fantasmas totales)        │
│  Cada función → filtra lo que necesita internamente             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
""")

# ==============================================================================
# RESUMEN EJECUTIVO — DECISIONES FINALES
# ==============================================================================
sep('RESUMEN EJECUTIVO — DECISIONES FINALES PARA data_loader.py')

n_fantasmas = len(df_orders[df_orders[WEEK_COLS_ORDERS_ROLL].isnull().all(axis=1)])
n_dupes     = df_metrics.duplicated().sum()
filas_met_esperadas = len(df_metrics) - n_dupes
filas_ord_esperadas = len(df_orders) - n_fantasmas
filas_long_esperadas = filas_met_esperadas * 9

print(f"""
┌─────────────────────────────────────────────────────────────────────┐
│  ORDEN DE OPERACIONES EN data_loader.py                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  df_metrics:                                                        │
│  1. drop_duplicates()              → elimina {n_dupes} filas exactas       │
│  2. clip Lead Penetration ≤ 1.0    → corrige outliers hasta 393.9  │
│  3. .str.strip().str.title()       → normaliza ZONE y CITY          │
│  4. melt → df_long + dropna(value) → formato largo para tendencias  │
│                                                                     │
│  df_orders:                                                         │
│  1. rename(L8W→L8W_ROLL ... L0W→L0W_ROLL)  → unifica esquema       │
│  2. dropna(how="all", subset=WEEK_COLS)     → elimina {n_fantasmas} fantasmas  │
│  3. .str.strip().str.title()                → normaliza ZONE y CITY │
│  ⚠️  NO hacer dropna(L0W_ROLL) aquí —                              │
│     el historial de zonas inactivas es útil para tendencias        │
│                                                                     │
│  tools.py — explain_growth:                                         │
│  - dropna(subset=[start_week, "L0W_ROLL"])  → filtra internamente  │
│  - dropna después del merge con metrics     → zonas sin métricas   │
│                                                                     │
│  context.py — system prompt:                                        │
│  - Nota: Gross Profit UE puede ser negativo (es margen, no ratio)  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  DATOS ESPERADOS DESPUÉS DE LIMPIEZA:                               │
│  df_metrics : ~{filas_met_esperadas:,} filas  ({len(df_metrics):,} - {n_dupes} duplicados)             │
│  df_orders  : ~{filas_ord_esperadas:,} filas   ({len(df_orders):,} - {n_fantasmas} fantasmas totales)          │
│  df_long    : ~{filas_long_esperadas:,} filas ({filas_met_esperadas:,} × 9 semanas)          │
└─────────────────────────────────────────────────────────────────────┘
""")