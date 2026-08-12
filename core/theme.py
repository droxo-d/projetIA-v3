"""
Design system for the app: a "customer vitals" console — RFM read as a
health signal (pulse, rhythm, weight) rather than a generic KPI dashboard.
Champions read as a strong steady pulse; Perdus read as a flatline.

Everything here is presentation only. Import what a page needs:
    from core.theme import inject, pulse_header, vital_card, segment_pill,
                            plotly_layout, SEGMENT_TONES
"""
import streamlit as st

# ---- palette -----------------------------------------------------------

BG = "#132420"
PANEL = "#1B322C"
LINE = "#2E4F45"
TEXT = "#F2F8F5"
TEXT_DIM = "#9FC2B6"

SEGMENT_TONES = {
    "Champions":   {"hex": "#3DDC97", "glow": "rgba(61,220,151,.55)", "css": "champions"},
    "Prometteurs": {"hex": "#E8B34C", "glow": "rgba(232,179,76,.55)", "css": "prometteurs"},
    "À risque":    {"hex": "#E8794C", "glow": "rgba(232,121,76,.55)", "css": "risque"},
    "Perdus":      {"hex": "#6B7A78", "glow": "rgba(107,122,120,.45)", "css": "perdus"},
}
DEFAULT_TONE = {"hex": "#3DDC97", "glow": "rgba(61,220,151,.55)", "css": "champions"}


def tone_for(label: str) -> dict:
    return SEGMENT_TONES.get(label, DEFAULT_TONE)


# ---- base styles + chrome removal --------------------------------------

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

:root {{
  --bg: {BG};
  --panel: {PANEL};
  --line: {LINE};
  --text: {TEXT};
  --text-dim: {TEXT_DIM};
}}

html, body, [class*="css"] {{
  font-family: 'IBM Plex Sans', sans-serif;
}}

.stApp {{
  background:
    radial-gradient(1200px 500px at 15% -10%, rgba(61,220,151,.06), transparent 60%),
    var(--bg);
  color: var(--text);
}}

/* remove default Streamlit chrome */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {{
  visibility: hidden;
  height: 0;
}}
header[data-testid="stHeader"] {{ background: transparent; }}

section[data-testid="stSidebar"] {{
  background: var(--panel);
  border-right: 1px solid var(--line);
}}
section[data-testid="stSidebar"] * {{ color: var(--text) !important; }}

h1, h2, h3 {{ font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; letter-spacing: -.01em; }}
p, li, label, .stMarkdown {{ color: var(--text); }}
[data-testid="stCaptionContainer"], small {{ color: var(--text-dim) !important; }}

hr {{ border-color: var(--line) !important; }}

/* inputs */
.stTextInput input, .stNumberInput input, textarea {{
  background: var(--panel) !important;
  color: var(--text) !important;
  border: 1px solid var(--line) !important;
  border-radius: 2px !important;
  font-family: 'IBM Plex Mono', monospace !important;
}}
label p {{ font-size: .8rem !important; letter-spacing: .02em; color: var(--text-dim) !important; }}

/* buttons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  background: #3DDC97 !important;
  color: #06120D !important;
  border: none !important;
  border-radius: 2px !important;
  font-family: 'IBM Plex Mono', monospace !important;
  letter-spacing: .06em;
  text-transform: uppercase;
  font-size: .75rem !important;
  font-weight: 600 !important;
  padding: .55rem 1.2rem !important;
  transition: transform .12s ease, box-shadow .12s ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{
  transform: translateY(-1px);
  box-shadow: 0 8px 22px -10px rgba(61,220,151,.7);
  color: #06120D !important;
}}

/* tabs */
[data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid var(--line); }}
[data-baseweb="tab"] {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: .78rem;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--text-dim);
}}
[data-baseweb="tab"][aria-selected="true"] {{ color: #3DDC97 !important; }}
[data-baseweb="tab-highlight"] {{ background-color: #3DDC97 !important; }}

/* alerts */
[data-testid="stAlert"] {{
  background: var(--panel) !important;
  border: 1px solid var(--line) !important;
  border-radius: 2px !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: .83rem !important;
}}

/* file uploader */
[data-testid="stFileUploaderDropzone"] {{
  background: var(--panel) !important;
  border: 1px dashed var(--line) !important;
  border-radius: 3px !important;
}}

/* dataframe */
[data-testid="stDataFrame"] {{ border: 1px solid var(--line); border-radius: 3px; }}

/* radio (segmented) */
[role="radiogroup"] label {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: .78rem;
}}

/* ---- signature components ---- */

.console-header {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.5rem;
  padding-bottom: .9rem;
  border-bottom: 1px solid var(--line);
  margin-bottom: 1.6rem;
}}
.console-kicker {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: .72rem;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: #3DDC97;
  margin-bottom: .3rem;
}}
.console-title {{
  font-size: 1.55rem;
  font-weight: 600;
  color: var(--text);
  line-height: 1.15;
}}
.ecg-wrap {{ width: 220px; height: 40px; overflow: hidden; flex-shrink: 0; }}
.ecg-wrap svg {{ width: 100%; height: 100%; display: block; }}
.ecg-base {{ stroke: rgba(61,220,151,.16); stroke-width: 2; fill: none; }}
.ecg-sweep {{
  stroke: #3DDC97; stroke-width: 2; fill: none;
  stroke-dasharray: 90 900;
  animation: ecgTravel 3.6s linear infinite;
}}
@keyframes ecgTravel {{
  from {{ stroke-dashoffset: 0; }}
  to   {{ stroke-dashoffset: -1400; }}
}}

.vital-grid {{ display: flex; gap: .8rem; flex-wrap: wrap; margin-bottom: 1.4rem; }}
.vital-card {{
  flex: 1 1 150px;
  background: linear-gradient(180deg, var(--panel), var(--bg));
  border: 1px solid var(--line);
  border-left: 3px solid #3DDC97;
  border-radius: 3px;
  padding: .85rem 1rem;
  position: relative;
}}
.vital-label {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: .64rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: .3rem;
}}
.vital-value {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text);
}}
.vital-suffix {{ font-size: .82rem; color: var(--text-dim); margin-left: .2rem; }}
.vital-dot {{
  position: absolute; top: .8rem; right: .8rem;
  width: 7px; height: 7px; border-radius: 50%;
}}
@media (prefers-reduced-motion: no-preference) {{
  .vital-dot {{ animation: dotPulse 2.2s ease-in-out infinite; }}
}}
@keyframes dotPulse {{
  0%   {{ box-shadow: 0 0 0 0 var(--glow); }}
  70%  {{ box-shadow: 0 0 0 8px transparent; }}
  100% {{ box-shadow: 0 0 0 0 transparent; }}
}}

