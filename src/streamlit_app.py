import random
import logging as _logging
import warnings as _warnings

# Silence Streamlit's own internal INFO/WARNING chatter — things like
# "missing ScriptRunContext", "Session state does not function when
# running a script without 'streamlit run'", "No runtime found, using
# MemoryCacheStorageManager", and the "streamlit run [FILE_NAME]..." banner.
# All of this is Streamlit talking to itself whenever a background worker
# process (kjscreener's multiprocessing screening workers) re-imports parts
# of the app outside a real Streamlit script context. It's 100% harmless —
# Streamlit's own docs say so — but it floods the terminal during a
# screening run, so we raise these loggers' threshold before anything else
# can spawn a worker and trigger them.
_logging.getLogger('streamlit').setLevel(_logging.CRITICAL)
for _noisy_logger in (
    'streamlit',
    'streamlit.runtime',
    'streamlit.runtime.scriptrunner_utils.script_run_context',
    'streamlit.runtime.scriptrunner_utils',
    'streamlit.runtime.scriptrunner',
    'streamlit.runtime.state.session_state_proxy',
    'streamlit.runtime.state',
    'streamlit.runtime.caching.storage.local_disk_cache_storage',
    'streamlit.runtime.caching.storage.in_memory_cache_storage_wrapper',
    'streamlit.runtime.caching.storage',
    'streamlit.runtime.caching',
):
    _logging.getLogger(_noisy_logger).setLevel(_logging.CRITICAL)

_warnings.filterwarnings('ignore', message='.*ScriptRunContext.*')
_warnings.filterwarnings('ignore', message='.*streamlit run.*')

import streamlit as st

if "_bcs_storage_init" not in st.session_state:
    st.session_state["_bcs_storage_init"] = {}

if "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "dark"

import requests
import os
import json
import yaml
import time
import configparser
import urllib
import datetime
from num2words import num2words
from time import sleep
from pathlib import Path
from threading import Thread
from math import floor
import math
import threading
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

st.set_page_config(layout="wide", page_title="KJScreener", page_icon="📈")

os.environ["PYTHONUNBUFFERED"] = "1"
# Critical: mark GUI mode so kjscreener.main() skips blocking input() prompts.
# Without this, screening hangs forever waiting for stdin when launched via
# `streamlit run` instead of the run_kjscreener.sh --gui wrapper.
os.environ["KJScreener_GUI"] = "TRUE"

# Suppress noisy Streamlit internal warnings (also re-applied so child processes
# that re-import this module pick up the quieter level).
import logging as _logging
_logging.getLogger("streamlit").setLevel(_logging.CRITICAL)
_logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").setLevel(_logging.CRITICAL)
_logging.getLogger("streamlit.runtime.scriptrunner").setLevel(_logging.CRITICAL)
_logging.getLogger("streamlit.runtime.state.session_state_proxy").setLevel(_logging.CRITICAL)
_logging.getLogger("streamlit.runtime.caching").setLevel(_logging.CRITICAL)

# ── Startup splash — shown immediately before heavy imports ───────────────────
_startup_placeholder = st.empty()
if not st.session_state.get('_app_loaded'):
    with _startup_placeholder.container():
        st.markdown("""
        <style>
          header[data-testid="stHeader"] { visibility: hidden; }
        </style>
        """, unsafe_allow_html=True)
        st.markdown(
            "<div style='display:flex;flex-direction:column;align-items:center;"
            "justify-content:center;height:80vh;gap:1.2rem;'>"
            "<div style='font-size:3.5rem;'>📈</div>"
            "<div style='font-size:1.6rem;font-weight:700;letter-spacing:0.04em;'>KJScreener</div>"
            "<div style='color:#888;font-size:0.95rem;'>Loading, please wait…</div>"
            "</div>",
            unsafe_allow_html=True,
        )

import pandas as pd
import classes.ConfigManager as ConfigManager
import classes.Utility as Utility
import classes.Fetcher as Fetcher
import classes.BrowserConfigStore as BrowserConfigStore
from kjscreener import main as KJScreener_main
from classes.OtaUpdater import OTAUpdater
OtaUpdater = OTAUpdater
from classes.Changelog import VERSION

# ── Global CSS (theme-aware) ───────────────────────────────────────────────────
if st.session_state.get("theme_mode", "dark") == "light":
    _bg = "#ffffff"
    _panel_bg = "#f0f2f6"
    _text = "#1a1d24"
    _label = "#555555"
else:
    _bg = "#0e1117"
    _panel_bg = "#1a1d24"
    _text = "#fafafa"
    _label = "#888888"

st.markdown(f"""
<style>
  .block-container {{ padding-top: 3rem; padding-bottom: 5rem; }}
  .stButton>button, .stDownloadButton>button {{ height: 56px; }}
  th {{ text-align: left !important; }}
  button[data-baseweb="tab"] {{ font-weight: 600; }}
  .section-header {{
    font-size: 1rem;
    font-weight: 700;
    color: {_label};
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 1.2rem;
    margin-bottom: 0.2rem;
  }}
  .stApp {{ background-color: {_bg}; color: {_text}; }}
  html, body, #root {{ background-color: {_bg}; color: {_text}; }}
  .stDataFrame, [data-testid="stDataFrame"] {{ background-color: {_panel_bg}; }}
  .stTextInput>div>div>input, .stSelectbox>div>div>select {{
    background-color: {_panel_bg}; color: {_text};
  }}
  textarea {{ background-color: {_panel_bg} !important; color: {_text} !important; }}
  .stAlert {{ background-color: {_panel_bg}; }}
  [data-testid="stExpanderToggleIcon"] {{ color: {_text}; }}
  div[data-testid="stMetricValue"] {{ color: {_text}; }}
  div[data-testid="stMetricLabel"] {{ color: {_label}; }}
  p, span, label, div {{ color: {_text}; }}
  .stMarkdown, .stCaption {{ color: {_text}; }}
  /* KJScreener selectbox / popover readability */
  div[data-baseweb="popover"] {{ background-color: {_panel_bg} !important; color: {_text} !important; }}
  div[data-baseweb="popover"] li, div[data-baseweb="popover"] ul,
  div[data-baseweb="menu"] li, div[data-baseweb="menu"] ul,
  ul[role="listbox"] li, [role="listbox"] {{
    background-color: {_panel_bg} !important;
    color: {_text} !important;
  }}
  ul[role="listbox"] li:hover, [role="option"]:hover {{
    background-color: {_bg} !important;
    color: {_text} !important;
  }}
  [data-baseweb="select"] > div {{ background-color: {_panel_bg} !important; color: {_text} !important; }}
  [data-baseweb="select"] span {{ color: {_text} !important; }}
  .stSelectbox label, .stSelectbox div {{ color: {_text} !important; }}
  /* date input popover */
  div[data-baseweb="calendar"], div[data-baseweb="calendar"] * {{
    color: {_text} !important;
  }}

  /* ── Button text/background contrast fix ──────────────────────────────────
     The broad `p, span, label, div {{ color: {_text} }}` rule above also
     recolors the text INSIDE Streamlit's default ("secondary") buttons —
     but those buttons keep Streamlit's native light/white background since
     no .streamlit/config.toml theme is set. Result: near-white text on a
     white button = invisible label until hover/click. Force a background
     on secondary buttons that always matches the label color's theme. */
  button[kind="secondary"], button[kind="secondaryFormSubmit"],
  [data-testid="stBaseButton-secondary"], [data-testid="baseButton-secondary"],
  .stDownloadButton>button, .stButton>button[kind="secondary"] {{
    background-color: {_panel_bg} !important;
    border: 1px solid {_label} !important;
    color: {_text} !important;
  }}
  button[kind="secondary"] p, button[kind="secondary"] span, button[kind="secondary"] div,
  [data-testid="stBaseButton-secondary"] p, [data-testid="stBaseButton-secondary"] span,
  [data-testid="baseButton-secondary"] p, [data-testid="baseButton-secondary"] span,
  .stDownloadButton>button p, .stDownloadButton>button span {{
    color: {_text} !important;
  }}
  /* Primary (red) buttons already have their own background — just make sure
     their label stays white regardless of theme mode. */
  button[kind="primary"] p, button[kind="primary"] span, button[kind="primary"] div,
  [data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primary"] span,
  [data-testid="baseButton-primary"] p, [data-testid="baseButton-primary"] span {{
    color: #ffffff !important;
  }}

  /* st.link_button ("Join WhatsApp Channel" etc.) renders an <a> tag, not a
     <button> — the selectors above never matched it, so it kept the same
     white-text-on-white-background problem in dark mode. */
  [data-testid="stLinkButton"] a, a[kind="secondary"] {{
    background-color: {_panel_bg} !important;
    border: 1px solid {_label} !important;
    color: {_text} !important;
  }}
  [data-testid="stLinkButton"] a p, [data-testid="stLinkButton"] a span,
  [data-testid="stLinkButton"] a div {{
    color: {_text} !important;
  }}

  /* st.toggle (dark/light switch) — force its track/thumb to stay visible
     against the app background in both modes, and make sure its label text
     isn't washed out. */
  [data-testid="stToggle"] label div[data-baseweb="checkbox"] div,
  [data-testid="stCheckbox"] label div[data-baseweb="checkbox"] div {{
    border-color: {_label} !important;
  }}
  [data-testid="stToggle"] p, [data-testid="stToggle"] span {{
    color: {_text} !important;
  }}

</style>
""", unsafe_allow_html=True)

