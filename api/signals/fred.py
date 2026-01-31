"""
FANTASMA - Señales FRED (Federal Reserve Economic Data)
C5: Spread MX-US Yields
G1: VIX
G3: US 10Y Yield
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, Tuple

FRED_API_KEY = "your_fred_api_key"  # Gratis en fred.stlouisfed.org
BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

async def fetch_fred_series(series_id: str, days: int = 30) -> list:
    """Obtiene datos de FRED API."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
        "observation_end": end_date,
        "sort_order": "desc"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(BASE_URL, params=params, timeout=30)
            data = response.json()
            return data.get("observations", [])
        except Exception as e:
            print(f"Error fetching FRED {series_id}: {e}")
            return []

async def get_g1_vix() -> Tuple[float, Dict]:
    """
    G1: VIX (8 pts max)
    - VIX >25 → 4 pts
    - VIX >35 → 8 pts
    """
    data = await fetch_fred_series("VIXCLS", days=5)
    
    if not data:
        return 0, {"signal": "G1_VIX", "error": "No data"}
    
    # FRED devuelve más reciente primero
    current_vix = float(data[0]["value"]) if data[0]["value"] != "." else 0
    
    score = 0
    if current_vix > 35:
        score = 8
    elif current_vix > 25:
        score = 4
    
    return score, {
        "signal": "G1_VIX",
        "value": round(current_vix, 2),
        "score": score,
        "max_score": 8
    }

async def get_g3_us10y() -> Tuple[float, Dict]:
    """
    G3: US 10Y Yield (5 pts max)
    - Cambio semanal >30 bps → 3 pts
    - Yield >5% → 5 pts
    """
    data = await fetch_fred_series("DGS10", days=10)
    
    if not data:
        return 0, {"signal": "G3_US10Y", "error": "No data"}
    
    # Filtrar valores válidos
    valid_data = [d for d in data if d["value"] != "."]
    if not valid_data:
        return 0, {"signal": "G3_US10Y", "error": "No valid data"}
    
    current_yield = float(valid_data[0]["value"])
    
    # Cambio semanal (aproximadamente 5 días hábiles)
    weekly_change_bps = 0
    if len(valid_data) >= 5:
        week_ago = float(valid_data[4]["value"])
        weekly_change_bps = (current_yield - week_ago) * 100
    
    score = 0
    if current_yield > 5:
        score = 5
    elif abs(weekly_change_bps) > 30:
        score = 3
    
    return score, {
        "signal": "G3_US10Y",
        "value": round(current_yield, 2),
        "weekly_change_bps": round(weekly_change_bps, 0),
        "score": score,
        "max_score": 5
    }

async def get_c5_spread(tiie_rate: float = None) -> Tuple[float, Dict]:
    """
    C5: Spread MX-US Yields (10 pts max)
    - Spread <400 bps (comprimiéndose) → 5 pts
    - Spread >650 bps (ampliándose) → 10 pts
    
    Usa TIIE como proxy de yield MX si no hay datos de bonos M.
    """
    us10y_data = await fetch_fred_series("DGS10", days=10)
    
    if not us10y_data:
        return 0, {"signal": "C5_SPREAD", "error": "No US10Y data"}
    
    us_yield = float(us10y_data[0]["value"]) if us10y_data[0]["value"] != "." else 0
    
    # Si no hay TIIE, usar un valor por defecto
    mx_yield = tiie_rate if tiie_rate else 11.0  # TIIE aproximado
    
    spread_bps = (mx_yield - us_yield) * 100
    
    score = 0
    if spread_bps > 650:
        score = 10
    elif spread_bps < 400:
        score = 5
    
    return score, {
        "signal": "C5_SPREAD",
        "mx_yield": round(mx_yield, 2),
        "us_yield": round(us_yield, 2),
        "spread_bps": round(spread_bps, 0),
        "score": score,
        "max_score": 10
    }

# Fed Funds Rate (para cálculos de TIIE)
async def get_fed_funds_rate() -> float:
    """Obtiene la tasa de Fed Funds actual."""
    data = await fetch_fred_series("FEDFUNDS", days=5)
    if data and data[0]["value"] != ".":
        return float(data[0]["value"])
    return 5.25  # Fallback
