# 👻 FANTASMA v1.0

## Sistema de Early Warning - Crisis Económica MXN

Sistema automatizado de monitoreo que genera un score de riesgo 0-100 para anticipar crisis cambiaria/económica en México.

## 📊 Señales Monitoreadas

### Core MXN (65 pts máx)
| Señal | Fuente | Puntos |
|-------|--------|--------|
| C1: Tipo de Cambio FIX | Banxico API | 20 |
| C2: TIIE 28 días | Banxico API | 10 |
| C3: Posiciones CFTC MXN | CFTC COT | 15 |
| C4: Reservas Internacionales | Banxico API | 10 |
| C5: Spread MX-US Yields | FRED + Banxico | 10 |

### Global Overlay (35 pts máx)
| Señal | Fuente | Puntos |
|-------|--------|--------|
| G1: VIX | FRED | 8 |
| G2: DXY Dollar Index | Yahoo Finance | 5 |
| G3: US 10Y Yield | FRED | 5 |
| G4: HY Spread Proxy | Yahoo (HYG/LQD) | 5 |
| G5: Cobre | Yahoo Finance | 5 |
| G6: Google Trends | Google Trends | 4 |
| G7: Volatilidad MXN | Calculado | 3 |

## 🚦 Niveles de Alerta

| Score | Nivel | Acción |
|-------|-------|--------|
| 0-20 | 🟢 BAJO | Normal |
| 21-40 | 🟡 MODERADO | Monitorear |
| 41-60 | 🟠 ELEVADO | Reducir exposición MXN |
| 61-80 | 🔴 ALTO | Cobertura activa |
| 81-100 | ⚫ CRÍTICO | Modo defensivo total |

## 🛠 Stack

- **Backend:** Python + FastAPI
- **Frontend:** HTML/JS estático
- **Deploy Frontend:** Vercel
- **Deploy Backend:** RPi / cualquier servidor
- **DB (opcional):** Supabase

## 🚀 Quick Start

### Frontend (Vercel)
```bash
# Deploy directo a Vercel
vercel --prod
```

### Backend (Local/RPi)
```bash
cd api
pip install -r requirements.txt

# Configurar variables de entorno
export BANXICO_TOKEN="tu_token"
export FRED_API_KEY="tu_api_key"

# Ejecutar
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📡 API Endpoints

- `GET /` - Health check
- `GET /score` - Score actual con todas las señales
- `GET /signals` - Solo las señales sin scoring
- `GET /history` - Histórico (requiere Supabase)

## 🔧 Variables de Entorno

```env
# Requeridas
BANXICO_TOKEN=xxx      # Obtener en banxico.org.mx
FRED_API_KEY=xxx       # Obtener en fred.stlouisfed.org

# Opcionales
SUPABASE_URL=xxx
SUPABASE_KEY=xxx
TELEGRAM_BOT_TOKEN=xxx
```

## 📅 Scheduler

El sistema está diseñado para ejecutarse diariamente a las **6:45 AM CT** (11:45 UTC), antes de la apertura del mercado mexicano.

Cron job recomendado:
```bash
45 6 * * * cd /path/to/fantasma/api && python -c "import asyncio; from scoring import run_scoring; print(asyncio.run(run_scoring()))"
```

## 📝 Licencia

MIT

---

**Duendes.app** 🐝
