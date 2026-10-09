import os
import sys
import csv
import queue
import threading
import subprocess
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime, time
import pandas as pd
import re
from time import time as _timer

# ==========================================
# CONSTANTS & COLORS (Professional Light Theme)
# ==========================================
BG_COLOR = '#f0f2f5'          # Light gray page background
PANEL_BG = '#ffffff'          # White card/panel background
SURFACE = '#e8eaed'           # Surface/border color
INPUT_BG = '#ffffff'          # Input background
BORDER_COLOR = '#dadce0'      # Border color
TEXT_COLOR = '#202124'        # Primary dark text
DIM_TEXT = '#5f6368'          # Secondary gray text
ACCENT_BLUE = '#1a73e8'       # Primary blue
PRIMARY_BLUE = '#185abc'      # Darker blue for headers
HEADER_NAVY = '#1a3a5c'       # Navy for section headers
SUCCESS_GREEN = '#1e8e3e'     # Green checkmarks/success
WARNING_YELLOW = '#f9ab00'    # Warning yellow
ERROR_RED = '#d93025'         # Error red
LIGHT_GREEN_BG = '#e6f4ea'    # Light green background for success panel
LIGHT_BLUE_BG = '#e8f0fe'     # Light blue background
BTN_GREEN = '#1e8e3e'         # Green button
BTN_GREEN_HOVER = '#137333'   # Green button hover
BTN_BLUE = '#1a73e8'          # Blue button
BTN_BLUE_HOVER = '#1557b0'    # Blue button hover
DROP_ZONE_BG = '#f8f9fa'      # Drop zone background
DROP_ZONE_BORDER = '#c4c7cc'  # Drop zone border
CONSOLE_BG = '#1e1e2e'        # Dark console background
CONSOLE_FG = '#d4d4d4'        # Console text

# ==========================================
# DATA PROCESSING UTILITIES
# ==========================================

# From convert_and_enrich.py
def normalize_am_pm(s: str) -> str:
    return (s.replace('a. m.', 'AM').replace('p. m.', 'PM')
             .replace('a.m.', 'AM').replace('p.m.', 'PM')
             .replace(' am', ' AM').replace(' pm', ' PM')
             .replace('Am', 'AM').replace('Pm', 'PM'))

def parse_date(val):
    if val is None: return None
    s = str(val).strip()
    if not s: return None
    for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y'):
        try: return datetime.strptime(s, fmt).date()
        except: pass
    return None

def parse_time(val):
    if val is None: return None
    s = normalize_am_pm(str(val).strip())
    if not s: return None
    for fmt in ('%H:%M:%S', '%H:%M', '%I:%M:%S %p', '%I:%M %p', '%H:%M:%S.%f'):
        try: return datetime.strptime(s, fmt).time()
        except: pass
    return None

def fmt_es(dt: datetime) -> str:
    ampm = 'a. m.' if dt.hour < 12 else 'p. m.'
    return f"{dt.strftime('%d/%m/%Y')} {dt.strftime('%I')}:{dt.strftime('%M:%S')} {ampm}"

def build_date(d, t):
    if d is None and t is None: return ''
    if d is None: d = datetime(1900,1,1).date()
    if t is None: t = time(0,0,0)
    return fmt_es(datetime.combine(d, t))

