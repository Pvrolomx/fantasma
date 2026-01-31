"""
FANTASMA - Señales Yahoo Finance
G2: DXY Dollar Index
G4: HY Spread Proxy (HYG vs LQD)
G5: Cobre (proxy China)
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, Tuple

async def fetch_yahoo_quote(symbol: str) -> Dict:
    """
    Obtiene cotización de Yahoo Finance.
    Usa el endpoint de query que no requiere API key.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "interval": "1d",
        "range": "1mo"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=30)
            data = response.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            
            meta = result.get("meta", {})
            quotes = result.get("indicators", {}).get("quote", [{}])[0]
            
            closes = quotes.get("close", [])
            # Filtrar None values
            valid_closes = [c for c in closes if c is not None]
            
            return {
                "symbol": symbol,
                "current": meta.get("regularMarketPrice", valid_closes[-1] if valid_closes else 0),
                "previous_close": meta.get("previousClose", valid_closes[-2] if len(valid_closes) > 1 else 0),
                "closes": valid_closes[-20:] if valid_closes else []  # Últimos 20 días
            }
        except Exception as e:
            print(f"Error fetching Yahoo {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

async def get_g2_dxy() -> Tuple[float, Dict]:
    """
    G2: DXY Dollar Index (5 pts max)
    - DXY >105 → 3 pts
    - DXY >110 → 5 pts
    """
    data = await fetch_yahoo_quote("DX-Y.NYB")
    
    if "error" in data:
        return 0, {"signal": "G2_DXY", "error": data["error"]}
    
    current = data.get("current", 0)
    
    score = 0
    if current > 110:
        score = 5
    elif current > 105:
        score = 3
    
    return score, {
        "signal": "G2_DXY",
        "value": round(current, 2),
        "score": score,
        "max_score": 5
    }

async def get_g4_hy_spread() -> Tuple[float, Dict]:
    """
    G4: HY Spread Proxy (5 pts max)
    Usa spread entre HYG (High Yield) y LQD (Investment Grade) como proxy.
    - Spread widening >50 bps semana → 3 pts
    - Spread >500 bps → 5 pts
    """
    hyg_data = await fetch_yahoo_quote("HYG")
    lqd_data = await fetch_yahoo_quote("LQD")
    
    if "error" in hyg_data or "error" in lqd_data:
        return 0, {"signal": "G4_HY_SPREAD", "error": "Could not fetch ETF data"}
    
    hyg_current = hyg_data.get("current", 0)
    lqd_current = lqd_data.get("current", 0)
    
    # El "spread" aquí es simplificado - en realidad deberías usar yields
    # Aproximación: ratio de precios invertido * factor
    # En producción, usar datos de yields reales
    spread_proxy = abs(hyg_current - lqd_current) * 10  # Simplificado
    
    # Cambio semanal
    hyg_closes = hyg_data.get("closes", [])
    lqd_closes = lqd_data.get("closes", [])
    
    weekly_change = 0
    if len(hyg_closes) >= 5 and len(lqd_closes) >= 5:
        current_diff = hyg_current - lqd_current
        week_ago_diff = hyg_closes[-5] - lqd_closes[-5]
        weekly_change = (current_diff - week_ago_diff) * 100  # bps aproximados
    
    score = 0
    if abs(weekly_change) > 50:
        score = 3
    # Nota: el umbral de 500 bps requeriría datos de yields reales
    
    return score, {
        "signal": "G4_HY_SPREAD",
        "hyg_price": round(hyg_current, 2),
        "lqd_price": round(lqd_current, 2),
        "spread_proxy": round(spread_proxy, 0),
        "weekly_change_bps": round(weekly_change, 0),
        "score": score,
        "max_score": 5
    }

async def get_g5_copper() -> Tuple[float, Dict]:
    """
    G5: Cobre - proxy China (5 pts max)
    - Caída >5% mensual → 3 pts
    - Caída >10% mensual → 5 pts
    """
    data = await fetch_yahoo_quote("HG=F")  # Copper Futures
    
    if "error" in data:
        return 0, {"signal": "G5_COPPER", "error": data["error"]}
    
    current = data.get("current", 0)
    closes = data.get("closes", [])
    
    monthly_change_pct = 0
    if len(closes) >= 20:
        month_ago = closes[0]  # Primer dato del rango
        if month_ago > 0:
            monthly_change_pct = ((current - month_ago) / month_ago) * 100
    
    score = 0
    if monthly_change_pct < -10:
        score = 5
    elif monthly_change_pct < -5:
        score = 3
    
    return score, {
        "signal": "G5_COPPER",
        "value": round(current, 2),
        "monthly_change_pct": round(monthly_change_pct, 2),
        "score": score,
        "max_score": 5
    }

async def get_usdmxn() -> Dict:
    """Obtiene USD/MXN para cálculos de volatilidad."""
    data = await fetch_yahoo_quote("MXN=X")
    return data
