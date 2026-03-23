"""
FANTASMA / OBSERVATORIO - History Vercel Endpoint
Serves /api/history?days=30
"""
from http.server import BaseHTTPRequestHandler
import json
import asyncio
import sys
import os
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))

from history import load_history, get_daily_summary


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            qs = parse_qs(urlparse(self.path).query)
            
            # Debug mode: show env var status (no values, just presence)
            if qs.get('debug', ['0'])[0] == '1':
                import os
                sk = os.getenv("SUPABASE_KEY", "")
                su = os.getenv("SUPABASE_URL", "")
                result = {
                    "supabase_key_len": len(sk),
                    "supabase_key_prefix": sk[:10] + "..." if len(sk) > 10 else "(empty)",
                    "supabase_url_len": len(su),
                    "supabase_url_prefix": su[:30] + "..." if len(su) > 30 else su,
                }
                self.wfile.write(json.dumps(result).encode())
                return
            
            days = int(qs.get('days', [30])[0])

            async def get_data():
                data = await load_history(days=days)
                summary = get_daily_summary(data)
                return {"days_requested": days, "data_points": len(data), "history": data, "summary": summary}

            result = asyncio.run(get_data())
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())
        except Exception as e:
            error = {"error": str(e)}
            self.wfile.write(json.dumps(error).encode())
