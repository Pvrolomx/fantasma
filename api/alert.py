"""
FANTASMA Alert Endpoint
Verifica score y envía email si > threshold
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse

# Config
EMAIL_SERVICE = "https://email.duendes.app/api/send"
ALERT_TO = "pvrolomx@yahoo.com.mx"
THRESHOLD = 40

def get_score():
    """Fetch current score from API"""
    try:
        req = urllib.request.Request("https://fantasma.duendes.app/api")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except:
        return None

def send_alert(data):
    """Send email alert"""
    score = data.get("total_score", 0)
    level = data.get("alert_level", "DESCONOCIDO")
    emoji = data.get("alert_emoji", "⚠️")
    action = data.get("recommended_action", "Revisar")
    
    # Build signals summary
    signals_text = []
    breakdown = data.get("breakdown", {})
    for category in ["core_mxn", "global_overlay"]:
        for sig in breakdown.get(category, {}).get("signals", []):
            if sig.get("score", 0) > 0:
                signals_text.append(f"• {sig['signal']}: {sig.get('value', 'N/A')} (+{sig['score']} pts)")
    
    signals_str = "\n".join(signals_text) if signals_text else "• Sin señales activas con puntaje"
    
    message = f"""
{emoji} ALERTA FANTASMA - Score: {score}/100

Nivel: {level}
Acción recomendada: {action}

SEÑALES ACTIVAS:
{signals_str}

---
Ver dashboard: https://fantasma.duendes.app
Timestamp: {data.get('timestamp', 'N/A')}
"""

    payload = json.dumps({
        "to": ALERT_TO,
        "subject": f"{emoji} FANTASMA: {level} - Score {score}/100",
        "message": message,
        "name": "FANTASMA Alert",
        "sendFrom": "duendes.app"
    }).encode()

    req = urllib.request.Request(
        EMAIL_SERVICE,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"success": False, "error": str(e)}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Get current score
        data = get_score()
        
        if not data:
            result = {"sent": False, "reason": "Could not fetch score"}
        elif data.get("total_score", 0) >= THRESHOLD:
            email_result = send_alert(data)
            result = {
                "sent": True,
                "score": data.get("total_score"),
                "level": data.get("alert_level"),
                "email": email_result
            }
        else:
            result = {
                "sent": False,
                "reason": f"Score {data.get('total_score', 0)} below threshold {THRESHOLD}",
                "score": data.get("total_score"),
                "level": data.get("alert_level")
            }
        
        self.wfile.write(json.dumps(result, ensure_ascii=False).encode())
