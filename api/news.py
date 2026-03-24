"""
FANTASMA - Modulo de Noticias v2
Scoring refinado basado en propuesta de Kimi (debate multi-IA).
Queries mas enfocados, scoring 0-10, penalizaciones de ruido,
bonuses por combinaciones, detector de silencio sospechoso.

Actualizado: 23 Marzo 2026 por CD02 (propuesta Kimi)
"""
import httpx
import os
from datetime import datetime, timedelta
from typing import Dict, List

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "").strip()
NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Query enfocado — propuesta Kimi
QUERY = '("Hormuz" OR "Ormuz" OR "Iran oil export" OR "BOJ rate" OR "Banxico rate" OR "MXN funding" OR "Mexico peso carry trade unwind" OR "Brent" OR "crude oil" OR "Israel Iran" OR "USMCA review" OR "yen carry trade" OR "emerging market currency stress") AND ("Mexico" OR "México" OR "MXN" OR "Latam" OR "emerging markets")'


# ============================================================
# SCORING 0-10 — Propuesta Kimi refinada
# ============================================================

KEYWORDS_ALTA = [
    "hormuz", "ormuz", "iran oil export", "banxico rate",
    "boj rate", "mxn funding", "carry trade unwind", "peso collapse",
    "mexico currency crisis", "emerging market stress", "swap line",
    "usmca review", "julio 2026", "carry trade mexico",
]

KEYWORDS_MEDIA = [
    "brent", "crude oil", "israel iran", "yen", "japan rate",
    "mexico central bank", "tipo de cambio", "devaluacion",
    "nearshoring", "reservas banxico", "cetes", "inversion extranjera",
    "oil crisis", "petroleum", "strait",
]

KEYWORDS_BAJA = [
    "mexico economy", "latam", "emerging markets", "inflation",
    "fed rate", "dollar index", "commodities", "interest rate",
]

RUIDO = [
    "anorexia", "elecciones locales", "voto electronico", "milei",
    "saquitos de te", "perder peso", "dieta", "belleza",
    "fondos de inversion", "europa bancos", "suizos votos",
    "asteroide", "boxeo", "futbol", "karpathy", "bitcoin",
]


def score_relevancia_fantasma(titulo: str, descripcion: str) -> int:
    """Scoring 0-10 de relevancia para el Observatorio."""
    texto = (titulo + " " + (descripcion or "")).lower()
    score = 0

    for term in KEYWORDS_ALTA:
        if term in texto:
            score += 3

    for term in KEYWORDS_MEDIA:
        if term in texto:
            score += 2

    for term in KEYWORDS_BAJA:
        if term in texto:
            score += 1

    # Penalizaciones
    for term in RUIDO:
        if term in texto:
            score -= 5

    # BONUS: MXN + petroleo juntos (+4)
    if ("mxn" in texto or "peso" in texto) and ("oil" in texto or "brent" in texto or "crude" in texto):
        score += 4

    # BONUS: Mexico + timing USMCA (+3)
    if ("mexico" in texto or "méxico" in texto) and ("julio" in texto or "2026" in texto or "review" in texto):
        score += 3

    return min(max(score, 0), 10)


def get_badge(score: int) -> str:
    if score >= 9:
        return "CRITICA"
    if score >= 7:
        return "ALTA"
    if score >= 4:
        return "MEDIA"
    return "BAJA"


async def fetch_news(max_articles: int = 50) -> List[Dict]:
    """Fetch noticias con query enfocado de Kimi."""
    if not NEWSAPI_KEY:
        return []

    from_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                NEWSAPI_URL,
                params={
                    "q": QUERY,
                    "sortBy": "relevancy",
                    "from": from_date,
                    "pageSize": max_articles,
                    "apiKey": NEWSAPI_KEY,
                },
                timeout=15,
            )
            data = resp.json()
            if data.get("status") != "ok":
                return []

            articles = []
            for a in data.get("articles", []):
                title = a.get("title", "")
                desc = a.get("description", "")
                score = score_relevancia_fantasma(title, desc)
                articles.append({
                    "title": title,
                    "source": a.get("source", {}).get("name", ""),
                    "date": (a.get("publishedAt") or "")[:10],
                    "url": a.get("url", ""),
                    "score": score,
                    "badge": get_badge(score),
                    "lang": "es" if any(c in title.lower() for c in ["ñ", "ó", "á", "é", "í", "ú"]) else "en",
                })

            # Filter score >= 4, sort by score desc
            articles = [a for a in articles if a["score"] >= 4]
            articles.sort(key=lambda x: -x["score"])
            return articles

        except Exception as e:
            return [{"error": str(e)}]


async def get_news_digest() -> Dict:
    """
    Digest de noticias con scoring Kimi + detector de silencio sospechoso.
    """
    articles = await fetch_news(50)
    clean = [a for a in articles if "error" not in a]

    # Detector de silencio sospechoso
    silencio = None
    if len(clean) == 0:
        silencio = "SIN NOTICIAS RELEVANTES en 48h. Si indices estan en alerta, el silencio es sospechoso."

    criticas = [a for a in clean if a["score"] >= 9]
    altas = [a for a in clean if a["score"] >= 7]

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total": len(clean),
        "criticas": len(criticas),
        "altas": len(altas),
        "silencio_sospechoso": silencio,
        "articles": clean[:10],
    }
