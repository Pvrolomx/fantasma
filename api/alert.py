"""
FANTASMA Alert Endpoint v2
Briefing diario + alertas criticas por senal individual.

Cron: 6:45 AM PV (12:45 UTC) via Vercel
Email: pvrolomx@yahoo.com.mx via email.duendes.app

2 modos:
1. BRIEFING DIARIO: resumen ejecutivo siempre (score, senales activas, dias rojo, cambios)
2. ALERTA CRITICA: email adicional inmediato si una senal cruza umbral peligroso

Implementado: 29 Marzo 2026 por CD03
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime

RESEND_API_KEY = "re_3TjH9vNV_ABkKQZHxufyPo9NXxWyPSihz"
RESEND_URL = "https://api.resend.com/emails"
ALERT_TO = "pvrolomx@yahoo.com.mx"
ALERT_FROM = "FANTASMA Observatorio <info@expatadvisormx.com>"

# Umbrales criticos - si se cruzan, email ADICIONAL con asunto de emergencia
CRITICAL_THRESHOLDS = {
    "F1_USDT_P2P": {"field": "spread_buy_pct", "threshold": 2.0, "msg": "Fuga de capital via crypto P2P"},
    "F3_TECH_BLUE": {"field": "spread_pct", "threshold": 15.0, "msg": "Apple precifica devaluacion fuerte"},
    "O1_BRENT": {"field": "value", "threshold": 110.0, "msg": "Petroleo en crisis"},
    "G1_VIX": {"field": "value", "threshold": 35.0, "msg": "Panico en mercados"},
    "C1_FIX": {"field": "daily_change_pct", "threshold": 2.0, "msg": "Peso en caida libre"},
}


def get_score():
    """Fetch current score from API"""
    try:
        req = urllib.request.Request("https://fantasma.duendes.app/api/score")
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return None


def send_email(subject, message):
    """Send email via Resend API from info@expatadvisormx.com."""
    payload = json.dumps({
        "from": ALERT_FROM,
        "to": [ALERT_TO],
        "subject": subject,
        "text": message,
    }).encode()
    req = urllib.request.Request(
        RESEND_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + RESEND_API_KEY,
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_critical_signals(data):
    """Check if any signal crossed a critical threshold."""
    alerts = []
    all_signals = []
    for mod in data.get("modules", {}).values():
        all_signals.extend(mod.get("signals", []))

    for sig_name, config in CRITICAL_THRESHOLDS.items():
        for s in all_signals:
            if s.get("signal") == sig_name:
                val = s.get(config["field"])
                if val is not None and val > config["threshold"]:
                    alerts.append({
                        "signal": sig_name,
                        "value": val,
                        "threshold": config["threshold"],
                        "msg": config["msg"],
                    })
    return alerts


def build_briefing(data):
    """Build the daily briefing email."""
    score = data.get("total_score", 0)
    level = data.get("alert_level", "?")
    emoji = data.get("alert_emoji", "")
    action = data.get("recommended_action", "")
    raw = data.get("raw_score", 0)
    max_raw = data.get("max_raw", 263)
    ts = data.get("timestamp", "")[:16]

    # Module scores
    mods = data.get("modules", {})
    mod_lines = []
    for name, display in [
        ("core_mxn", "Core MXN"),
        ("global_overlay", "Global"),
        ("ormuz_coreografia", "Ormuz"),
        ("mexico_local", "Mexico"),
        ("friccion_real", "Friccion"),
    ]:
        m = mods.get(name, {})
        mod_lines.append(f"  {display}: {m.get('score',0)}/{m.get('max',0)}")

    # Active signals with values
    active = data.get("active_details", [])
    active_lines = []
    for s in active:
        sig = s.get("signal", "?")
        sc = s.get("score", 0)
        mx = s.get("max_score", 0)
        # Get the most relevant value
        val = s.get("value", s.get("spread_buy_pct", s.get("spread_pct",
              s.get("estimated_premium_pct", s.get("spread_bps", "?")))))
        active_lines.append(f"  {sig}: {val} ({sc}/{mx} pts)")

    # Protocolo 0
    p0 = data.get("protocolo_0", {})
    p0_text = "Normal"
    if p0.get("protocolo_0_active"):
        p0_text = p0.get("severity", "ACTIVO")
        mi = p0.get("manipulation_index", {})
        if mi:
            p0_text += f" | Manipulacion: {mi.get('value', '?')}"

    # Dias en rojo summary
    dr = data.get("dias_rojo", {})
    dr_summary = dr.get("summary", {})
    red_count = dr_summary.get("currently_red", 0)
    red_total = dr_summary.get("total_monitored", 0)
    red_signals = dr_summary.get("red_signals", [])
    chronic = dr_summary.get("chronic_signals", [])

    red_details = []
    for sig_name in red_signals:
        sig_data = dr.get("signals", {}).get(sig_name, {})
        days = sig_data.get("consecutive_days", 0)
        label = sig_data.get("label", sig_name)
        red_details.append(f"  {label}: {days}d en rojo")

    # Build message
    msg = f"""{emoji} BRIEFING FANTASMA — {datetime.utcnow().strftime('%d/%m/%Y')}
{'='*50}