# From format_date_column.py
_iso_ms_re = re.compile(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(\.\d+)?$')

def normalize_spanish_ampm(s: str) -> str:
    return (s.replace('a. m.', 'AM').replace('p. m.', 'PM')
             .replace('a.m.', 'AM').replace('p.m.', 'PM')
             .replace(' a m', ' AM').replace(' p m', ' PM')
             .replace(' am', ' AM').replace(' pm', ' PM')
             .replace('Am', 'AM').replace('Pm', 'PM'))

def parse_any_datetime(val: str):
    if val is None: return None
    s = str(val).strip()
    if not s: return None
    s2 = normalize_spanish_ampm(s)
    if _iso_ms_re.match(s2):
        for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
            try: return datetime.strptime(s2, fmt)
            except: pass
    for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M'):
        try: return datetime.strptime(s2, fmt)
        except: pass
    for fmt in ('%d/%m/%Y %I:%M:%S %p', '%d/%m/%Y %I:%M %p'):
        try: return datetime.strptime(s2, fmt)
        except: pass
    return None

def format_es_ampm(dt: datetime) -> str:
    ampm = 'a. m.' if dt.hour < 12 else 'p. m.'
    return f"{dt.strftime('%d/%m/%Y')} {dt.strftime('%I:%M:%S')} {ampm}"

# ==========================================
# CSV & COLUMN UTILITIES (exported for tests)
# ==========================================

def sniff_delimiter(path, encoding=None):
    """Detect CSV delimiter. If encoding not given, try common ones."""
    encs = [encoding] if encoding else ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']
    for enc in encs:
        try:
            with open(path, 'r', encoding=enc, errors='replace', newline='') as f:
                sample = f.read(4096)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                    return dialect.delimiter
                except csv.Error:
                    return ','
        except Exception:
            continue
    return ','

def try_open_reader(path):
    """Open a CSV and return (reader, file_handle, encoding).
    Tries utf-8, utf-8-sig, cp1252, latin1."""
    for enc in ('utf-8', 'utf-8-sig', 'cp1252', 'latin1'):
        try:
            sep = sniff_delimiter(path, enc)
            fh = open(path, 'r', encoding=enc, errors='replace', newline='')
            reader = csv.reader(fh, delimiter=sep)
            return reader, fh, enc
        except Exception:
            try: fh.close()
            except: pass
    raise RuntimeError("No se pudo abrir el CSV con codificaciones comunes.")

def find_column(fieldnames, targets):
    """Find the best matching column from fieldnames for any of the target names.
    Case-insensitive, accent-insensitive, space/underscore tolerant.
    targets can be a list of strings or a single string."""
    if isinstance(targets, str):
        targets = [targets]
    def norm(x):
        return (
            (x or '').strip().lower()
            .replace('ã³', 'o').replace('ã¡', 'a').replace('ã©', 'e')
            .replace('ã\xad', 'i').replace('ãº', 'u')
            .replace('ó', 'o').replace('á', 'a').replace('é', 'e')
            .replace('í', 'i').replace('ú', 'u')
            .replace(' ', '_').replace('-', '_')
        )
    mapping = {norm(c): c for c in fieldnames}
    for t in targets:
        t_norm = norm(t)
        if t_norm in mapping:
            return mapping[t_norm]
        # Partial match
        for k, v in mapping.items():
            if t_norm in k or k in t_norm:
                return v
    return None

# From merge_iterative_1to1_full.py
TIERS = [('exact_minute', 0)] + [(f'±{i}min', i) for i in range(1, 1441)]

def _clean_spanish_ampm(s: pd.Series) -> pd.Series:
    s = s.astype('string')
    s = s.str.replace(r'\s+', ' ', regex=True)
    s = s.str.replace(' a. m.', ' AM', regex=False).str.replace(' p. m.', ' PM', regex=False)
    s = s.str.replace(' a m', ' AM', regex=False).str.replace(' p m', ' PM', regex=False)
    return s.str.strip()

def parse_datetime_spanish(series: pd.Series) -> pd.Series:
    s = _clean_spanish_ampm(series)
    dt = pd.to_datetime(s, format='%d/%m/%Y %I:%M:%S %p', errors='coerce', cache=True)
    mask = dt.isna()
    if mask.any():
        dt2 = pd.to_datetime(s[mask], dayfirst=True, errors='coerce', cache=True)
        dt.loc[mask] = dt2
    return dt.dt.floor('min')

def normalize_tel_series(tel: pd.Series) -> pd.Series:
    s = tel.astype('string').str.replace(r'\D+', '', regex=True)
    s = s.mask(s.eq(''), pd.NA)
    s = s.mask(s.str.startswith('521'), s.str[3:])
    s = s.mask(s.str.startswith('52'), s.str[2:])
    s = s.mask(s.str.len() > 10, s.str[-10:])
    s = s.mask(s.str.len() < 10, pd.NA)
    return s

def greedy_unique(pairs: pd.DataFrame) -> pd.DataFrame:
    if pairs is None or pairs.empty: return pairs
    pairs = pairs.sort_values(['delta_seconds', 'orig_idx_left', 'orig_idx_right'], kind='mergesort').copy()
    used_left, used_right, out = set(), set(), []
    for r in pairs.itertuples(index=False):
        li = r.orig_idx_left
        ri = r.orig_idx_right
        if li in used_left or ri in used_right: continue
        out.append(r)
        used_left.add(li)
        used_right.add(ri)
    return pd.DataFrame(out, columns=pairs.columns) if out else pairs.iloc[0:0]

def match_exact_minute(lday_slim, rday_slim):
    merged = lday_slim.merge(rday_slim, how='inner', on=['telephone', 'day', 'date'])
    if merged.empty: return merged
    merged['delta_seconds'] = 0.0
    merged['tier'] = 'exact_minute'
    return greedy_unique(merged[['orig_idx_left', 'orig_idx_right', 'delta_seconds', 'tier']])

def match_with_tolerance(lday_slim, rday_slim, tol_minutes):
    tol = pd.Timedelta(minutes=tol_minutes)
    a = lday_slim.rename(columns={'date': 'date_left'}).copy()
    b = rday_slim.rename(columns={'date': 'date_right'}).copy()
    a = a.sort_values(['date_left', 'telephone'], kind='mergesort').reset_index(drop=True)
    b = b.sort_values(['date_right', 'telephone'], kind='mergesort').reset_index(drop=True)
    res = pd.merge_asof(a, b, left_on='date_left', right_on='date_right', by='telephone', direction='nearest', tolerance=tol, allow_exact_matches=True)
    if res.empty or 'orig_idx_right' not in res.columns: return pd.DataFrame()
    res = res[res['orig_idx_right'].notna()].copy()
    if res.empty: return res
    res['delta_seconds'] = (res['date_left'] - res['date_right']).abs().dt.total_seconds()
    res = res[res['delta_seconds'] <= tol.total_seconds()].copy()
    if res.empty: return res
    out = res[['orig_idx_left', 'orig_idx_right', 'delta_seconds']].copy()
    out['tier'] = f'±{tol_minutes}min'
    return greedy_unique(out)

# ==========================================
# DATA PROCESSING PIPELINE
# ==========================================

def get_csv_dialect_and_encoding(filepath):
    encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                sample = f.read(4096)
                if not sample:
                    return csv.excel, enc
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample)
                return dialect, enc
        except UnicodeDecodeError:
            continue
        except csv.Error:
            return csv.excel, enc
    return csv.excel, 'utf-8'

def clean_phone_number(val):
    if not val: return ''
    s = re.sub(r'\D+', '', str(val))
    if s.startswith('521'): s = s[3:]
    elif s.startswith('52'): s = s[2:]
    if len(s) > 10: s = s[-10:]
    if len(s) < 10: return ''
    return s