# ── Proxy ─────────────────────────────────────────────────────────────────────
try:
    proxyServer = urllib.request.getproxies()['http']
except KeyError:
    proxyServer = ""

# ── Static file server ────────────────────────────────────────────────────────
def start_static_file_server():
    class ThreadedHTTPServer(TCPServer):
        allow_reuse_address = True

    server = ThreadedHTTPServer(("0.0.0.0", 8000), SimpleHTTPRequestHandler)

    def serve():
        with server:
            server.serve_forever()

    threading.Thread(target=serve, daemon=True).start()
    return server

try:
    staticFileServer = start_static_file_server()
except OSError as e:
    if e.errno not in (98, 10048):
        raise

# ── Update check ──────────────────────────────────────────────────────────────
@st.cache_data(ttl='1h', show_spinner=False)
def check_updates():
    return OTAUpdater.checkForUpdate(proxyServer, VERSION)

isDevVersion, guiUpdateMessage = check_updates()

st.session_state['_app_loaded'] = True
_startup_placeholder.empty()

# ── Result table function ─────────────────────────────────────────────────────
def _style_result_df(df: pd.DataFrame):
    GREEN = 'background-color: #1a4d2e; color: #6fcf97'
    RED = 'background-color: #4d1a1a; color: #eb5757'
    AMBER = 'background-color: #3d3000; color: #f2c94c'
    RESET = ''

    def colour_signal(val):
        v = str(val).lower()
        if any(k in v for k in ('bull', 'buy', 'breakout', 'up', 'strong', 'stage-2', 'above')):
            return GREEN
        if any(k in v for k in ('bear', 'sell', 'breakdown', 'down', 'weak', 'below')):
            return RED
        if any(k in v for k in ('neutral', 'sideways', 'consolidat', 'watch')):
            return AMBER
        return RESET

    signal_cols = [c for c in df.columns if c in (
        'MA-Signal', 'Trend (30Days)', 'Breakout (30Days)', 'Consolidating', 'Pattern'
    )]
    style = df.style
    for col in signal_cols:
        style = style.map(colour_signal, subset=[col])
    return style.set_properties(**{'font-size': '0.85rem'})


def show_df_as_result_table(selected_index="Result", selected_criteria="Screening"):
    try:
        df: pd.DataFrame = pd.read_pickle('last_screened_unformatted_results.pkl')

        ac, cc, bc = st.columns([6, 1, 1])
        ac.markdown(f'#### 🔍 Found **{len(df)}** Results for **{selected_index}** ({selected_criteria})')

        if cc.button('🗑️ Clear Cache', width='stretch', key=random.randint(1, 999_999_999)):
            for p in Path.cwd().glob('stock_data_*.pkl'):
                p.unlink(missing_ok=True)
            st.toast('Stock cache deleted!', icon='🗑️')

        bc.download_button(
            label='⬇️ Export CSV',
            data=df.to_csv().encode('utf-8'),
            file_name=f'KJScreener_{datetime.datetime.now().strftime("%H%M%S_%d%m%Y")}.csv',
            mime='text/csv',
            width='stretch',
        )

        tv_col = 'Chart'
        ticker_opt = st.session_state.get('execute_inputs', [12])[0]
        try:
            if type(ticker_opt) == str or int(ticker_opt) < 15:
                df[tv_col] = [f"https://in.tradingview.com/chart?symbol=NSE%3A{t}" for t in df.index]
            elif str(ticker_opt) == '16':
                try:
                    fetcher = Fetcher.tools(configManager=ConfigManager.tools())
                    url_map = {v: k.replace('^', '').replace('.NS', '')
                               for k, v in fetcher.getAllNiftyIndices().items()}
                    df[tv_col] = [
                        f"https://in.tradingview.com/chart?symbol=NSE%3A{url_map.get(t, t)}"
                        for t in df.index
                    ]
                except Exception:
                    df[tv_col] = [f"https://in.tradingview.com/chart?symbol=NSE%3A{t}" for t in df.index]
            else:
                df[tv_col] = [
                    f"https://in.tradingview.com/chart?symbol={t}" for t in df.index
                ]
        except Exception:
            df[tv_col] = [f"https://in.tradingview.com/chart?symbol=NSE%3A{t}" for t in df.index]

        df.index.name = 'Stock'
        # If the pickled results already contain a literal "Stock" data column
        # (in addition to the index), reset_index() below tries to insert a
        # second "Stock" column and pandas raises "cannot insert Stock,
        # already exists". Drop the stray duplicate first so it never happens.
        if 'Stock' in df.columns:
            df = df.drop(columns=['Stock'])
        df = df.reset_index()

        cols = ['Stock', tv_col] + [c for c in df.columns if c not in ('Stock', tv_col)]
        df = df[cols]

        col_cfg = {
            'Stock': st.column_config.TextColumn('Stock', width='small'),
            tv_col: st.column_config.LinkColumn(
                'Chart', display_text='📈 View', width='small'
            ),
            'LTP': st.column_config.TextColumn('LTP (₹)', width='small'),
            'RSI': st.column_config.TextColumn('RSI', width='small'),
            'Volume': st.column_config.TextColumn('Volume', width='small'),
            'MA-Signal': st.column_config.TextColumn('MA Signal', width='medium'),
            'Breakout (30Days)': st.column_config.TextColumn('Breakout', width='small'),
            'Consolidating': st.column_config.TextColumn('Consolidating', width='small'),
            'Trend (30Days)': st.column_config.TextColumn('Trend', width='medium'),
            'Pattern': st.column_config.TextColumn('Pattern', width='medium'),
        }
        col_cfg = {k: v for k, v in col_cfg.items() if k in df.columns}

        st.dataframe(
            _style_result_df(df),
            width='stretch',
            hide_index=True,
            height=min(48 + len(df) * 36, 640),
            column_config=col_cfg,
        )

    except FileNotFoundError:
        st.info('Run a screen first — results will appear here.', icon='📊')
    except Exception as e:
        st.error(f'Could not load results: {e}')


def on_config_change():
    cm = ConfigManager.tools()
    cm.period = st.session_state.get('cfg_period', cm.period)
    cm.daysToLookback = st.session_state.get('cfg_lookback', cm.daysToLookback)
    cm.duration = st.session_state.get('cfg_duration', cm.duration)
    cm.minLTP = st.session_state.get('cfg_minprice', cm.minLTP)
    cm.maxLTP = st.session_state.get('cfg_maxprice', cm.maxLTP)
    cm.volumeRatio = st.session_state.get('cfg_volratio', cm.volumeRatio)
    cm.consolidationPercentage = st.session_state.get('cfg_consolpct', cm.consolidationPercentage)
    cm.shuffle = st.session_state.get('cfg_shuffle', cm.shuffleEnabled)
    cm.cacheEnabled = st.session_state.get('cfg_cache', cm.cacheEnabled)
    cm.stageTwo = st.session_state.get('cfg_stagetwo', cm.stageTwo)
    cm.useEMA = st.session_state.get('cfg_useema', cm.useEMA)
    data = {
        "period": cm.period,
        "daysToLookback": cm.daysToLookback,
        "duration": cm.duration,
        "minLTP": cm.minLTP,
        "maxLTP": cm.maxLTP,
        "volumeRatio": cm.volumeRatio,
        "consolidationPercentage": cm.consolidationPercentage,
        "shuffleEnabled": cm.shuffleEnabled,
        "cacheEnabled": cm.cacheEnabled,
        "stageTwo": cm.stageTwo,
        "useEMA": cm.useEMA,
    }
    BrowserConfigStore.save_screening_config(data, cm)
    st.toast('Configuration saved!', icon='💾')


_SCREENING_LOCK_FILE = 'kjscreener_running.lock'


import builtins as _builtins

def _noninteractive_input(prompt=''):
    """
    kjscreener's CLI (main()) sometimes prompts interactively, e.g.
    "Do you want to save the results in excel file? [Y/N]:". That works fine
    in bare terminal mode, but when Streamlit calls the same function in the
    background there is no way for the browser to answer that prompt — the
    process just blocks on stdin forever and the GUI spinner never finishes.
    We auto-answer 'N' (don't save/duplicate-save via CLI; the GUI already
    has its own Export CSV button) so the call always returns.
    """
    if isDevVersion is not None:
        st.caption(f'(auto-answered "N" to prompt: {prompt!r})')
    return 'N'


