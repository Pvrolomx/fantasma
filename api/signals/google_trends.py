"""
FANTASMA - Señales Google Trends
G6: Búsquedas de crisis/devaluación
Keywords: "crisis México", "devaluación peso", "corralito", "comprar dólares"
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, Tuple
import json

# pytrends requiere instalación: pip install pytrends
# Alternativa: usar unofficial API

KEYWORDS = [
    "crisis México",
    "devaluación peso",
    "comprar dólares",
    "dólar hoy México"
]

async def fetch_trends_unofficial(keyword: str, geo: str = "MX") -> Dict:
    """
    Intenta obtener datos de Google Trends sin API oficial.
    En producción, usar pytrends o scraping más robusto.
    """
    # URL del widget de Google Trends (puede cambiar)
    base_url = "https://trends.google.com/trends/api/dailytrends"
    
    params = {
        "hl": "es-MX",
        "tz": "360",  # UTC-6
        "geo": geo,
        "ns": "15"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(base_url, params=params, headers=headers, timeout=30)
            # Google Trends prepends ")]}'" to JSON
            text = response.text
            if text.startswith(")]}'"):
                text = text[5:]
            data = json.loads(text)
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

def calculate_trend_spike(current: float, baseline: float) -> float:
    """Calcula el spike ratio vs baseline."""
    if baseline <= 0:
        return 0
    return current / baseline

async def get_g6_google_trends() -> Tuple[float, Dict]:
    """
    G6: Google Trends (4 pts max)
    - Spike >2x promedio 30 días → 2 pts
    - Spike >4x → 4 pts
    
    NOTA: Esta es una implementación simplificada.
    En producción, usar pytrends o SerpAPI.
    """
    # En producción, aquí iría la lógica real de pytrends
    # Por ahora, retornamos estructura de datos placeholder
    
    # Ejemplo de cómo sería con pytrends:
    """
    from pytrends.request import TrendReq
    
    pytrends = TrendReq(hl='es-MX', tz=360)
    pytrends.build_payload(KEYWORDS, cat=0, timeframe='today 1-m', geo='MX')
    interest = pytrends.interest_over_time()
    
    # Calcular spike
    current = interest.iloc[-1].mean()
    baseline = interest.iloc[:-7].mean().mean()
    spike_ratio = current / baseline if baseline > 0 else 0
    """
    
    # Placeholder - en producción conectar con pytrends
    spike_ratio = 1.0  # Normal
    
    score = 0
    if spike_ratio > 4:
        score = 4
    elif spike_ratio > 2:
        score = 2
    
    return score, {
        "signal": "G6_GOOGLE_TRENDS",
        "keywords": KEYWORDS,
        "spike_ratio": round(spike_ratio, 2),
        "note": "Requires pytrends integration",
        "score": score,
        "max_score": 4
    }

# Script helper para usar con pytrends (ejecutar por separado)
PYTRENDS_SCRIPT = '''
from pytrends.request import TrendReq
import json

def get_crisis_trends():
    pytrends = TrendReq(hl='es-MX', tz=360)
    keywords = ["crisis México", "devaluación peso", "comprar dólares"]
    
    pytrends.build_payload(keywords, cat=0, timeframe='today 1-m', geo='MX')
    interest = pytrends.interest_over_time()
    
    if interest.empty:
        return {"error": "No data"}
    
    # Último valor vs promedio
    current = interest.iloc[-1][keywords].mean()
    baseline = interest.iloc[:-7][keywords].mean().mean()
    spike = current / baseline if baseline > 0 else 1
    
    return {
        "current_interest": float(current),
        "baseline_30d": float(baseline),
        "spike_ratio": float(spike)
    }

if __name__ == "__main__":
    print(json.dumps(get_crisis_trends(), indent=2))
'''
