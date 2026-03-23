"""
RTA Service Indices Dashboard — Liquid Glass Theme
pip3 install dash pandas plotly openpyxl && python3 service_indices_dashboard.py
http://127.0.0.1:8075

Auto-watches ~/Desktop/Service Indices/ for new files and refreshes data.
"""
import os, glob, re
import pandas as pd
from dash import Dash, html, dcc, Input, Output, callback, no_update
import warnings
warnings.filterwarnings("ignore")

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PORT = int(os.environ.get("PORT", 8075))
MAIN_DAYS = ['PVR (M-Tu-W-Th)', 'PVR (Friday)', 'PVR (Saturday)', 'PVR (Sunday)']

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE TYPE COLORS
# ═══════════════════════════════════════════════════════════════════════════════
TYPE_COLORS = {
    'Feeder':    '#0066cc',   # Blue
    'Urban':     '#ea580c',   # Orange
    'Intercity': '#dc2626',   # Red
    'Express':   '#7c3aed',   # Purple
    'Night':     '#4338ca',   # Indigo
    'Seasonal':  '#0891b2',   # Cyan
    'Seasonal Cost Sharing': '#0891b2',
    'Urban Cost Sharing': '#ea580c',
    'Rural (Fixed Fare)': '#65a30d',
    'On Hold':   '#9ca3af',   # Grey
}
DEFAULT_TYPE_COLOR = '#6b7280'

# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════
def find_latest_file():
    files = glob.glob(os.path.join(FOLDER, "Service Indices *.xlsx"))
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def extract_date_from_filename(fp):
    m = re.search(r'(\d{2}-\d{2}-\d{4})', os.path.basename(fp))
    return m.group(1) if m else "Unknown"

def load_data():
    fp = find_latest_file()
    if not fp:
        return pd.DataFrame(), "No file found", None, []
    date_str = extract_date_from_filename(fp)
    df_raw = pd.read_excel(fp, sheet_name='RawData')
    routes = []
    for (route, name, stype, depot, vtype), grp in df_raw.groupby(
        ['rte_identifier5', 'rte_long_name', 'rte_service_type', 'rte_depot_Name', 'rte_veh_type']
    ):
        row = {
            'Route': str(route),
            'Route Name': str(name),
            'Service Type': str(stype),
            'Depot': str(depot),
            'Vehicle Type': str(vtype),
        }
        for _, r in grp.iterrows():
            sched = str(r['sched_type'])
            pvr = r['rte_peak_req']
            if pd.notna(pvr):
                row[f'PVR ({sched})'] = int(pvr)
        routes.append(row)

    df = pd.DataFrame(routes)
    sched_cols = [c for c in df.columns if c.startswith('PVR')]
    for c in sched_cols:
        df[c] = df[c].fillna(0).astype(int)

    # ── Merge rows with same Route + Depot ──
    pvr_cols_merge = [c for c in df.columns if c.startswith('PVR')]
    agg_dict = {
        'Route Name': 'first',
        'Service Type': 'first',
        'Vehicle Type': lambda x: ' / '.join(sorted(set(x))),
    }
    for pc in pvr_cols_merge:
        agg_dict[pc] = 'sum'
    df = df.groupby(['Route', 'Depot'], as_index=False).agg(agg_dict)

    df['_sort'] = df['Route'].apply(lambda x: (re.sub(r'\d+', '', x), int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))
    df = df.sort_values('_sort').drop(columns=['_sort']).reset_index(drop=True)

    # Remove routes where all PVR values are 0
    pvr_cols = [c for c in df.columns if c.startswith('PVR')]
    if pvr_cols:
        df = df[df[pvr_cols].sum(axis=1) > 0].reset_index(drop=True)

    # Remove "On Hold" routes entirely
    df = df[df['Service Type'].str.lower() != 'on hold'].reset_index(drop=True)

    locations = set()
    for name in df['Route Name'].dropna().unique():
        parts = [p.strip() for p in str(name).split(' - ')]
        locations.update(parts)

    return df, date_str, fp, sorted(locations)

DATA, LAST_UPDATE, CURRENT_FILE, LOCATIONS = load_data()

FILE_VERSION = [0]