def process_delta_file(filepath, outpath, col_fecha, col_hora, col_tel, q, cancel_event):
    if cancel_event.is_set(): return False
    q.put(('log', (f"Procesando archivo Delta/Neon: {os.path.basename(filepath)}", 'info')))
    
    if filepath.lower().endswith('.xlsx'):
        q.put(('log', ("Convirtiendo Delta XLSX a CSV temporal...", 'info')))
        df = pd.read_excel(filepath, dtype=str, engine='openpyxl')
        temp_csv = filepath + ".tmp.csv"
        df.to_csv(temp_csv, index=False, encoding='utf-8-sig')
        filepath = temp_csv

    dialect, enc = get_csv_dialect_and_encoding(filepath)
    
    total_lines = 0
    with open(filepath, 'r', encoding=enc) as f:
        total_lines = sum(1 for _ in f)
        
    processed = 0
    with open(filepath, 'r', encoding=enc) as fin, \
         open(outpath, 'w', encoding='utf-8-sig', newline='') as fout:
         
        reader = csv.DictReader(fin, dialect=dialect)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError("No se pudieron leer las columnas del archivo Delta")
        
        has_date = 'date' in [f.lower() for f in fieldnames]
        has_tel = 'telephone' in [f.lower() for f in fieldnames]
        
        out_fields = list(fieldnames)
        if not has_date and 'date' not in out_fields:
            out_fields.append('date')
        if not has_tel and 'telephone' not in out_fields:
            out_fields.append('telephone')
            
        writer = csv.DictWriter(fout, fieldnames=out_fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        
        for row in reader:
            if cancel_event.is_set(): 
                return False
            
            # Enrich date
            if not has_date:
                d_val = row.get(col_fecha, '')
                t_val = row.get(col_hora, '')
                d_obj = parse_date(d_val)
                t_obj = parse_time(t_val)
                row['date'] = build_date(d_obj, t_obj)
            
            # Enrich telephone
            if not has_tel:
                tel_val = row.get(col_tel, '')
                row['telephone'] = clean_phone_number(tel_val)
                
            writer.writerow(row)
            
            processed += 1
            if processed % 10000 == 0:
                q.put(('progress', (processed, total_lines, f"Procesando Delta: {processed}/{total_lines} filas")))
                
    if filepath.endswith(".tmp.csv") and os.path.exists(filepath):
        os.remove(filepath)
        
    return True

def process_bank_file(filepath, outpath, col_date, col_tel, q, cancel_event):
    if cancel_event.is_set(): return False
    q.put(('log', (f"Procesando archivo Banco: {os.path.basename(filepath)}", 'info')))
    
    if filepath.lower().endswith('.xlsx'):
        df = pd.read_excel(filepath, dtype=str, engine='openpyxl')
    else:
        dialect, enc = get_csv_dialect_and_encoding(filepath)
        sep = dialect.delimiter if hasattr(dialect, 'delimiter') else ','
        df = pd.read_csv(filepath, dtype=str, encoding=enc, sep=sep)
        
    total = len(df)
    q.put(('progress', (0, total, f"Procesando Banco: formateando fechas y teléfonos...")))
    
    if col_date in df.columns:
        def fix_date(x):
            dt = parse_any_datetime(str(x)) if pd.notna(x) else None
            return format_es_ampm(dt) if dt else ''
        df['date'] = df[col_date].apply(fix_date)
    else:
        df['date'] = ''
        
    if col_tel in df.columns:
        df['telephone'] = df[col_tel].apply(clean_phone_number)
    else:
        df['telephone'] = ''
        
    df.to_csv(outpath, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
    q.put(('progress', (total, total, "Archivo Banco procesado")))
    return True

def finalize_coincidencias(df):
    if df is None:
        return df

    cw_dialog_col = None
    if 'CW_dialog' in df.columns:
        cw_dialog_col = 'CW_dialog'
    else:
        for c in df.columns:
            if str(c).lower() == 'cw_dialog':
                cw_dialog_col = c
                break

    if cw_dialog_col:
        idx = list(df.columns).index(cw_dialog_col)
        dialog_vals = pd.to_numeric(df[cw_dialog_col], errors='coerce')
        df.insert(idx + 1, 'CW_minutes', dialog_vals / 60.0)

    cols_to_drop = ['TIER_CRUCE', 'DELTA_SEGUNDOS', 'date', 'telephone']
    present_drops = [c for c in cols_to_drop if c in df.columns]
    if present_drops:
        df.drop(columns=present_drops, inplace=True)

    return df

def run_merge(delta_csv, bank_csv, out_dir, out_base, q, cancel_event):
    if cancel_event.is_set(): return None
    q.put(('log', ("Cargando archivos para el cruce...", 'info')))
    
    df_left = pd.read_csv(delta_csv, dtype=str, encoding='utf-8-sig')
    df_right = pd.read_csv(bank_csv, dtype=str, encoding='utf-8-sig')
    
    df_left['orig_idx_left'] = df_left.index
    df_right['orig_idx_right'] = df_right.index
    
    df_left['telephone'] = normalize_tel_series(df_left['telephone'] if 'telephone' in df_left.columns else df_left.get('telephone', pd.Series(dtype=str)))
    df_right['telephone'] = normalize_tel_series(df_right['telephone'] if 'telephone' in df_right.columns else df_right.get('telephone', pd.Series(dtype=str)))
    
    df_left['date'] = parse_datetime_spanish(df_left['date'] if 'date' in df_left.columns else pd.Series(dtype=str))
    df_right['date'] = parse_datetime_spanish(df_right['date'] if 'date' in df_right.columns else pd.Series(dtype=str))
    
    df_left['day'] = df_left['date'].dt.floor('D')
    df_right['day'] = df_right['date'].dt.floor('D')
    
    valid_left = df_left.dropna(subset=['telephone', 'date', 'day']).copy()
    valid_right = df_right.dropna(subset=['telephone', 'date', 'day']).copy()
    
    common_days = sorted(list(set(valid_left['day'].unique()).intersection(set(valid_right['day'].unique()))))
    q.put(('stats', {'dias': len(common_days)}))
    
    all_matches = []
    total_days = len(common_days)
    
    q.put(('log', (f"Iniciando cruce iterativo por días ({total_days} días comunes)...", 'info')))
    
    for idx, day in enumerate(common_days):
        if cancel_event.is_set(): return None
        q.put(('log', (f"Cruzando día: {day.strftime('%Y-%m-%d')}...", 'info')))
        q.put(('progress', (idx, total_days, f"Cruce día {idx+1}/{total_days}")))
        
        ld = valid_left[valid_left['day'] == day].copy()
        rd = valid_right[valid_right['day'] == day].copy()
        
        l_slim = ld[['orig_idx_left', 'telephone', 'date', 'day']].copy()
        r_slim = rd[['orig_idx_right', 'telephone', 'date', 'day']].copy()
        
        matches = match_exact_minute(l_slim, r_slim)
        day_matches = [matches] if not matches.empty else []
        
        if not matches.empty:
            matched_l = set(matches['orig_idx_left'])
            matched_r = set(matches['orig_idx_right'])
            l_slim = l_slim[~l_slim['orig_idx_left'].isin(matched_l)]
            r_slim = r_slim[~r_slim['orig_idx_right'].isin(matched_r)]
            
        for tier_name, tol_minutes in TIERS[1:]:
            if cancel_event.is_set(): return None
            if l_slim.empty or r_slim.empty: break
            m = match_with_tolerance(l_slim, r_slim, tol_minutes)
            if not m.empty:
                day_matches.append(m)
                matched_l = set(m['orig_idx_left'])
                matched_r = set(m['orig_idx_right'])
                l_slim = l_slim[~l_slim['orig_idx_left'].isin(matched_l)]
                r_slim = r_slim[~r_slim['orig_idx_right'].isin(matched_r)]
                
        if day_matches:
            all_matches.append(pd.concat(day_matches, ignore_index=True))
            
    q.put(('stats', {'registros': len(valid_left) + len(valid_right)}))
    if all_matches:
        final_matches = pd.concat(all_matches, ignore_index=True)
    else:
        final_matches = pd.DataFrame(columns=['orig_idx_left', 'orig_idx_right', 'delta_seconds', 'tier'])
        
    matched_left_idx = set(final_matches['orig_idx_left']) if not final_matches.empty else set()
    matched_right_idx = set(final_matches['orig_idx_right']) if not final_matches.empty else set()
    
    coincidencias = df_left.iloc[final_matches['orig_idx_left'].values if not final_matches.empty else []].copy()
    
    if not final_matches.empty:
        df_right_aligned = df_right.iloc[final_matches['orig_idx_right'].values].reset_index(drop=True)
        coincidencias = coincidencias.reset_index(drop=True)
        for c in df_right.columns:
            if c not in ['orig_idx_right', 'day']:
                new_col = f"CW_{c}"
                coincidencias[new_col] = df_right_aligned[c]
        coincidencias['TIER_CRUCE'] = final_matches['tier'].values
        coincidencias['DELTA_SEGUNDOS'] = final_matches['delta_seconds'].values
    else:
        coincidencias['TIER_CRUCE'] = []
        coincidencias['DELTA_SEGUNDOS'] = []
        
    remanentes_left = df_left[~df_left['orig_idx_left'].isin(matched_left_idx)].copy()
    remanentes_right = df_right[~df_right['orig_idx_right'].isin(matched_right_idx)].copy()
    
    for df in (coincidencias, remanentes_left, remanentes_right):
        for col in ['orig_idx_left', 'orig_idx_right', 'day']:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)
                
    coincidencias = finalize_coincidencias(coincidencias)

    f_coin = os.path.join(out_dir, f"{out_base}_coincidencias.csv")
    f_rem_l = os.path.join(out_dir, f"{out_base}_remanentes_left.csv")
    f_rem_r = os.path.join(out_dir, f"{out_base}_remanentes_right.csv")
    
    coincidencias.to_csv(f_coin, index=False, encoding='utf-8-sig')
    remanentes_left.to_csv(f_rem_l, index=False, encoding='utf-8-sig')
    remanentes_right.to_csv(f_rem_r, index=False, encoding='utf-8-sig')
    
    q.put(('log', ("Cruce completado con éxito.", 'success')))
    return {
        'coincidencias': (len(coincidencias), f_coin),
        'remanentes_left': (len(remanentes_left), f_rem_l),
        'remanentes_right': (len(remanentes_right), f_rem_r)
    }

# ==========================================
# WORKER THREAD
# ==========================================

def worker_thread(params, q, cancel_event):
    try:
        delta_path = params['delta_path']
        bank_path = params['bank_path']
        out_dir = params['out_dir']
        out_base = params['out_base']
        
        delta_enriched = os.path.join(out_dir, f"{out_base}_delta_enriched.csv")
        bank_enriched = os.path.join(out_dir, f"{out_base}_bank_enriched.csv")
        
        q.put(('log', ("═══ INICIANDO PROCESO DE FACTURACIÓN ═══", 'info')))
        
        if not process_delta_file(delta_path, delta_enriched, params['delta_fecha'], params['delta_hora'], params['delta_tel'], q, cancel_event):
            q.put(('log', ("Proceso cancelado por el usuario.", 'warning')))
            q.put(('done', None))
            return
            
        if not process_bank_file(bank_path, bank_enriched, params['bank_date'], params['bank_tel'], q, cancel_event):
            q.put(('log', "Proceso cancelado por el usuario.", 'warning'))
            q.put(('done', None))
            return
            
        results = run_merge(delta_enriched, bank_enriched, out_dir, out_base, q, cancel_event)
        
        if results:
            q.put(('done', results))
        else:
            q.put(('log', ("Proceso cancelado por el usuario.", 'warning')))
            q.put(('done', None))
            
    except Exception as e:
        q.put(('error', f"Error inesperado:\n{traceback.format_exc()}"))
        q.put(('done', None))


# ==========================================
# UI APPLICATION
# ==========================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Procesamiento de CDRs - Facturación")
        self.geometry("1000x800")
        self.minsize(900, 700)
        self.configure(bg=BG_COLOR)
        
        # Set window icon
        try:
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            ico_path = os.path.join(base_path, 'procesar.ico')
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
            else:
                png_path = os.path.join(base_path, 'procesar.png')
                if os.path.exists(png_path):
                    icon = tk.PhotoImage(file=png_path)
                    self.iconphoto(True, icon)
        except Exception:
            pass
        
        self.q = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker = None
        
        self.delta_file = tk.StringVar()
        self.bank_file = tk.StringVar()
        self.out_dir = tk.StringVar()
        self.out_base = tk.StringVar(value="Facturacion")
        
        self.stats = {'registros': 0, 'dias': 0}
        
        self.setup_styles()
        self.build_ui()
        
    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        
        # General configurations
        style.configure('TFrame', background=BG_COLOR)
        style.configure('Panel.TFrame', background=PANEL_BG)
        style.configure('DropZone.TFrame', background=DROP_ZONE_BG)
        
        # Labels
        style.configure('TLabel', background=BG_COLOR, foreground=TEXT_COLOR, font=('Segoe UI', 10))
        style.configure('Panel.TLabel', background=PANEL_BG, foreground=TEXT_COLOR, font=('Segoe UI', 10))
        style.configure('Header.TLabel', background=PANEL_BG, foreground=HEADER_NAVY, font=('Segoe UI', 16, 'bold'))
        style.configure('Subheader.TLabel', background=PANEL_BG, foreground=DIM_TEXT, font=('Segoe UI', 10))
        style.configure('SectionTitle.TLabel', background=PANEL_BG, foreground=HEADER_NAVY, font=('Segoe UI', 12, 'bold'))
        
        # Progressbar
        style.configure('Horizontal.TProgressbar', background=ACCENT_BLUE, troughcolor=SURFACE, thickness=15)
        
        # Checkbutton
        style.configure('TCheckbutton', background=PANEL_BG, foreground=TEXT_COLOR, font=('Segoe UI', 9))
        style.map('TCheckbutton', background=[('active', PANEL_BG)])

    def create_card_frame(self, parent):
        outer = tk.Frame(parent, bg=BG_COLOR, pady=10)
        card = tk.Frame(outer, bg=PANEL_BG, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=20, pady=20)
        card.pack(fill=tk.BOTH, expand=True)
        return outer, card

    def create_button(self, parent, text, cmd, style_type='blue'):
        btn = tk.Button(parent, text=text, command=cmd, font=('Segoe UI', 10), cursor="hand2", relief=tk.FLAT)
        if style_type == 'blue':
            btn.config(bg=BTN_BLUE, fg="white", activebackground=BTN_BLUE_HOVER, activeforeground="white")
        elif style_type == 'green':
            btn.config(bg=BTN_GREEN, fg="white", activebackground=BTN_GREEN_HOVER, activeforeground="white")
        elif style_type == 'blue_outline':
            btn.config(bg=PANEL_BG, fg=BTN_BLUE, highlightbackground=BTN_BLUE, highlightthickness=1, activebackground=LIGHT_BLUE_BG, activeforeground=BTN_BLUE)
        elif style_type == 'gray_outline':
            btn.config(bg=PANEL_BG, fg=DIM_TEXT, highlightbackground=BORDER_COLOR, highlightthickness=1, activebackground=SURFACE, activeforeground=TEXT_COLOR)
        return btn

    def build_ui(self):
        # Header
        header_frame = tk.Frame(self, bg=PANEL_BG, borderwidth=1, relief=tk.SOLID, highlightbackground=BORDER_COLOR)
        header_frame.pack(fill=tk.X)
        
        h_inner = tk.Frame(header_frame, bg=PANEL_BG, padx=20, pady=15)
        h_inner.pack(fill=tk.X)
        
        ttk.Label(h_inner, text="Procesamiento de CDRs", style='Header.TLabel').pack(anchor=tk.W)
        
        # Scrollable area
        self.canvas = tk.Canvas(self, bg=BG_COLOR, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=BG_COLOR)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        content_pad = tk.Frame(self.scrollable_frame, bg=BG_COLOR, padx=30, pady=10)
        content_pad.pack(fill=tk.BOTH, expand=True)

        # STEP 1
        s1_outer, s1_card = self.create_card_frame(content_pad)
        s1_outer.pack(fill=tk.X)
        
        # Files container
        files_frame = tk.Frame(s1_card, bg=PANEL_BG)
        files_frame.pack(fill=tk.X)
        files_frame.columnconfigure(0, weight=1, pad=10)
        files_frame.columnconfigure(1, weight=1, pad=10)
        
        # Delta Panel
        pnl_delta = tk.Frame(files_frame, bg=PANEL_BG)
        pnl_delta.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        ttk.Label(pnl_delta, text="Step 1: Carga y Mapeo (Step 1 of 3)", style='SectionTitle.TLabel').pack(anchor=tk.W, pady=(0,10))
        
        delta_top = tk.Frame(pnl_delta, bg=PANEL_BG)
        delta_top.pack(fill=tk.X, pady=5)
        
        self.create_button(delta_top, "📂 Examinar...", self.browse_delta, 'blue_outline').pack(side=tk.LEFT, padx=(0,10))
        
        dz_delta = tk.Frame(delta_top, bg=DROP_ZONE_BG, highlightbackground=DROP_ZONE_BORDER, highlightthickness=1)
        dz_delta.pack(side=tk.LEFT, fill=tk.X, expand=True)
        dz_lbl = tk.Label(dz_delta, text="Subir archivo...", bg=DROP_ZONE_BG, fg=DIM_TEXT, cursor="hand2")
        dz_lbl.pack(pady=5)
        dz_lbl.bind("<Button-1>", lambda e: self.browse_delta())
        dz_delta.bind("<Button-1>", lambda e: self.browse_delta())
        
        delta_info = tk.Frame(pnl_delta, bg=PANEL_BG)
        delta_info.pack(fill=tk.X, pady=5)
        self.lbl_delta_info = tk.Label(delta_info, text="Ningún archivo seleccionado", bg=PANEL_BG, fg=DIM_TEXT, font=('Segoe UI', 9))
        self.lbl_delta_info.pack(side=tk.LEFT)
        self.lbl_delta_status = tk.Label(delta_info, text="", bg=PANEL_BG, fg=SUCCESS_GREEN, font=('Segoe UI', 9, 'bold'))
        self.lbl_delta_status.pack(side=tk.RIGHT)
        
        f_dcols = tk.Frame(pnl_delta, bg=PANEL_BG)
        f_dcols.pack(fill=tk.X, pady=(10,0))
        
        tk.Label(f_dcols, text="Columna Fecha:", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.cb_delta_fecha = ttk.Combobox(f_dcols, state="readonly", width=25)
        self.cb_delta_fecha.grid(row=0, column=1, sticky=tk.EW, padx=10, pady=5)
        
        tk.Label(f_dcols, text="Columna Hora:", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.cb_delta_hora = ttk.Combobox(f_dcols, state="readonly", width=25)
        self.cb_delta_hora.grid(row=1, column=1, sticky=tk.EW, padx=10, pady=5)
        
        tk.Label(f_dcols, text="Columna Teléfono:", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.cb_delta_tel = ttk.Combobox(f_dcols, state="readonly", width=25)
        self.cb_delta_tel.grid(row=2, column=1, sticky=tk.EW, padx=10, pady=5)
        f_dcols.columnconfigure(1, weight=1)
        
        # Bank Panel
        pnl_bank = tk.Frame(files_frame, bg=PANEL_BG)
        pnl_bank.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        ttk.Label(pnl_bank, text="Step 1: Archivo Banco (Step 1 of 3)", style='SectionTitle.TLabel').pack(anchor=tk.W, pady=(0,10))
        
        bank_top = tk.Frame(pnl_bank, bg=PANEL_BG)
        bank_top.pack(fill=tk.X, pady=5)
        self.create_button(bank_top, "📂 Examinar...", self.browse_bank, 'blue_outline').pack(side=tk.LEFT, padx=(0,10))
        
        dz_bank = tk.Frame(bank_top, bg=DROP_ZONE_BG, highlightbackground=DROP_ZONE_BORDER, highlightthickness=1)
        dz_bank.pack(side=tk.LEFT, fill=tk.X, expand=True)
        dz_lbl_b = tk.Label(dz_bank, text="Subir archivo...", bg=DROP_ZONE_BG, fg=DIM_TEXT, cursor="hand2")
        dz_lbl_b.pack(pady=5)
        dz_lbl_b.bind("<Button-1>", lambda e: self.browse_bank())
        dz_bank.bind("<Button-1>", lambda e: self.browse_bank())
        
        bank_info = tk.Frame(pnl_bank, bg=PANEL_BG)
        bank_info.pack(fill=tk.X, pady=5)
        self.lbl_bank_info = tk.Label(bank_info, text="Ningún archivo seleccionado", bg=PANEL_BG, fg=DIM_TEXT, font=('Segoe UI', 9))
        self.lbl_bank_info.pack(side=tk.LEFT)
        self.lbl_bank_status = tk.Label(bank_info, text="", bg=PANEL_BG, fg=SUCCESS_GREEN, font=('Segoe UI', 9, 'bold'))
        self.lbl_bank_status.pack(side=tk.RIGHT)
        
        f_bcols = tk.Frame(pnl_bank, bg=PANEL_BG)
        f_bcols.pack(fill=tk.X, pady=(10,0))
        
        tk.Label(f_bcols, text="Columna Fecha:", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.cb_bank_fecha = ttk.Combobox(f_bcols, state="readonly", width=25)
        self.cb_bank_fecha.grid(row=0, column=1, sticky=tk.EW, padx=10, pady=5)
        
        tk.Label(f_bcols, text="Columna Teléfono:", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.cb_bank_tel = ttk.Combobox(f_bcols, state="readonly", width=25)
        self.cb_bank_tel.grid(row=1, column=1, sticky=tk.EW, padx=10, pady=5)
        f_bcols.columnconfigure(1, weight=1)

        for cb in (self.cb_delta_fecha, self.cb_delta_hora, self.cb_delta_tel, self.cb_bank_fecha, self.cb_bank_tel):
            cb.bind("<<ComboboxSelected>>", self.on_combobox_changed)

        # STEP 2
        s2_outer, s2_card = self.create_card_frame(content_pad)
        s2_outer.pack(fill=tk.X)
        
        ttk.Label(s2_card, text="Configuración de Salida (Step 2 of 3)", style='SectionTitle.TLabel').pack(anchor=tk.W, pady=(0,10))
        
        f_out = tk.Frame(s2_card, bg=PANEL_BG)
        f_out.pack(fill=tk.X)
        
        tk.Label(f_out, text="Nombre de Base:", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=0, column=0, sticky=tk.W, pady=5)
        e_base = tk.Entry(f_out, textvariable=self.out_base, bg=INPUT_BG, fg=TEXT_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1, relief=tk.FLAT)
        e_base.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5, ipadx=5, ipady=3)
        
        tk.Label(f_out, text="Carpeta Salida:", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=1, column=0, sticky=tk.W, pady=5)
        e_out = tk.Entry(f_out, textvariable=self.out_dir, bg=INPUT_BG, fg=TEXT_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1, relief=tk.FLAT)
        e_out.grid(row=1, column=1, sticky=tk.EW, padx=10, pady=5, ipadx=5, ipady=3)
        
        out_btn_frame = tk.Frame(f_out, bg=PANEL_BG)
        out_btn_frame.grid(row=1, column=2, padx=5, pady=5)
        tk.Label(out_btn_frame, text="📁", bg=PANEL_BG).pack(side=tk.LEFT, padx=(0,5))
        self.create_button(out_btn_frame, "Cambiar...", self.browse_out, 'gray_outline').pack(side=tk.LEFT)
        
        f_out.columnconfigure(1, weight=1)

        # STEP 3
        s3_outer, s3_card = self.create_card_frame(content_pad)
        s3_outer.pack(fill=tk.X)
        
        ttk.Label(s3_card, text="Procesamiento (Step 3 of 3)", style='SectionTitle.TLabel').pack(anchor=tk.W, pady=(0,10))
        
        proc_top = tk.Frame(s3_card, bg=PANEL_BG)
        proc_top.pack(fill=tk.X)
        
        self.btn_run = self.create_button(proc_top, "Iniciar Cruce", self.run_process, 'green')
        self.btn_run.pack(side=tk.LEFT, ipadx=10, ipady=3)
        
        self.btn_cancel = self.create_button(proc_top, "Cancelar", self.cancel_process, 'gray_outline')
        
        prog_frame = tk.Frame(proc_top, bg=PANEL_BG)
        prog_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, style='Horizontal.TProgressbar', maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(5,0))
        self.lbl_progress = tk.Label(prog_frame, text="Listo para iniciar.", bg=PANEL_BG, fg=DIM_TEXT, font=('Segoe UI', 9))
        self.lbl_progress.pack(anchor=tk.W)

        # Status panel
        self.status_panel = tk.Frame(proc_top, bg=PANEL_BG, padx=10, pady=5)
        self.status_panel.pack(side=tk.RIGHT)
        
        self.status_lbl = tk.Label(self.status_panel, text="Esperando...", bg=PANEL_BG, fg=DIM_TEXT, font=('Segoe UI', 10))
        self.status_lbl.pack(side=tk.TOP)
        self.stats_lbl = tk.Label(self.status_panel, text="", bg=PANEL_BG, fg=TEXT_COLOR, font=('Segoe UI', 9))
        self.stats_lbl.pack(side=tk.TOP)
        
        # Log section
        log_ctrl = tk.Frame(s3_card, bg=PANEL_BG)
        log_ctrl.pack(fill=tk.X, pady=(20, 5))
        
        self.show_log_var = tk.BooleanVar(value=True)
        cb_log = ttk.Checkbutton(log_ctrl, text="Ver Detalles del Registro", variable=self.show_log_var, command=self.toggle_log)
        cb_log.pack(side=tk.LEFT)
        
        self.log_frame = tk.Frame(s3_card, bg=CONSOLE_BG, bd=1, relief=tk.SOLID)
        self.log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_area = scrolledtext.ScrolledText(self.log_frame, bg=CONSOLE_BG, fg=CONSOLE_FG, font=('Consolas', 9), height=12, bd=0)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_area.tag_config('info', foreground=CONSOLE_FG)
        self.log_area.tag_config('success', foreground=SUCCESS_GREEN)
        self.log_area.tag_config('warning', foreground=WARNING_YELLOW)
        self.log_area.tag_config('error', foreground=ERROR_RED)

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def toggle_log(self):
        if self.show_log_var.get():
            self.log_frame.pack(fill=tk.BOTH, expand=True)
        else:
            self.log_frame.pack_forget()

    def _get_columns(self, filepath):
        if not filepath or not os.path.exists(filepath): return []
        try:
            if filepath.lower().endswith('.xlsx'):
                df = pd.read_excel(filepath, nrows=0, engine='openpyxl')
                return list(df.columns)
            else:
                dialect, enc = get_csv_dialect_and_encoding(filepath)
                with open(filepath, 'r', encoding=enc) as f:
                    reader = csv.reader(f, dialect=dialect)
                    return next(reader, [])
        except Exception as e:
            self.log(f"Error al leer columnas de {filepath}: {str(e)}", 'error')
            return []
            
    def _find_best_match(self, options, targets):
        for t in targets:
            for opt in options:
                clean_opt = re.sub(r'[^a-zA-Z0-9]', '', str(opt).lower())
                clean_t = re.sub(r'[^a-zA-Z0-9]', '', str(t).lower())
                if clean_t in clean_opt:
                    return opt
        return ''

    def browse_delta(self):
        f = filedialog.askopenfilename(filetypes=[("Archivos", "*.csv *.xlsx")])
        if f:
            self.delta_file.set(f)
            size_mb = os.path.getsize(f) / (1024*1024)
            self.lbl_delta_info.config(text=f"{os.path.basename(f)} ({size_mb:.1f} MB)")
            
            if not self.out_dir.get():
                self.out_dir.set(os.path.dirname(f))
                
            cols = self._get_columns(f)
            self.cb_delta_fecha['values'] = cols
            self.cb_delta_hora['values'] = cols
            self.cb_delta_tel['values'] = cols
            
            # Reset dropdowns
            self.cb_delta_fecha.set('')
            self.cb_delta_hora.set('')
            self.cb_delta_tel.set('')

            # Auto-detect best column matches
            f_match = self._find_best_match(cols, ['fecha de conexión', 'fechadeconexion', 'fecha de conexion', 'fecha', 'date'])
            h_match = self._find_best_match(cols, ['hora de conexión', 'horadeconexion', 'hora de conexion', 'hora', 'time'])
            t_match = self._find_best_match(cols, ['numerob_destino', 'numerob', 'destino', 'telefono', 'telephone', 'tel', 'phone'])
            
            if f_match: self.cb_delta_fecha.set(f_match)
            if h_match: self.cb_delta_hora.set(h_match)
            if t_match: self.cb_delta_tel.set(t_match)

            missing = []
            if not self.cb_delta_fecha.get(): missing.append("Fecha")
            if not self.cb_delta_hora.get(): missing.append("Hora")
            if not self.cb_delta_tel.get(): missing.append("Teléfono")

            if missing:
                self.log(f"⚠️ Delta ({os.path.basename(f)}): No se encontró la(s) columna(s) para: {', '.join(missing)}. Por favor selecciónala(s) manualmente.", 'warning')
                messagebox.showwarning(
                    "⚠️ Columna no encontrada", 
                    f"En el archivo Delta ({os.path.basename(f)}):\n\nNo se pudo detectar automáticamente la(s) columna(s):\n• {', '.join(missing)}\n\nPor favor selecciónalas en las listas desplegables de la pantalla."
                )
            else:
                self.log(f"✅ Delta ({os.path.basename(f)}): Columnas auto-asignadas -> Fecha: '{f_match}', Hora: '{h_match}', Teléfono: '{t_match}'", 'success')
            
            self.check_status()

    def browse_bank(self):
        f = filedialog.askopenfilename(filetypes=[("Archivos", "*.csv *.xlsx")])
        if f:
            self.bank_file.set(f)
            size_mb = os.path.getsize(f) / (1024*1024)
            self.lbl_bank_info.config(text=f"{os.path.basename(f)} ({size_mb:.1f} MB)")
            
            cols = self._get_columns(f)
            self.cb_bank_fecha['values'] = cols
            self.cb_bank_tel['values'] = cols
            
            self.cb_bank_fecha.set('')
            self.cb_bank_tel.set('')

            f_match = self._find_best_match(cols, ['date', 'fecha', 'fechahora', 'fecha_hora'])
            t_match = self._find_best_match(cols, ['telephone', 'telefono', 'tel', 'phone', 'numerob'])
            
            if f_match: self.cb_bank_fecha.set(f_match)
            if t_match: self.cb_bank_tel.set(t_match)
            
            missing = []
            if not self.cb_bank_fecha.get(): missing.append("Fecha")
            if not self.cb_bank_tel.get(): missing.append("Teléfono")

            if missing:
                self.log(f"⚠️ Banco ({os.path.basename(f)}): No se encontró la(s) columna(s) para: {', '.join(missing)}. Por favor selecciónala(s) manualmente.", 'warning')
                messagebox.showwarning(
                    "⚠️ Columna no encontrada", 
                    f"En el archivo Banco ({os.path.basename(f)}):\n\nNo se pudo detectar automáticamente la(s) columna(s):\n• {', '.join(missing)}\n\nPor favor selecciónalas en las listas desplegables de la pantalla."
                )
            else:
                self.log(f"✅ Banco ({os.path.basename(f)}): Columnas auto-asignadas -> Fecha: '{f_match}', Teléfono: '{t_match}'", 'success')

            self.check_status()
            
    def browse_out(self):
        d = filedialog.askdirectory()
        if d: self.out_dir.set(d)

    def on_combobox_changed(self, event=None):
        self.check_status()
        if event and event.widget:
            val = event.widget.get()
            self.log(f"Columna seleccionada manualmente: '{val}'", 'info')

    def check_status(self):
        d_f = self.cb_delta_fecha.get()
        d_h = self.cb_delta_hora.get()
        d_t = self.cb_delta_tel.get()
        b_f = self.cb_bank_fecha.get()
        b_t = self.cb_bank_tel.get()

        d_ok = bool(d_f and d_h and d_t)
        b_ok = bool(b_f and b_t)
        
        if d_ok:
            self.lbl_delta_status.config(text="✓ Listo", fg=SUCCESS_GREEN)
        elif self.delta_file.get():
            missing = []
            if not d_f: missing.append("Fecha")
            if not d_h: missing.append("Hora")
            if not d_t: missing.append("Teléfono")
            self.lbl_delta_status.config(text=f"⚠️ Falta: {', '.join(missing)}", fg=WARNING_YELLOW)
        else:
            self.lbl_delta_status.config(text="")
            
        if b_ok:
            self.lbl_bank_status.config(text="✓ Listo", fg=SUCCESS_GREEN)
        elif self.bank_file.get():
            missing = []
            if not b_f: missing.append("Fecha")
            if not b_t: missing.append("Teléfono")
            self.lbl_bank_status.config(text=f"⚠️ Falta: {', '.join(missing)}", fg=WARNING_YELLOW)
        else:
            self.lbl_bank_status.config(text="")

    def log(self, text, tag='info'):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_area.insert(tk.END, f"[{ts}] {text}\n", tag)
        self.log_area.see(tk.END)

    def run_process(self):
        if not self.delta_file.get() or not self.bank_file.get():
            messagebox.showerror("Error", "Seleccione ambos archivos.")
            return
            
        if not self.cb_delta_fecha.get() or not self.cb_delta_hora.get() or not self.cb_delta_tel.get():
            messagebox.showwarning("Atención", "Seleccione las columnas del archivo Delta.")
            return
            
        if not self.cb_bank_fecha.get() or not self.cb_bank_tel.get():
            messagebox.showwarning("Atención", "Seleccione las columnas del archivo Banco.")
            return
            
        if not self.out_dir.get():
            messagebox.showwarning("Atención", "Seleccione la carpeta de salida.")
            return

        self.btn_run.pack_forget()
        self.btn_cancel.pack(side=tk.LEFT, ipadx=10, ipady=3)
        self.progress_var.set(0)
        
        self.status_panel.config(bg=PANEL_BG)
        self.status_lbl.config(text="Procesando...", bg=PANEL_BG, fg=TEXT_COLOR)
        self.stats_lbl.config(text="", bg=PANEL_BG)
        
        self.log_area.delete(1.0, tk.END)
        self.cancel_event.clear()
        self.stats = {'registros': 0, 'dias': 0}
        
        params = {
            'delta_path': self.delta_file.get(),
            'bank_path': self.bank_file.get(),
            'out_dir': self.out_dir.get(),
            'out_base': self.out_base.get().strip() or "Facturacion",
            'delta_fecha': self.cb_delta_fecha.get(),
            'delta_hora': self.cb_delta_hora.get(),
            'delta_tel': self.cb_delta_tel.get(),
            'bank_date': self.cb_bank_fecha.get(),
            'bank_tel': self.cb_bank_tel.get()
        }
        
        self.worker = threading.Thread(target=worker_thread, args=(params, self.q, self.cancel_event), daemon=True)
        self.worker.start()
        self.after(100, self.poll_queue)

    def cancel_process(self):
        self.cancel_event.set()
        self.log("Solicitando cancelación...", 'warning')
        self.btn_cancel.config(state=tk.DISABLED)

    def poll_queue(self):
        try:
            while True:
                item = self.q.get_nowait()
                if len(item) == 2:
                    msg_type, data = item
                elif len(item) == 3:
                    msg_type = item[0]
                    data = (item[1], item[2])
                else:
                    continue
                    
                if msg_type == 'log':
                    text, tag = data if isinstance(data, tuple) else (data, 'info')
                    self.log(text, tag)
                elif msg_type == 'progress':
                    val, max_val, text = data
                    self.lbl_progress.config(text=text)
                    if max_val > 0:
                        self.progress_var.set((val / max_val) * 100)
                elif msg_type == 'stats':
                    self.stats.update(data)
                    st_text = f"{self.stats['dias']} días encontrados"
                    self.stats_lbl.config(text=st_text)
                elif msg_type == 'error':
                    self.log(data, 'error')
                    messagebox.showerror("Error", data)
                elif msg_type == 'done':
                    self.finish_process(data)
                    return
        except queue.Empty:
            pass
            
        self.after(100, self.poll_queue)

    def finish_process(self, results):
        self.btn_cancel.pack_forget()
        self.btn_cancel.config(state=tk.NORMAL)
        self.btn_run.pack(side=tk.LEFT, ipadx=10, ipady=3)
        self.progress_var.set(100)
        
        if results:
            self.lbl_progress.config(text="Proceso finalizado.")
            self.status_panel.config(bg=LIGHT_GREEN_BG)
            self.status_lbl.config(text="✅ Proceso finalizado con éxito", bg=LIGHT_GREEN_BG, fg=SUCCESS_GREEN, font=('Segoe UI', 10, 'bold'))
            
            # Update stats with actual result counts
            coin_count = results.get('coincidencias', (0,''))[0]
            rem_l_count = results.get('remanentes_left', (0,''))[0]
            rem_r_count = results.get('remanentes_right', (0,''))[0]
            dias = self.stats.get('dias', 0)
            
            stats_text = f"Matches: {coin_count:,} | Rem.L: {rem_l_count:,} | Rem.R: {rem_r_count:,}\n{dias} días cruzados"
            self.stats_lbl.config(text=stats_text, bg=LIGHT_GREEN_BG, fg=SUCCESS_GREEN)
            
            self.log("═" * 50, 'info')
            self.log("  RESUMEN FINAL", 'success')
            self.log("═" * 50, 'info')
            for name, (count, filepath) in results.items():
                label = {'coincidencias': 'Matches totales', 'remanentes_left': 'Remanentes LEFT', 'remanentes_right': 'Remanentes RIGHT'}[name]
                self.log(f"  {label}: {count:,}. Salida: {os.path.basename(filepath)}", 'success')
            self.log("═" * 50, 'info')
        else:
            self.lbl_progress.config(text="Proceso cancelado o fallido.")

if __name__ == "__main__":
    app = App()
    app.mainloop()
