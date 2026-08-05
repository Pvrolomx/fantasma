"""
FANTASMA / OBSERVATORIO - Motor de Scoring v2
5 Modulos: Core MXN (75) + Global (63) + Ormuz (55) + Mexico (30) + Friccion (25) = 258 pts
Score normalizado a 0-100.
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Tuple

from signals import (
    get_g13_cftc_momentum, get_o6_freight,
    get_g12_yen_pressure, get_c7_cetes_extranjeros, get_carry_trade_real,
    get_g8_carry_trade,
    get_g9_swap_lines, get_g10_interbank, get_g11_dragon, get_c6_contrarian,
    get_c1_fix, get_c2_tiie, get_c3_cftc, get_c4_reservas, get_c5_spread,
    get_g1_vix, get_g2_dxy, get_g3_us10y, get_g4_hy_spread, get_g5_copper,
    get_g6_google_trends, get_g7_volatility, get_fed_funds_rate,
    get_o1_brent, get_o2_gas_europe, get_o3_usdchf, get_o4_sofr, get_o5_war_risk,
    get_m1_usdmxn, get_m2_corn, get_m3_urea,
    get_f1_usdt_p2p, get_f2_oro_fisico, get_f3_tech_blue, get_f4_remesa_spread, get_f4_remesa_spread,
)
from protocolo_cero import check_protocolo_cero

ALERT_LEVELS = {
    (0, 20): {"level": "BAJO", "emoji": "🟢", "action": "Normal"},
    (21, 40): {"level": "MODERADO", "emoji": "🟡", "action": "Monitorear"},
    (41, 60): {"level": "ELEVADO", "emoji": "🟠", "action": "Reducir exposicion MXN"},
    (61, 80): {"level": "ALTO", "emoji": "🔴", "action": "Cobertura activa"},
    (81, 100): {"level": "CRITICO", "emoji": "⚫", "action": "Modo defensivo total"},
}

MAX_RAW_SCORE = 263  # G14 degradado a informativo 01-ago-2026 (no suma; ver tests/g14_minitest.py)


def get_alert_level(score: int) -> Dict:
    for (low, high), info in ALERT_LEVELS.items():
        if low <= score <= high:
            return info
    return ALERT_LEVELS[(81, 100)]


# --- P5: deteccion de dato rancio (CD02, 12-jul-2026) ---
# Los mercados cierran vie 13:00 CST y reabren dom 17:00 CST.
# El cron corre TODOS los dias 6:45 CST, incluidos sab y dom.
# Sin esta marca, el JSON de fin de semana sirve datos del ultimo cierre
# con fecha de hoy y alert_level BAJO, como si hubiera medido algo.
# NO apagamos el cron: eso rompe la serie historica. El archivo se DECLARA rancio.
def get_data_staleness() -> dict:
    """Marca si el snapshot corre sobre datos del ultimo cierre en vez de datos vivos."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/Mexico_City"))
    except Exception:
        # Fallback: UTC-6 aprox. Solo afecta el borde de medianoche; el cron
        # corre 6:45 CST, muy lejos de ese borde.
        from datetime import timedelta
        now = datetime.utcnow() - timedelta(hours=6)

    wd = now.weekday()  # 0=lunes ... 5=sabado, 6=domingo
    if wd == 5:
        return {
            "is_stale": True,
            "reason": "WEEKEND_SABADO",
            "note": "Mercados cerrados. Datos del ultimo cierre (viernes). El score NO es una medicion de hoy.",
            "last_close": "viernes",
            "checked_local": now.isoformat(),
        }
    if wd == 6:
        return {
            "is_stale": True,
            "reason": "WEEKEND_DOMINGO",
            "note": "Mercados cerrados. Datos del ultimo cierre (viernes). El score NO es una medicion de hoy.",
            "last_close": "viernes",
            "checked_local": now.isoformat(),
        }
    return {
        "is_stale": False,
        "reason": "DIA_HABIL",
        "note": "Datos vivos.",
        "last_close": None,
        "checked_local": now.isoformat(),
    }