.result-panel {{
  background: linear-gradient(180deg, var(--panel), var(--bg));
  border: 1px solid var(--line);
  border-left: 3px solid var(--tone-hex);
  border-radius: 3px;
  padding: 1rem 1.2rem;
  display: flex;
  align-items: center;
  gap: .8rem;
  margin: .6rem 0 1rem 0;
}}
.result-dot {{
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--tone-hex);
  flex-shrink: 0;
}}
.result-text {{ font-family: 'IBM Plex Mono', monospace; font-size: .95rem; }}
.result-text b {{ color: var(--tone-hex); }}

.segment-pill {{
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  font-family: 'IBM Plex Mono', monospace;
  font-size: .72rem;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--text-dim);
}}
.segment-pill .dot {{ width: 7px; height: 7px; border-radius: 50%; }}
</style>
"""


def inject():
    st.markdown(_CSS, unsafe_allow_html=True)


def pulse_header(kicker: str, title: str):
    """Section header with a signature scrolling ECG line."""
    ecg_path = "M0,20 L28,20 L36,6 L44,34 L52,20 L120,20 L148,20 L156,6 L164,34 L172,20 L240,20 L268,20 L276,6 L284,34 L292,20 L360,20"
    html = (
        '<div class="console-header">'
        f'<div><div class="console-kicker">{kicker}</div>'
        f'<div class="console-title">{title}</div></div>'
        '<div class="ecg-wrap"><svg viewBox="0 0 360 40" preserveAspectRatio="none">'
        f'<path class="ecg-base" d="{ecg_path}"/>'
        f'<path class="ecg-sweep" d="{ecg_path}"/>'
        '</svg></div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def vital_card(label: str, value, suffix: str = "", tone_hex: str = "#3DDC97", glow: str = "rgba(61,220,151,.55)") -> str:
    return (
        f'<div class="vital-card" style="border-left-color:{tone_hex}">'
        f'<div class="vital-label">{label}</div>'
        f'<div class="vital-value">{value}<span class="vital-suffix">{suffix}</span></div>'
        f'<div class="vital-dot" style="background:{tone_hex}; --glow:{glow}"></div>'
        '</div>'
    )


def vital_grid(cards: list[str]):
    st.markdown('<div class="vital-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)


def result_panel(text_html: str, tone_hex: str = "#3DDC97"):
    html = (
        f'<div class="result-panel" style="--tone-hex:{tone_hex}">'
        '<div class="result-dot"></div>'
        f'<div class="result-text">{text_html}</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def segment_pill(label: str) -> str:
    tone = tone_for(label)
    return f'<span class="segment-pill"><span class="dot" style="background:{tone["hex"]}"></span>{label}</span>'


def plotly_layout(fig, height: int = 380):
    """Applies the console theme to a plotly figure in place, returns it."""
    fig.update_layout(
        height=height,
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(family="IBM Plex Mono, monospace", color=TEXT, size=12),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(family="IBM Plex Mono, monospace", color=TEXT, size=12),
            title=dict(font=dict(color=TEXT_DIM)),
        ),
    )
    fig.update_xaxes(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE)
    fig.update_yaxes(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE)
    return fig


SEGMENT_COLOR_MAP = {k: v["hex"] for k, v in SEGMENT_TONES.items()}