def run_screener_execution(exec_inputs, backtestDate, index_label='', criteria_label=''):
    print(f'[KJScreener] run_screener_execution called with exec_inputs={exec_inputs}', flush=True)

    if isDevVersion is not None:
        st.info(f'Debug inputs: {exec_inputs}')

    if Utility.tools.isBacktesting(backtestDate=backtestDate):
        st.write(f'Running in :red[**Backtesting Mode**] for *T = {backtestDate}* (Y-M-D)')

    # Guard: don't allow a second run to start (and clobber the pkl) while one is in flight.
    # A lock file older than 10 minutes is assumed stale (e.g. leftover from a crashed
    # or force-stopped run) and is cleared automatically instead of blocking forever.
    if os.path.exists(_SCREENING_LOCK_FILE):
        _lock_age = time.time() - os.path.getmtime(_SCREENING_LOCK_FILE)
        if _lock_age > 600:
            print(f'[KJScreener] Stale lock file found ({_lock_age:.0f}s old) — removing it.', flush=True)
            try:
                os.remove(_SCREENING_LOCK_FILE)
            except Exception:
                pass
        else:
            print(f'[KJScreener] Screening already in progress (lock age {_lock_age:.0f}s) — refusing to start.', flush=True)
            st.warning('Ek screening already chal rahi hai — thodi der ruk ke phir try karo.', icon='⏳')
            return

    Path(_SCREENING_LOCK_FILE).touch()
    try:
        if os.path.exists('last_screened_unformatted_results.pkl'):
            try:
                os.remove('last_screened_unformatted_results.pkl')
            except Exception:
                pass

        _orig_input = _builtins.input
        _builtins.input = _noninteractive_input
        try:
            print('[KJScreener] Calling KJScreener_main()...', flush=True)
            KJScreener_main(execute_inputs=exec_inputs, isDevVersion=isDevVersion, backtestDate=backtestDate)
            print('[KJScreener] KJScreener_main() returned normally.', flush=True)
        except StopIteration:
            print('[KJScreener] KJScreener_main() raised StopIteration (expected, ignoring).', flush=True)
        except requests.exceptions.RequestException as _req_e:
            print(f'[KJScreener] RequestException: {_req_e}', flush=True)
            st.error('Failed to reach KJScreener server!')
        except Exception as _run_e:
            import traceback
            print('[KJScreener] UNEXPECTED EXCEPTION in KJScreener_main():', flush=True)
            traceback.print_exc()
            st.error(f'Screening failed: {_run_e}')
        finally:
            _builtins.input = _orig_input

        # Stamp the run's labels onto disk alongside the data, so the header shown
        # after a reload always matches what's actually in the pkl — never stale session_state.
        if os.path.exists('last_screened_unformatted_results.pkl'):
            print('[KJScreener] Results pickle found on disk — success.', flush=True)
            try:
                with open('last_screened_run_meta.txt', 'w') as f:
                    f.write(f'{index_label}|{criteria_label}')
            except Exception:
                pass
        else:
            print('[KJScreener] WARNING: no results pickle found after run — screening produced nothing.', flush=True)
    finally:
        try:
            os.remove(_SCREENING_LOCK_FILE)
        except Exception:
            pass


def get_extra_inputs(tickerOption, executeOption, c_index=None, c_criteria=None):
    exec_inputs = []
    if not str(tickerOption).isnumeric():
        exec_inputs = [tickerOption, 0, 'N']
    elif int(tickerOption) == 0 or tickerOption is None:
        stock_codes = c_index.text_input('Enter Stock Code(s)', placeholder='SBIN, INFY, ITC')
        exec_inputs = [tickerOption, executeOption, stock_codes.upper(), 'N']
    elif int(executeOption) >= 0 and int(executeOption) < 4:
        exec_inputs = [tickerOption, executeOption, 'N']
    elif int(executeOption) == 4:
        num_candles = c_criteria.text_input('Volume lowest since last how many candles?', value='20')
        if num_candles:
            exec_inputs = [tickerOption, executeOption, num_candles, 'N']
        else:
            c_criteria.error("Number of candles can't be blank!")
    elif int(executeOption) == 5:
        min_col, max_col = c_criteria.columns(2)
        min_rsi = min_col.number_input('Min RSI', min_value=0, max_value=100, value=50, step=1)
        max_rsi = max_col.number_input('Max RSI', min_value=0, max_value=100, value=70, step=1)
        if min_rsi >= max_rsi:
            c_criteria.warning('Min RSI must be less than Max RSI')
        else:
            exec_inputs = [tickerOption, executeOption, min_rsi, max_rsi, 'N']
    elif int(executeOption) == 6:
        c1, c2 = c_criteria.columns([7, 2])
        select_reversal = int(c1.selectbox(
            'Select Reversal Type',
            options=[
                '1 > Buy Signal (Bullish Reversal)',
                '2 > Sell Signal (Bearish Reversal)',
                '3 > Momentum Gainers (Rising Bullish Momentum)',
                '4 > Reversal at Moving Average (Bullish Reversal)',
                '5 > Volume Spread Analysis (Bullish VSA Reversal)',
                '6 > Narrow Range (NRx) Reversal',
                '8 > RSI Crossing with 9-SMA of RSI',
            ],
        ).split(' ')[0])
        if select_reversal == 4:
            ma_length = c2.number_input('MA Length', value=44, step=1)
            exec_inputs = [tickerOption, executeOption, select_reversal, ma_length, 'N']
        elif select_reversal == 6:
            nr = c2.number_input('NR(x)', min_value=1, max_value=14, value=4, step=1)
            exec_inputs = [tickerOption, executeOption, select_reversal, nr, 'N']
        else:
            exec_inputs = [tickerOption, executeOption, select_reversal, 'N']
    elif int(executeOption) == 7:
        c1, c2 = c_criteria.columns([11, 4])
        select_pattern = int(c1.selectbox(
            'Select Chart Pattern',
            options=[
                '1 > Bullish Inside Bar (Flag) Pattern',
                '2 > Bearish Inside Bar (Flag) Pattern',
                '3 > Confluence (50 & 200 MA/EMA)',
                '4 > VCP (Experimental)',
                '5 > Buying at Trendline (Swing/Mid/Long term)',
            ],
        ).split(' ')[0])
        if select_pattern in (1, 2):
            num_candles = c2.number_input('Lookback Candles', min_value=1, max_value=25, value=12, step=1)
            exec_inputs = [tickerOption, executeOption, select_pattern, int(num_candles), 'N']
        elif select_pattern == 3:
            confluence_pct = c2.number_input('MA Confluence %', min_value=0.1, max_value=5.0, value=1.0, step=0.1, format="%1.1f") / 100.0
            exec_inputs = [tickerOption, executeOption, select_pattern, confluence_pct, 'N']
        else:
            exec_inputs = [tickerOption, executeOption, select_pattern, 'N']

    st.session_state['execute_inputs'] = exec_inputs


# ══════════════════════════════════════════════════════════════════════════════
# HEADER & WHATSAPP INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════
WA_CHANNEL_URL = "https://whatsapp.com/channel/0029VbDBzHuFSAtDL0vkQQ3Q"

col_title, col_theme, col_wa = st.columns([9, 1, 3])

with col_title:
    st.title('📈 KJScreener')
    if guiUpdateMessage == "":
        st.caption('Open-source & AI-powered & technical screening for NSE stocks.')
    elif isDevVersion:
        st.warning(guiUpdateMessage, icon='⚠️')
    else:
        st.success(guiUpdateMessage, icon='✅')

with col_theme:
    _is_light = st.session_state.get('theme_mode', 'dark') == 'light'
    _toggled = st.toggle('☀️', value=_is_light, key='theme_toggle', help='Switch between dark and light theme')
    _new_mode = 'light' if _toggled else 'dark'
    if _new_mode != st.session_state.get('theme_mode', 'dark'):
        st.session_state['theme_mode'] = _new_mode
        st.rerun()

with col_wa:
    st.markdown("<div style='text-align: right;'>", unsafe_allow_html=True)
    # Direct click button for mobile & desktop users
    st.link_button("💬 Join WhatsApp Channel", WA_CHANNEL_URL, type="secondary")
    # Dynamic QR code generated automatically for scanner users
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=90x90&data={WA_CHANNEL_URL}"
    st.image(qr_url, caption="Scan to Join", width=90)
    st.markdown("</div>", unsafe_allow_html=True)




# ── Multi-source news (yfinance's Yahoo coverage is thin for NSE names) ─────────
@st.cache_data(ttl=300, show_spinner=False)
def _fetch_google_news_rss(query: str, max_items: int = 12):
    """Google News RSS — no API key needed, broad coverage including Indian
    financial press (Moneycontrol, Economic Times, LiveMint, Business
    Standard, etc.) that Yahoo Finance's own news feed often misses for NSE
    stocks. Used as a second source alongside yfinance's native news."""
    try:
        import xml.etree.ElementTree as ET
        import urllib.parse as _up
        q = _up.quote(query)
        url = f'https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en'
        resp = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall('.//item')[:max_items]:
            title = (item.findtext('title') or '').strip()
            link = (item.findtext('link') or '').strip()
            pub_date = (item.findtext('pubDate') or '').strip()
            source_el = item.find('source')
            source = source_el.text.strip() if source_el is not None and source_el.text else 'Google News'
            if title and link:
                items.append({'title': title, 'link': link, 'publisher': source, 'pubDate': pub_date})
        return items
    except Exception:
        return []


# ── Live Ticker Tape ───────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _fetch_ticker_tape():
    """Fetch last prices for major NSE names for the top marquee."""
    symbols = [
        'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
        'BHARTIARTL.NS', 'SBIN.NS', 'LT.NS', 'ITC.NS', 'HINDUNILVR.NS',
        'AXISBANK.NS', 'BAJFINANCE.NS', 'KOTAKBANK.NS', 'MARUTI.NS', 'SUNPHARMA.NS',
        'TITAN.NS', 'NTPC.NS', 'POWERGRID.NS', 'ULTRACEMCO.NS', 'ASIANPAINT.NS',
        'WIPRO.NS', 'ONGC.NS', 'TMPV.NS', 'ADANIENT.NS', 'INDIGO.NS',
    ]
    rows = []
    try:
        import yfinance as yf
        data = yf.download(symbols, period='2d', interval='1d', group_by='ticker',
                           progress=False, threads=True, auto_adjust=True)
        for sym in symbols:
            try:
                short = sym.replace('.NS', '')
                if isinstance(data.columns, pd.MultiIndex):
                    closes = data[sym]['Close'].dropna()
                else:
                    closes = data['Close'].dropna() if 'Close' in data else pd.Series(dtype=float)
                if len(closes) >= 2:
                    last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
                elif len(closes) == 1:
                    last, prev = float(closes.iloc[-1]), float(closes.iloc[-1])
                else:
                    continue
                chg = last - prev
                pct = (chg / prev * 100) if prev else 0.0
                rows.append((short, last, chg, pct))
            except Exception:
                continue
    except Exception:
        pass
    return rows