async def collect_all_signals() -> Tuple[int, List[Dict]]:
    signals = []
    total_score = 0
    fed_rate = await get_fed_funds_rate()

    tasks = [
        # Module 1: Core MXN (75 pts max)
        ("C1_FIX", get_c1_fix()),
        ("C2_TIIE", get_c2_tiie(fed_rate)),
        ("C3_CFTC", get_c3_cftc()),
        ("C4_RESERVAS", get_c4_reservas()),
        ("C5_SPREAD", get_c5_spread()),
        # Module 2: Global Overlay (63 pts max)
        ("G1_VIX", get_g1_vix()),
        ("G2_DXY", get_g2_dxy()),
        ("G3_US10Y", get_g3_us10y()),
        ("G4_HY_SPREAD", get_g4_hy_spread()),
        ("G5_COPPER", get_g5_copper()),
        ("G6_TRENDS", get_g6_google_trends()),
        ("G7_VOL", get_g7_volatility()),
        ("G8_CARRY", get_g8_carry_trade()),
        ("G9_SWAPS", get_g9_swap_lines()),
        ("G10_INTERBANK", get_g10_interbank()),
        ("G11_DRAGON", get_g11_dragon()),
        ("G12_YEN_PRESSURE", get_g12_yen_pressure()),
        ("G13_CFTC_MOM", get_g13_cftc_momentum()),
        # Module 3: Ormuz / Coreografia (55 pts max)
        ("O1_BRENT", get_o1_brent()),
        ("O2_GAS_EU", get_o2_gas_europe()),
        ("O3_USDCHF", get_o3_usdchf()),
        ("O4_SOFR", get_o4_sofr()),
        ("O5_WAR_RISK", get_o5_war_risk()),
        ("O6_FREIGHT", get_o6_freight()),
        # Module 4: Mexico / Impacto Local (30 pts max)
        ("M1_USDMXN", get_m1_usdmxn()),
        ("M2_CORN", get_m2_corn()),
        ("M3_UREA", get_m3_urea()),
        ("C6_CONTRARIAN", get_c6_contrarian()),
        ("C7_CETES_NR", get_c7_cetes_extranjeros()),
        # Module 5: Friccion Real (30 pts max)
        ("F1_USDT_P2P", get_f1_usdt_p2p()),
        ("F2_ORO_FISICO", get_f2_oro_fisico()),
        ("F3_TECH_BLUE", get_f3_tech_blue()),
        ("F4_REMESA", get_f4_remesa_spread()),
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

    # PROTOCOLO 0 DEGRADADO A INFORMATIVO (05-ago-2026).
    # Antes imponia un PISO al score via Indice de Manipulacion (anclado a Brent).
    # tests/test_tercios_p1.py: ni Brent ni DXY explican al peso sobre retornos
    # (r global ~0.04); el indice inflaba el numero con ruido (hoy forzaba 28
    # sobre un raw de ~13). Protocolo 0 ahora solo es contexto; NO toca el score.

    alert = get_alert_level(normalized)

    core = [s for s in signals if s.get("signal", "").startswith("C")]
    glob = [s for s in signals if s.get("signal", "").startswith("G")]
    ormuz = [s for s in signals if s.get("signal", "").startswith("O")]
    mexico = [s for s in signals if s.get("signal", "").startswith("M")]
    friccion = [s for s in signals if s.get("signal", "").startswith("F")]

    active = [s for s in signals if s.get("score", 0) > 0]

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "data_staleness": get_data_staleness(),
        "total_score": normalized,
        "raw_score": score_raw,
        "max_raw": MAX_RAW_SCORE,
        "alert_level": alert["level"],
        "alert_emoji": alert["emoji"],
        "recommended_action": alert["action"],
        "protocolo_0": protocolo,
        "modules": {
            "core_mxn": {"score": sum(s.get("score", 0) for s in core), "max": 75, "signals": core},
            "global_overlay": {"score": sum(s.get("score", 0) for s in glob), "max": 71, "signals": glob},
            "ormuz_coreografia": {"score": sum(s.get("score", 0) for s in ormuz), "max": 55, "signals": ormuz},
            "mexico_local": {"score": sum(s.get("score", 0) for s in mexico), "max": 30, "signals": mexico},
            "friccion_real": {"score": sum(s.get("score", 0) for s in friccion), "max": 30, "signals": friccion},
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
