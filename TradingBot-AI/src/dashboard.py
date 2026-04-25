"""
MSA Trading Bot - Professional Dashboard v2
"""
import os
import json
import time
import threading
import logging
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse, unquote

import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from flask import Flask, jsonify, request, session, redirect, Response

DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'MSA2025')
SECRET_KEY = os.getenv('SECRET_KEY', 'msa-bot-secret-2025')
CACHE_CHECK_INTERVAL = 30
BINANCE_API = "https://api.binance.com/api/v3"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY


class DashboardDB:
    def __init__(self):
        self.db_params = None
        self._setup()

    def _setup(self):
        url = os.getenv('DATABASE_URL')
        if not url:
            logger.error("DATABASE_URL not found!")
            return
        p = urlparse(url)
        self.db_params = {
            'host': p.hostname, 'port': p.port or 5432,
            'database': p.path[1:], 'user': p.username,
            'password': unquote(p.password),
            'sslmode': 'require', 'connect_timeout': 10,
        }
        logger.info("Dashboard DB configured")

    def get_fingerprint(self):
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), MAX(buy_time) FROM positions;")
            r = cur.fetchone()
            conn.close()
            return r
        except:
            return None

    def load_positions(self):
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM positions ORDER BY buy_time DESC;")
            rows = cur.fetchall()
            conn.close()
            positions = []
            for row in rows:
                pos = dict(row)
                if pos.get('data'):
                    try:
                        extra = json.loads(pos['data']) if isinstance(pos['data'], str) else pos['data']
                        pos['buy_confidence'] = extra.get('buy_confidence', 0)
                        pos['stop_loss_threshold'] = extra.get('stop_loss_threshold') or 0
                    except:
                        pass
                positions.append(pos)
            return positions
        except Exception as e:
            logger.error(f"Load error: {e}")
            return []


db = DashboardDB()


class SmartCache:
    def __init__(self):
        self.positions = []
        self.fp = None
        self.last_check = 0
        self.prices = {}
        self.last_price = 0
        self.lock = threading.Lock()

    def get_positions(self):
        now = time.time()
        if now - self.last_check > CACHE_CHECK_INTERVAL:
            self.last_check = now
            fp = db.get_fingerprint()
            if fp != self.fp:
                self.fp = fp
                with self.lock:
                    self.positions = db.load_positions()
        return self.positions

    def get_prices(self, symbols):
        now = time.time()
        if now - self.last_price > 5:
            self.last_price = now
            try:
                resp = requests.get(f"{BINANCE_API}/ticker/price", timeout=5)
                if resp.status_code == 200:
                    all_p = {p['symbol']: float(p['price']) for p in resp.json()}
                    with self.lock:
                        for s in symbols:
                            bs = s.replace('/', '')
                            if bs in all_p:
                                self.prices[s] = all_p[bs]
            except:
                pass
        return self.prices

    def force_refresh(self):
        self.fp = None
        self.last_check = 0


cache = SmartCache()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ""
    if request.method == 'POST':
        if request.form.get('password') == DASHBOARD_PASSWORD:
            session['logged_in'] = True
            return redirect('/')
        error = "Wrong password"
    return Response(get_login_html(error), mimetype='text/html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')


@app.route('/')
@login_required
def dashboard():
    return Response(get_dashboard_html(), mimetype='text/html')


