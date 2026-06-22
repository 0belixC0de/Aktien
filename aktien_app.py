"""
Aktien Signal-App — Trade Republic Style
==========================================
INSTALLATION: pip install streamlit yfinance pandas plotly requests numpy
STARTEN:      streamlit run aktien_app.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
import concurrent.futures
import json
import requests

# ---------------------------------------------------------------------------
# PAGE CONFIG + TRADE REPUBLIC DARK THEME
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Aktien", page_icon="📈", layout="centered")

TR_CSS = """
<style>
/* ── Base ── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    background-color: #0a0a0a !important;
    color: #ffffff !important;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif !important;
}

[data-testid="stSidebar"] {
    background-color: #111111 !important;
    border-right: 1px solid #1e1e1e !important;
}

[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] button {
    background: transparent !important;
    color: #888888 !important;
    border: none !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 10px 16px !important;
    border-radius: 0 !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #ffffff !important;
    border-bottom: 2px solid #ffffff !important;
    background: transparent !important;
}
[data-testid="stTabs"] [data-testid="stTabPanel"] {
    padding-top: 16px !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #141414 !important;
    border-radius: 12px !important;
    padding: 16px !important;
    border: 1px solid #1e1e1e !important;
}
[data-testid="stMetricLabel"] { color: #888888 !important; font-size: 12px !important; }
[data-testid="stMetricValue"] { color: #ffffff !important; font-size: 20px !important; font-weight: 600 !important; }
[data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stMetricDelta"] [data-testid="stMetricDeltaPositive"] { color: #00c26f !important; }
[data-testid="stMetricDelta"] [data-testid="stMetricDeltaNegative"] { color: #f04040 !important; }

/* ── Buttons ── */
[data-testid="stButton"] button {
    background: #1e1e1e !important;
    color: #ffffff !important;
    border: 1px solid #2e2e2e !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
}
[data-testid="stButton"] button[kind="primary"] {
    background: #ffffff !important;
    color: #000000 !important;
    border: none !important;
}

/* ── Inputs ── */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div,
[data-testid="stNumberInput"] input {
    background: #141414 !important;
    color: #ffffff !important;
    border: 1px solid #2e2e2e !important;
    border-radius: 10px !important;
}

