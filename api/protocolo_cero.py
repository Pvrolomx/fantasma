"""
FANTASMA / OBSERVATORIO - Protocolo 0: Modulo de Coherencia
Detecta cuando los datos oficiales no cuadran con la realidad.
Si SOFR esta plano pero USD/CHF se mueve >1%, alguien miente.
"""
from typing import Dict, Tuple


async def check_protocolo_cero(signals: list) -> Dict:
    """
    Protocolo 0: Verifica coherencia entre senales.
    Busca divergencias que indican manipulacion o informacion incompleta.
    """
    alerts = []
    sofr_data = next((s for s in signals if s.get("signal") == "O4_SOFR"), None)
    chf_data = next((s for s in signals if s.get("signal") == "O3_USDCHF"), None)
    brent_data = next((s for s in signals if s.get("signal") == "O1_BRENT"), None)
    vix_data = next((s for s in signals if s.get("signal") == "G1_VIX"), None)
    dxy_data = next((s for s in signals if s.get("signal") == "G2_DXY"), None)
    fix_data = next((s for s in signals if s.get("signal") == "C1_FIX"), None)

    # Check 1: SOFR stable but CHF moving = hidden stress
    if sofr_data and chf_data:
        sofr_stable = abs(sofr_data.get("weekly_change_bps", 0)) < 5
        chf_moving = abs(chf_data.get("weekly_change_pct", 0)) > 1
        if sofr_stable and chf_moving:
            alerts.append({
                "type": "DIVERGENCE",
                "name": "SOFR_vs_CHF",
                "severity": "HIGH",
                "message": "SOFR estable pero CHF en movimiento. Estres oculto en el sistema.",
                "sofr_change_bps": sofr_data.get("weekly_change_bps", 0),
                "chf_change_pct": chf_data.get("weekly_change_pct", 0)
            })

    # Check 2: Brent spiking but VIX calm = market complacency
    if brent_data and vix_data:
        brent_hot = brent_data.get("value", 0) > 90
        vix_calm = vix_data.get("value", 0) < 20
        if brent_hot and vix_calm:
            alerts.append({
                "type": "COMPLACENCY",
                "name": "BRENT_vs_VIX",
                "severity": "MEDIUM",
                "message": "Petroleo en crisis pero VIX tranquilo. Mercado no esta priceando el riesgo.",
                "brent": brent_data.get("value", 0),
                "vix": vix_data.get("value", 0)
            })

    # Check 3: DXY rising but MXN stable = artificial peso support
    if dxy_data and fix_data:
        dxy_value = dxy_data.get("value", 0)
        fix_change = abs(fix_data.get("daily_change_pct", 0))
        if dxy_value > 105 and fix_change < 0.5:
            alerts.append({
                "type": "ARTIFICIAL_SUPPORT",
                "name": "DXY_vs_MXN",
                "severity": "MEDIUM",
                "message": "Dolar subiendo globalmente pero peso estable. Posible intervencion Banxico.",
                "dxy": dxy_value,
                "fix_daily_change": fix_change
            })

    # Check 4: Oil crisis but no MXN impact = delayed reaction
    if brent_data and fix_data:
        brent_crisis = brent_data.get("value", 0) > 100
        mxn_calm = abs(fix_data.get("daily_change_pct", 0)) < 1
        if brent_crisis and mxn_calm:
            alerts.append({
                "type": "DELAYED_IMPACT",
                "name": "BRENT_vs_MXN",
                "severity": "HIGH",
                "message": "Petroleo en crisis pero MXN no reacciona. El impacto viene con retraso.",
                "brent": brent_data.get("value", 0)
            })

    protocolo_active = len(alerts) > 0
    severity = "NORMAL"
    if any(a["severity"] == "HIGH" for a in alerts):
        severity = "ALERTA ROJA - Datos no coherentes"
    elif any(a["severity"] == "MEDIUM" for a in alerts):
        severity = "PRECAUCION - Divergencias detectadas"

    return {
        "protocolo_0_active": protocolo_active,
        "severity": severity,
        "alerts_count": len(alerts),
        "alerts": alerts,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }
