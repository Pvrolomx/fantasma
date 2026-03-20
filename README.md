# OBSERVATORIO (ex-FANTASMA) v2.0

## Panel de Control de la Realidad — Crisis 2026

Sistema de monitoreo personal que conecta la geopolitica global
con tu realidad operativa en Mexico/Puerto Vallarta.

## 4 Modulos

### M1: Pulso Macro (Core MXN + Global) — 100 pts max
- C1: Tipo de Cambio FIX (Banxico)
- C2: TIIE 28 dias
- C3: Posiciones CFTC MXN
- C4: Reservas Internacionales
- C5: Spread MX-US Yields
- G1-G7: VIX, DXY, US10Y, HY Spread, Cobre, Trends, Volatilidad

### M2: Coreografia / Ormuz — 50 pts max
- O1: Brent Crude (termometro del conflicto)
- O2: Gas Natural Europa TTF
- O3: USD/CHF (refugio suizo, fuga de capital)
- O4: SOFR (estres financiero core EEUU)
- O5: War Risk Premium (spread Brent-WTI = Ormuz premium)

### M3: Impacto Local (Mexico/PV) — 30 pts max
- M1: USD/MXN stress
- M2: Precio del Maiz (crisis alimentaria)
- M3: Fertilizantes/Urea (escasez agricola)

### Protocolo 0: Coherencia de Datos
Detecta divergencias que indican manipulacion:
- SOFR estable + CHF moviéndose = estres oculto
- Brent en crisis + VIX tranquilo = complacencia
- DXY subiendo + MXN estable = soporte artificial Banxico
- Petroleo en crisis + MXN sin reaccion = impacto retrasado

## Score: 0-100 (normalizado de 180 pts raw)
| Score | Nivel | Accion |
|-------|-------|--------|
| 0-20 | BAJO | Normal |
| 21-40 | MODERADO | Monitorear |
| 41-60 | ELEVADO | Reducir exposicion MXN |
| 61-80 | ALTO | Cobertura activa |
| 81-100 | CRITICO | Modo defensivo total |

## API Keys Requeridas

```env
BANXICO_TOKEN=xxx      # banxico.org.mx/SieAPIRest
FRED_API_KEY=xxx       # fred.stlouisfed.org
```

## Deploy
```bash
vercel --prod
```

## Cron (RPi)
```bash
# 6:45 AM CT = 12:45 UTC
45 12 * * * cd ~/repos/fantasma/api && python3 -c "import asyncio; from scoring import run_scoring; print(asyncio.run(run_scoring()))"
```

---
**Duendes.app** — El Observatorio v2