/* ── Sliders ── */
[data-testid="stSlider"] [role="slider"] { background: #ffffff !important; }
[data-testid="stSlider"] [data-testid="stSliderTrack"] div:first-child { background: #ffffff !important; }

/* ── DataFrames ── */
[data-testid="stDataFrame"] { background: #141414 !important; border-radius: 12px !important; }
iframe { background: #141414 !important; }

/* ── Alerts ── */
[data-testid="stAlert"] {
    background: #141414 !important;
    border-radius: 10px !important;
    border-left: 3px solid #00c26f !important;
}
[data-testid="stAlert"][data-baseweb="notification"] {
    border-left-color: #f04040 !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #141414 !important;
    border: 1px solid #1e1e1e !important;
    border-radius: 12px !important;
}
[data-testid="stExpander"] summary { color: #ffffff !important; }

/* ── Divider ── */
hr { border-color: #1e1e1e !important; }

/* ── Captions ── */
[data-testid="stCaptionContainer"], .stMarkdown small { color: #666666 !important; }

/* ── Spinner ── */
[data-testid="stSpinner"] { color: #ffffff !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #2e2e2e; border-radius: 4px; }

/* ── Price display ── */
.tr-price { font-size: 36px; font-weight: 700; color: #ffffff; letter-spacing: -1px; }
.tr-change-pos { font-size: 16px; color: #00c26f; font-weight: 500; }
.tr-change-neg { font-size: 16px; color: #f04040; font-weight: 500; }
.tr-label { font-size: 12px; color: #666666; text-transform: uppercase; letter-spacing: 0.5px; }
.tr-card {
    background: #141414;
    border-radius: 14px;
    border: 1px solid #1e1e1e;
    padding: 16px;
    margin-bottom: 12px;
}
.tr-section-title {
    font-size: 13px;
    color: #666666;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 12px;
    font-weight: 500;
}
</style>
"""
st.markdown(TR_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# PLOTLY DARK TEMPLATE
# ---------------------------------------------------------------------------
PLOTLY_LAYOUT = dict(
    paper_bgcolor="#0a0a0a",
    plot_bgcolor="#0a0a0a",
    font=dict(color="#888888", size=11),
    margin=dict(l=8, r=8, t=8, b=8),
    xaxis=dict(showgrid=False, color="#444444", showline=False, zeroline=False),
    yaxis=dict(showgrid=True, gridcolor="#1a1a1a", color="#444444", showline=False, zeroline=False),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#888888", size=10)),
)

# ---------------------------------------------------------------------------
# DATEN-FUNKTIONEN
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def search_ticker(query):
    if not query or len(query) < 2:
        return []
    try:
        r = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": 8, "newsCount": 0, "enableFuzzyQuery": True},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=5,
        )
        if r.status_code != 200:
            return []
        results = []
        for q in r.json().get("quotes", []):
            if q.get("typeDisp") not in ("Equity", "ETF", "Index"):
                continue
            results.append({
                "symbol": q.get("symbol", ""),
                "name": q.get("shortname") or q.get("longname") or q.get("symbol", ""),
                "exchange": q.get("exchDisp", ""),
            })
        return results
    except Exception:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def get_live_quote(ticker, finnhub_key):
    """Finnhub live quote."""
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": ticker, "token": finnhub_key},
            timeout=5,
        )
        if r.status_code == 200:
            d = r.json()
            if d.get("c", 0) > 0:
                return d  # c=current, o=open, h=high, l=low, pc=prev close, dp=% change
    except Exception:
        pass
    return None


@st.cache_data(ttl=30, show_spinner=False)
def get_live_candles(ticker, finnhub_key, resolution="5", days=1):
    """Finnhub intraday candles."""
    try:
        now = int(datetime.now().timestamp())
        from_ts = int((datetime.now() - timedelta(days=days)).timestamp())
        r = requests.get(
            "https://finnhub.io/api/v1/stock/candle",
            params={"symbol": ticker, "resolution": resolution, "from": from_ts, "to": now, "token": finnhub_key},
            timeout=8,
        )
        if r.status_code == 200:
            d = r.json()
            if d.get("s") == "ok":
                df = pd.DataFrame({
                    "time": pd.to_datetime(d["t"], unit="s"),
                    "open": d["o"], "high": d["h"], "low": d["l"],
                    "close": d["c"], "volume": d["v"],
                })
                return df
    except Exception:
        pass
    return None


@st.cache_data(ttl=600, show_spinner=False)
def get_close(ticker, days=120):
    data = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
    if data.empty:
        return None
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna()


@st.cache_data(ttl=300, show_spinner=False)
def get_fundamentals(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "Marktkapitalisierung": info.get("marketCap"),
            "KGV (TTM)": info.get("trailingPE"),
            "KGV (Forward)": info.get("forwardPE"),
            "KUV": info.get("priceToSalesTrailing12Months"),
            "KBV": info.get("priceToBook"),
            "EPS (TTM)": info.get("trailingEps"),
            "Dividendenrendite": info.get("dividendYield"),
            "Beta": info.get("beta"),
            "52W Hoch": info.get("fiftyTwoWeekHigh"),
            "52W Tief": info.get("fiftyTwoWeekLow"),
            "Ø Volumen": info.get("averageVolume"),
            "Sektor": info.get("sector"),
            "Branche": info.get("industry"),
        }
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def get_analyst_ratings(ticker, finnhub_key):
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/stock/recommendation",
            params={"symbol": ticker, "token": finnhub_key},
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                return data[0]  # Most recent
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_earnings_calendar(ticker, finnhub_key):
    try:
        from_date = datetime.now().strftime("%Y-%m-%d")
        to_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        r = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"symbol": ticker, "from": from_date, "to": to_date, "token": finnhub_key},
            timeout=5,
        )
        if r.status_code == 200:
            d = r.json()
            return d.get("earningsCalendar", [])
    except Exception:
        pass
    return []


@st.cache_data(ttl=60, show_spinner=False)
def get_orderbook(ticker, finnhub_key):
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/stock/bidask",
            params={"symbol": ticker, "token": finnhub_key},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


@st.cache_data(ttl=300, show_spinner=False)
def get_news(ticker):
    try:
        return yf.Ticker(ticker).news or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def get_market_overview():
    symbols = {
        "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "DAX": "^GDAXI",
        "Dow Jones": "^DJI", "EUR/USD": "EURUSD=X", "Gold": "GC=F",
    }
    rows = []
    for name, sym in symbols.items():
        try:
            d = yf.download(sym, period="2d", interval="1d", progress=False)
            if d.empty or len(d) < 2:
                continue
            close = d["Close"].iloc[:, 0] if isinstance(d["Close"], pd.DataFrame) else d["Close"]
            close = close.dropna()
            if len(close) < 2:
                continue
            prev, curr = float(close.iloc[-2]), float(close.iloc[-1])
            pct = (curr - prev) / prev * 100
            rows.append({"name": name, "price": curr, "pct": pct})
        except Exception:
            pass
    return rows


@st.cache_data(ttl=3600, show_spinner=False)
def get_seasonality(ticker, years=5):
    try:
        data = yf.download(ticker, period=f"{years}y", interval="1d", progress=False)
        if data.empty or len(data) < 100:
            return None
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close = close.dropna()
        monthly = close.resample("ME").last()
        ret = monthly.pct_change().dropna() * 100
        df = ret.to_frame("return")
        df["month"] = df.index.month
        names = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]
        avg = df.groupby("month")["return"].mean().reindex(range(1, 13))
        avg.index = names
        return avg
    except Exception:
        return None


def fetch_ticker_momentum(ticker, lookback):
    try:
        close = get_close(ticker, days=lookback + 20)
        if close is None or len(close) < lookback + 1:
            return None
        curr = float(close.iloc[-1])
        past = float(close.iloc[-1 - lookback])
        pct = (curr - past) / past * 100
        return {"Ticker": ticker, "Kurs": round(curr, 2), "Veränderung %": round(pct, 2)}
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def scan_market(tickers, lookback):
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as ex:
        results = list(ex.map(lambda t: fetch_ticker_momentum(t, lookback), tickers))
    return pd.DataFrame([r for r in results if r])


# ---------------------------------------------------------------------------
# INDIKATOR-FUNKTIONEN
# ---------------------------------------------------------------------------

def compute_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    val = rsi.iloc[-1]
    return float(val) if not pd.isna(val) else None


def compute_momentum(close, period=10):
    if len(close) <= period:
        return None
    return float((close.iloc[-1] / close.iloc[-1 - period] - 1) * 100)


def compute_risk(close, rfr=0.04):
    ret = close.pct_change().dropna()
    if len(ret) < 10:
        return None
    ann_vol = float(ret.std() * np.sqrt(252))
    ann_ret = float(ret.mean() * 252)
    sharpe = (ann_ret - rfr) / ann_vol if ann_vol > 0 else 0.0
    running_max = close.cummax()
    drawdown = (close - running_max) / running_max
    return {
        "ann_vol": ann_vol, "ann_ret": ann_ret,
        "sharpe": float(sharpe), "max_drawdown": float(drawdown.min()),
        "drawdown_series": drawdown,
    }


# ---------------------------------------------------------------------------
# SENTIMENT
# ---------------------------------------------------------------------------

POS_WORDS = ["surge","soar","jump","rally","beat","beats","growth","record","upgrade","outperform",
             "strong","gain","gains","rise","rises","boost","profit","bullish","breakthrough","wins",
             "approval","approved","partnership","deal","exceed","exceeds"]
NEG_WORDS = ["plunge","plummet","drop","drops","fall","falls","miss","misses","downgrade","underperform",
             "weak","loss","losses","decline","declines","cut","cuts","bearish","lawsuit","investigation",
             "recall","warning","scandal","layoff","layoffs","crash","default","fraud","ban","tariff","sanction"]


def simple_sentiment(news_items):
    pos, neg, matched = 0, 0, []
    for item in news_items:
        cb = item.get("content", item)
        title = (cb.get("title") or item.get("title") or "").lower()
        for w in POS_WORDS:
            if w in title: pos += 1; matched.append((title[:70], "positiv", w))
        for w in NEG_WORDS:
            if w in title: neg += 1; matched.append((title[:70], "negativ", w))
    total = pos + neg
    score = 0.0 if total == 0 else (pos - neg) / total
    return score, pos, neg, matched


# ---------------------------------------------------------------------------
# WATCHLIST
# ---------------------------------------------------------------------------

WATCHLIST = [
    "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A","APD","ABNB","AKAM","ALB","ARE",
    "ALGN","ALLE","LNT","ALL","GOOGL","GOOG","MO","AMZN","AMCR","AEE","AEP","AXP","AIG","AMT",
    "AWK","AMP","AME","AMGN","APH","ADI","AON","APA","APO","AAPL","AMAT","APP","APTV","ACGL",
    "ADM","ARES","ANET","AJG","AIZ","T","ATO","ADSK","ADP","AZO","AVB","AVY","AXON","BKR","BALL",
    "BAC","BAX","BDX","BRK-B","BBY","TECH","BIIB","BLK","BX","BNY","BA","BKNG","BSX","BMY",
    "AVGO","BR","BRO","BLDR","BG","BXP","CHRW","CDNS","CPT","CPB","COF","CAH","CCL","CARR",
    "CAT","CBOE","CBRE","CDW","COR","CNC","CNP","CF","CRL","SCHW","CHTR","CVX","CMG","CB","CHD",
    "CI","CINF","CTAS","CSCO","C","CFG","CLX","CME","CMS","KO","CTSH","COHR","COIN","CL","CMCSA",
    "CAG","COP","ED","STZ","CEG","COO","CPRT","GLW","CTVA","CSGP","COST","CRH","CRWD","CCI",
    "CSX","CMI","CVS","DHR","DRI","DDOG","DVA","DECK","DE","DELL","DAL","DVN","DXCM","FANG",
    "DLR","DG","DLTR","D","DPZ","DASH","DOV","DOW","DHI","DTE","DUK","DD","ETN","EBAY","ECL",
    "EIX","EW","EA","ELV","EME","EMR","ETR","EOG","EPAM","EQT","EFX","EQIX","EQR","ERIE","ESS",
    "EL","EG","EVRG","ES","EXC","EXPE","EXPD","EXR","XOM","FFIV","FDS","FICO","FAST","FRT",
    "FDX","FIS","FITB","FSLR","FE","FISV","F","FTNT","FTV","FOXA","FOX","BEN","FCX","GRMN",
    "IT","GE","GEHC","GEV","GEN","GNRC","GD","GIS","GM","GPC","GILD","GPN","GL","GDDY","GS",
    "HAL","HIG","HAS","HCA","HSIC","HSY","HPE","HLT","HD","HON","HRL","HST","HWM","HPQ","HUBB",
    "HUM","HBAN","HII","IBM","IEX","IDXX","ITW","INCY","IR","PODD","INTC","IBKR","ICE","IFF",
    "IP","INTU","ISRG","IVZ","INVH","IQV","IRM","JBHT","JBL","JKHY","J","JNJ","JCI","JPM",
    "KVUE","KDP","KEY","KEYS","KMB","KIM","KMI","KKR","KLAC","KHC","KR","LHX","LH","LRCX",
    "LVS","LDOS","LEN","LII","LLY","LIN","LYV","LMT","L","LOW","LULU","LYB","MTB","MPC","MAR",
    "MLM","MAS","MA","MKC","MCD","MCK","MDT","MRK","META","MET","MTD","MGM","MCHP","MU","MSFT",
    "MAA","MRNA","TAP","MDLZ","MPWR","MNST","MCO","MS","MOS","MSI","MSCI","NDAQ","NTAP","NFLX",
    "NEM","NWSA","NWS","NEE","NKE","NI","NDSN","NSC","NTRS","NOC","NCLH","NRG","NUE","NVDA",
    "NVR","NXPI","ORLY","OXY","ODFL","OMC","ON","OKE","ORCL","OTIS","PCAR","PKG","PLTR","PANW",
    "PH","PAYX","PYPL","PNR","PEP","PFE","PCG","PM","PSX","PNW","PNC","POOL","PPG","PPL","PFG",
    "PG","PGR","PLD","PRU","PEG","PTC","PSA","PHM","PWR","QCOM","DGX","RL","RJF","RTX","O",
    "REG","REGN","RF","RSG","RMD","RVTY","HOOD","ROK","ROL","ROP","ROST","RCL","SPGI","CRM",
    "SBAC","SLB","STX","SRE","NOW","SHW","SPG","SWKS","SJM","SNA","SO","LUV","SWK","SBUX",
    "STT","STLD","STE","SYK","SMCI","SYF","SNPS","SYY","TMUS","TROW","TTWO","TPR","TRGP","TGT",
    "TEL","TDY","TER","TSLA","TXN","TPL","TXT","TMO","TJX","TKO","TTD","TSCO","TT","TDG","TRV",
    "TRMB","TFC","TYL","TSN","USB","UBER","UDR","ULTA","UNP","UAL","UPS","URI","UNH","UHS",
    "VLO","VEEV","VTR","VLTO","VRSN","VRSK","VZ","VRTX","VRT","VTRS","VICI","V","VST","VMC",
    "WRB","GWW","WAB","WMT","DIS","WBD","WM","WAT","WEC","WFC","WELL","WST","WDC","WY","WSM",
    "WMB","WTW","WDAY","WYNN","XEL","XYL","YUM","ZBRA","ZBH","ZTS",
]

SECTOR_MAP = {
    "MMM":"Industrie","AOS":"Industrie","ABT":"Gesundheit","ABBV":"Gesundheit","ACN":"Technologie",
    "ADBE":"Technologie","AMD":"Technologie","AES":"Versorger","AFL":"Finanzen","A":"Gesundheit",
    "APD":"Rohstoffe","ABNB":"Konsum (zyklisch)","AKAM":"Technologie","ALB":"Rohstoffe","ARE":"Immobilien",
    "ALGN":"Gesundheit","ALLE":"Industrie","LNT":"Versorger","ALL":"Finanzen","GOOGL":"Kommunikation",
    "GOOG":"Kommunikation","MO":"Konsum (Basis)","AMZN":"Konsum (zyklisch)","AMCR":"Rohstoffe",
    "AEE":"Versorger","AEP":"Versorger","AXP":"Finanzen","AIG":"Finanzen","AMT":"Immobilien",
    "AWK":"Versorger","AMP":"Finanzen","AME":"Industrie","AMGN":"Gesundheit","APH":"Technologie",
    "ADI":"Technologie","AON":"Finanzen","APA":"Energie","APO":"Finanzen","AAPL":"Technologie",
    "AMAT":"Technologie","APP":"Technologie","APTV":"Konsum (zyklisch)","ACGL":"Finanzen",
    "ADM":"Konsum (Basis)","ARES":"Finanzen","ANET":"Technologie","AJG":"Finanzen","AIZ":"Finanzen",
    "T":"Kommunikation","ATO":"Versorger","ADSK":"Technologie","ADP":"Industrie","AZO":"Konsum (zyklisch)",
    "AVB":"Immobilien","AVY":"Rohstoffe","AXON":"Industrie","BKR":"Energie","BALL":"Rohstoffe",
    "BAC":"Finanzen","BAX":"Gesundheit","BDX":"Gesundheit","BRK-B":"Finanzen","BBY":"Konsum (zyklisch)",
    "TECH":"Gesundheit","BIIB":"Gesundheit","BLK":"Finanzen","BX":"Finanzen","BNY":"Finanzen",
    "BA":"Industrie","BKNG":"Konsum (zyklisch)","BSX":"Gesundheit","BMY":"Gesundheit","AVGO":"Technologie",
    "BR":"Industrie","BRO":"Finanzen","BLDR":"Industrie","BG":"Konsum (Basis)","BXP":"Immobilien",
    "CHRW":"Industrie","CDNS":"Technologie","CPT":"Immobilien","CPB":"Konsum (Basis)","COF":"Finanzen",
    "CAH":"Gesundheit","CCL":"Konsum (zyklisch)","CARR":"Industrie","CAT":"Industrie","CBOE":"Finanzen",
    "CBRE":"Immobilien","CDW":"Technologie","COR":"Gesundheit","CNC":"Gesundheit","CNP":"Versorger",
    "CF":"Rohstoffe","CRL":"Gesundheit","SCHW":"Finanzen","CHTR":"Kommunikation","CVX":"Energie",
    "CMG":"Konsum (zyklisch)","CB":"Finanzen","CHD":"Konsum (Basis)","CI":"Gesundheit","CINF":"Finanzen",
    "CTAS":"Industrie","CSCO":"Technologie","C":"Finanzen","CFG":"Finanzen","CLX":"Konsum (Basis)",
    "CME":"Finanzen","CMS":"Versorger","KO":"Konsum (Basis)","CTSH":"Technologie","COHR":"Technologie",
    "COIN":"Finanzen","CL":"Konsum (Basis)","CMCSA":"Kommunikation","CAG":"Konsum (Basis)","COP":"Energie",
    "ED":"Versorger","STZ":"Konsum (Basis)","CEG":"Versorger","COO":"Gesundheit","CPRT":"Industrie",
    "GLW":"Technologie","CTVA":"Rohstoffe","CSGP":"Immobilien","COST":"Konsum (Basis)","CRH":"Rohstoffe",
    "CRWD":"Technologie","CCI":"Immobilien","CSX":"Industrie","CMI":"Industrie","CVS":"Gesundheit",
    "DHR":"Gesundheit","DRI":"Konsum (zyklisch)","DDOG":"Technologie","DVA":"Gesundheit","DECK":"Konsum (zyklisch)",
    "DE":"Industrie","DELL":"Technologie","DAL":"Industrie","DVN":"Energie","DXCM":"Gesundheit",
    "FANG":"Energie","DLR":"Immobilien","DG":"Konsum (Basis)","DLTR":"Konsum (Basis)","D":"Versorger",
    "DPZ":"Konsum (zyklisch)","DASH":"Konsum (zyklisch)","DOV":"Industrie","DOW":"Rohstoffe",
    "DHI":"Konsum (zyklisch)","DTE":"Versorger","DUK":"Versorger","DD":"Rohstoffe","ETN":"Industrie",
    "EBAY":"Konsum (zyklisch)","ECL":"Rohstoffe","EIX":"Versorger","EW":"Gesundheit","EA":"Kommunikation",
    "ELV":"Gesundheit","EME":"Industrie","EMR":"Industrie","ETR":"Versorger","EOG":"Energie",
    "EPAM":"Technologie","EQT":"Energie","EFX":"Industrie","EQIX":"Immobilien","EQR":"Immobilien",
    "ERIE":"Finanzen","ESS":"Immobilien","EL":"Konsum (Basis)","EG":"Finanzen","EVRG":"Versorger",
    "ES":"Versorger","EXC":"Versorger","EXPE":"Konsum (zyklisch)","EXPD":"Industrie","EXR":"Immobilien",
    "XOM":"Energie","FFIV":"Technologie","FDS":"Finanzen","FICO":"Technologie","FAST":"Industrie",
    "FRT":"Immobilien","FDX":"Industrie","FIS":"Finanzen","FITB":"Finanzen","FSLR":"Technologie",
    "FE":"Versorger","FISV":"Finanzen","F":"Konsum (zyklisch)","FTNT":"Technologie","FTV":"Industrie",
    "FOXA":"Kommunikation","FOX":"Kommunikation","BEN":"Finanzen","FCX":"Rohstoffe","GRMN":"Konsum (zyklisch)",
    "IT":"Technologie","GE":"Industrie","GEHC":"Gesundheit","GEV":"Industrie","GEN":"Technologie",
    "GNRC":"Industrie","GD":"Industrie","GIS":"Konsum (Basis)","GM":"Konsum (zyklisch)","GPC":"Konsum (zyklisch)",
    "GILD":"Gesundheit","GPN":"Finanzen","GL":"Finanzen","GDDY":"Technologie","GS":"Finanzen",
    "HAL":"Energie","HIG":"Finanzen","HAS":"Konsum (zyklisch)","HCA":"Gesundheit","HSIC":"Gesundheit",
    "HSY":"Konsum (Basis)","HPE":"Technologie","HLT":"Konsum (zyklisch)","HD":"Konsum (zyklisch)",
    "HON":"Industrie","HRL":"Konsum (Basis)","HST":"Immobilien","HWM":"Industrie","HPQ":"Technologie",
    "HUBB":"Industrie","HUM":"Gesundheit","HBAN":"Finanzen","HII":"Industrie","IBM":"Technologie",
    "IEX":"Industrie","IDXX":"Gesundheit","ITW":"Industrie","INCY":"Gesundheit","IR":"Industrie",
    "PODD":"Gesundheit","INTC":"Technologie","IBKR":"Finanzen","ICE":"Finanzen","IFF":"Rohstoffe",
    "IP":"Rohstoffe","INTU":"Technologie","ISRG":"Gesundheit","IVZ":"Finanzen","INVH":"Immobilien",
    "IQV":"Gesundheit","IRM":"Immobilien","JBHT":"Industrie","JBL":"Technologie","JKHY":"Finanzen",
    "J":"Industrie","JNJ":"Gesundheit","JCI":"Industrie","JPM":"Finanzen","KVUE":"Konsum (Basis)",
    "KDP":"Konsum (Basis)","KEY":"Finanzen","KEYS":"Technologie","KMB":"Konsum (Basis)","KIM":"Immobilien",
    "KMI":"Energie","KKR":"Finanzen","KLAC":"Technologie","KHC":"Konsum (Basis)","KR":"Konsum (Basis)",
    "LHX":"Industrie","LH":"Gesundheit","LRCX":"Technologie","LVS":"Konsum (zyklisch)","LDOS":"Industrie",
    "LEN":"Konsum (zyklisch)","LII":"Industrie","LLY":"Gesundheit","LIN":"Rohstoffe","LYV":"Kommunikation",
    "LMT":"Industrie","L":"Finanzen","LOW":"Konsum (zyklisch)","LULU":"Konsum (zyklisch)","LYB":"Rohstoffe",
    "MTB":"Finanzen","MPC":"Energie","MAR":"Konsum (zyklisch)","MLM":"Rohstoffe","MAS":"Industrie",
    "MA":"Finanzen","MKC":"Konsum (Basis)","MCD":"Konsum (zyklisch)","MCK":"Gesundheit","MDT":"Gesundheit",
    "MRK":"Gesundheit","META":"Kommunikation","MET":"Finanzen","MTD":"Gesundheit","MGM":"Konsum (zyklisch)",
    "MCHP":"Technologie","MU":"Technologie","MSFT":"Technologie","MAA":"Immobilien","MRNA":"Gesundheit",
    "TAP":"Konsum (Basis)","MDLZ":"Konsum (Basis)","MPWR":"Technologie","MNST":"Konsum (Basis)",
    "MCO":"Finanzen","MS":"Finanzen","MOS":"Rohstoffe","MSI":"Technologie","MSCI":"Finanzen",
    "NDAQ":"Finanzen","NTAP":"Technologie","NFLX":"Kommunikation","NEM":"Rohstoffe","NWSA":"Kommunikation",
    "NWS":"Kommunikation","NEE":"Versorger","NKE":"Konsum (zyklisch)","NI":"Versorger","NDSN":"Industrie",
    "NSC":"Industrie","NTRS":"Finanzen","NOC":"Industrie","NCLH":"Konsum (zyklisch)","NRG":"Versorger",
    "NUE":"Rohstoffe","NVDA":"Technologie","NVR":"Konsum (zyklisch)","NXPI":"Technologie",
    "ORLY":"Konsum (zyklisch)","OXY":"Energie","ODFL":"Industrie","OMC":"Kommunikation","ON":"Technologie",
    "OKE":"Energie","ORCL":"Technologie","OTIS":"Industrie","PCAR":"Industrie","PKG":"Rohstoffe",
    "PLTR":"Technologie","PANW":"Technologie","PH":"Industrie","PAYX":"Industrie","PYPL":"Finanzen",
    "PNR":"Industrie","PEP":"Konsum (Basis)","PFE":"Gesundheit","PCG":"Versorger","PM":"Konsum (Basis)",
    "PSX":"Energie","PNW":"Versorger","PNC":"Finanzen","POOL":"Konsum (zyklisch)","PPG":"Rohstoffe",
    "PPL":"Versorger","PFG":"Finanzen","PG":"Konsum (Basis)","PGR":"Finanzen","PLD":"Immobilien",
    "PRU":"Finanzen","PEG":"Versorger","PTC":"Technologie","PSA":"Immobilien","PHM":"Konsum (zyklisch)",
    "PWR":"Industrie","QCOM":"Technologie","DGX":"Gesundheit","RL":"Konsum (zyklisch)","RJF":"Finanzen",
    "RTX":"Industrie","O":"Immobilien","REG":"Immobilien","REGN":"Gesundheit","RF":"Finanzen",
    "RSG":"Industrie","RMD":"Gesundheit","RVTY":"Gesundheit","HOOD":"Finanzen","ROK":"Industrie",
    "ROL":"Industrie","ROP":"Technologie","ROST":"Konsum (zyklisch)","RCL":"Konsum (zyklisch)",
    "SPGI":"Finanzen","CRM":"Technologie","SBAC":"Immobilien","SLB":"Energie","STX":"Technologie",
    "SRE":"Versorger","NOW":"Technologie","SHW":"Rohstoffe","SPG":"Immobilien","SWKS":"Technologie",
    "SJM":"Konsum (Basis)","SNA":"Industrie","SO":"Versorger","LUV":"Industrie","SWK":"Industrie",
    "SBUX":"Konsum (zyklisch)","STT":"Finanzen","STLD":"Rohstoffe","STE":"Gesundheit","SYK":"Gesundheit",
    "SMCI":"Technologie","SYF":"Finanzen","SNPS":"Technologie","SYY":"Konsum (Basis)","TMUS":"Kommunikation",
    "TROW":"Finanzen","TTWO":"Kommunikation","TPR":"Konsum (zyklisch)","TRGP":"Energie","TGT":"Konsum (Basis)",
    "TEL":"Technologie","TDY":"Technologie","TER":"Technologie","TSLA":"Konsum (zyklisch)","TXN":"Technologie",
    "TPL":"Energie","TXT":"Industrie","TMO":"Gesundheit","TJX":"Konsum (zyklisch)","TKO":"Kommunikation",
    "TTD":"Kommunikation","TSCO":"Konsum (zyklisch)","TT":"Industrie","TDG":"Industrie","TRV":"Finanzen",
    "TRMB":"Technologie","TFC":"Finanzen","TYL":"Technologie","TSN":"Konsum (Basis)","USB":"Finanzen",
    "UBER":"Industrie","UDR":"Immobilien","ULTA":"Konsum (zyklisch)","UNP":"Industrie","UAL":"Industrie",
    "UPS":"Industrie","URI":"Industrie","UNH":"Gesundheit","UHS":"Gesundheit","VLO":"Energie",
    "VEEV":"Gesundheit","VTR":"Immobilien","VLTO":"Industrie","VRSN":"Technologie","VRSK":"Industrie",
    "VZ":"Kommunikation","VRTX":"Gesundheit","VRT":"Industrie","VTRS":"Gesundheit","VICI":"Immobilien",
    "V":"Finanzen","VST":"Versorger","VMC":"Rohstoffe","WRB":"Finanzen","GWW":"Industrie","WAB":"Industrie",
    "WMT":"Konsum (Basis)","DIS":"Kommunikation","WBD":"Kommunikation","WM":"Industrie","WAT":"Gesundheit",
    "WEC":"Versorger","WFC":"Finanzen","WELL":"Immobilien","WST":"Gesundheit","WDC":"Technologie",
    "WY":"Immobilien","WSM":"Konsum (zyklisch)","WMB":"Energie","WTW":"Finanzen","WDAY":"Technologie",
    "WYNN":"Konsum (zyklisch)","XEL":"Versorger","XYL":"Industrie","YUM":"Konsum (zyklisch)",
    "ZBRA":"Technologie","ZBH":"Gesundheit","ZTS":"Gesundheit",
}

# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = "AAPL"

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📈 Aktien")
    st.divider()

    st.markdown('<p class="tr-label">Finnhub API Key</p>', unsafe_allow_html=True)
    finnhub_key = st.text_input(
        "Finnhub Key",
        type="password",
        placeholder="Dein Finnhub API Key",
        label_visibility="collapsed",
        key="finnhub_key",
    )
    if finnhub_key:
        st.caption("✅ Live-Daten aktiv")
    else:
        st.caption("⚠️ Kein Key → verzögerte Daten")

    st.divider()

    st.markdown('<p class="tr-label">Watchlist</p>', unsafe_allow_html=True)
    col_in, col_btn = st.columns([3, 1])
    new_fav = col_in.text_input("Ticker", placeholder="NVDA", label_visibility="collapsed", key="new_fav")
    if col_btn.button("＋", key="add_fav"):
        t = new_fav.strip().upper()
        if t and t not in st.session_state.favorites:
            st.session_state.favorites.append(t)
            st.rerun()

    if st.session_state.favorites:
        for fav in list(st.session_state.favorites):
            c1, c2 = st.columns([4, 1])
            if c1.button(fav, key=f"sel_{fav}", use_container_width=True):
                st.session_state.selected_ticker = fav
                st.rerun()
            if c2.button("✕", key=f"rm_{fav}"):
                st.session_state.favorites.remove(fav)
                st.rerun()
    else:
        st.caption("Noch leer")

    st.divider()
    st.markdown('<p class="tr-label">Auto-Refresh</p>', unsafe_allow_html=True)
    auto_refresh = st.toggle("Aktiv", value=False, key="ar_toggle")
    if auto_refresh:
        refresh_interval = st.selectbox("Intervall", [15, 30, 60, 120],
            format_func=lambda x: f"{x} Sek", key="ar_interval")
        st.caption(f"✅ Alle {refresh_interval} Sek.")

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 Aktie", "🔥 Scanner", "🌍 Märkte"])

# ===========================================================================
# TAB 1: AKTIEN-DETAIL
# ===========================================================================
with tab1:

    # --- TICKER SUCHE ---
    s_c1, s_c2 = st.columns([3, 2])
    search_query = s_c1.text_input(
        "Suche",
        placeholder="Name oder Ticker …",
        key="t1_search",
        label_visibility="collapsed",
    )
    fav_pick = "—"
    if st.session_state.favorites:
        fav_pick = s_c2.selectbox("Watchlist", ["—"] + st.session_state.favorites,
                                   key="t1_fav", label_visibility="collapsed")

    if fav_pick != "—":
        st.session_state.selected_ticker = fav_pick
    elif search_query and len(search_query) >= 2:
        with st.spinner("Suche…"):
            suggestions = search_ticker(search_query)
        if suggestions:
            options = [f"{s['symbol']} — {s['name']} ({s['exchange']})" for s in suggestions]
            chosen = st.selectbox("Treffer:", options, key="t1_pick", label_visibility="collapsed")
            if chosen:
                new_ticker = chosen.split(" — ")[0].strip()
                if new_ticker != st.session_state.selected_ticker:
                    st.session_state.selected_ticker = new_ticker
                    st.rerun()
        else:
            st.caption(f"Keine Treffer für '{search_query}'")

    ticker = st.session_state.selected_ticker

    # --- LIVE KURS ---
    live = None
    if finnhub_key:
        with st.spinner(""):
            live = get_live_quote(ticker, finnhub_key)

    close_hist = get_close(ticker, days=365)

    if live:
        price = live["c"]
        prev_close = live["pc"]
        change = price - prev_close
        change_pct = live.get("dp", (change / prev_close * 100) if prev_close else 0)
        color_cls = "tr-change-pos" if change >= 0 else "tr-change-neg"
        sign = "+" if change >= 0 else ""
        st.markdown(f"""
        <div style="margin: 8px 0 20px 0;">
            <div class="tr-label">{ticker}</div>
            <div class="tr-price">${price:,.2f}</div>
            <div class="{color_cls}">{sign}{change:.2f} ({sign}{change_pct:.2f}%) heute</div>
        </div>
        """, unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Eröffnung", f"${live['o']:,.2f}")
        m2.metric("Tageshoch", f"${live['h']:,.2f}")
        m3.metric("Tagestief", f"${live['l']:,.2f}")
        m4.metric("Vortag", f"${prev_close:,.2f}")

    elif close_hist is not None:
        price = float(close_hist.iloc[-1])
        prev_close = float(close_hist.iloc[-2]) if len(close_hist) > 1 else price
        change = price - prev_close
        change_pct = change / prev_close * 100
        color_cls = "tr-change-pos" if change >= 0 else "tr-change-neg"
        sign = "+" if change >= 0 else ""
        st.markdown(f"""
        <div style="margin: 8px 0 20px 0;">
            <div class="tr-label">{ticker} · verzögerte Daten</div>
            <div class="tr-price">${price:,.2f}</div>
            <div class="{color_cls}">{sign}{change:.2f} ({sign}{change_pct:.2f}%)</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning(f"Keine Daten für {ticker}")
        st.stop()

    # --- LIVE CHART ---
    chart_period = st.radio(
        "Zeitraum",
        ["1T", "1W", "1M", "3M", "6M", "1J"],
        horizontal=True,
        key="t1_period",
        label_visibility="collapsed",
    )

    period_map = {"1T": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1J": 365}
    days = period_map[chart_period]

    if finnhub_key and chart_period == "1T":
        candles = get_live_candles(ticker, finnhub_key, resolution="5", days=1)
        if candles is not None and not candles.empty:
            fig = go.Figure()
            open_p = float(candles["close"].iloc[0])
            line_color = "#00c26f" if candles["close"].iloc[-1] >= open_p else "#f04040"
            fill_color = "rgba(0,194,111,0.08)" if line_color == "#00c26f" else "rgba(240,64,64,0.08)"
            fig.add_trace(go.Scatter(
                x=candles["time"], y=candles["close"],
                line=dict(color=line_color, width=2),
                fill="tozeroy", fillcolor=fill_color,
                name="Kurs",
            ))
            fig.add_hline(y=open_p, line_dash="dot", line_color="#444444")
            fig.update_layout(height=280, showlegend=False, **PLOTLY_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Intraday-Daten nicht verfügbar (Markt geschlossen?)")
    else:
        if close_hist is not None:
            hist = close_hist.tail(days)
            open_p = float(hist.iloc[0])
            last_p = float(hist.iloc[-1])
            line_color = "#00c26f" if last_p >= open_p else "#f04040"
            fill_color = "rgba(0,194,111,0.06)" if line_color == "#00c26f" else "rgba(240,64,64,0.06)"
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=hist.index, y=hist,
                line=dict(color=line_color, width=2),
                fill="tozeroy", fillcolor=fill_color,
                name="Kurs",
            ))
            fig.update_layout(height=280, showlegend=False, **PLOTLY_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- ORDERBOOK / BID-ASK ---
    st.markdown('<p class="tr-section-title">Bid / Ask</p>', unsafe_allow_html=True)
    if finnhub_key:
        ob = get_orderbook(ticker, finnhub_key)
        if ob and ob.get("a") and ob.get("b"):
            ob_c1, ob_c2 = st.columns(2)
            ob_c1.metric("Bid (Kauf)", f"${ob['b']:,.2f}")
            ob_c2.metric("Ask (Verkauf)", f"${ob['a']:,.2f}")
            spread = ob['a'] - ob['b']
            st.caption(f"Spread: ${spread:.4f}")
        else:
            st.caption("Bid/Ask nicht verfügbar (außerhalb Handelszeiten)")
    else:
        st.caption("Finnhub Key erforderlich für Live Bid/Ask")

    st.divider()

    # --- FUNDAMENTALDATEN ---
    st.markdown('<p class="tr-section-title">Fundamentaldaten</p>', unsafe_allow_html=True)
    with st.spinner(""):
        fund = get_fundamentals(ticker)

    if fund:
        def fmt_val(k, v):
            if v is None:
                return "—"
            if k == "Marktkapitalisierung":
                if v >= 1e12: return f"${v/1e12:.2f}T"
                if v >= 1e9: return f"${v/1e9:.2f}B"
                return f"${v/1e6:.0f}M"
            if k == "Dividendenrendite":
                return f"{v*100:.2f}%"
            if k in ("Ø Volumen",):
                return f"{v/1e6:.1f}M"
            if isinstance(v, float):
                return f"{v:.2f}"
            return str(v)

        fund_keys = ["Marktkapitalisierung", "KGV (TTM)", "KGV (Forward)", "KUV", "KBV",
                     "EPS (TTM)", "Dividendenrendite", "Beta", "52W Hoch", "52W Tief"]
        cols = st.columns(2)
        for i, k in enumerate(fund_keys):
            v = fund.get(k)
            cols[i % 2].metric(k, fmt_val(k, v))

        if fund.get("Sektor"):
            st.caption(f"🏭 {fund['Sektor']} · {fund.get('Branche', '')}")

    st.divider()

    # --- ANALYST RATINGS ---
    st.markdown('<p class="tr-section-title">Analysten-Konsens</p>', unsafe_allow_html=True)
    if finnhub_key:
        with st.spinner(""):
            ratings = get_analyst_ratings(ticker, finnhub_key)
        if ratings:
            total = (ratings.get("strongBuy", 0) + ratings.get("buy", 0) +
                     ratings.get("hold", 0) + ratings.get("sell", 0) + ratings.get("strongSell", 0))
            if total > 0:
                r1, r2, r3, r4, r5 = st.columns(5)
                r1.metric("Strong Buy", ratings.get("strongBuy", 0))
                r2.metric("Buy", ratings.get("buy", 0))
                r3.metric("Hold", ratings.get("hold", 0))
                r4.metric("Sell", ratings.get("sell", 0))
                r5.metric("Strong Sell", ratings.get("strongSell", 0))

                buy_pct = (ratings.get("strongBuy", 0) + ratings.get("buy", 0)) / total * 100
                if buy_pct >= 60:
                    st.success(f"✅ {buy_pct:.0f}% der Analysten empfehlen Kauf ({total} Analysten)")
                elif buy_pct >= 40:
                    st.info(f"➡️ Gemischte Einschätzungen ({total} Analysten)")
                else:
                    st.error(f"⚠️ Mehrheit empfiehlt Halten/Verkaufen ({total} Analysten)")
                st.caption(f"Stand: {ratings.get('period', '—')}")
        else:
            st.caption("Keine Analysten-Daten verfügbar")
    else:
        st.caption("Finnhub Key erforderlich")

    st.divider()

    # --- EARNINGS KALENDER ---
    st.markdown('<p class="tr-section-title">Earnings Kalender</p>', unsafe_allow_html=True)
    if finnhub_key:
        with st.spinner(""):
            earnings = get_earnings_calendar(ticker, finnhub_key)
        if earnings:
            for e in earnings[:3]:
                date_str = e.get("date", "—")
                eps_est = e.get("epsEstimate")
                rev_est = e.get("revenueEstimate")
                hour = e.get("hour", "")
                hour_str = {"bmo": "vor Marktöffnung", "amc": "nach Marktschluss"}.get(hour, "")
                eps_str = f"EPS-Schätzung: ${eps_est:.2f}" if eps_est else ""
                rev_str = f"· Umsatz: ${rev_est/1e9:.1f}B" if rev_est else ""
                st.markdown(f"""
                <div class="tr-card">
                    <div style="color:#ffffff; font-weight:600;">📅 {date_str} {hour_str}</div>
                    <div style="color:#888888; font-size:13px; margin-top:4px;">{eps_str} {rev_str}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("Kein Earnings-Termin in den nächsten 12 Monaten")
    else:
        st.caption("Finnhub Key erforderlich")

    st.divider()

    # --- PROJEKTION ---
    st.markdown('<p class="tr-section-title">Statistische Projektion</p>', unsafe_allow_html=True)
    st.caption("⚠️ Keine Vorhersage — mathematische Hochrechnung auf Basis historischer Volatilität")

    pc1, pc2 = st.columns(2)
    hist_days_proj = pc1.slider("Basis (Tage)", 20, 250, 90, key="t1_hist")
    horizon_days = pc2.slider("Projektion (Tage)", 5, 60, 20, key="t1_hor")

    if close_hist is not None and len(close_hist) >= 20:
        close_proj = close_hist.tail(hist_days_proj)
        log_ret = np.log(close_proj / close_proj.shift(1)).dropna()
        base_drift = log_ret.mean()
        vol = log_ret.std()
        last_price_proj = float(close_proj.iloc[-1])

        t_arr = np.arange(1, horizon_days + 1)
        math_proj = last_price_proj * np.exp(base_drift * t_arr)
        upper_95 = last_price_proj * np.exp(base_drift * t_arr + 1.96 * vol * np.sqrt(t_arr))
        lower_95 = last_price_proj * np.exp(base_drift * t_arr - 1.96 * vol * np.sqrt(t_arr))
        future_dates = [close_proj.index[-1] + timedelta(days=int(d)) for d in t_arr]

        pm1, pm2, pm3 = st.columns(3)
        pm1.metric("Aktuell", f"${last_price_proj:.2f}")
        pm2.metric(f"+{horizon_days}T (Mitte)", f"${math_proj[-1]:.2f}",
                   f"{(math_proj[-1]/last_price_proj-1)*100:+.1f}%")
        pm3.metric("Volatilität/Tag", f"{vol*100:.2f}%")

        fig_proj = go.Figure()
        fig_proj.add_trace(go.Scatter(x=close_proj.index, y=close_proj,
                                      line=dict(color="#888888", width=1.5), name="Verlauf"))
        fig_proj.add_trace(go.Scatter(x=future_dates, y=upper_95,
                                      line=dict(width=0), showlegend=False))
        fig_proj.add_trace(go.Scatter(x=future_dates, y=lower_95,
                                      fill="tonexty", fillcolor="rgba(255,255,255,0.05)",
                                      line=dict(width=0), name="95% Band"))
        fig_proj.add_trace(go.Scatter(x=future_dates, y=math_proj,
                                      line=dict(color="#ffffff", width=2, dash="dot"), name="Projektion"))
        fig_proj.update_layout(height=260, **PLOTLY_LAYOUT,
                                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#666", size=10)))
        st.plotly_chart(fig_proj, use_container_width=True)

    st.divider()

    # --- RISIKO ---
    with st.expander("📐 Risiko-Kennzahlen"):
        if close_hist is not None:
            risk = compute_risk(close_hist)
            if risk:
                rr1, rr2, rr3 = st.columns(3)
                rr1.metric("Sharpe Ratio", f"{risk['sharpe']:.2f}")
                rr2.metric("Volatilität p.a.", f"{risk['ann_vol']*100:.1f}%")
                rr3.metric("Max. Drawdown", f"{risk['max_drawdown']*100:.1f}%")

    # --- NEWS ---
    with st.expander("📰 Aktuelle News"):
        news_items = get_news(ticker)
        if news_items:
            score, pos, neg, matched = simple_sentiment(news_items)
            if score > 0.15:
                st.success(f"Stimmung: eher positiv (Score {score:+.2f})")
            elif score < -0.15:
                st.error(f"Stimmung: eher negativ (Score {score:+.2f})")
            else:
                st.info(f"Stimmung: neutral (Score {score:+.2f})")
            for item in news_items[:8]:
                cb = item.get("content", item)
                title = cb.get("title") or item.get("title")
                link = (cb.get("canonicalUrl", {}).get("url")
                        if isinstance(cb.get("canonicalUrl"), dict) else item.get("link"))
                if title:
                    st.markdown(f"- [{title}]({link})" if link else f"- {title}")
        else:
            st.caption("Keine News gefunden.")

    # --- SAISONALITÄT ---
    with st.expander("📅 Saisonalität"):
        season = get_seasonality(ticker)
        if season is not None:
            fig_s = go.Figure()
            fig_s.add_trace(go.Bar(
                x=season.index, y=season.values,
                marker_color=["#00c26f" if v >= 0 else "#f04040" for v in season.values],
                text=[f"{v:+.1f}%" if not np.isnan(v) else "" for v in season.values],
                textposition="outside",
                textfont=dict(color="#888888", size=10),
            ))
            fig_s.update_layout(height=220, **PLOTLY_LAYOUT, yaxis_title="Ø Rendite %")
            st.plotly_chart(fig_s, use_container_width=True)
            st.caption("Ø Monatsrendite letzte 5 Jahre — keine Garantie")
        else:
            st.caption("Nicht genug Daten")

    st.caption("Keine Finanzberatung. Technische Analyse auf Basis historischer Kurse.")


# ===========================================================================
# TAB 2: SCANNER
# ===========================================================================
with tab2:
    st.markdown('<p class="tr-section-title">Markt-Scanner</p>', unsafe_allow_html=True)
    st.caption(f"Durchsucht {len(WATCHLIST)} S&P-500-Aktien")

    s_col1, s_col2 = st.columns(2)
    lookback = s_col1.slider("Zeitraum (Tage)", 1, 30, 5, key="t2_lb")
    top_n = s_col2.slider("Top anzeigen", 3, 20, 8, key="t2_top")

    if st.button("🔍 Scannen", type="primary", key="t2_scan"):
        with st.spinner(f"Scanne {len(WATCHLIST)} Aktien…"):
            df = scan_market(WATCHLIST, lookback)

        if df.empty:
            st.warning("Keine Daten — bitte später erneut versuchen.")
        else:
            df = df.sort_values("Veränderung %", ascending=False)

            g_col, l_col = st.columns(2)
            with g_col:
                st.markdown(f"**🚀 Top {top_n} Gewinner**")
                gainers = df.head(top_n).reset_index(drop=True)
                st.dataframe(gainers.style.format({"Kurs": "{:.2f}", "Veränderung %": "{:+.2f}%"}),
                             use_container_width=True, hide_index=True)
            with l_col:
                st.markdown(f"**📉 Top {top_n} Verlierer**")
                losers = df.tail(top_n).sort_values("Veränderung %").reset_index(drop=True)
                st.dataframe(losers.style.format({"Kurs": "{:.2f}", "Veränderung %": "{:+.2f}%"}),
                             use_container_width=True, hide_index=True)

            st.divider()
            st.markdown(f"**🏭 Sektoren ({lookback}T)**")
            df["Sektor"] = df["Ticker"].map(SECTOR_MAP).fillna("Sonstige")
            sector_avg = df.groupby("Sektor")["Veränderung %"].mean().round(2).sort_values(ascending=False).reset_index()
            sector_avg.columns = ["Sektor", "Ø %"]
            fig_sec = go.Figure(go.Bar(
                x=sector_avg["Sektor"], y=sector_avg["Ø %"],
                marker_color=["#00c26f" if v >= 0 else "#f04040" for v in sector_avg["Ø %"]],
                text=sector_avg["Ø %"].apply(lambda v: f"{v:+.2f}%"),
                textposition="outside",
                textfont=dict(color="#888888", size=10),
            ))
            fig_sec.update_layout(height=300, **PLOTLY_LAYOUT,
                                   yaxis_title="Ø %", xaxis_tickangle=-35)
            st.plotly_chart(fig_sec, use_container_width=True)
    else:
        st.info("Klick auf 'Scannen' um zu starten.")


# ===========================================================================
# TAB 3: MÄRKTE
# ===========================================================================
with tab3:
    st.markdown('<p class="tr-section-title">Live-Marktübersicht</p>', unsafe_allow_html=True)

    if st.button("🔄 Aktualisieren", key="t3_refresh"):
        st.cache_data.clear()

    with st.spinner(""):
        market = get_market_overview()

    if market:
        row1 = market[:3]
        cols = st.columns(3)
        for i, q in enumerate(row1):
            sign = "+" if q["pct"] >= 0 else ""
            cols[i].metric(q["name"], f"{q['price']:,.2f}", f"{sign}{q['pct']:.2f}%")
        if len(market) > 3:
            st.markdown("")
            row2 = market[3:]
            cols2 = st.columns(len(row2))
            for i, q in enumerate(row2):
                sign = "+" if q["pct"] >= 0 else ""
                cols2[i].metric(q["name"], f"{q['price']:,.2f}", f"{sign}{q['pct']:.2f}%")

    st.divider()

    # ETFs
    st.markdown('<p class="tr-section-title">ETFs</p>', unsafe_allow_html=True)
    ETFS = {
        "S&P 500 (SPY)": "SPY", "Nasdaq 100 (QQQ)": "QQQ", "Welt (VT)": "VT",
        "Europa (VGK)": "VGK", "Emerging Markets (EEM)": "EEM",
        "Gold (GLD)": "GLD", "Anleihen (TLT)": "TLT", "Immobilien (VNQ)": "VNQ",
    }

    @st.cache_data(ttl=300, show_spinner=False)
    def get_etf_quotes(symbols):
        rows = []
        for name, sym in symbols.items():
            try:
                d = yf.download(sym, period="2d", interval="1d", progress=False)
                if d.empty or len(d) < 2:
                    continue
                close = d["Close"].iloc[:, 0] if isinstance(d["Close"], pd.DataFrame) else d["Close"]
                close = close.dropna()
                if len(close) < 2:
                    continue
                prev, curr = float(close.iloc[-2]), float(close.iloc[-1])
                pct = (curr - prev) / prev * 100
                rows.append({"name": name, "price": curr, "pct": pct})
            except Exception:
                pass
        return rows

    with st.spinner(""):
        etf_data = get_etf_quotes(ETFS)

    if etf_data:
        ec1, ec2 = st.columns(2)
        for i, q in enumerate(etf_data):
            col = ec1 if i % 2 == 0 else ec2
            sign = "+" if q["pct"] >= 0 else ""
            col.metric(q["name"], f"{q['price']:.2f}", f"{sign}{q['pct']:.2f}%")

    st.divider()

    # Watchlist
    st.markdown('<p class="tr-section-title">Meine Watchlist</p>', unsafe_allow_html=True)
    if not st.session_state.favorites:
        st.caption("Noch keine Favoriten — füge Ticker in der Sidebar hinzu.")
    else:
        @st.cache_data(ttl=300, show_spinner=False)
        def get_watchlist_quotes(tickers):
            def fetch(t):
                try:
                    d = yf.download(t, period="2d", interval="1d", progress=False)
                    if d.empty or len(d) < 2:
                        return None
                    close = d["Close"].iloc[:, 0] if isinstance(d["Close"], pd.DataFrame) else d["Close"]
                    close = close.dropna()
                    if len(close) < 2:
                        return None
                    prev, curr = float(close.iloc[-2]), float(close.iloc[-1])
                    pct = (curr - prev) / prev * 100
                    return {"ticker": t, "price": curr, "pct": pct}
                except Exception:
                    return None
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                results = list(ex.map(fetch, tickers))
            return [r for r in results if r]

        with st.spinner(""):
            wl_data = get_watchlist_quotes(tuple(st.session_state.favorites))

        if wl_data:
            wc1, wc2 = st.columns(2)
            for i, q in enumerate(wl_data):
                col = wc1 if i % 2 == 0 else wc2
                sign = "+" if q["pct"] >= 0 else ""
                col.metric(q["ticker"], f"{q['price']:.2f}", f"{sign}{q['pct']:.2f}%")

    st.divider()
    st.caption(f"Stand: {datetime.now().strftime('%H:%M:%S')} · Keine Finanzberatung · Daten via Yahoo Finance & Finnhub")

# ---------------------------------------------------------------------------
# AUTO-REFRESH
# ---------------------------------------------------------------------------
if st.session_state.get("ar_toggle"):
    import time
    interval = st.session_state.get("ar_interval", 30)
    time.sleep(interval)
    st.cache_data.clear()
    st.rerun()