@app.route('/api/data')
@login_required
def api_data():
    positions = cache.get_positions()
    symbols = [p['symbol'] for p in positions]
    prices = cache.get_prices(symbols) if symbols else {}

    total_invested = 0
    pos_list = []

    for p in positions:
        sym = p['symbol']
        bp = float(p.get('buy_price', 0) or 0)
        amt = float(p.get('amount', 0) or 0)
        hi = float(p.get('highest_price', bp) or bp)
        inv = float(p.get('invested', 0) or 0)
        cp = prices.get(sym, bp)
        slt = float(p.get('stop_loss_threshold', 0) or 0)
        conf = float(p.get('buy_confidence', 0) or 0)

        if not inv or inv == 0:
            inv = bp * amt

        pp = ((cp - bp) / bp * 100) if bp > 0 else 0
        pu = (cp - bp) * amt
        total_invested += inv

        if pp >= 0.5:
            st, si = 'RIDING', 'green'
        elif pp < -1.0 and slt > 0:
            st, si = 'SL ZONE', 'red'
        elif pp < 0:
            st, si = 'WAITING', 'yellow'
        else:
            st, si = 'WAITING', 'yellow'

        pos_list.append({
            'symbol': sym, 'buy_price': bp, 'current_price': cp,
            'highest_price': hi, 'amount': amt, 'invested': round(inv, 2),
            'profit_pct': round(pp, 2), 'profit_usd': round(pu, 2),
            'sl_threshold': round(slt, 2), 'confidence': round(conf, 1),
            'buy_time': str(p.get('buy_time', '')),
            'status': st, 'status_color': si,
        })

    pos_list.sort(key=lambda x: x['profit_pct'], reverse=True)
    w = sum(1 for p in pos_list if p['profit_pct'] > 0)
    l = sum(1 for p in pos_list if p['profit_pct'] < 0)
    tp = sum(p['profit_usd'] for p in pos_list)

    return jsonify({
        'positions': pos_list,
        'summary': {
            'active': len(pos_list), 'max_positions': 20,
            'total_invested': round(total_invested, 2),
            'total_pnl': round(tp, 2), 'winners': w, 'losers': l,
        },
        'last_update': datetime.now(timezone.utc).strftime('%H:%M:%S UTC'),
    })


@app.route('/api/chart/<path:symbol>')
@login_required
def api_chart(symbol):
    try:
        bs = symbol.replace('/', '')
        url = f"{BINANCE_API}/klines?symbol={bs}&interval=1h&limit=168"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            candles = []
            for k in resp.json():
                candles.append({
                    'time': int(k[0]) // 1000,
                    'open': float(k[1]), 'high': float(k[2]),
                    'low': float(k[3]), 'close': float(k[4]),
                    'volume': float(k[5]),
                })
            return jsonify({'candles': candles, 'symbol': symbol})
    except:
        pass
    return jsonify({'candles': [], 'symbol': symbol})