_tape_rows = _fetch_ticker_tape()
if _tape_rows:
    parts = []
    for short, last, chg, pct in _tape_rows:
        color = '#26a69a' if chg >= 0 else '#ef5350'
        arrow = '▲' if chg >= 0 else '▼'
        parts.append(
            f"<span style='margin:0 1.4rem;white-space:nowrap;'>"
            f"<b style='color:#e0e0e0'>{short}</b> "
            f"<span style='color:#fafafa'>{last:,.2f}</span> "
            f"<span style='color:{color}'>{arrow} {abs(pct):.2f}%</span>"
            f"</span>"
        )
    tape_html = (
        "<div style='overflow:hidden;background:#161b22;border:1px solid #30363d;"
        "border-radius:8px;padding:0.55rem 0;margin:0.4rem 0 0.8rem 0;'>"
        "<div style='display:inline-block;white-space:nowrap;"
        "animation:kjs-ticker 45s linear infinite;'>"
        + "".join(parts + parts)  # duplicate for seamless loop
        + "</div></div>"
        "<style>"
        "@keyframes kjs-ticker { from { transform: translateX(0); } to { transform: translateX(-50%); } }"
        "</style>"
    )
    st.markdown(tape_html, unsafe_allow_html=True)


def gap_predict(index_choice: str, col, custom_symbol: str = None):
    """
    AI/statistical Gap Up-Gap Down prediction for next trading day.
    NIFTY 50 uses the real trained ML model (dense NN ported from Screeni-py,
    trained on Nifty/Gold/Crude daily % change). BANK NIFTY, SENSEX, and any
    custom stock symbol have no bundled trained model, so they use a
    transparent statistical heuristic (recent momentum + historical gap
    base-rate) — clearly labeled as such, never presented as the same ML
    prediction.
    """
    import classes.Fetcher as Fetcher
    import classes.Screener as Screener
    label = custom_symbol.strip().upper() if index_choice == 'CUSTOM STOCK' and custom_symbol else index_choice
    with col.container():
        with st.spinner(f'🔮 Taking a look into the future for {label}, please wait...'):
            configManager = ConfigManager.tools()
            fetcher = Fetcher.tools(configManager)
            screener = Screener.tools(configManager)
            try:
                if index_choice == 'NIFTY 50':
                    data = fetcher.fetchLatestNiftyDaily(proxyServer=proxyServer)
                    prediction, trend, confidence, data_used = screener.getNiftyPrediction(
                        data=data, proxyServer=proxyServer,
                    )
                    is_ml = True
                elif index_choice == 'BANK NIFTY':
                    data = fetcher.fetchLatestBankNiftyDaily(proxyServer=proxyServer)
                    trend, confidence, data_used = screener.getIndexGapHeuristic('BANK NIFTY', data)
                    is_ml = False
                elif index_choice == 'SENSEX':
                    data = fetcher.fetchLatestSensexDaily(proxyServer=proxyServer)
                    trend, confidence, data_used = screener.getIndexGapHeuristic('SENSEX', data)
                    is_ml = False
                else:  # CUSTOM STOCK
                    if not custom_symbol or not custom_symbol.strip():
                        col.warning('Type an NSE stock symbol (e.g. RELIANCE, TCS, INFY) first.', icon='⚠️')
                        return
                    data = fetcher.fetchLatestStockDaily(custom_symbol, proxyServer=proxyServer)
                    trend, confidence, data_used = screener.getIndexGapHeuristic(label, data)
                    is_ml = False
            except Exception as _gap_e:
                col.error(f'😾 Could not fetch/predict for {label}: {_gap_e}')
                return

    if 'BULLISH' in trend:
        col.success(f'{label} may Open **Gap Up** next day!\n\nProbability/Strength of Prediction = {confidence}%', icon='📈')
    elif 'BEARISH' in trend:
        col.error(f'{label} may Open **Gap Down** next day!\n\nProbability/Strength of Prediction = {confidence}%', icon='📉')
    else:
        col.info(f"Couldn't determine the trend for {label}. Try again later!")
    col.warning('This prediction should be read After 3 PM or Around the Closing hours as its accuracy is based on the closing price!\n\nThis is Just a Statistical Prediction and There are Chances of **False** Predictions!', icon='⚠️')
    if is_ml:
        col.info("**Method:** Trained ML model (dense neural net) using NIFTY, Crude and Gold historical prices.", icon='🧠')
    else:
        col.info(f"**Method:** Statistical heuristic (recent momentum + historical gap base-rate) — {label} has no bundled trained ML model like NIFTY 50 does, so this is not the same neural-net prediction.", icon='📐')
    col.markdown("**Following data is used to make the above prediction:**")
    col.dataframe(data_used, width='stretch')


tab_screen, tab_ai, tab_gap, tab_optchain, tab_ledger, tab_config, tab_psc, tab_opt, tab_blog, tab_about = st.tabs([
    '📊 Classic Screen',
    '🤖 AI Native',
    '🔮 Gap Prediction',
    '⛓️ Option Chain',
    '📒 LedgerLens',
    '⚙️ Configuration',
    '💸 Position Size Calculator',
    '🧮 Options Calculator',
    '📝 Blog',
    'ℹ️ About',
])

# ── Classic Screen ─────────────────────────────────────────────────────────────
with tab_screen:
    list_index = [
        'All Stocks (Default)',
        '0 > By Stock Names (NSE Stock Code)',
        '1 > Nifty 50',
        '2 > Nifty Next 50',
        '3 > Nifty 100',
        '4 > Nifty 200',
        '5 > Nifty 500',
        '6 > Nifty Smallcap 50',
        '7 > Nifty Smallcap 100',
        '8 > Nifty Smallcap 250',
        '9 > Nifty Midcap 50',
        '10 > Nifty Midcap 100',
        '11 > Nifty Midcap 150',
        '13 > Newly Listed (IPOs in last 2 Years)',
        '14 > F&O Stocks Only',
        '15 > US S&P 500',
        '16 > Sectoral Indices (NSE)',
    ]

    list_criteria = [
        '0 > Full Screening (All Technical Parameters)',
        '1 > Breakout or Consolidation',
        '2 > Recent Breakout with Volume',
        '3 > Consolidating Stocks',
        '4 > Lowest Volume in last N Days (Early Breakout Detection)',
        '5 > RSI Range Filter',
        '6 > Reversal Signals',
        '7 > Chart Patterns',
    ]

    configManager = ConfigManager.tools()
    configManager.getConfig(parser=ConfigManager.parser)

    c_index, c_datepick, c_criteria, c_btn = st.columns((2, 1, 4, 1))

    selected_index_raw = c_index.selectbox('Index', options=list_index)
    tickerOption = selected_index_raw.split(' ')[0]
    tickerOption = str(12 if '>' not in selected_index_raw else int(tickerOption) if tickerOption.isnumeric() else str(tickerOption))

    picked_date = c_datepick.date_input('Screen / Backtest For', max_value=datetime.date.today(), value=datetime.date.today())
    backtestDate = picked_date

    selected_criteria_raw = c_criteria.selectbox('Screening Criteria', options=list_criteria)
    executeOption = str(selected_criteria_raw.split(' ')[0])

    get_extra_inputs(tickerOption=tickerOption, executeOption=executeOption, c_index=c_index, c_criteria=c_criteria)

    start_button = c_btn.button('▶ Start', type='primary', key='start_button', width='stretch')

    if start_button:
        exec_inputs = st.session_state.get('execute_inputs', [])
        if int(tickerOption) == 0 and len(exec_inputs) > 2 and not exec_inputs[2].strip():
            st.warning('Please enter at least one stock code before starting.', icon='⚠️')
        else:
            with st.spinner("🔍 Screening stocks... Please wait!"):
                run_screener_execution(
                    exec_inputs, backtestDate,
                    index_label=selected_index_raw,
                    criteria_label=selected_criteria_raw,
                )
            st.rerun()

    with st.container():
        # Read the labels for the CURRENTLY SAVED pkl from disk, not from session_state.
        # session_state resets on browser reload, but the meta file always matches the
        # actual data on disk — so the header can never show a mismatched label again.
        show_idx, show_crit = selected_index_raw, selected_criteria_raw
        if os.path.exists('last_screened_run_meta.txt'):
            try:
                with open('last_screened_run_meta.txt') as f:
                    _saved_idx, _saved_crit = f.read().split('|', 1)
                show_idx, show_crit = _saved_idx, _saved_crit
            except Exception:
                pass
        show_df_as_result_table(selected_index=show_idx, selected_criteria=show_crit)

# ── AI Native ──────────────────────────────────────────────────────────────────
with tab_ai:
    try:
        import sys as _sys
        _src = os.path.dirname(os.path.abspath(__file__))
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        from ui.ai_native_tab import render as render_ai
        render_ai()
    except Exception as _ai_e:
        st.error(f'AI Native tab failed to load: {_ai_e}')