# ═══════════════════════════════════════════════════════════════════════════════
# DASH APP — LIQUID GLASS THEME
# ═══════════════════════════════════════════════════════════════════════════════
from flask import Response as FlaskResponse
import json as _json

app = Dash(__name__)
app.title = "DepotSum"
server = app.server

# ═══════════════════════════════════════════════════════════════════════════════
# PWA — manifest, service worker, app icon
# ═══════════════════════════════════════════════════════════════════════════════
_MANIFEST = {
    "name": "DepotSum",
    "short_name": "DepotSum",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#f0f4f8",
    "theme_color": "#dc0f0f",
    "icons": [
        {"src": "/app-icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/app-icon-512.png", "sizes": "512x512", "type": "image/png"},
    ]
}

_ICON_DIR = os.path.dirname(os.path.abspath(__file__))

@server.route('/manifest.json')
def pwa_manifest():
    return FlaskResponse(_json.dumps(_MANIFEST), mimetype='application/manifest+json')

@server.route('/sw.js')
def pwa_sw():
    sw = "self.addEventListener('fetch', function(e){e.respondWith(fetch(e.request))});"
    return FlaskResponse(sw, mimetype='application/javascript')

@server.route('/app-icon-192.png')
def pwa_icon_192():
    with open(os.path.join(_ICON_DIR, 'app-icon-192.png'), 'rb') as f:
        return FlaskResponse(f.read(), mimetype='image/png')

@server.route('/app-icon-512.png')
def pwa_icon_512():
    with open(os.path.join(_ICON_DIR, 'app-icon-512.png'), 'rb') as f:
        return FlaskResponse(f.read(), mimetype='image/png')

TEXT = "#1e293b"
MUTED = "#64748b"
ACCENT = "#0066cc"
ACCENT2 = "#e65100"
GREEN = "#0d8a4e"
PURPLE = "#7c3aed"
CYAN = "#0891b2"
ORANGE = "#ea580c"
PINK = "#db2777"
YELLOW = "#ca8a04"