def get_login_html(error=""):
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MSA Trading Bot</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#080b12;color:#e2e8f0;font-family:'Inter',sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;overflow:hidden}}
body::before{{content:'';position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(ellipse at 30% 20%,rgba(59,130,246,0.08) 0%,transparent 50%),radial-gradient(ellipse at 70% 80%,rgba(139,92,246,0.06) 0%,transparent 50%);animation:bgMove 20s ease infinite;z-index:-1}}
@keyframes bgMove{{0%,100%{{transform:translate(0,0)}}50%{{transform:translate(-2%,-2%)}}}}
.box{{background:rgba(17,24,39,0.8);backdrop-filter:blur(20px);padding:48px;border-radius:24px;border:1px solid rgba(255,255,255,0.06);width:400px;text-align:center;box-shadow:0 25px 50px rgba(0,0,0,0.5)}}
.logo{{width:80px;height:80px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);border-radius:20px;display:flex;align-items:center;justify-content:center;font-size:36px;margin:0 auto 24px;box-shadow:0 10px 30px rgba(59,130,246,0.3)}}
h1{{font-size:22px;font-weight:700;margin-bottom:6px;background:linear-gradient(135deg,#e2e8f0,#94a3b8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.sub{{color:#64748b;margin-bottom:32px;font-size:13px;font-weight:400}}
input{{width:100%;padding:14px 18px;background:rgba(15,23,42,0.8);border:1px solid rgba(255,255,255,0.08);border-radius:12px;color:#e2e8f0;font-size:15px;margin-bottom:18px;text-align:center;font-family:'Inter',sans-serif;transition:all 0.3s}}
input:focus{{outline:none;border-color:rgba(59,130,246,0.5);box-shadow:0 0 20px rgba(59,130,246,0.15)}}
button{{width:100%;padding:14px;background:linear-gradient(135deg,#3b82f6,#6366f1);color:white;border:none;border-radius:12px;font-size:15px;cursor:pointer;font-weight:600;font-family:'Inter',sans-serif;transition:all 0.3s;box-shadow:0 4px 15px rgba(59,130,246,0.3)}}
button:hover{{transform:translateY(-2px);box-shadow:0 8px 25px rgba(59,130,246,0.4)}}
.err{{color:#f87171;margin-bottom:16px;font-size:13px;padding:10px;background:rgba(248,113,113,0.1);border-radius:8px}}
</style></head><body>
<form class="box" method="POST">
<div class="logo">🤖</div>
<h1>MSA Trading Bot</h1>
<p class="sub">Professional Trading Dashboard</p>
{"<div class='err'>"+error+"</div>" if error else ""}
<input type="password" name="password" placeholder="Enter Password" autofocus>
<button type="submit">Access Dashboard</button>
</form></body></html>"""


def get_dashboard_html():
    return """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MSA Trading Bot</title>
<script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
--bg:#080b12;--card:rgba(17,24,39,0.6);--card-border:rgba(255,255,255,0.06);
--green:#10b981;--green-bg:rgba(16,185,129,0.1);--green-glow:rgba(16,185,129,0.3);
--red:#ef4444;--red-bg:rgba(239,68,68,0.1);--red-glow:rgba(239,68,68,0.3);
--blue:#3b82f6;--blue-bg:rgba(59,130,246,0.1);--blue-glow:rgba(59,130,246,0.3);
--purple:#8b5cf6;--yellow:#f59e0b;--yellow-bg:rgba(245,158,11,0.1);
--text:#e2e8f0;--text2:#94a3b8;--text3:#64748b;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;padding:20px;min-height:100vh}
body::before{content:'';position:fixed;top:0;left:0;width:100%;height:100%;background:radial-gradient(ellipse at 20% 0%,rgba(59,130,246,0.06) 0%,transparent 50%),radial-gradient(ellipse at 80% 100%,rgba(139,92,246,0.04) 0%,transparent 50%);pointer-events:none;z-index:-1}

.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px}
.header-left{display:flex;align-items:center;gap:14px}
.logo-sm{width:42px;height:42px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 4px 15px rgba(59,130,246,0.3)}
.header h1{font-size:18px;font-weight:700;background:linear-gradient(135deg,#e2e8f0,#94a3b8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header-right{display:flex;gap:16px;align-items:center}
.header-right span{color:var(--text3);font-size:12px;font-family:'JetBrains Mono',monospace}
.live-dot{width:8px;height:8px;background:var(--green);border-radius:50%;display:inline-block;animation:pulse 2s infinite;margin-right:4px}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 var(--green-glow)}50%{opacity:0.7;box-shadow:0 0 0 8px transparent}}
.btn-logout{color:var(--text3);text-decoration:none;font-size:12px;padding:6px 14px;border:1px solid var(--card-border);border-radius:8px;transition:all 0.3s}
.btn-logout:hover{border-color:var(--red);color:var(--red)}

.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:24px}
.stat{background:var(--card);backdrop-filter:blur(10px);padding:20px;border-radius:16px;border:1px solid var(--card-border);position:relative;overflow:hidden;transition:all 0.3s}
.stat:hover{transform:translateY(-2px);border-color:rgba(255,255,255,0.1)}
.stat::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;border-radius:16px 16px 0 0}
.stat-blue::before{background:linear-gradient(90deg,var(--blue),var(--purple))}
.stat-green::before{background:var(--green)}
.stat-red::before{background:var(--red)}
.stat-yellow::before{background:var(--yellow)}
.stat-purple::before{background:var(--purple)}
.stat .icon{font-size:20px;margin-bottom:8px}
.stat .val{font-size:26px;font-weight:800;font-family:'JetBrains Mono',monospace;margin-bottom:4px}
.stat .lbl{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:1px;font-weight:500}
.val-green{color:var(--green)}.val-red{color:var(--red)}.val-blue{color:var(--blue)}.val-yellow{color:var(--yellow)}.val-purple{color:var(--purple)}

.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
@media(max-width:900px){.grid2{grid-template-columns:1fr}}

.card{background:var(--card);backdrop-filter:blur(10px);border-radius:16px;border:1px solid var(--card-border);padding:20px;transition:all 0.3s}
.card:hover{border-color:rgba(255,255,255,0.1)}
.card-title{font-size:14px;font-weight:600;margin-bottom:16px;display:flex;align-items:center;gap:8px;color:var(--text2)}
.card-full{margin-bottom:24px}

#chart{width:100%;height:380px;border-radius:12px;overflow:hidden}
#miniChart{width:100%;height:200px;border-radius:12px;overflow:hidden}

.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
.tab{padding:7px 14px;border-radius:8px;border:1px solid var(--card-border);background:transparent;color:var(--text3);cursor:pointer;font-size:12px;font-family:'Inter',sans-serif;font-weight:500;transition:all 0.3s}
.tab:hover{border-color:rgba(255,255,255,0.15);color:var(--text)}
.tab.act{background:linear-gradient(135deg,var(--blue),var(--purple));color:white;border-color:transparent;box-shadow:0 4px 12px var(--blue-glow)}

.tbl-wrap{overflow-x:auto;border-radius:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:12px 10px;color:var(--text3);font-size:10px;text-transform:uppercase;letter-spacing:1px;font-weight:600;border-bottom:1px solid rgba(255,255,255,0.04);position:sticky;top:0;background:rgba(8,11,18,0.9);backdrop-filter:blur(10px)}
td{padding:14px 10px;border-bottom:1px solid rgba(255,255,255,0.03);font-family:'JetBrains Mono',monospace;font-size:12px}
tr{transition:all 0.2s}
tr:hover{background:rgba(255,255,255,0.02)}

.coin-name{display:flex;align-items:center;gap:10px}
.coin-icon{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;font-family:'Inter',sans-serif}
.coin-sym{font-weight:600;font-family:'Inter',sans-serif;font-size:13px;color:var(--text)}
.coin-pair{font-size:10px;color:var(--text3);font-family:'Inter',sans-serif}

.pnl-bar{height:4px;border-radius:2px;background:rgba(255,255,255,0.04);overflow:hidden;width:80px;display:inline-block;vertical-align:middle;margin-left:8px}
.pnl-fill{height:100%;border-radius:2px;transition:width 0.5s}

.pos{color:var(--green);font-weight:600}
.neg{color:var(--red);font-weight:600}
.zer{color:var(--text3)}

.badge{padding:4px 10px;border-radius:6px;font-size:10px;font-weight:600;font-family:'Inter',sans-serif;letter-spacing:0.5px}
.b-green{background:var(--green-bg);color:var(--green)}
.b-red{background:var(--red-bg);color:var(--red)}
.b-yellow{background:var(--yellow-bg);color:var(--yellow)}

.chart-btn{padding:6px 10px;border-radius:6px;border:1px solid var(--card-border);background:transparent;color:var(--text3);cursor:pointer;font-size:11px;transition:all 0.3s}
.chart-btn:hover{border-color:var(--blue);color:var(--blue)}

.pnl-summary{display:flex;gap:16px;margin-bottom:16px;align-items:center}
.pnl-bar-big{flex:1;height:8px;border-radius:4px;background:rgba(255,255,255,0.04);overflow:hidden;display:flex}
.pnl-bar-big .w{background:linear-gradient(90deg,var(--green),#34d399);transition:width 0.5s}
.pnl-bar-big .lo{background:linear-gradient(90deg,#f87171,var(--red));transition:width 0.5s}
.pnl-label{font-size:11px;color:var(--text3);white-space:nowrap}

.footer{text-align:center;color:var(--text3);font-size:11px;margin-top:24px;padding:16px;opacity:0.6}

@media(max-width:600px){
body{padding:12px}
.stats{grid-template-columns:repeat(2,1fr);gap:10px}
.stat{padding:14px}
.stat .val{font-size:20px}
table{font-size:11px}
td,th{padding:8px 6px}
#chart{height:280px}
}
</style></head><body>

<div class="header">
<div class="header-left">
<div class="logo-sm">🤖</div>
<h1>MSA Trading Bot</h1>
</div>
<div class="header-right">
<span><span class="live-dot"></span>LIVE</span>
<span id="clk"></span>
<span id="upd"></span>
<a href="/logout" class="btn-logout">Logout</a>
</div>
</div>

<div class="stats">
<div class="stat stat-blue"><div class="icon">📊</div><div class="val val-blue" id="sA">-</div><div class="lbl">Active Trades</div></div>
<div class="stat stat-yellow"><div class="icon">💰</div><div class="val val-yellow" id="sI">-</div><div class="lbl">Total Invested</div></div>
<div class="stat stat-green"><div class="icon">📈</div><div class="val" id="sP">-</div><div class="lbl">Total P&L</div></div>
<div class="stat stat-green"><div class="icon">🏆</div><div class="val val-green" id="sW">-</div><div class="lbl">Winners</div></div>
<div class="stat stat-red"><div class="icon">📉</div><div class="val val-red" id="sL">-</div><div class="lbl">Losers</div></div>
</div>

<div class="card card-full">
<div class="card-title">📊 Price Chart &mdash; <span id="cSym" style="color:var(--blue)">Select a coin</span></div>
<div class="tabs" id="cTabs"></div>
<div id="chart"></div>
</div>

<div class="card card-full">
<div class="card-title">📋 Open Positions</div>
<div class="pnl-summary">
<span class="pnl-label" id="wLabel">0 Winners</span>
<div class="pnl-bar-big" id="pBar"><div class="w"></div><div class="lo"></div></div>
<span class="pnl-label" id="lLabel">0 Losers</span>
</div>
<div class="tbl-wrap">
<table><thead><tr>
<th>Coin</th><th>Profit</th><th>P&L</th><th>Buy</th><th>Current</th><th>Highest</th><th>Invested</th><th>SL</th><th>Status</th><th></th>
</tr></thead><tbody id="tBody"></tbody></table>
</div>
</div>

<div class="footer">MSA Trading Bot &copy; 2025 &bull; Professional Dashboard v2 &bull; Auto-refresh 10s</div>

<script>
var ch=null,cs=null,lineSeries=null,volSeries=null,bl=null,curSym=null;
var coinColors={BTC:'#f7931a',ETH:'#627eea',SOL:'#9945ff',ADA:'#0033ad',XLM:'#14b6e7',DOT:'#e6007a',AVAX:'#e84142',LTC:'#bfbbbb',UNI:'#ff007a',LINK:'#2a5ada',FIL:'#0090ff',VET:'#15bdff',ETC:'#328332',ICP:'#29abe2',THETA:'#2ab8e6',HBAR:'#000',DOGE:'#c3a634'};

setInterval(function(){document.getElementById('clk').textContent=new Date().toLocaleTimeString()},1000);

function initC(){
var el=document.getElementById('chart');
ch=LightweightCharts.createChart(el,{
layout:{background:{type:'solid',color:'transparent'},textColor:'#64748b',fontFamily:'JetBrains Mono'},
grid:{vertLines:{color:'rgba(255,255,255,0.03)'},horzLines:{color:'rgba(255,255,255,0.03)'}},
width:el.clientWidth,height:380,
timeScale:{timeVisible:true,secondsVisible:false,borderColor:'rgba(255,255,255,0.06)'},
rightPriceScale:{borderColor:'rgba(255,255,255,0.06)'},
crosshair:{mode:LightweightCharts.CrosshairMode.Normal,vertLine:{color:'rgba(59,130,246,0.3)',style:3},horzLine:{color:'rgba(59,130,246,0.3)',style:3}}
});

cs=ch.addCandlestickSeries({upColor:'#10b981',downColor:'#ef4444',borderUpColor:'#10b981',borderDownColor:'#ef4444',wickUpColor:'#10b98180',wickDownColor:'#ef444480'});
lineSeries=ch.addLineSeries({color:'#3b82f6',lineWidth:2,crosshairMarkerVisible:true,priceLineVisible:false});
volSeries=ch.addHistogramSeries({color:'rgba(59,130,246,0.15)',priceFormat:{type:'volume'},priceScaleId:'vol'});
ch.priceScale('vol').applyOptions({scaleMargins:{top:0.85,bottom:0}});

window.addEventListener('resize',function(){ch.applyOptions({width:el.clientWidth})});
}

function loadC(sym,bp){
curSym=sym;
var coin=sym.replace('/USDT','');
document.getElementById('cSym').textContent=sym;
document.getElementById('cSym').style.color=coinColors[coin]||'#3b82f6';
document.querySelectorAll('.tab').forEach(function(t){t.classList.toggle('act',t.getAttribute('data-s')===sym)});

fetch('/api/chart/'+encodeURIComponent(sym))
.then(function(r){return r.json()})
.then(function(d){
if(d.candles&&d.candles.length>0){
cs.setData(d.candles);
var lineData=d.candles.map(function(c){return{time:c.time,value:c.close}});
lineSeries.setData(lineData);
var volData=d.candles.map(function(c){return{time:c.time,value:c.volume,color:c.close>=c.open?'rgba(16,185,129,0.2)':'rgba(239,68,68,0.2)'}});
volSeries.setData(volData);
if(bl){cs.removePriceLine(bl)}
if(bp>0){bl=cs.createPriceLine({price:bp,color:'#f59e0b',lineWidth:2,lineStyle:2,axisLabelVisible:true,title:'Buy: $'+bp.toFixed(2)})}
ch.timeScale().fitContent();
}
});
}

function fetchD(){
fetch('/api/data')
.then(function(r){return r.json()})
.then(function(d){
var s=d.summary;
document.getElementById('sA').textContent=s.active+'/'+s.max_positions;
document.getElementById('sI').textContent='$'+s.total_invested.toLocaleString();
var pnl=s.total_pnl;
var pEl=document.getElementById('sP');
pEl.textContent=(pnl>=0?'+$':'-$')+Math.abs(pnl).toFixed(2);
pEl.className='val '+(pnl>=0?'val-green':'val-red');
document.getElementById('sW').textContent=s.winners;
document.getElementById('sL').textContent=s.losers;
document.getElementById('upd').textContent=d.last_update;
document.getElementById('wLabel').textContent=s.winners+' Winners';
document.getElementById('lLabel').textContent=s.losers+' Losers';

var tot=s.winners+s.losers||1;
var wp=(s.winners/tot*100);
var lp=(s.losers/tot*100);
document.getElementById('pBar').innerHTML='<div class="w" style="width:'+wp+'%"></div><div class="lo" style="width:'+lp+'%"></div>';

var tb=document.getElementById('tBody');
tb.innerHTML='';
var tabs=document.getElementById('cTabs');
tabs.innerHTML='';

d.positions.forEach(function(p){
var coin=p.symbol.replace('/USDT','');
var cc=coinColors[coin]||'#3b82f6';
var pc=p.profit_pct>0?'pos':(p.profit_pct<0?'neg':'zer');
var uc=p.profit_usd>0?'pos':(p.profit_usd<0?'neg':'zer');
var bc='b-'+p.status_color;
var sl=p.sl_threshold>0?('-'+p.sl_threshold+'%'):'-';
var barW=Math.min(Math.abs(p.profit_pct)*20,100);
var barC=p.profit_pct>=0?'var(--green)':'var(--red)';

var row=document.createElement('tr');
row.innerHTML='<td><div class="coin-name"><div class="coin-icon" style="background:'+cc+'20;color:'+cc+'">'+coin.substring(0,3)+'</div><div><div class="coin-sym">'+coin+'</div><div class="coin-pair">USDT</div></div></div></td>'+
'<td class="'+pc+'">'+(p.profit_pct>0?'+':'')+p.profit_pct.toFixed(2)+'%<div class="pnl-bar"><div class="pnl-fill" style="width:'+barW+'%;background:'+barC+'"></div></div></td>'+
'<td class="'+uc+'">'+(p.profit_usd>=0?'+$':'-$')+Math.abs(p.profit_usd).toFixed(2)+'</td>'+
'<td>$'+fmtP(p.buy_price)+'</td>'+
'<td>$'+fmtP(p.current_price)+'</td>'+
'<td>$'+fmtP(p.highest_price)+'</td>'+
'<td>$'+p.invested.toFixed(0)+'</td>'+
'<td>'+sl+'</td>'+
'<td><span class="badge '+bc+'">'+p.status+'</span></td>'+
'<td></td>';

var btn=document.createElement('button');
btn.className='chart-btn';
btn.textContent='View';
btn.onclick=function(){loadC(p.symbol,p.buy_price)};
row.lastChild.appendChild(btn);
tb.appendChild(row);

var tabBtn=document.createElement('button');
tabBtn.className='tab'+(p.symbol===curSym?' act':'');
tabBtn.setAttribute('data-s',p.symbol);
tabBtn.textContent=coin;
tabBtn.style.borderColor=cc+'40';
tabBtn.onclick=function(){loadC(p.symbol,p.buy_price)};
tabs.appendChild(tabBtn);
});

if(!curSym&&d.positions.length>0){
loadC(d.positions[0].symbol,d.positions[0].buy_price);
}
});
}

function fmtP(p){
if(p>=1000)return p.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
if(p>=1)return p.toFixed(4);
if(p>=0.01)return p.toFixed(6);
return p.toFixed(8);
}

initC();
fetchD();
setInterval(fetchD,10000);
</script>
</body></html>"""


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
