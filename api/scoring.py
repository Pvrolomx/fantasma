"""
FANTASMA / OBSERVATORIO - Motor de Scoring v2
4 Modulos: Core MXN (70) + Global (43) + Ormuz (50) + Mexico (30) = 193 pts
Score normalizado a 0-100.
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Tuple

from signals import (
    get_g8_carry_trade,
    get_c1_fix, get_c2_tiie, get_c3_cftc, get_c4_reservas, get_c5_spread,
    get_g1_vix, get_g2_dxy, get_g3_us10y, get_g4_hy_spread, get_g5_copper,
    get_g6_google_trends, get_g7_volatility, get_fed_funds_rate,
    get_o1_brent, get_o2_gas_europe, get_o3_usdchf, get_o4_sofr, get_o5_war_risk,
    get_m1_usdmxn, get_m2_corn, get_m3_urea,
)
from protocolo_cero import check_protocolo_cero

ALERT_LEVELS = {
    (0, 20): {"level": "BAJO", "emoji": "🟢", "action": "Normal"},
    (21, 40): {"level": "MODERADO", "emoji": "🟡", "action": "Monitorear"},
    (41, 60): {"level": "ELEVADO", "emoji": "🟠", "action": "Reducir exposicion MXN"},
    (61, 80): {"level": "ALTO", "emoji": "🔴", "action": "Cobertura activa"},
    (81, 100): {"level": "CRITICO", "emoji": "⚫", "action": "Modo defensivo total"},
}

MAX_RAW_SCORE = 193  # 70 + 43 + 50 + 30


def get_alert_level(score: int) -> Dict:
    for (low, high), info in ALERT_LEVELS.items():
        if low <= score <= high:
            return info
    return ALERT_LEVELS[(81, 100)]


async def collect_all_signals() -> Tuple[int, List[Dict]]:
    signals = []
    total_score = 0
    fed_rate = await get_fed_funds_rate()

    tasks = [
        # Module 1: Core MXN (65 pts max)
        ("C1_FIX", get_c1_fix()),
        ("C2_TIIE", get_c2_tiie(fed_rate)),
        ("C3_CFTC", get_c3_cftc()),
        ("C4_RESERVAS", get_c4_reservas()),
        ("C5_SPREAD", get_c5_spread()),
        # Module 1b: Global Overlay (35 pts max)
        ("G1_VIX", get_g1_vix()),
        ("G2_DXY", get_g2_dxy()),
        ("G3_US10Y", get_g3_us10y()),
        ("G4_HY_SPREAD", get_g4_hy_spread()),
        ("G5_COPPER", get_g5_copper()),
        ("G6_TRENDS", get_g6_google_trends()),
        ("G7_VOL", get_g7_volatility()),
        ("G8_CARRY", get_g8_carry_trade()),
        # Module 2: Ormuz / Coreografia (50 pts max)
        ("O1_BRENT", get_o1_brent()),
        ("O2_GAS_EU", get_o2_gas_europe()),
        ("O3_USDCHF", get_o3_usdchf()),
        ("O4_SOFR", get_o4_sofr()),
        ("O5_WAR_RISK", get_o5_war_risk()),
        # Module 3: Mexico / Impacto Local (30 pts max)
        ("M1_USDMXN", get_m1_usdmxn()),
        ("M2_CORN", get_m2_corn()),
        ("M3_UREA", get_m3_urea()),
    ]

    results = await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)

    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            signals.append({"signal": name, "error": str(result), "score": 0})
        else:
            score, data = result
            total_score += score
            signals.append(data)

    return total_score, signals


def generate_report(score_raw: int, signals: list, protocolo: dict) -> dict:
    normalized = round((score_raw / MAX_RAW_SCORE) * 100)
    alert = get_alert_level(normalized)

    core = [s for s in signals if s.get("signal", "").startswith("C")]
    glob = [s for s in signals if s.get("signal", "").startswith("G")]
    ormuz = [s for s in signals if s.get("signal", "").startswith("O")]
    mexico = [s for s in signals if s.get("signal", "").startswith("M")]

    active = [s for s in signals if s.get("score", 0) > 0]

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_score": normalized,
        "raw_score": score_raw,
        "max_raw": MAX_RAW_SCORE,
        "alert_level": alert["level"],
        "alert_emoji": alert["emoji"],
        "recommended_action": alert["action"],
        "protocolo_0": protocolo,
        "modules": {
            "core_mxn": {"score": sum(s.get("score", 0) for s in core), "max": 70, "signals": core},
            "global_overlay": {"score": sum(s.get("score", 0) for s in glob), "max": 43, "signals": glob},
            "ormuz_coreografia": {"score": sum(s.get("score", 0) for s in ormuz), "max": 50, "signals": ormuz},
            "mexico_local": {"score": sum(s.get("score", 0) for s in mexico), "max": 30, "signals": mexico},
        },
        "active_signals": len(active),
        "active_details": active,
    }


async def run_scoring() -> dict:
    score, signals = await collect_all_signals()
    protocolo = await check_protocolo_cero(signals)
    return generate_report(score, signals, protocolo)


if __name__ == "__main__":
    import json
    report = asyncio.run(run_scoring())
    print(json.dumps(report, indent=2, ensure_ascii=False))
