"""
FANTASMA - Señales CFTC
C3: Posiciones Especulativas MXN
Fuente: CFTC COT Reports (Commitment of Traders)
"""
import httpx
from datetime import datetime
from typing import Dict, Tuple
import re

# CFTC publica los viernes, datos del martes anterior
COT_URL = "https://www.cftc.gov/dea/futures/financial_lf.htm"

async def fetch_cftc_mxn() -> Dict:
    """
    Obtiene posiciones netas de MXN del reporte COT.
    Mexican Peso - CME Code: 095741
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(COT_URL, timeout=30)
            html = response.text
            
            # Buscar línea de Mexican Peso
            # Formato típico: MEXICAN PESO - CHICAGO MERCANTILE EXCHANGE
            lines = html.split('\n')
            mxn_data = None
            
            for i, line in enumerate(lines):
                if 'MEXICAN PESO' in line.upper():
                    # Las siguientes líneas contienen los datos
                    # Formato: Long, Short, Spreading, etc.
                    mxn_data = lines[i:i+10]
                    break
            
            if mxn_data:
                # Parsear posiciones (esto es simplificado)
                # En producción usar regex más robusto
                numbers = re.findall(r'[\d,]+', ' '.join(mxn_data))
                if len(numbers) >= 4:
                    # Típicamente: Long Speculative, Short Speculative
                    long_spec = int(numbers[0].replace(',', ''))
                    short_spec = int(numbers[1].replace(',', ''))
                    net_position = long_spec - short_spec
                    return {
                        "long": long_spec,
                        "short": short_spec,
                        "net": net_position,
                        "net_billions": net_position * 500000 / 1e9  # Cada contrato = 500k MXN
                    }
            
            return {"error": "Could not parse MXN data"}
            
        except Exception as e:
            print(f"Error fetching CFTC: {e}")
            return {"error": str(e)}

async def get_c3_cftc() -> Tuple[float, Dict]:
    """
    C3: Posiciones CFTC MXN (15 pts max)
    - Net short >$5B → 10 pts
    - Net short >$8B → 15 pts
    - Cambio semanal >$2B hacia short → 5 pts
    """
    data = await fetch_cftc_mxn()
    
    if "error" in data:
        # Usar valores de fallback/cache en producción
        return 0, {"signal": "C3_CFTC", "error": data["error"]}
    
    net_billions = data.get("net_billions", 0)
    
    score = 0
    # Net short significa posición neta negativa
    if net_billions < -8:
        score = 15
    elif net_billions < -5:
        score = 10
    
    return score, {
        "signal": "C3_CFTC",
        "net_contracts": data.get("net", 0),
        "net_billions_usd": round(net_billions, 2),
        "long_contracts": data.get("long", 0),
        "short_contracts": data.get("short", 0),
        "score": score,
        "max_score": 15
    }

# Alternativa: usar datos ya parseados de Quandl/Nasdaq Data Link
async def fetch_cftc_quandl(api_key: str = None) -> Dict:
    """
    Alternativa usando Nasdaq Data Link (antes Quandl)
    Dataset: CFTC/098662_FO_L_ALL - Mexican Peso
    """
    if not api_key:
        return {"error": "No API key"}
    
    url = f"https://data.nasdaq.com/api/v3/datasets/CFTC/098662_FO_L_ALL.json?api_key={api_key}&rows=5"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30)
            data = response.json()
            dataset = data.get("dataset", {})
            latest = dataset.get("data", [[]])[0]
            
            if latest:
                # Índices dependen del dataset específico
                return {
                    "date": latest[0],
                    "open_interest": latest[1],
                    "long_spec": latest[2],
                    "short_spec": latest[3],
                    "net": latest[2] - latest[3]
                }
            return {"error": "No data"}
        except Exception as e:
            return {"error": str(e)}
