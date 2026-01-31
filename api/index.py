"""
FANTASMA API - Vercel Serverless Function
Endpoint: /api
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import asyncio
from datetime import datetime

# Importar módulos de señales
import httpx

# Configuración
BANXICO_TOKEN = os.getenv("BANXICO_TOKEN", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# ==================== SEÑALES ====================

async def fetch_banxico(series_id: str):
    """Fetch Banxico API"""
    url = f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{series_id}/datos/oportuno"
    headers = {"Bmx-Token": BANXICO_TOKEN}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30)
            data = response.json()
            series = data.get("bmx", {}).get("series", [{}])[0]
            datos = series.get("datos", [{}])
            if datos:
                return float(datos[-1].get("dato", "0").replace(",", ""))
        except:
            pass
    return None

async def fetch_fred(series_id: str):
    """Fetch FRED API"""
    url = f"https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 5
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30)
            data = response.json()
            obs = data.get("observations", [])
            for o in obs:
                if o.get("value") != ".":
                    return float(o["value"])
        except:
            pass
    return None

async def fetch_yahoo(symbol: str):
    """Fetch Yahoo Finance"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30)
            data = response.json()
            return data.get("chart", {}).get("result", [{}])[0].get("meta", {}).get("regularMarketPrice")
        except:
            pass
    return None

async def collect_signals():
    """Recolecta todas las señales y calcula score"""
    signals = []
    total_score = 0
    
    # C1: FIX (20 pts)
    fix = await fetch_banxico("SF43718")
    c1_score = 0
    if fix:
        signals.append({"signal": "C1_FIX", "value": fix, "score": c1_score, "max_score": 20})
    
    # C2: TIIE (10 pts)
    tiie = await fetch_banxico("SF60648")
    c2_score = 0
    fed_rate = await fetch_fred("FEDFUNDS") or 5.25
    if tiie:
        spread = (tiie - fed_rate) * 100
        if spread > 600:
            c2_score = 5
        signals.append({"signal": "C2_TIIE", "value": tiie, "spread_bps": round(spread), "score": c2_score, "max_score": 10})
        total_score += c2_score
    
    # G1: VIX (8 pts)
    vix = await fetch_fred("VIXCLS")
    g1_score = 0
    if vix:
        if vix > 35:
            g1_score = 8
        elif vix > 25:
            g1_score = 4
        signals.append({"signal": "G1_VIX", "value": round(vix, 2), "score": g1_score, "max_score": 8})
        total_score += g1_score
    
    # G2: DXY (5 pts)
    dxy = await fetch_yahoo("DX-Y.NYB")
    g2_score = 0
    if dxy:
        if dxy > 110:
            g2_score = 5
        elif dxy > 105:
            g2_score = 3
        signals.append({"signal": "G2_DXY", "value": round(dxy, 2), "score": g2_score, "max_score": 5})
        total_score += g2_score
    
    # G3: US 10Y (5 pts)
    us10y = await fetch_fred("DGS10")
    g3_score = 0
    if us10y:
        if us10y > 5:
            g3_score = 5
        signals.append({"signal": "G3_US10Y", "value": round(us10y, 2), "score": g3_score, "max_score": 5})
        total_score += g3_score
    
    # G5: Copper (5 pts)
    copper = await fetch_yahoo("HG=F")
    g5_score = 0
    if copper:
        signals.append({"signal": "G5_COPPER", "value": round(copper, 2), "score": g5_score, "max_score": 5})
    
    return total_score, signals

def get_alert_level(score):
    """Determina nivel de alerta"""
    if score <= 20:
        return {"level": "BAJO", "emoji": "🟢", "action": "Normal"}
    elif score <= 40:
        return {"level": "MODERADO", "emoji": "🟡", "action": "Monitorear"}
    elif score <= 60:
        return {"level": "ELEVADO", "emoji": "🟠", "action": "Reducir exposición MXN"}
    elif score <= 80:
        return {"level": "ALTO", "emoji": "🔴", "action": "Cobertura activa"}
    else:
        return {"level": "CRÍTICO", "emoji": "⚫", "action": "Modo defensivo total"}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # CORS headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Run async collection
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        score, signals = loop.run_until_complete(collect_signals())
        loop.close()
        
        alert = get_alert_level(score)
        
        # Separar señales
        core = [s for s in signals if s["signal"].startswith("C")]
        glob = [s for s in signals if s["signal"].startswith("G")]
        
        response = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_score": score,
            "max_possible": 100,
            "alert_level": alert["level"],
            "alert_emoji": alert["emoji"],
            "recommended_action": alert["action"],
            "breakdown": {
                "core_mxn": {
                    "score": sum(s.get("score", 0) for s in core),
                    "max": 65,
                    "signals": core
                },
                "global_overlay": {
                    "score": sum(s.get("score", 0) for s in glob),
                    "max": 35,
                    "signals": glob
                }
            },
            "active_signals": len([s for s in signals if s.get("score", 0) > 0])
        }
        
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode())
