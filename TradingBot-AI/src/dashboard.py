"""
MSA Trading Bot - Live Dashboard
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
SECRET_KEY = os.getenv('SECRET_KEY', 'msa-trading-bot-secret-key-2025')
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
                        pos['stop_loss_threshold'] = extra.get('stop_loss_threshold', 0)
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
            st, si = f'SL ZONE', 'red'
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
        url = f"{BINANCE_API}/klines?symbol={bs}&interval=1h&limit=100"
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
<title>MSA Bot - Login</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0e17;color:#e2e8f0;font-family:'Segoe UI',sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh}}
.box{{background:#111827;padding:40px;border-radius:16px;border:1px solid #1e293b;width:360px;text-align:center}}
h1{{font-size:24px;margin-bottom:8px}}
p{{color:#64748b;margin-bottom:24px;font-size:14px}}
input{{width:100%;padding:12px;background:#0a0e17;border:1px solid #334155;border-radius:8px;color:#e2e8f0;font-size:16px;margin-bottom:16px;text-align:center}}
input:focus{{outline:none;border-color:#3b82f6}}
button{{width:100%;padding:12px;background:#3b82f6;color:white;border:none;border-radius:8px;font-size:16px;cursor:pointer;font-weight:600}}
button:hover{{background:#2563eb}}
.err{{color:#ef4444;margin-bottom:16px}}
.icon{{font-size:48px;margin-bottom:16px}}
</style></head><body>
<form class="box" method="POST">
<div class="icon">🤖</div><h1>MSA Trading Bot</h1><p>Enter password</p>
{"<div class='err'>"+error+"</div>" if error else ""}
<input type="password" name="password" placeholder="Password" autofocus>
<button type="submit">Login</button>
</form></body></html>"""