# ── Gap Prediction ────────────────────────────────────────────────────────────
with tab_gap:
    ac, bc = st.columns([2, 1])
    ac.subheader('🧠 AI-based prediction for Next Day Gap Up / Gap Down')
    _gap_index = bc.selectbox(
        'Index', ['NIFTY 50', 'BANK NIFTY', 'SENSEX', 'CUSTOM STOCK'],
        key='gap_index_select', label_visibility='collapsed',
    )
    _gap_custom_symbol = None
    if _gap_index == 'CUSTOM STOCK':
        _gap_custom_symbol = bc.text_input(
            'NSE Symbol', placeholder='e.g. RELIANCE, TCS, INFY',
            key='gap_custom_symbol', label_visibility='collapsed',
        )
    bc.button('**Predict**', type='primary', key='gap_predict_btn',
              on_click=gap_predict, args=(_gap_index, ac, _gap_custom_symbol),
              use_container_width=True)

# ── Option Chain ───────────────────────────────────────────────────────────────
with tab_optchain:
    try:
        import sys as _sys
        _src = os.path.dirname(os.path.abspath(__file__))
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        from ui.option_chain_tab import render as render_option_chain
        render_option_chain()
    except Exception as _oc_e:
        st.error(f'Option Chain tab failed to load: {_oc_e}')

