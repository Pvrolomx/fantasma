"""
FANTASMA / OBSERVATORIO - News Vercel Endpoint
Serves /api/news
"""
from http.server import BaseHTTPRequestHandler
import json
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from news import get_news_digest


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            result = asyncio.run(get_news_digest())
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())
        except Exception as e:
            error = {"error": str(e)}
            self.wfile.write(json.dumps(error).encode())
