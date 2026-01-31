"""
FANTASMA API
Sistema de Early Warning - Crisis Económica MXN

Endpoints:
- GET /           → Health check
- GET /score      → Score actual con todas las señales
- GET /signals    → Solo las señales sin scoring
- GET /history    → Histórico de scores (requiere Supabase)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import os

from scoring import run_scoring, collect_all_signals, get_alert_level

app = FastAPI(
    title="FANTASMA API",
    description="Sistema de Early Warning para Crisis Económica MXN",
    version="1.0.0"
)

# CORS para frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Health check."""
    return {
        "status": "online",
        "service": "FANTASMA",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/score")
async def get_score():
    """
    Obtiene el score actual con todas las señales.
    Este es el endpoint principal.
    """
    try:
        report = await run_scoring()
        return JSONResponse(content=report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/signals")
async def get_signals():
    """Obtiene solo las señales sin el reporte completo."""
    try:
        score, signals = await collect_all_signals()
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "signals": signals,
            "raw_score": score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alert/{score}")
async def check_alert(score: int):
    """Verifica qué nivel de alerta corresponde a un score dado."""
    if not 0 <= score <= 100:
        raise HTTPException(status_code=400, detail="Score must be between 0 and 100")
    
    alert = get_alert_level(score)
    return {
        "score": score,
        "level": alert["level"],
        "emoji": alert["emoji"],
        "action": alert["action"]
    }

# Supabase integration (opcional)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

@app.get("/history")
async def get_history(days: int = 30):
    """
    Obtiene histórico de scores.
    Requiere configuración de Supabase.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {
            "error": "Supabase not configured",
            "note": "Set SUPABASE_URL and SUPABASE_KEY environment variables"
        }
    
    # TODO: Implementar fetch de Supabase
    return {
        "message": "History endpoint - requires Supabase setup",
        "days_requested": days
    }

@app.post("/webhook/telegram")
async def telegram_webhook():
    """
    Webhook para notificaciones Telegram.
    Se activa cuando score > 40.
    """
    # TODO: Implementar integración Telegram
    return {"status": "webhook received"}

# Para desarrollo local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