app.index_string = '''<!DOCTYPE html>
<html><head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="DepotSum">
<meta name="theme-color" content="#f0f4f8">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/app-icon-192.png">
{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
*{margin:0;padding:0;box-sizing:border-box}

body{
  font-family:'Inter',sans-serif;color:#1e293b;min-height:100vh;
  background:
    radial-gradient(ellipse 80% 60% at 10% 20%, rgba(147,197,253,0.35) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 85% 15%, rgba(196,181,253,0.3) 0%, transparent 55%),
    radial-gradient(ellipse 70% 55% at 50% 80%, rgba(167,243,208,0.25) 0%, transparent 55%),
    radial-gradient(ellipse 50% 40% at 75% 60%, rgba(253,186,116,0.2) 0%, transparent 50%),
    linear-gradient(160deg, #f0f4f8 0%, #e8edf5 30%, #f1f0fb 60%, #eef6f0 100%);
  background-attachment:fixed;
}

/* Animated floating orbs behind content */
body::before, body::after{
  content:''; position:fixed; border-radius:50%; z-index:0; pointer-events:none;
  filter:blur(80px); opacity:0.4;
}
body::before{
  width:500px;height:500px;top:-100px;left:-100px;
  background:radial-gradient(circle, rgba(99,180,255,0.5), transparent 70%);
  animation:float1 20s ease-in-out infinite;
}
body::after{
  width:400px;height:400px;bottom:-50px;right:-80px;
  background:radial-gradient(circle, rgba(168,130,255,0.4), transparent 70%);
  animation:float2 25s ease-in-out infinite;
}
@keyframes float1{0%,100%{transform:translate(0,0)}50%{transform:translate(60px,40px)}}
@keyframes float2{0%,100%{transform:translate(0,0)}50%{transform:translate(-50px,-30px)}}

/* Scrollbar */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(100,116,139,0.25);border-radius:3px}
input,select{font-family:'Inter',sans-serif}

/* ════════════════════════ LIQUID GLASS CORE ════════════════════════ */
.liquid-glass{
  background: linear-gradient(135deg,
    rgba(255,255,255,0.55) 0%,
    rgba(255,255,255,0.35) 40%,
    rgba(255,255,255,0.45) 100%);
  backdrop-filter: blur(24px) saturate(1.8);
  -webkit-backdrop-filter: blur(24px) saturate(1.8);
  border: 1px solid rgba(255,255,255,0.65);
  box-shadow:
    0 8px 32px rgba(0,0,0,0.06),
    0 2px 8px rgba(0,0,0,0.04),
    inset 0 1px 0 rgba(255,255,255,0.9),
    inset 0 -1px 0 rgba(255,255,255,0.3);
  border-radius: 20px;
  position: relative;
  overflow: hidden;
}

/* Top shine reflection */
.liquid-glass::before{
  content:''; position:absolute; top:0; left:0; right:0;
  height:50%; pointer-events:none;
  background: linear-gradient(180deg,
    rgba(255,255,255,0.45) 0%,
    rgba(255,255,255,0.1) 50%,
    transparent 100%);
  border-radius: 20px 20px 0 0;
}

/* Subtle inner glow */
.liquid-glass::after{
  content:''; position:absolute; top:1px; left:1px; right:1px; bottom:1px;
  pointer-events:none;
  border-radius: 19px;
  border: 1px solid rgba(255,255,255,0.4);
}

/* Header glass */
.header-glass{
  background: linear-gradient(135deg,
    rgba(255,255,255,0.6) 0%,
    rgba(255,255,255,0.4) 100%);
  backdrop-filter: blur(30px) saturate(1.8);
  -webkit-backdrop-filter: blur(30px) saturate(1.8);
  border-bottom: 1px solid rgba(255,255,255,0.6);
  box-shadow:
    0 4px 20px rgba(0,0,0,0.05),
    inset 0 -1px 0 rgba(255,255,255,0.5);
}

/* KPI card hover */
.kpi-glass{transition:all 0.3s cubic-bezier(0.4,0,0.2,1)}
.kpi-glass:hover{
  transform:translateY(-3px);
  box-shadow:
    0 16px 48px rgba(0,0,0,0.1),
    0 4px 12px rgba(0,0,0,0.06),
    inset 0 1px 0 rgba(255,255,255,0.95);
}

/* Route card glass */
.route-glass{
  background: linear-gradient(145deg,
    rgba(255,255,255,0.5) 0%,
    rgba(255,255,255,0.3) 50%,
    rgba(255,255,255,0.4) 100%);
  backdrop-filter: blur(20px) saturate(1.6);
  -webkit-backdrop-filter: blur(20px) saturate(1.6);
  border: 1px solid rgba(255,255,255,0.6);
  box-shadow:
    0 4px 24px rgba(0,0,0,0.05),
    0 1px 4px rgba(0,0,0,0.03),
    inset 0 1px 0 rgba(255,255,255,0.85);
  border-radius: 18px;
  position: relative;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
}
.route-glass:hover{
  transform:translateY(-2px);
  box-shadow:
    0 12px 40px rgba(0,0,0,0.1),
    0 2px 8px rgba(0,0,0,0.05),
    inset 0 1px 0 rgba(255,255,255,0.95);
  border-color:rgba(255,255,255,0.8);
}
/* Color strip on left */
.route-glass::before{
  content:''; position:absolute; top:0; left:0; width:4px; height:100%;
  background:var(--type-color,#6b7280);
  border-radius:18px 0 0 18px;
}
/* Inner shine */
.route-glass::after{
  content:''; position:absolute; top:0; left:0; right:0;
  height:40%; pointer-events:none;
  background: linear-gradient(180deg,
    rgba(255,255,255,0.35) 0%,
    transparent 100%);
  border-radius: 18px 18px 0 0;
}

/* Dropdowns liquid glass */
.Select-control,.Select-menu-outer,[class*="css-"]{
  background: linear-gradient(135deg, rgba(255,255,255,0.6), rgba(255,255,255,0.4)) !important;
  border-color:rgba(255,255,255,0.5) !important;color:#1e293b !important;
  backdrop-filter:blur(16px) !important;-webkit-backdrop-filter:blur(16px) !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.7) !important;
}
.Select-value-label,[class*="singleValue"]{color:#1e293b !important}
[class*="option"]{color:#1e293b !important}
[class*="option"]:hover{background:rgba(0,102,204,0.08) !important}
[class*="menu"]{
  background:linear-gradient(135deg, rgba(255,255,255,0.85), rgba(255,255,255,0.75)) !important;
  border:1px solid rgba(255,255,255,0.6) !important;
  box-shadow:0 12px 40px rgba(0,0,0,0.12) !important;
  backdrop-filter:blur(24px) !important;-webkit-backdrop-filter:blur(24px) !important;
  border-radius:14px !important;
}

/* Refresh button */
.refresh-btn{
  cursor:pointer;
  background:linear-gradient(135deg, rgba(255,255,255,0.6), rgba(255,255,255,0.35));
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
  border:1px solid rgba(255,255,255,0.6);
  color:#0066cc; padding:8px 20px; border-radius:12px;
  font-weight:700; font-size:13px; font-family:Inter,sans-serif;
  transition:all 0.25s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.8);
}
.refresh-btn:hover{
  background:linear-gradient(135deg, rgba(0,102,204,0.9), rgba(0,82,180,0.95));
  color:white; border-color:rgba(0,102,204,0.5);
  box-shadow:0 8px 24px rgba(0,102,204,0.3);
  transform:translateY(-1px);
}

/* PVR badges */
.pvr-badge{
  display:inline-block; padding:4px 12px; border-radius:24px;
  font-size:11px; font-weight:600; margin-right:6px; margin-bottom:4px;
  backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
  border:1px solid rgba(255,255,255,0.4);
}

/* On Hold badge */
.on-hold-badge{background:rgba(156,163,175,0.15);color:#9ca3af;border:1px solid rgba(156,163,175,0.3);
  padding:2px 10px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:0.5px;
  text-transform:uppercase;animation:pulse 2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}

/* Content wrapper */
.content-wrap{position:relative;z-index:1}

/* ═══════ MOBILE RESPONSIVE ═══════ */
@media(max-width:768px){
  .dash-header{padding:14px 16px !important}
  .dash-header h1{font-size:20px !important}
  .kpi-all-grid{grid-template-columns:repeat(2,1fr) !important;gap:10px !important;padding:14px 16px 14px !important}
  .filter-row{flex-direction:column !important;padding:0 16px 10px !important;gap:12px !important}
  .filter-row > div{min-width:100% !important;flex:unset !important}
  .route-grid{grid-template-columns:1fr !important;padding:0 16px 20px !important;gap:10px !important}
  .results-count{padding:0 16px 14px !important}
  body::before,body::after{display:none}
}
@media(max-width:480px){
  .kpi-all-grid{grid-template-columns:1fr 1fr !important;gap:8px !important;padding:12px 12px 12px !important}
  .kpi-glass{padding:14px 14px !important}
  .kpi-glass .kpi-value{font-size:26px !important}
  .day-kpi-card{padding:12px 14px !important}
  .day-kpi-card .day-value{font-size:20px !important}
  .filter-row{padding:0 12px 8px !important}
  .route-grid{padding:0 12px 16px !important}
  .route-glass{padding:14px 14px !important}
  .route-glass .route-number{font-size:18px !important}
  .results-count{padding:0 12px 12px !important}
  .dash-header{padding:12px !important}
  .refresh-btn{padding:6px 12px;font-size:11px}
}
</style></head><body>{%app_entry%}{%config%}{%scripts%}{%renderer%}
<script>
if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(()=>{})}
</script>
</body></html>'''

