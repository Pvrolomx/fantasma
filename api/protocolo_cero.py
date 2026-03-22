"""
FANTASMA / OBSERVATORIO - Protocolo 0: Modulo de Coherencia
Detecta cuando los datos oficiales no cuadran con la realidad.
Si SOFR esta plano pero USD/CHF se mueve >1%, alguien miente.

Check 5 (Indice de Manipulacion): Propuesta original de Mistral AI,
adaptada al contexto del Observatorio. Mide el desfase entre el
impacto esperado del petroleo en el tipo de cambio vs el impacto real.
"""
from typing import Dict, Tuple


# Baselines pre-crisis para el Indice de Manipulacion
BRENT_BASELINE = 65.0   # Pre-guerra Ormuz
USDMXN_BASELINE = 17.5  # Nivel "normal" del peso
VIX_FLOOR = 12.0         # VIX minimo historico para evitar division por cero


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
    usdmxn_data = next((s for s in signals if s.get("signal") == "M1_USDMXN"), None)

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

    # Check 5: INDICE DE MANIPULACION (propuesta Mistral, adaptada)
    # Formula: (Var% Brent vs baseline - Var% USDMXN vs baseline) / (VIX / VIX_FLOOR)
    # Valores > 1.5 = Alta probabilidad de manipulacion del tipo de cambio
    # Logica: Si el petroleo sube 50% pero el peso solo 2%, alguien esta
    # conteniendo artificialmente el impacto en el tipo de cambio.
    manipulation_index = None
    if brent_data and usdmxn_data and vix_data:
        brent_val = brent_data.get("value", 0)
        usdmxn_val = usdmxn_data.get("value", 0)
        vix_val = max(vix_data.get("value", 0), VIX_FLOOR)

        if brent_val > 0 and usdmxn_val > 0:
            brent_var = ((brent_val - BRENT_BASELINE) / BRENT_BASELINE) * 100
            usdmxn_var = ((usdmxn_val - USDMXN_BASELINE) / USDMXN_BASELINE) * 100
            vix_normalized = vix_val / VIX_FLOOR

            if vix_normalized > 0:
                manipulation_index = round((brent_var - usdmxn_var) / vix_normalized, 2)

            severity_mi = "LOW"
            if manipulation_index is not None:
                if manipulation_index > 25:
                    severity_mi = "EXTREME"
                elif manipulation_index > 15:
                    severity_mi = "HIGH"
                elif manipulation_index > 8:
                    severity_mi = "MEDIUM"

                if manipulation_index > 8:
                    alerts.append({
                        "type": "MANIPULATION",
                        "name": "INDICE_MANIPULACION",
                        "severity": severity_mi,
                        "message": "Desfase anormal entre petroleo y tipo de cambio. Indice: " + str(manipulation_index),
                        "index_value": manipulation_index,
                        "brent_var_pct": round(brent_var, 1),
                        "usdmxn_var_pct": round(usdmxn_var, 1),
                        "vix": vix_val,
                        "interpretation": "El petroleo ha subido " + str(round(brent_var, 1)) + "% desde su baseline pero el USDMXN solo " + str(round(usdmxn_var, 1)) + "%"
                    })

    protocolo_active = len(alerts) > 0
    severity = "NORMAL"
    if any(a["severity"] in ("HIGH", "EXTREME") for a in alerts):
        severity = "ALERTA ROJA - Datos no coherentes"
    elif any(a["severity"] == "MEDIUM" for a in alerts):
        severity = "PRECAUCION - Divergencias detectadas"

    result = {
        "protocolo_0_active": protocolo_active,
        "severity": severity,
        "alerts_count": len(alerts),
        "alerts": alerts,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }

    # Incluir indice de manipulacion siempre (aunque no sea alerta)
    if manipulation_index is not None:
        result["manipulation_index"] = {
            "value": manipulation_index,
            "threshold_medium": 8,
            "threshold_high": 15,
            "threshold_extreme": 25,
        }

    return result
