"""
FANTASMA Alert Endpoint v3
Email minimalista (score + link) + Telegram (score + senales + link).
Cron: 6:45 AM PV (12:45 UTC)
Actualizado: 22 Apr 2026 por CD71
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
from datetime import datetime

RESEND_API_KEY = "re_3TjH9vNV_ABkKQZHxufyPo9NXxWyPSihz"
RESEND_URL = "https://api.resend.com/emails"
ALERT_TO = "pvrolomx@yahoo.com.mx"
ALERT_FROM = "FANTASMA Observatorio <info@expatadvisormx.com>"
DASHBOARD = "https://fantasma.duendes.app"

BOT_TOKEN = "8498803967:AAEeq_jSQwOiWDXWLBYXXpzep18MVrCebj8"
CHAT_ID = "6392026932"

CRITICAL_THRESHOLDS = {
    "F1_USDT_P2P": {"field": "spread_buy_pct", "threshold": 2.0, "msg": "Fuga de capital via crypto P2P"},
    "F3_TECH_BLUE": {"field": "spread_pct", "threshold": 15.0, "msg": "Apple precifica devaluacion fuerte"},
    "O1_BRENT": {"field": "value", "threshold": 110.0, "msg": "Petroleo en crisis"},
    "G1_VIX": {"field": "value", "threshold": 35.0, "msg": "Panico en mercados"},
    "C1_FIX": {"field": "daily_change_pct", "threshold": 2.0, "msg": "Peso en caida libre"},
}


def get_score():
    try:
        req = urllib.request.Request(DASHBOARD + "/api/score")
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return None


def send_email(subject, message):
    payload = json.dumps({
        "from": ALERT_FROM,
        "to": [ALERT_TO],
        "subject": subject,
        "text": message,
    }).encode()
    req = urllib.request.Request(
        RESEND_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + RESEND_API_KEY}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def send_telegram(text):
    try:
        payload = json.dumps({
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def check_critical_signals(data):
    alerts = []
    all_signals = []
    for mod in data.get("modules", {}).values():
        all_signals.extend(mod.get("signals", []))
    for sig_name, config in CRITICAL_THRESHOLDS.items():
        for s in all_signals:
            if s.get("signal") == sig_name:
                val = s.get(config["field"])
                if val is not None and val > config["threshold"]:
                    alerts.append({"signal": sig_name, "value": val,
                                   "threshold": config["threshold"], "msg": config["msg"]})
    return alerts


def level_emoji(score):
    if score >= 60: return "🔴"
    if score >= 40: return "🟡"
    return "🟢"


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
        action = data.get("recommended_action", "")
        em = level_emoji(score)
        today = datetime.utcnow().strftime("%d/%m/%Y")

        # Active signals
        active = data.get("active_details", [])
        active_names = [s.get("signal", "?") for s in active]

        # Dias en rojo
        dr = data.get("dias_rojo", {}).get("summary", {})
        red_count = dr.get("currently_red", 0)
        red_total = dr.get("total_monitored", 0)

        # --- EMAIL: una sola linea + link ---
        if score >= 60:
            email_subj = f"🚨 FANTASMA {score}/100 — {level} — ACCION REQUERIDA"
        elif score >= 40:
            email_subj = f"⚠️ FANTASMA {score}/100 — {level}"
        else:
            email_subj = f"✅ FANTASMA {score}/100 — {level}"

        email_body = f"{em} Score: {score}/100 — {level}\n{DASHBOARD}"
        send_email(email_subj, email_body)

        # --- TELEGRAM: score + senales activas + link ---
        tg_lines = [f"{em} *FANTASMA* — {today}",
                    f"Score: *{score}/100* — {level}",
                    f"Accion: {action}"]

        if active_names:
            tg_lines.append(f"Senales: {', '.join(active_names)}")

        tg_lines.append(f"Dias rojo: {red_count}/{red_total}")
        tg_lines.append(f"[Ver dashboard]({DASHBOARD})")

        # Si hay criticas, agregar alerta
        critical = check_critical_signals(data)
        if critical:
            tg_lines.insert(1, "🚨 *ALERTA CRITICA*")
            for c in critical:
                tg_lines.append(f"⚠️ {c['signal']}: {c['value']} — {c['msg']}")

        send_telegram("\n".join(tg_lines))

        results["done"] = True
        results["score"] = score
        self.wfile.write(json.dumps(results, ensure_ascii=False).encode())