SCORE: {score}/100 {level}
Raw: {raw}/{max_raw} | Accion: {action}

MODULOS:
{chr(10).join(mod_lines)}

PROTOCOLO 0: {p0_text}

SENALES ACTIVAS ({len(active)}):
{chr(10).join(active_lines) if active_lines else '  Ninguna'}

DIAS EN ROJO ({red_count}/{red_total}):
{chr(10).join(red_details) if red_details else '  Todo limpio'}
"""

    if chronic:
        msg += f"\n⚠️ CRONICAS (>30d en rojo): {', '.join(chronic)}\n"

    # Friction module highlight
    fr = mods.get("friccion_real", {})
    fr_sigs = fr.get("signals", [])
    if fr_sigs:
        msg += f"\nFRICCION REAL ({fr.get('score',0)}/{fr.get('max',30)}):\n"
        for s in fr_sigs:
            sig = s.get("signal", "?")
            sp = s.get("spread_buy_pct", s.get("spread_pct",
                 s.get("estimated_premium_pct", "?")))
            status = s.get("status", "")
            accel = s.get("acceleration", {})
            trend = accel.get("trend", "")
            msg += f"  {sig}: {sp}% | {status}"
            if trend and trend != "SIN DATOS":
                msg += f" | {trend}"
            msg += "\n"

    msg += f"""
{'='*50}
Dashboard: https://fantasma.duendes.app
"""
    return msg


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        data = get_score()
        results = {"timestamp": datetime.utcnow().isoformat()}

        if not data:
            results["error"] = "Could not fetch score"
            self.wfile.write(json.dumps(results).encode())
            return

        score = data.get("total_score", 0)
        level = data.get("alert_level", "?")

        # 1. ALWAYS send daily briefing
        briefing = build_briefing(data)
        emoji = data.get("alert_emoji", "")

        if score >= 60:
            subj = f"🚨 FANTASMA ALTO: {score}/100 — ACCION REQUERIDA"
        elif score >= 40:
            subj = f"⚠️ FANTASMA ELEVADO: {score}/100 — Monitorear"
        else:
            subj = f"{emoji} FANTASMA Briefing: {score}/100 {level}"

        briefing_result = send_email(subj, briefing)
        results["briefing"] = {"sent": True, "score": score, "level": level}

        # 2. Check critical signals — send ADDITIONAL urgent email if triggered
        critical = check_critical_signals(data)
        if critical:
            crit_lines = []
            for c in critical:
                crit_lines.append(f"🚨 {c['signal']}: {c['value']} (umbral: {c['threshold']})")
                crit_lines.append(f"   → {c['msg']}")

            crit_msg = f"""🚨🚨🚨 ALERTA CRITICA FANTASMA 🚨🚨🚨

{chr(10).join(crit_lines)}

Score actual: {score}/100 {level}

ACCION INMEDIATA REQUERIDA.
Dashboard: https://fantasma.duendes.app
"""
            crit_subj = f"🚨🚨 CRITICO: {critical[0]['msg']} — {critical[0]['signal']}={critical[0]['value']}"
            crit_result = send_email(crit_subj, crit_msg)
            results["critical_alert"] = {
                "sent": True,
                "signals": [c["signal"] for c in critical],
            }

        self.wfile.write(json.dumps(results, ensure_ascii=False).encode())
