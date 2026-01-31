"""
FANTASMA - Motor de Scoring
Calcula score agregado 0-100 y determina nivel de alerta.
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Tuple

from signals import (
    get_c1_fix, get_c2_tiie, get_c3_cftc, get_c4_reservas, get_c5_spread,
    get_g1_vix, get_g2_dxy, get_g3_us10y, get_g4_hy_spread, get_g5_copper,
    get_g6_google_trends, get_g7_volatility, get_fed_funds_rate
)

# Niveles de alerta
ALERT_LEVELS = {
    (0, 20): {"level": "BAJO", "emoji": "🟢", "action": "Normal"},
    (21, 40): {"level": "MODERADO", "emoji": "🟡", "action": "Monitorear"},
    (41, 60): {"level": "ELEVADO", "emoji": "🟠", "action": "Reducir exposición MXN"},
    (61, 80): {"level": "ALTO", "emoji": "🔴", "action": "Cobertura activa"},
    (81, 100): {"level": "CRÍTICO", "emoji": "⚫", "action": "Modo defensivo total"}
}

def get_alert_level(score: int) -> Dict:
    """Determina el nivel de alerta basado en el score."""
    for (low, high), info in ALERT_LEVELS.items():
        if low <= score <= high:
            return info
    return ALERT_LEVELS[(81, 100)]

async def collect_all_signals() -> Tuple[int, List[Dict]]:
    """
    Recolecta todas las señales y calcula el score total.
    
    Returns:
        Tuple de (score_total, lista_de_señales)
    """
    signals = []
    total_score = 0
    
    # Obtener Fed Funds Rate primero (necesario para TIIE)
    fed_rate = await get_fed_funds_rate()
    
    # Ejecutar todas las señales en paralelo
    tasks = [
        ("C1_FIX", get_c1_fix()),
        ("C2_TIIE", get_c2_tiie(fed_rate)),
        ("C3_CFTC", get_c3_cftc()),
        ("C4_RESERVAS", get_c4_reservas()),
        ("C5_SPREAD", get_c5_spread()),
        ("G1_VIX", get_g1_vix()),
        ("G2_DXY", get_g2_dxy()),
        ("G3_US10Y", get_g3_us10y()),
        ("G4_HY_SPREAD", get_g4_hy_spread()),
        ("G5_COPPER", get_g5_copper()),
        ("G6_TRENDS", get_g6_google_trends()),
        ("G7_VOL", get_g7_volatility())
    ]
    
    # Ejecutar en paralelo
    results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
    
    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            signals.append({
                "signal": name,
                "error": str(result),
                "score": 0
            })
        else:
            score, data = result
            total_score += score
            signals.append(data)
    
    return total_score, signals

def generate_report(score: int, signals: List[Dict]) -> Dict:
    """Genera reporte completo."""
    alert = get_alert_level(score)
    
    # Separar señales core y global
    core_signals = [s for s in signals if s.get("signal", "").startswith("C")]
    global_signals = [s for s in signals if s.get("signal", "").startswith("G")]
    
    core_score = sum(s.get("score", 0) for s in core_signals)
    global_score = sum(s.get("score", 0) for s in global_signals)
    
    # Señales activas (score > 0)
    active_signals = [s for s in signals if s.get("score", 0) > 0]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_score": score,
        "max_possible": 100,
        "alert_level": alert["level"],
        "alert_emoji": alert["emoji"],
        "recommended_action": alert["action"],
        "breakdown": {
            "core_mxn": {
                "score": core_score,
                "max": 65,
                "signals": core_signals
            },
            "global_overlay": {
                "score": global_score,
                "max": 35,
                "signals": global_signals
            }
        },
        "active_signals": len(active_signals),
        "active_details": active_signals
    }

async def run_scoring() -> Dict:
    """Ejecuta el scoring completo y retorna el reporte."""
    score, signals = await collect_all_signals()
    return generate_report(score, signals)

# Para pruebas
if __name__ == "__main__":
    import json
    report = asyncio.run(run_scoring())
    print(json.dumps(report, indent=2, ensure_ascii=False))
