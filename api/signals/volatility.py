"""
FANTASMA - Volatilidad Realizada MXN
G7: Calculada de datos FIX (rolling 20 días)
"""
import math
from datetime import datetime, timedelta
from typing import Dict, Tuple, List

def calculate_log_returns(prices: List[float]) -> List[float]:
    """Calcula retornos logarítmicos."""
    if len(prices) < 2:
        return []
    return [math.log(prices[i] / prices[i-1]) for i in range(1, len(prices))]

def calculate_realized_volatility(prices: List[float], annualize: bool = True) -> float:
    """
    Calcula volatilidad realizada (desviación estándar de retornos).
    
    Args:
        prices: Lista de precios históricos
        annualize: Si True, anualiza la volatilidad (252 días trading)
    
    Returns:
        Volatilidad como porcentaje
    """
    if len(prices) < 3:
        return 0.0
    
    log_returns = calculate_log_returns(prices)
    
    if not log_returns:
        return 0.0
    
    # Desviación estándar
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    std_dev = math.sqrt(variance)
    
    # Anualizar
    if annualize:
        std_dev *= math.sqrt(252)  # 252 días de trading
    
    return std_dev * 100  # Convertir a porcentaje

async def get_g7_volatility(fix_data: List[Dict] = None) -> Tuple[float, Dict]:
    """
    G7: Volatilidad Realizada MXN (3 pts max)
    - Vol >15% anualizada → 2 pts
    - Vol >25% → 3 pts
    
    Args:
        fix_data: Datos del FIX de Banxico (lista de dicts con 'dato')
    """
    # Si no hay datos, usar fetch de Banxico
    if fix_data is None:
        from .banxico import fetch_series
        fix_data = await fetch_series("SF43718", days=25)
    
    if not fix_data or len(fix_data) < 5:
        return 0, {"signal": "G7_VOLATILITY", "error": "Insufficient data"}
    
    # Extraer precios
    try:
        prices = [float(d["dato"].replace(",", "")) for d in fix_data]
    except (ValueError, KeyError):
        return 0, {"signal": "G7_VOLATILITY", "error": "Parse error"}
    
    # Calcular volatilidad de 20 días
    recent_prices = prices[-20:] if len(prices) >= 20 else prices
    vol_20d = calculate_realized_volatility(recent_prices, annualize=True)
    
    score = 0
    if vol_20d > 25:
        score = 3
    elif vol_20d > 15:
        score = 2
    
    return score, {
        "signal": "G7_VOLATILITY",
        "volatility_20d_annualized": round(vol_20d, 2),
        "data_points": len(recent_prices),
        "score": score,
        "max_score": 3
    }

def calculate_historical_vol_percentile(current_vol: float, historical_vols: List[float]) -> float:
    """
    Calcula en qué percentil está la volatilidad actual vs histórica.
    Útil para contextualizar si la vol actual es "alta" o "baja".
    """
    if not historical_vols:
        return 50.0
    
    below = sum(1 for v in historical_vols if v < current_vol)
    return (below / len(historical_vols)) * 100