# ── Configuration ──────────────────────────────────────────────────────────────
with tab_config:
    configManager = ConfigManager.tools()
    configManager.getConfig(parser=ConfigManager.parser)
    _sc = BrowserConfigStore.load_screening_config(configManager)

    hdr_col, exp_col = st.columns([10, 2])
    hdr_col.markdown('## ⚙️ Configuration')

    _export_data = {
        "period": st.session_state.get('cfg_period', _sc.get('period', configManager.period)),
        "daysToLookback": st.session_state.get('cfg_lookback', _sc.get('daysToLookback', configManager.daysToLookback)),
        "duration": st.session_state.get('cfg_duration', _sc.get('duration', configManager.duration)),
        "minLTP": st.session_state.get('cfg_minprice', _sc.get('minLTP', configManager.minLTP)),
        "maxLTP": st.session_state.get('cfg_maxprice', _sc.get('maxLTP', configManager.maxLTP)),
        "volumeRatio": st.session_state.get('cfg_volratio', _sc.get('volumeRatio', configManager.volumeRatio)),
        "consolidationPercentage": st.session_state.get('cfg_consolpct', _sc.get('consolidationPercentage', configManager.consolidationPercentage)),
        "shuffleEnabled": st.session_state.get('cfg_shuffle', _sc.get('shuffleEnabled', configManager.shuffleEnabled)),
        "cacheEnabled": st.session_state.get('cfg_cache', _sc.get('cacheEnabled', configManager.cacheEnabled)),
        "stageTwo": st.session_state.get('cfg_stagetwo', _sc.get('stageTwo', configManager.stageTwo)),
        "useEMA": st.session_state.get('cfg_useema', _sc.get('useEMA', configManager.useEMA)),
    }
    exp_col.download_button(
        label='⬇️ Export Config',
        data=json.dumps(_export_data, indent=2),
        file_name=f'kjscreener_config_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
        mime='application/json',
        width='stretch',
    )

    st.markdown('<p class="section-header">Screening Settings</p>', unsafe_allow_html=True)
    st.divider()

    period_options = ['15d', '60d', '300d', '52wk', '3y', '5y', 'max']
    duration_options = ['5m', '15m', '1h', '4h', '1d', '1wk']

    _sc_period = _sc.get('period', configManager.period)
    _sc_duration = _sc.get('duration', configManager.duration)
    _period_idx = period_options.index(_sc_period) if _sc_period in period_options else 2
    _duration_idx = duration_options.index(_sc_duration) if _sc_duration in duration_options else 4

    c1, c2, c3 = st.columns(3)
    period = c1.selectbox('Period', options=period_options, index=_period_idx, key='cfg_period')
    daystolookback = c2.number_input('Lookback Candles', value=int(_sc.get('daysToLookback', configManager.daysToLookback)), step=1, key='cfg_lookback')
    duration = c3.selectbox('Candle Duration', options=duration_options, index=_duration_idx, key='cfg_duration')

    c1, c2 = st.columns(2)
    c1.number_input('Min Price (₹)', value=float(_sc.get('minLTP', configManager.minLTP)), step=0.1, key='cfg_minprice')
    c2.number_input('Max Price (₹)', value=float(_sc.get('maxLTP', configManager.maxLTP)), step=0.1, key='cfg_maxprice')

    c1, c2 = st.columns(2)
    c1.number_input('Volume Multiplier', value=float(_sc.get('volumeRatio', configManager.volumeRatio)), step=0.1, key='cfg_volratio')
    c2.number_input('Consolidation Range (%)', value=int(_sc.get('consolidationPercentage', configManager.consolidationPercentage)), step=1, key='cfg_consolpct')

    c1, c2, c3, c4 = st.columns(4)
    c1.checkbox('Shuffle stocks', value=bool(_sc.get('shuffleEnabled', configManager.shuffleEnabled)), key='cfg_shuffle')
    c2.checkbox('Cache stock data', value=bool(_sc.get('cacheEnabled', configManager.cacheEnabled)), key='cfg_cache')
    c3.checkbox('Stage-2 stocks only', value=bool(_sc.get('stageTwo', configManager.stageTwo)), key='cfg_stagetwo',
                help='Screen only for Stage-2 stocks (see Weinstein stage analysis).')
    c4.checkbox('Use EMA (instead of SMA)', value=bool(_sc.get('useEMA', configManager.useEMA)), key='cfg_useema',
                help='EMA suits short-term trades; SMA suits mid/long-term trades.')

    st.button('💾 Save Screening Configuration', on_click=on_config_change, type='primary', width='stretch')

    st.markdown('<p class="section-header">Import Configuration</p>', unsafe_allow_html=True)
    st.divider()

    _imported_file = st.file_uploader('Upload a previously exported config JSON', type=['json'], key='cfg_import_uploader')
    if _imported_file is not None:
        try:
            _imported_data = json.loads(_imported_file.read().decode('utf-8'))
            if st.button('📥 Apply Imported Config', type='secondary', key='cfg_apply_import'):
                BrowserConfigStore.save_screening_config(_imported_data, configManager)
                st.toast('Configuration imported!', icon='📥')
                st.rerun()
        except Exception as _imp_e:
            st.error(f'Invalid config file: {_imp_e}')

    st.markdown('<p class="section-header">LLM Configuration (AI Native Tab)</p>', unsafe_allow_html=True)
    st.divider()
    st.caption('Config saved to browser localStorage (primary) and KJScreener.yaml (CLI fallback). API key is session-only unless you enable "Remember API key" below.')

    _llm_cfg = BrowserConfigStore.load_llm_config()
    _provider_options = ['openai', 'anthropic', 'openai-compatible']

    # Seed widget keys ONLY if missing — never assign after widgets exist
    if 'ai_provider' not in st.session_state:
        _p = _llm_cfg.get('provider', 'openai-compatible')
        st.session_state['ai_provider'] = _p if _p in _provider_options else 'openai-compatible'
    if 'ai_model' not in st.session_state:
        st.session_state['ai_model'] = _llm_cfg.get('model', 'openai/gpt-oss-120b')
    if 'ai_base_url' not in st.session_state:
        st.session_state['ai_base_url'] = _llm_cfg.get('base_url') or 'https://api.groq.com/openai/v1'
    if 'ai_api_key' not in st.session_state:
        _k = ''
        if _llm_cfg.get('remember_api_key') and _llm_cfg.get('api_key'):
            _k = _llm_cfg.get('api_key') or ''
        if not _k:
            _k = (
                os.environ.get('KJScreener_API_KEY', '')
                or os.environ.get('GROQ_API_KEY', '')
                or os.environ.get('OPENAI_API_KEY', '')
            )
        st.session_state['ai_api_key'] = _k
    if 'ai_remember_key' not in st.session_state:
        st.session_state['ai_remember_key'] = bool(_llm_cfg.get('remember_api_key', False))

    lc1, lc2 = st.columns(2)
    # key= only — no index=/value= (avoids Streamlit session_state conflicts)
    llm_provider = lc1.selectbox(
        'Provider', options=_provider_options, key='ai_provider',
        help='Which LLM API to call for the AI Native tab.',
    )
    llm_model = lc2.text_input(
        'Model', key='ai_model',
        help='Model name/ID for the chosen provider, e.g. openai/gpt-oss-120b, gpt-4o.',
    )

    if llm_provider == 'openai-compatible':
        llm_base_url = st.text_input(
            'Base URL', key='ai_base_url',
            help='Endpoint for an OpenAI-compatible server, e.g. https://api.groq.com/openai/v1',
        )
    else:
        llm_base_url = st.session_state.get('ai_base_url', '')

    llm_api_key = st.text_input(
        'API Key', key='ai_api_key', type='password',
        help='Not stored on disk unless "Remember API key" is checked.',
    )

    remember_key = st.checkbox(
        'Remember API key on this device (stored in browser localStorage — only enable on trusted devices)',
        key='ai_remember_key',
    )

    if not st.session_state.get('ai_api_key'):
        st.warning('No API key set. The AI Native tab will not be able to run agents.', icon='⚠️')

    if st.button('💾 Save LLM Config', type='primary', key='cfg_save_llm'):
        # Widgets already own session_state for these keys — only persist to storage
        BrowserConfigStore.save_llm_config(
            {
                'provider': llm_provider,
                'model': llm_model,
                'base_url': llm_base_url if llm_provider == 'openai-compatible' else '',
                'api_key': llm_api_key,
            },
            remember_api_key=bool(remember_key),
        )
        st.session_state['_ai_creds_retries'] = 0
        st.toast('LLM configuration saved!', icon='💾')

    st.markdown('<p class="section-header">Agent Personas</p>', unsafe_allow_html=True)
    st.divider()
    st.caption('Create, edit, or delete AI agent personas. Tool selection updates the YAML automatically.')

    try:
        import sys as _sys2
        _src2 = os.path.dirname(os.path.abspath(__file__))
        if _src2 not in _sys2.path:
            _sys2.path.insert(0, _src2)
        from agents.agent_loader import AgentLoader
        from agents.screener_tools import ALL_TOOLS as _ALL_TOOL_FNS
        _persona_loader = AgentLoader()
        _personas = _persona_loader.load_all()
        _persona_names = [p.get('name', 'Unknown') for p in _personas]
        _all_tool_names = [fn.__name__ for fn in _ALL_TOOL_FNS]
        _persona_load_error = None
    except Exception as _pl_e:
        _persona_loader = None
        _personas = []
        _persona_names = []
        _all_tool_names = [
            'screen_breakout', 'screen_volume_breakout', 'screen_consolidation',
            'screen_rsi', 'screen_reversal', 'screen_chart_patterns', 'screen_vcp',
            'screen_lorentzian', 'screen_momentum', 'screen_narrow_range',
            'screen_ipo_base', 'screen_confluence', 'screen_ma_reversal', 'screen_rsi_ma_cross',
        ]
        _persona_load_error = _pl_e

    if _persona_load_error:
        st.warning(f'Could not load personas module: {_persona_load_error}', icon='⚠️')

    if 'persona_select' not in st.session_state:
        st.session_state['persona_select'] = '+ New Persona'

    if st.session_state.pop('_persona_reset_pending', False):
        st.session_state['persona_select'] = '+ New Persona'

    _select_options = ['+ New Persona'] + _persona_names
    if st.session_state['persona_select'] not in _select_options:
        st.session_state['persona_select'] = '+ New Persona'

    _selected_persona_name = st.selectbox('Select Persona to Edit', options=_select_options, key='persona_select')

    _editing_existing = _selected_persona_name != '+ New Persona'
    _current_persona = next((p for p in _personas if p.get('name') == _selected_persona_name), None) if _editing_existing else None

    _index_options = [
        'Nifty 50', 'Nifty Next 50', 'Nifty 100', 'Nifty 200', 'Nifty 500',
        'Nifty Smallcap 50', 'Nifty Smallcap 100', 'Nifty Smallcap 250',
        'Nifty Midcap 50', 'Nifty Midcap 100', 'Nifty Midcap 150',
        'F&O Stocks Only', 'All Stocks',
    ]

    def _slugify_persona_name(name: str) -> str:
        import re as _re3
        s = _re3.sub(r'(?<!^)(?=[A-Z])', '_', (name or '').strip())
        s = _re3.sub(r'[^a-zA-Z0-9]+', '_', s)
        return s.lower().strip('_') or 'persona'

    pc1, pc2 = st.columns(2)
    with pc1:
        persona_name = st.text_input(
            'Persona Name',
            value=_current_persona.get('name', '') if _current_persona else '',
            placeholder='MyPersona', key=f'persona_name_{_selected_persona_name}',
        )
        persona_desc = st.text_input(
            'Description',
            value=_current_persona.get('description', '') if _current_persona else '',
            placeholder='Describe what this persona does', key=f'persona_desc_{_selected_persona_name}',
        )
        _cur_index = _current_persona.get('index', 'Nifty 500') if _current_persona else 'Nifty 500'
        _index_idx = _index_options.index(_cur_index) if _cur_index in _index_options else 4
        persona_index = st.selectbox('Default Index', options=_index_options, index=_index_idx, key=f'persona_index_{_selected_persona_name}')
    with pc2:
        persona_instructions = st.text_area(
            'Instructions',
            value=_current_persona.get('instructions', '') if _current_persona else '',
            placeholder='You are a ... analyst. Screen for ...',
            height=180, key=f'persona_instr_{_selected_persona_name}',
            help='Full system prompt for this agent persona.',
        )

    _current_tools = _current_persona.get('tools', []) if _current_persona else []
    persona_tools = st.multiselect(
        'Allowed Tools', options=_all_tool_names,
        default=[t for t in _current_tools if t in _all_tool_names],
        key=f'persona_tools_{_selected_persona_name}',
        help='Which screener functions this agent is allowed to call.',
    )

    _preview_data = {
        'name': persona_name or 'MyPersona',
        'description': persona_desc or '',
        'instructions': persona_instructions or '',
        'tools': persona_tools,
        'index': persona_index,
    }
    with st.expander('Preview YAML', expanded=False):
        st.code(yaml.dump(_preview_data, default_flow_style=False, allow_unicode=True, sort_keys=False), language='yaml')

    pb1, pb2 = st.columns([3, 1])
    _save_label = '💾 Save New Persona' if not _editing_existing else '💾 Save Persona'
    if pb1.button(_save_label, type='primary', key='persona_save_btn', width='stretch'):
        if not persona_name.strip():
            st.error('Persona Name is required.')
        elif _persona_loader is None:
            st.error('Personas module not available.')
        else:
            _filename = _slugify_persona_name(persona_name) + '.yaml'
            os.makedirs(_persona_loader.personas_dir, exist_ok=True)
            _filepath = os.path.join(_persona_loader.personas_dir, _filename)
            # If renaming an existing persona, remove the old file first
            if _editing_existing and _current_persona:
                _old_path = os.path.join(
                    _persona_loader.personas_dir,
                    _slugify_persona_name(_current_persona.get('name', _selected_persona_name)) + '.yaml',
                )
                if _old_path != _filepath and os.path.exists(_old_path):
                    os.remove(_old_path)
            with open(_filepath, 'w') as _f:
                yaml.dump(_preview_data, _f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            st.toast(f'Persona "{persona_name}" saved!', icon='💾')
            st.session_state['_persona_reset_pending'] = True
            st.rerun()

    if _editing_existing:
        if pb2.button('🗑️ Delete', key='persona_delete_btn', width='stretch'):
            if _persona_loader is not None and _current_persona:
                _del_path = os.path.join(
                    _persona_loader.personas_dir,
                    _slugify_persona_name(_current_persona.get('name', _selected_persona_name)) + '.yaml',
                )
                if os.path.exists(_del_path):
                    os.remove(_del_path)
                st.toast(f'Persona "{_selected_persona_name}" deleted.', icon='🗑️')
            st.session_state['_persona_reset_pending'] = True
            st.rerun()

    st.markdown('<p class="section-header">Reset</p>', unsafe_allow_html=True)
    st.divider()

    with st.expander('🗑️ Reset All Settings', expanded=False):
        st.warning('Ye tumhare saare saved settings (screening config + LLM config) hata dega.', icon='⚠️')
        if st.button('Confirm Reset All Settings', type='primary', key='cfg_reset_all'):
            BrowserConfigStore.clear_all()
            st.toast('All settings reset!', icon='🗑️')
            st.rerun()

# ── Position Size Calculator ───────────────────────────────────────────────────
with tab_psc:
    left_col, result_col = st.columns([1, 1])
    with left_col:
        st.markdown('## 💸 Position Size Calculator')
        st.caption('Formula: Quantity = floor( (Capital × Risk%) / Stoploss points )')
        capital = st.number_input('Capital Size (₹)', min_value=0, value=100000, key='psc_capital')
        risk = st.number_input('Risk on Capital (%)', min_value=0.0, max_value=10.0, step=0.1, value=0.5, key='psc_risk')
        risk_rs = capital * (risk / 100.0)
        st.caption(f'Risk amount: **₹{risk_rs:,.2f}**')
        sl = st.number_input('Stoploss in Points (₹)', min_value=0.0, step=0.1, key='psc_sl')
        entry = st.number_input('Entry Price (₹) — optional', min_value=0.0, step=0.05, value=0.0, key='psc_entry',
                               help='Agar entry doge to position value bhi dikhega')
        calc_btn = st.button('📐 Calculate Quantity', type='primary', width='stretch', key='psc_calc')

    with result_col:
        st.markdown('## Result')
        st.divider()
        if calc_btn:
            if sl > 0:
                qty = floor(risk_rs / sl)
                max_loss = qty * sl
                r1, r2 = st.columns(2)
                r1.metric('Quantity', f'{qty:,}')
                r2.metric('Max Loss', f'₹{max_loss:,.0f}', delta_color='inverse')
                if entry and entry > 0:
                    pos_val = qty * entry
                    r3, r4 = st.columns(2)
                    r3.metric('Position Value', f'₹{pos_val:,.0f}')
                    r4.metric('Risk : Capital', f'{(max_loss / capital * 100) if capital else 0:.2f}%')
                st.caption(f'Risk ₹{risk_rs:,.2f} ÷ SL ₹{sl:.2f} = **{qty}** shares')
            else:
                st.warning('Stoploss in Points 0 se zyada honi chahiye.', icon='⚠️')

# ── Options Calculator ──────────────────────────────────────────────────────────
with tab_opt:
    st.markdown('## 🧮 Options Calculator')

    def _norm_cdf(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _norm_pdf(x):
        return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

    def _black_scholes(spot, strike, days, iv_pct, rate_pct, opt_type):
        T = max(days, 0) / 365.0
        sigma = iv_pct / 100.0
        r = rate_pct / 100.0
        if T <= 0 or sigma <= 0 or spot <= 0 or strike <= 0:
            return None
        d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        pdf_d1 = _norm_pdf(d1)
        if opt_type == 'Call':
            price = spot * _norm_cdf(d1) - strike * math.exp(-r * T) * _norm_cdf(d2)
            delta = _norm_cdf(d1)
            theta = (-(spot * sigma * pdf_d1) / (2 * math.sqrt(T))
                     - r * strike * math.exp(-r * T) * _norm_cdf(d2)) / 365
            rho = (strike * T * math.exp(-r * T) * _norm_cdf(d2)) / 100
        else:
            price = strike * math.exp(-r * T) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
            delta = _norm_cdf(d1) - 1
            theta = (-(spot * sigma * pdf_d1) / (2 * math.sqrt(T))
                     + r * strike * math.exp(-r * T) * _norm_cdf(-d2)) / 365
            rho = (-strike * T * math.exp(-r * T) * _norm_cdf(-d2)) / 100
        gamma = pdf_d1 / (spot * sigma * math.sqrt(T))
        vega = (spot * pdf_d1 * math.sqrt(T)) / 100
        return {'price': price, 'delta': delta, 'gamma': gamma, 'theta': theta, 'vega': vega, 'rho': rho}

    sub_premium, sub_payoff, sub_margin = st.tabs(['💰 Premium & Greeks', '📈 Payoff', '🛡️ Margin (Approx)'])

    # -- Premium & Greeks (Black-Scholes) --------------------------------------
    with sub_premium:
        st.caption('Black-Scholes model — European style, theoretical estimate. Actual market premium may differ due to liquidity, skew, and American-style early exercise (stock options).')
        p1, p2, p3 = st.columns(3)
        opt_type = p1.selectbox('Option Type', options=['Call', 'Put'], key='bs_type')
        spot = p2.number_input('Spot Price (₹)', min_value=0.0, value=24250.0, step=0.5, key='bs_spot')
        strike = p3.number_input('Strike Price (₹)', min_value=0.0, value=24300.0, step=0.5, key='bs_strike')

        p4, p5, p6 = st.columns(3)
        days = p4.number_input('Days to Expiry', min_value=0, value=7, step=1, key='bs_days')
        iv = p5.number_input('Implied Volatility (%)', min_value=0.0, value=13.0, step=0.5, key='bs_iv')
        rate = p6.number_input('Risk-free Rate (%)', min_value=0.0, value=6.5, step=0.1, key='bs_rate')

        if st.button('📐 Calculate Premium & Greeks', type='primary', width='stretch', key='bs_calc'):
            res = _black_scholes(spot, strike, days, iv, rate, opt_type)
            if res is None:
                st.warning('Spot, Strike, IV aur Days sab 0 se zyada hone chahiye.', icon='⚠️')
            else:
                st.divider()
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric('Theoretical Price', f"₹{res['price']:.2f}")
                m2.metric('Delta', f"{res['delta']:.4f}")
                m3.metric('Gamma', f"{res['gamma']:.4f}")
                m4.metric('Theta/day', f"₹{res['theta']:.2f}")
                m5.metric('Vega (per 1% IV)', f"₹{res['vega']:.2f}")
                m6.metric('Rho (per 1% rate)', f"₹{res['rho']:.2f}")

    # -- Payoff Calculator -------------------------------------------------------
    with sub_payoff:
        st.caption('Ek ya multiple legs daal ke combined strategy ka Profit/Loss payoff dekho expiry par.')
        num_legs = st.number_input('Number of Legs', min_value=1, max_value=4, value=1, step=1, key='payoff_legs')

        legs = []
        for i in range(int(num_legs)):
            st.markdown(f'**Leg {i + 1}**')
            c1, c2, c3, c4, c5 = st.columns(5)
            action = c1.selectbox('Action', options=['Buy', 'Sell'], key=f'pf_action_{i}')
            otype = c2.selectbox('Type', options=['Call', 'Put'], key=f'pf_type_{i}')
            strike_l = c3.number_input('Strike (₹)', min_value=0.0, value=24300.0, step=0.5, key=f'pf_strike_{i}')
            premium_l = c4.number_input('Premium (₹)', min_value=0.0, value=100.0, step=0.5, key=f'pf_premium_{i}')
            lot_l = c5.number_input('Qty (Lot Size)', min_value=1, value=75, step=1, key=f'pf_lot_{i}')
            legs.append((action, otype, strike_l, premium_l, lot_l))

        spot_ref = st.number_input('Current Spot Price (₹) — for chart range', min_value=0.0, value=24250.0, step=0.5, key='pf_spot')

        if st.button('📊 Plot Payoff', type='primary', width='stretch', key='pf_calc'):
            lo = max(spot_ref * 0.85, 1)
            hi = spot_ref * 1.15
            spot_range = [lo + (hi - lo) * i / 200 for i in range(201)]
            net_payoff = []
            for s in spot_range:
                total = 0.0
                for action, otype, k, prem, lot in legs:
                    intrinsic = max(s - k, 0) if otype == 'Call' else max(k - s, 0)
                    leg_pl = (intrinsic - prem) if action == 'Buy' else (prem - intrinsic)
                    total += leg_pl * lot
                net_payoff.append(total)

            payoff_df = pd.DataFrame({'Spot Price': spot_range, 'P&L (₹)': net_payoff}).set_index('Spot Price')
            st.line_chart(payoff_df, height=380)

            breakevens = []
            for i in range(len(net_payoff) - 1):
                if net_payoff[i] == 0 or (net_payoff[i] < 0) != (net_payoff[i + 1] < 0):
                    breakevens.append(spot_range[i])
            max_profit = max(net_payoff)
            max_loss = min(net_payoff)
            b1, b2, b3 = st.columns(3)
            b1.metric('Max Profit (in range)', f"₹{max_profit:,.0f}")
            b2.metric('Max Loss (in range)', f"₹{max_loss:,.0f}")
            b3.metric('Approx Breakeven(s)', ', '.join(f'{b:.0f}' for b in breakevens[:3]) if breakevens else '—')

    # -- Margin Calculator (approximate) -----------------------------------------
    with sub_margin:
        st.warning('Ye sirf rough estimate hai (SPAN + Exposure ka simplified approximation, VIX-based heuristic). Actual margin apne broker ke margin calculator se hi confirm karo.', icon='⚠️')
        n1, n2, n3 = st.columns(3)
        position = n1.selectbox('Position', options=['Sell (Short)', 'Buy (Long)'], key='mg_position')
        spot_m = n2.number_input('Spot Price (₹)', min_value=0.0, value=24250.0, step=0.5, key='mg_spot')
        lot_m = n3.number_input('Lot Size', min_value=1, value=65, step=1, key='mg_lot')

        premium_m = st.number_input('Premium (₹)', min_value=0.0, value=100.0, step=0.5, key='mg_premium')

        auto_pct = st.checkbox('India VIX se SPAN% / Exposure% automatic calculate karo', value=True, key='mg_auto')

        if auto_pct:
            vix = st.number_input(
                'India VIX (current value)', min_value=5.0, max_value=60.0, value=12.5, step=0.1, key='mg_vix',
                help='Apne broker/NSE se current India VIX dekh ke daal do — jitna volatility zyada, utna margin zyada.'
            )
            # Heuristic: real NSE SPAN for near-month Nifty options tracks roughly
            # 0.7-0.8x of India VIX, clamped to the typical observed 6%-20% band.
            span_pct = max(6.0, min(0.75 * vix, 20.0))
            # SEBI mandates a minimum 3% exposure margin for index options; it rises
            # mildly with volatility too.
            exposure_pct = max(3.0, min(0.12 * vix, 6.0))
            v1, v2 = st.columns(2)
            v1.metric('Auto SPAN %', f'{span_pct:.2f}%')
            v2.metric('Auto Exposure %', f'{exposure_pct:.2f}%')
        else:
            n5, n6 = st.columns(2)
            span_pct = n5.number_input('SPAN Margin (%)', min_value=0.0, value=10.0, step=0.5, key='mg_span')
            exposure_pct = n6.number_input('Exposure Margin (%)', min_value=0.0, value=3.0, step=0.5, key='mg_exposure')

        if st.button('🛡️ Calculate Margin', type='primary', width='stretch', key='mg_calc'):
            contract_value = spot_m * lot_m
            if position == 'Buy (Long)':
                margin_required = premium_m * lot_m
                st.metric('Margin Required (Premium Paid)', f"₹{margin_required:,.0f}")
            else:
                span_amt = contract_value * (span_pct / 100)
                exposure_amt = contract_value * (exposure_pct / 100)
                margin_required = span_amt + exposure_amt
                mm1, mm2, mm3 = st.columns(3)
                mm1.metric('SPAN Margin', f"₹{span_amt:,.0f}")
                mm2.metric('Exposure Margin', f"₹{exposure_amt:,.0f}")
                mm3.metric('Total Margin (Approx)', f"₹{margin_required:,.0f}")


# ── LedgerLens ────────────────────────────────────────────────────────────────
with tab_ledger:
    try:
        import sys as _sys
        _src = os.path.dirname(os.path.abspath(__file__))
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        from ui.ledgerlens_tab import render as render_ledgerlens
        render_ledgerlens()
    except Exception as _ll_e:
        st.error(f'LedgerLens tab failed to load: {_ll_e}')


# ── Blog ──────────────────────────────────────────────────────────────────────
with tab_blog:
    from classes.BlogManager import BlogManager
    blog_mgr = BlogManager()

    hcol, bcol = st.columns([3, 1])
    hcol.markdown('## 📝 Blog')
    hcol.caption('Trading notes, market write-ups, and screener updates — posted straight from here.')
    bcol.link_button(
        '📈 Read on TradingView', 'https://in.tradingview.com/u/khushaljain023/',
        width='stretch',
        help='Previously published TradingView educational posts',
    )

    read_sub, write_sub = st.tabs(['📖 Read Posts', '✍️ Write New Post'])

    with write_sub:
        with st.form('blog_new_post_form', clear_on_submit=True):
            b_title = st.text_input('Title', placeholder='e.g. Nifty 50 — Weekly Technical Outlook')
            b_content = st.text_area(
                'Content (Markdown supported)', height=280,
                placeholder='Write your post here. **Bold**, *italic*, bullet points, and ```code``` all work.',
            )
            b_image = st.file_uploader('Cover image (optional)', type=['png', 'jpg', 'jpeg', 'gif', 'webp'])
            b_submit = st.form_submit_button('🚀 Publish Post', type='primary', width='stretch')

        if b_submit:
            if not b_title.strip() or not b_content.strip():
                st.warning('Title and content are both required.', icon='⚠️')
            else:
                img_bytes, img_ext = None, 'png'
                if b_image is not None:
                    img_bytes = b_image.getvalue()
                    img_ext = b_image.name.rsplit('.', 1)[-1] if '.' in b_image.name else 'png'
                blog_mgr.add_post(b_title.strip(), b_content, image_bytes=img_bytes, image_ext=img_ext)
                st.success('Post published!', icon='✅')
                st.rerun()

    with read_sub:
        posts = blog_mgr.list_posts()
        if not posts:
            st.info('No posts yet — write your first one in the "Write New Post" tab.')
        else:
            for post in posts:
                with st.container(border=True):
                    has_img = bool(post.get('image_path')) and os.path.isfile(post.get('image_path', ''))
                    if has_img:
                        pc1, pc2 = st.columns([1, 4])
                        pc1.image(post['image_path'], width='stretch')
                    else:
                        pc2 = st.container()
                    with pc2:
                        st.markdown(f"### {post['title']}")
                        try:
                            _dt = datetime.datetime.fromisoformat(post['created_at'])
                            st.caption(_dt.strftime('%d %b %Y, %I:%M %p'))
                        except Exception:
                            st.caption(post['created_at'])
                        st.markdown(post['content'])
                    del_key = f"del_blog_{post['id']}"
                    if st.button('🗑️ Delete', key=del_key):
                        blog_mgr.delete_post(post['id'])
                        st.rerun()


# ── About ──────────────────────────────────────────────────────────────────────
with tab_about:
    from classes.Changelog import VERSION, changelog
    st.markdown(f'## ℹ️ About KJScreener v{VERSION}')
    st.info("👨🏻‍💻 Developer: Khushal Jain | Open Source NSE Stock Screener")

    st.warning(
        "**Disclaimer:** This tool is for analysis and study purposes only. "
        "We do **not** provide Buy/Sell advice for any securities. "
        "Authors will not be held liable for any financial losses. "
        "Please understand the risks of market investing before trading.",
        icon="⚠️",
    )

    st.markdown('<p class="section-header">Project</p>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="in-profiles">
      <a class="in-card in-saffron" href="https://github.com/85599/KJStockScreener" target="_blank" rel="noopener">
        <div class="stripe-top"></div>
        <div class="body">
          <div class="icon">🏠</div>
          <div class="title">Home Page</div>
          <div class="handle">85599/KJStockScreener</div>
          <div class="cta">View repo →</div>
        </div>
        <div class="stripe-bot"></div>
      </a>
      <a class="in-card in-white" href="https://github.com/85599/KJStockScreener/issues" target="_blank" rel="noopener">
        <div class="stripe-top"></div>
        <div class="body">
          <div class="icon">⚠️</div>
          <div class="title">Issues</div>
          <div class="handle">Report a bug</div>
          <div class="cta">Open issue →</div>
        </div>
        <div class="stripe-bot"></div>
      </a>
      <a class="in-card in-green" href="https://github.com/85599/KJStockScreener/discussions" target="_blank" rel="noopener">
        <div class="stripe-top"></div>
        <div class="body">
          <div class="icon">📣</div>
          <div class="title">Discussions</div>
          <div class="handle">Ask & suggest</div>
          <div class="cta">Join in →</div>
        </div>
        <div class="stripe-bot"></div>
      </a>
      <a class="in-card in-saffron" href="https://github.com/85599/KJStockScreener/releases/latest" target="_blank" rel="noopener">
        <div class="stripe-top"></div>
        <div class="body">
          <div class="icon">⬇️</div>
          <div class="title">Latest Release</div>
          <div class="handle">v{VERSION}</div>
          <div class="cta">Download →</div>
        </div>
        <div class="stripe-bot"></div>
      </a>
      <a class="in-card in-white" href="https://whatsapp.com/channel/0029VbDBzHuFSAtDL0vkQQ3Q" target="_blank" rel="noopener">
        <div class="stripe-top"></div>
        <div class="body">
          <div class="icon">💬</div>
          <div class="title">WhatsApp</div>
          <div class="handle">Join channel</div>
          <div class="cta">Open →</div>
        </div>
        <div class="stripe-bot"></div>
      </a>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<p class="section-header">Connect</p>', unsafe_allow_html=True)

    # India tricolour profile cards — saffron / white / green
    st.markdown("""
    <style>
      .in-profiles {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin: 0.8rem 0 1.5rem 0;
      }
      .in-card {
        position: relative;
        border-radius: 14px;
        overflow: hidden;
        text-decoration: none !important;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        box-shadow: 0 4px 18px rgba(0,0,0,0.35);
        min-height: 120px;
      }
      .in-card:hover { transform: translateY(-4px); box-shadow: 0 8px 28px rgba(0,0,0,0.45); }
      .in-card .stripe-top { height: 6px; width: 100%; }
      .in-card .stripe-bot { height: 6px; width: 100%; position: absolute; bottom: 0; left: 0; }
      .in-card .body {
        padding: 1.1rem 1.2rem 1.4rem 1.2rem;
        background: linear-gradient(160deg, #1a1d24 0%, #12151a 100%);
        display: flex; flex-direction: column; gap: 0.35rem;
      }
      .in-card .icon { font-size: 1.6rem; line-height: 1; }
      .in-card .title { font-size: 1.05rem; font-weight: 700; color: #f0f6fc; letter-spacing: 0.02em; }
      .in-card .handle { font-size: 0.82rem; color: #8b949e; }
      .in-card .cta {
        margin-top: 0.45rem; font-size: 0.78rem; font-weight: 600;
        color: #ff9933; letter-spacing: 0.04em; text-transform: uppercase;
      }
      /* saffron / white / green accents */
      .in-saffron .stripe-top, .in-saffron .stripe-bot { background: #FF9933; }
      .in-white .stripe-top, .in-white .stripe-bot { background: #FFFFFF; }
      .in-green .stripe-top, .in-green .stripe-bot { background: #138808; }
      .in-saffron .cta { color: #FF9933; }
      .in-white .cta { color: #e8e8e8; }
      .in-green .cta { color: #3dd68c; }
      /* Ashoka Chakra hint on white card */
      .in-white .body::after {
        content: '⚙';
        position: absolute; right: 0.9rem; top: 50%; transform: translateY(-30%);
        font-size: 2.2rem; opacity: 0.12; color: #000080;
      }
      @media (max-width: 700px) { .in-profiles { grid-template-columns: 1fr; } }
    </style>
    <div class="in-profiles">
      <a class="in-card in-saffron" href="https://in.tradingview.com/u/khushaljain023/" target="_blank" rel="noopener">
        <div class="stripe-top"></div>
        <div class="body">
          <div class="icon">📈</div>
          <div class="title">TradingView</div>
          <div class="handle">@khushaljain023</div>
          <div class="cta">Open profile →</div>
        </div>
        <div class="stripe-bot"></div>
      </a>
      <a class="in-card in-white" href="https://x.com/khushaljai48011" target="_blank" rel="noopener">
        <div class="stripe-top"></div>
        <div class="body">
          <div class="icon">𝕏</div>
          <div class="title">Twitter / X</div>
          <div class="handle">@khushaljai48011</div>
          <div class="cta">Follow →</div>
        </div>
        <div class="stripe-bot"></div>
      </a>
      <a class="in-card in-green" href="https://github.com/85599" target="_blank" rel="noopener">
        <div class="stripe-top"></div>
        <div class="body">
          <div class="icon">💻</div>
          <div class="title">GitHub</div>
          <div class="handle">@85599</div>
          <div class="cta">View repos →</div>
        </div>
        <div class="stripe-bot"></div>
      </a>
    </div>
    """, unsafe_allow_html=True)
   
