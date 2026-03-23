"""
FANTASMA - Modulo de Noticias
Scrapea titulares relevantes de NewsAPI y los presenta en el dashboard.
NO es una senal de scoring - es contexto informativo.
Busca: peso mexicano, Banxico, carry trade, Ormuz, petroleo, tipo de cambio.

Agregado: 23 Marzo 2026 por CD02
"""
import httpx
import os
from datetime import datetime, timedelta
from typing import Dict, List

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "").strip()
NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Queries relevantes para el Observatorio
QUERIES = {
    "en": '(Mexico peso OR Banxico OR USDMXN OR "carry trade" Mexico OR Ormuz petroleum oil)',
    "es": '(peso mexicano OR Banxico OR "tipo de cambio" OR petroleo Ormuz OR "carry trade")',
}


# Palabras clave para clasificar relevancia
KEYWORDS_HIGH = ["banxico", "carry trade", "ormuz", "peso mexicano", "usdmxn", "devaluacion", "tipo de cambio", "reservas internacionales"]
KEYWORDS_MEDIUM = ["petroleo", "brent", "iran", "japon", "yen", "fed", "tasas", "inflacion mexico", "nearshoring"]


def _score_relevance(title: str, description: str) -> int:
    """Score 0-3 de relevancia para el Observatorio."""
    text = (title + " " + (description or "")).lower()
    score = 0
    for kw in KEYWORDS_HIGH:
        if kw in text:
            score += 2
    for kw in KEYWORDS_MEDIUM:
        if kw in text:
            score += 1
    return min(score, 3)


async def fetch_news(lang: str = "en", max_articles: int = 10) -> List[Dict]:
    """Fetch noticias relevantes de NewsAPI."""
    if not NEWSAPI_KEY:
        return [{"error": "No NEWSAPI_KEY configured"}]

    query = QUERIES.get(lang, QUERIES["en"])
    from_date = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                NEWSAPI_URL,
                params={
                    "q": query,
                    "language": lang,
                    "from": from_date,
                    "sortBy": "publishedAt",
                    "pageSize": max_articles,
                    "apiKey": NEWSAPI_KEY,
                },
                timeout=15,
            )
            data = resp.json()
            if data.get("status") != "ok":
                return [{"error": data.get("message", "NewsAPI error")}]

            articles = []
            for a in data.get("articles", []):
                title = a.get("title", "")
                desc = a.get("description", "")
                relevance = _score_relevance(title, desc)
                articles.append({
                    "title": title,
                    "source": a.get("source", {}).get("name", ""),
                    "date": (a.get("publishedAt") or "")[:10],
                    "url": a.get("url", ""),
                    "relevance": relevance,
                })

            # Sort by relevance desc, then date desc
            articles.sort(key=lambda x: (-x["relevance"], x["date"]), reverse=False)
            articles.sort(key=lambda x: -x["relevance"])
            return articles

        except Exception as e:
            return [{"error": str(e)}]


async def get_news_digest() -> Dict:
    """
    Obtiene noticias en ingles y espanol, las combina y devuelve
    un digest con las mas relevantes para el Observatorio.
    """
    en_news = await fetch_news("en", 8)
    es_news = await fetch_news("es", 8)

    # Filter out errors
    en_clean = [a for a in en_news if "error" not in a]
    es_clean = [a for a in es_news if "error" not in a]

    # Tag language
    for a in en_clean:
        a["lang"] = "en"
    for a in es_clean:
        a["lang"] = "es"

    # Combine and sort by relevance
    all_news = en_clean + es_clean
    all_news.sort(key=lambda x: -x["relevance"])

    # Top 10
    top = all_news[:10]

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_en": len(en_clean),
        "total_es": len(es_clean),
        "articles": top,
        "high_relevance": len([a for a in top if a["relevance"] >= 2]),
    }