def serve_layout():
    depots = sorted(DATA['Depot'].unique().tolist()) if not DATA.empty else []
    vtypes = sorted(DATA['Vehicle Type'].unique().tolist()) if not DATA.empty else []
    stypes = sorted(DATA['Service Type'].unique().tolist()) if not DATA.empty else []
    return html.Div([
        dcc.Interval(id='refresh-interval', interval=10_000, n_intervals=0),
        dcc.Store(id='file-version', data=FILE_VERSION[0]),

        # HEADER
        html.Div([
            html.Div([
                html.H1("Service Indices", style={
                    'fontSize': '28px', 'fontWeight': '800', 'margin': 0, 'color': TEXT,
                    'letterSpacing': '-0.5px',
                }),
                html.Div(id='update-badge', children=[
                    html.Span("Last Update: ", style={'color': MUTED, 'fontSize': '13px'}),
                    html.Span(LAST_UPDATE, style={'color': ACCENT, 'fontSize': '13px', 'fontWeight': '700'}),
                ], style={'marginTop': '2px'}),
            ], style={'flex': '1', 'minWidth': '0'}),
            html.Div([
                html.Button(
                    id='refresh-btn',
                    children=["Refresh"],
                    className='refresh-btn',
                    n_clicks=0,
                ),
                html.Div(id='file-badge', children=os.path.basename(CURRENT_FILE) if CURRENT_FILE else "",
                         style={'color': MUTED, 'fontSize': '11px', 'textAlign': 'right',
                                'background': 'rgba(255,255,255,0.3)', 'padding': '4px 12px', 'borderRadius': '8px',
                                'marginTop': '6px', 'wordBreak': 'break-all',
                                'backdropFilter': 'blur(8px)', 'WebkitBackdropFilter': 'blur(8px)'}),
            ], style={'textAlign': 'right', 'flexShrink': '0'}),
        ], className='dash-header header-glass', style={
            'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between',
            'padding': '20px 30px', 'position': 'relative', 'zIndex': '1',
        }),

        # CONTENT (above floating orbs)
        html.Div([
            # ALL KPIs — unified grid
            html.Div(id='kpi-all', className='kpi-all-grid', style={
                'display': 'grid', 'gridTemplateColumns': 'repeat(6, 1fr)',
                'gap': '14px', 'padding': '22px 30px 22px',
            }),

            # FILTERS ROW 1
            html.Div([
                html.Div([
                    html.Label("Search Route", style={'fontSize': '10px', 'color': MUTED, 'textTransform': 'uppercase',
                                                       'letterSpacing': '1.2px', 'marginBottom': '6px', 'display': 'block',
                                                       'fontWeight': '700'}),
                    dcc.Input(
                        id='search-input', type='text', placeholder='Type route number...',
                        debounce=False,
                        style={
                            'width': '100%', 'padding': '10px 14px', 'borderRadius': '14px',
                            'border': '1px solid rgba(255,255,255,0.5)',
                            'background': 'linear-gradient(135deg, rgba(255,255,255,0.55), rgba(255,255,255,0.35))',
                            'backdropFilter': 'blur(16px)', 'WebkitBackdropFilter': 'blur(16px)',
                            'color': TEXT, 'fontSize': '14px', 'outline': 'none',
                            'boxShadow': '0 2px 8px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.7)',
                        }
                    ),
                ], style={'flex': '2', 'minWidth': '250px'}),
                html.Div([
                    html.Label("Search Location", style={'fontSize': '10px', 'color': MUTED, 'textTransform': 'uppercase',
                                                          'letterSpacing': '1.2px', 'marginBottom': '6px', 'display': 'block',
                                                          'fontWeight': '700'}),
                    dcc.Dropdown(
                        id='location-dropdown',
                        options=[{'label': 'All Locations', 'value': 'ALL'}] + [{'label': loc, 'value': loc} for loc in LOCATIONS],
                        value='ALL', clearable=False, searchable=True,
                        placeholder='Search for a location...',
                        style={'borderRadius': '14px', 'fontSize': '14px'},
                    ),
                ], style={'flex': '2', 'minWidth': '280px'}),
            ], className='filter-row', style={
                'display': 'flex', 'gap': '20px', 'padding': '0 30px 10px', 'flexWrap': 'wrap',
            }),

            # FILTERS ROW 2
            html.Div([
                html.Div([
                    html.Label("Filter by Depot", style={'fontSize': '10px', 'color': MUTED, 'textTransform': 'uppercase',
                                                          'letterSpacing': '1.2px', 'marginBottom': '6px', 'display': 'block',
                                                          'fontWeight': '700'}),
                    dcc.Dropdown(
                        id='depot-dropdown',
                        options=[{'label': 'All Depots', 'value': 'ALL'}] + [{'label': d, 'value': d} for d in depots],
                        value='ALL', clearable=False,
                        style={'borderRadius': '14px', 'fontSize': '14px'},
                    ),
                ], style={'flex': '1', 'minWidth': '200px'}),
                html.Div([
                    html.Label("Route Type", style={'fontSize': '10px', 'color': MUTED, 'textTransform': 'uppercase',
                                                     'letterSpacing': '1.2px', 'marginBottom': '6px', 'display': 'block',
                                                     'fontWeight': '700'}),
                    dcc.Dropdown(
                        id='service-dropdown',
                        options=[{'label': 'All Types', 'value': 'ALL'}] + [{'label': s, 'value': s} for s in stypes],
                        value='ALL', clearable=False,
                        style={'borderRadius': '14px', 'fontSize': '14px'},
                    ),
                ], style={'flex': '1', 'minWidth': '180px'}),
                html.Div([
                    html.Label("Vehicle Type", style={'fontSize': '10px', 'color': MUTED, 'textTransform': 'uppercase',
                                                       'letterSpacing': '1.2px', 'marginBottom': '6px', 'display': 'block',
                                                       'fontWeight': '700'}),
                    dcc.Dropdown(
                        id='vehicle-dropdown',
                        options=[{'label': 'All Vehicles', 'value': 'ALL'}] + [{'label': v, 'value': v} for v in vtypes],
                        value='ALL', clearable=False,
                        style={'borderRadius': '14px', 'fontSize': '14px'},
                    ),
                ], style={'flex': '1', 'minWidth': '160px'}),
            ], className='filter-row', style={
                'display': 'flex', 'gap': '20px', 'padding': '0 30px 22px', 'flexWrap': 'wrap',
            }),

            # ROUTE CARDS GRID
            html.Div(id='route-cards', className='route-grid', style={
                'padding': '0 30px 30px', 'display': 'grid',
                'gridTemplateColumns': 'repeat(auto-fill, minmax(340px, 1fr))',
                'gap': '14px',
            }),

            html.Div(id='results-count', className='results-count', style={
                'padding': '0 30px 20px', 'color': MUTED, 'fontSize': '12px',
            }),

        ], className='content-wrap'),

    ], style={'maxWidth': '1600px', 'margin': '0 auto'})

