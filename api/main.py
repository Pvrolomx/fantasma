"""
FANTASMA / OBSERVATORIO API v2.0
Sistema de Early Warning + Modulo de Coherencia

Endpoints:
- GET /           -> Health check
- GET /score      -> Score completo con 4 modulos + Protocolo 0
- GET /signals    -> Solo senales sin scoring
- GET /protocolo  -> Solo Protocolo 0 (coherencia)
- GET /history    -> Historico (requiere Supabase)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import os

from scoring import run_scoring, collect_all_signals, get_alert_level
from protocolo_cero import check_protocolo_cero
from history import save_snapshot, load_history, get_daily_summary

app = FastAPI(
    title="FANTASMA / OBSERVATORIO API",
    description="Early Warning System + Protocolo 0 de Coherencia",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "FANTASMA / OBSERVATORIO",
        "version": "2.0.0",
        "modules": ["core_mxn", "global_overlay", "ormuz_coreografia", "mexico_local", "protocolo_0"],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/score")
async def get_score():
    try:
        report = await run_scoring()
        try:
            save_snapshot(report)
        except Exception:
            pass  # Don't fail score if history save fails
        return JSONResponse(content=report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/signals")
async def get_signals():
    try:
        score, signals = await collect_all_signals()
        return {"timestamp": datetime.utcnow().isoformat(), "signals": signals, "raw_score": score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/protocolo")
async def get_protocolo():
    """Protocolo 0: Verifica coherencia de datos."""
    try:
        _, signals = await collect_all_signals()
        protocolo = await check_protocolo_cero(signals)
        return JSONResponse(content=protocolo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alert/{score}")
async def check_alert(score: int):
    if not 0 <= score <= 100:
        raise HTTPException(status_code=400, detail="Score must be between 0 and 100")
    alert = get_alert_level(score)
    return {"score": score, "level": alert["level"], "emoji": alert["emoji"], "action": alert["action"]}


@app.get("/history")
async def get_history(days: int = 30):
    """Historico de scores - ultimos N dias."""
    try:
        data = load_history(days=days)
        summary = get_daily_summary()
        return {"days_requested": days, "data_points": len(data), "history": data, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