def get_dashboard_html():
    return """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>MSA Trading Bot</title>
<script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0e17;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:16px}
.hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px}
.hdr h1{font-size:20px}
.hdr-r{display:flex;gap:12px;align-items:center}
.hdr-r span{color:#64748b;font-size:13px}
.hdr-r a{color:#ef4444;text-decoration:none;font-size:13px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px}
.sc{background:#111827;padding:16px;border-radius:12px;border:1px solid #1e293b;text-align:center}
.sc .v{font-size:22px;font-weight:700;margin-bottom:4px}
.sc .l{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.5px}
.v-blue{color:#3b82f6}.v-green{color:#10b981}.v-red{color:#ef4444}.v-yellow{color:#f59e0b}
.cc{background:#111827;border-radius:12px;border:1px solid #1e293b;padding:16px;margin-bottom:16px}
.ch{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px}
.ch h2{font-size:16px}
.tabs{display:flex;gap:6px;flex-wrap:wrap}
.tab{padding:6px 12px;border-radius:6px;border:1px solid #334155;background:transparent;color:#94a3b8;cursor:pointer;font-size:12px}
.tab.act{background:#3b82f6;color:white;border-color:#3b82f6}
#chart{width:100%;height:350px}
.tc{background:#111827;border-radius:12px;border:1px solid #1e293b;padding:16px;overflow-x:auto}
.tc h2{font-size:16px;margin-bottom:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:10px 8px;color:#64748b;font-size:11px;text-transform:uppercase;border-bottom:1px solid #1e293b}
td{padding:10px 8px;border-bottom:1px solid #0f172a}
tr:hover{background:#1e293b30}
.pos{color:#10b981;font-weight:600}.neg{color:#ef4444;font-weight:600}.zer{color:#94a3b8}
.badge{padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600}
.b-green{background:#10b98120;color:#10b981}.b-red{background:#ef444420;color:#ef4444}.b-yellow{background:#f59e0b20;color:#f59e0b}
.bar{display:flex;gap:0;margin-bottom:16px;height:8px;border-radius:4px;overflow:hidden}
.bar .w{background:#10b981}.bar .lo{background:#ef4444}
.ft{text-align:center;color:#334155;font-size:12px;margin-top:16px}
@media(max-width:600px){.stats{grid-template-columns:repeat(2,1fr)}table{font-size:11px}td,th{padding:6px 4px}}
</style></head><body>

<div class="hdr">
<h1>🤖 MSA Trading Bot</h1>
<div class="hdr-r"><span id="clk"></span><span id="upd"></span><a href="/logout">🔒 Logout</a></div>
</div>

<div class="stats">
<div class="sc"><div class="v v-blue" id="sA">-</div><div class="l">Active Trades</div></div>
<div class="sc"><div class="v v-yellow" id="sI">-</div><div class="l">Invested</div></div>
<div class="sc"><div class="v" id="sP">-</div><div class="l">Total P&L</div></div>
<div class="sc"><div class="v v-green" id="sW">-</div><div class="l">Winners</div></div>
<div class="sc"><div class="v v-red" id="sL">-</div><div class="l">Losers</div></div>
</div>

<div class="cc">
<div class="ch"><h2>📊 <span id="cSym">Select a coin</span></h2><div class="tabs" id="cTabs"></div></div>
<div id="chart"></div>
</div>

<div class="tc">
<h2>📋 Open Positions</h2>
<div class="bar" id="pBar"></div>
<table><thead><tr>
<th>Symbol</th><th>Profit</th><th>$ P&L</th><th>Buy</th><th>Current</th><th>Highest</th><th>Invested</th><th>SL</th><th>Status</th><th>Chart</th>
</tr></thead><tbody id="tBody"></tbody></table>
</div>

<div class="ft">MSA Trading Bot Dashboard &copy; 2025</div>

<script>
var ch=null,cs=null,bl=null,curSym=null;
setInterval(function(){document.getElementById('clk').textContent=new Date().toLocaleTimeString()},1000);

function initC(){
var el=document.getElementById('chart');
ch=LightweightCharts.createChart(el,{
layout:{background:{color:'#111827'},textColor:'#94a3b8'},
grid:{vertLines:{color:'#1e293b'},horzLines:{color:'#1e293b'}},
width:el.clientWidth,height:350,
timeScale:{timeVisible:true,secondsVisible:false}
});
cs=ch.addCandlestickSeries({upColor:'#10b981',downColor:'#ef4444',borderUpColor:'#10b981',borderDownColor:'#ef4444',wickUpColor:'#10b981',wickDownColor:'#ef4444'});
window.addEventListener('resize',function(){ch.applyOptions({width:el.clientWidth})});
}

function loadC(sym,bp){
curSym=sym;
document.getElementById('cSym').textContent=sym;
document.querySelectorAll('.tab').forEach(function(t){t.classList.toggle('act',t.getAttribute('data-s')===sym)});
fetch('/api/chart/'+encodeURIComponent(sym))
.then(function(r){return r.json()})
.then(function(d){
if(d.candles&&d.candles.length>0){
cs.setData(d.candles);
if(bl){cs.removePriceLine(bl)}
if(bp>0){bl=cs.createPriceLine({price:bp,color:'#3b82f6',lineWidth:2,lineStyle:2,axisLabelVisible:true,title:'Buy'})}
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
document.getElementById('sI').textContent='$'+s.total_invested.toFixed(2);
var pnl=s.total_pnl;
document.getElementById('sP').textContent=(pnl>=0?'+$':'-$')+Math.abs(pnl).toFixed(2);
document.getElementById('sP').className='v '+(pnl>=0?'v-green':'v-red');
document.getElementById('sW').textContent=s.winners;
document.getElementById('sL').textContent=s.losers;
document.getElementById('upd').textContent=d.last_update;

var tot=s.winners+s.losers||1;
var wp=(s.winners/tot*100).toFixed(0);
var lp=(s.losers/tot*100).toFixed(0);
document.getElementById('pBar').innerHTML='<div class="w" style="width:'+wp+'%"></div><div class="lo" style="width:'+lp+'%"></div>';

var tb=document.getElementById('tBody');
tb.innerHTML='';
var tabs=document.getElementById('cTabs');
tabs.innerHTML='';

d.positions.forEach(function(p){
var pc=p.profit_pct>0?'pos':(p.profit_pct<0?'neg':'zer');
var uc=p.profit_usd>0?'pos':(p.profit_usd<0?'neg':'zer');
var bc='b-'+p.status_color;
var sl=p.sl_threshold>0?('-'+p.sl_threshold+'%'):'-';
var coin=p.symbol.replace('/USDT','');
var icon=p.status_color==='green'?'🟢':(p.status_color==='red'?'🔴':'🟡');

var row=document.createElement('tr');
row.innerHTML='<td><strong>'+coin+'</strong></td>'+
'<td class="'+pc+'">'+(p.profit_pct>0?'+':'')+p.profit_pct.toFixed(2)+'%</td>'+
'<td class="'+uc+'">'+(p.profit_usd>=0?'+$':'-$')+Math.abs(p.profit_usd).toFixed(2)+'</td>'+
'<td>$'+fmtP(p.buy_price)+'</td>'+
'<td>$'+fmtP(p.current_price)+'</td>'+
'<td>$'+fmtP(p.highest_price)+'</td>'+
'<td>$'+p.invested.toFixed(2)+'</td>'+
'<td>'+sl+'</td>'+
'<td><span class="badge '+bc+'">'+icon+' '+p.status+'</span></td>'+
'<td></td>';

var btn=document.createElement('button');
btn.className='tab';
btn.textContent='📊';
btn.onclick=function(){loadC(p.symbol,p.buy_price)};
row.lastChild.appendChild(btn);
tb.appendChild(row);

var tabBtn=document.createElement('button');
tabBtn.className='tab'+(p.symbol===curSym?' act':'');
tabBtn.setAttribute('data-s',p.symbol);
tabBtn.textContent=coin;
tabBtn.onclick=function(){loadC(p.symbol,p.buy_price)};
tabs.appendChild(tabBtn);
});
});
}

function fmtP(p){
if(p>=1000)return p.toFixed(2);
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