app.layout = serve_layout


# ═══════════════════════════════════════════════════════════════════════════════
# REFRESH BUTTON — reloads data from disk
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output('refresh-interval', 'n_intervals'),
    Input('refresh-btn', 'n_clicks'),
    prevent_initial_call=True,
)
def manual_refresh(n):
    global DATA, LAST_UPDATE, CURRENT_FILE, LOCATIONS
    DATA, LAST_UPDATE, CURRENT_FILE, LOCATIONS = load_data()
    FILE_VERSION[0] += 1
    print(f"[Manual refresh] Loaded: {os.path.basename(CURRENT_FILE) if CURRENT_FILE else 'none'}")
    return FILE_VERSION[0]


# ═══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def kpi_card(title, value, sub="", color=ACCENT):
    return html.Div([
        html.Div(title, style={'fontSize': '10px', 'color': MUTED, 'textTransform': 'uppercase',
                                'letterSpacing': '1.2px', 'fontWeight': '700', 'position': 'relative', 'zIndex': '1'}),
        html.Div(str(value), className='kpi-value', style={
            'fontSize': '36px', 'fontWeight': '800', 'color': color, 'lineHeight': '1', 'marginTop': '10px',
            'position': 'relative', 'zIndex': '1',
        }),
        html.Div(sub, style={'fontSize': '11px', 'color': MUTED, 'marginTop': '6px',
                              'position': 'relative', 'zIndex': '1'}) if sub else html.Div(),
    ], className='kpi-glass liquid-glass', style={
        'padding': '22px 24px',
    })


def day_kpi_card(day_label, pvr_total, color):
    return html.Div([
        html.Div(day_label, style={
            'fontSize': '10px', 'color': MUTED, 'textTransform': 'uppercase',
            'letterSpacing': '0.8px', 'fontWeight': '700', 'marginBottom': '6px',
            'position': 'relative', 'zIndex': '1',
        }),
        html.Div(str(pvr_total), className='day-value', style={
            'fontSize': '28px', 'fontWeight': '800', 'color': color, 'lineHeight': '1',
            'position': 'relative', 'zIndex': '1',
        }),
        html.Div("Total PVR", style={'fontSize': '10px', 'color': MUTED, 'marginTop': '4px',
                                      'position': 'relative', 'zIndex': '1'}),
    ], className='day-kpi-card liquid-glass', style={
        'padding': '18px 20px',
        'borderLeft': f'4px solid {color}',
    })


def route_card(row):
    stype = row['Service Type']
    type_color = TYPE_COLORS.get(stype, DEFAULT_TYPE_COLOR)
    is_on_hold = stype.lower() == 'on hold'

    # Use only main 4 days for max PVR display
    main_cols = [c for c in MAIN_DAYS if c in row.index]
    max_pvr = max((row[c] for c in main_cols), default=0)

    pvr_badges = []
    sched_colors = {
        'M-Tu-W-Th': ACCENT, 'Friday': ORANGE, 'Saturday': GREEN,
        'Sunday': PINK, 'Mon-Wed': CYAN, 'Thursday': YELLOW,
    }
    pvr_cols = [c for c in row.index if c.startswith('PVR')]
    for c in pvr_cols:
        sched = c.replace('PVR (', '').replace(')', '')
        val = int(row[c])
        if val > 0:
            color = sched_colors.get(sched, MUTED)
            pvr_badges.append(
                html.Span(f"{sched}: {val}", className='pvr-badge', style={
                    'background': f'linear-gradient(135deg, {color}18, {color}0a)',
                    'color': color,
                    'border': f'1px solid {color}30',
                })
            )

    # Service type badge with color
    type_badge_style = {
        'fontSize': '10px', 'textTransform': 'uppercase',
        'color': '#ffffff', 'fontWeight': '700',
        'background': f'linear-gradient(135deg, {type_color}, {type_color}dd)',
        'padding': '3px 12px', 'borderRadius': '8px',
        'letterSpacing': '0.5px',
        'boxShadow': f'0 2px 8px {type_color}33',
    }
    if is_on_hold:
        type_badge = html.Span(stype, className='on-hold-badge')
    else:
        type_badge = html.Span(stype, style=type_badge_style)

    # PVR display
    pvr_display_color = '#9ca3af' if is_on_hold else ACCENT2
    pvr_label = f"PVR {max_pvr}" if not is_on_hold else "ON HOLD"

    card_opacity = '0.65' if is_on_hold else '1'

    return html.Div([
        html.Div([
            html.Div([
                html.Span(str(row['Route']), className='route-number', style={
                    'fontSize': '22px', 'fontWeight': '800', 'color': type_color, 'marginRight': '10px',
                    'position': 'relative', 'zIndex': '1',
                }),
                type_badge,
            ], style={'display': 'flex', 'alignItems': 'center', 'flexWrap': 'wrap', 'gap': '6px',
                      'position': 'relative', 'zIndex': '1'}),
            html.Div(pvr_label, style={
                'fontSize': '14px', 'fontWeight': '800', 'color': pvr_display_color,
                'background': f'linear-gradient(135deg, {pvr_display_color}15, {pvr_display_color}08)',
                'padding': '4px 14px', 'borderRadius': '10px',
                'position': 'relative', 'zIndex': '1',
                'border': f'1px solid {pvr_display_color}20',
            }),
        ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '8px'}),

        html.Div(row['Route Name'], style={
            'fontSize': '13px', 'color': TEXT, 'marginBottom': '12px',
            'lineHeight': '1.4', 'opacity': '0.7',
            'position': 'relative', 'zIndex': '1',
        }),

        html.Div([
            html.Div([
                html.Span("Depot", style={'fontSize': '10px', 'color': MUTED, 'display': 'block', 'fontWeight': '700',
                                           'letterSpacing': '0.5px'}),
                html.Span(row['Depot'], style={'fontSize': '12px', 'fontWeight': '700', 'color': TEXT}),
            ], style={'marginRight': '24px'}),
            html.Div([
                html.Span("Vehicle", style={'fontSize': '10px', 'color': MUTED, 'display': 'block', 'fontWeight': '700',
                                             'letterSpacing': '0.5px'}),
                html.Span(row['Vehicle Type'], style={'fontSize': '12px', 'fontWeight': '700', 'color': TEXT}),
            ]),
        ], style={'display': 'flex', 'marginBottom': '12px', 'position': 'relative', 'zIndex': '1'}),

        html.Div(pvr_badges, style={'lineHeight': '2', 'position': 'relative', 'zIndex': '1'}),
    ], className='route-glass', style={
        'padding': '20px 22px 18px 26px',
        'opacity': card_opacity,
        '--type-color': type_color,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CALLBACK
# ═══════════════════════════════════════════════════════════════════════════════
@callback(
    Output('kpi-all', 'children'),
    Output('route-cards', 'children'),
    Output('results-count', 'children'),
    Output('update-badge', 'children'),
    Output('file-badge', 'children'),
    Input('search-input', 'value'),
    Input('location-dropdown', 'value'),
    Input('depot-dropdown', 'value'),
    Input('service-dropdown', 'value'),
    Input('vehicle-dropdown', 'value'),
    Input('refresh-interval', 'n_intervals'),
)
def update_dashboard(search, location, depot, stype, vtype, _n):
    df = DATA.copy()
    if df.empty:
        empty = [html.Div("No data found", style={'color': MUTED, 'padding': '40px', 'textAlign': 'center'})]
        return [], empty, "", [], ""

    if location and location != 'ALL':
        df = df[df['Route Name'].str.contains(re.escape(location), case=False, na=False)]
    if depot and depot != 'ALL':
        df = df[df['Depot'] == depot]
    if stype and stype != 'ALL':
        df = df[df['Service Type'] == stype]
    if vtype and vtype != 'ALL':
        df = df[df['Vehicle Type'] == vtype]
    if search:
        s_upper = search.strip().upper()
        df = df[df['Route'].str.upper() == s_upper]

    main_pvr_cols = [c for c in MAIN_DAYS if c in df.columns]
    total_routes = df['Route'].nunique() if not df.empty else 0
    total_depots = df['Depot'].nunique() if not df.empty else 0

    if main_pvr_cols and not df.empty:
        max_single = int(df[main_pvr_cols].max(axis=1).max())
    else:
        max_single = 0

    kpis = [
        kpi_card("Total Routes", total_routes, f"{len(df)} cards across {total_depots} depots", ACCENT),
        kpi_card("Depots", total_depots, "Across filtered selection", GREEN),
    ]

    day_order = ['M-Tu-W-Th', 'Friday', 'Saturday', 'Sunday']
    day_colors = {'M-Tu-W-Th': ACCENT, 'Friday': ORANGE, 'Saturday': GREEN, 'Sunday': PINK}
    day_kpis = []
    for day in day_order:
        col = f'PVR ({day})'
        if col in df.columns and not df.empty:
            day_total = int(df[col].sum())
            day_kpis.append(day_kpi_card(day, day_total, day_colors[day]))

    cards = [route_card(row) for _, row in df.iterrows()]
    if not cards:
        cards = [html.Div("No routes match your search.", style={
            'color': MUTED, 'padding': '40px', 'textAlign': 'center', 'gridColumn': '1 / -1',
        })]

    unique_total = DATA['Route'].nunique() if not DATA.empty else 0
    count_text = f"Showing {total_routes} unique routes ({len(df)} cards) of {unique_total} total"
    update_badge = [
        html.Span("Last Update: ", style={'color': MUTED, 'fontSize': '13px'}),
        html.Span(LAST_UPDATE, style={'color': ACCENT, 'fontSize': '13px', 'fontWeight': '700'}),
    ]
    file_badge = os.path.basename(CURRENT_FILE) if CURRENT_FILE else ""

    all_kpis = kpis + day_kpis
    return all_kpis, cards, count_text, update_badge, file_badge


if __name__ == '__main__':
    print(f"\n  Service Indices Dashboard — Liquid Glass")
    print(f"  http://127.0.0.1:{PORT}")
    print(f"  Watching: {FOLDER}")
    print(f"  Loaded: {os.path.basename(CURRENT_FILE) if CURRENT_FILE else 'No file'}")
    print(f"  Routes: {len(DATA)}\n")
    app.run(debug=False, port=PORT, host='0.0.0.0')
