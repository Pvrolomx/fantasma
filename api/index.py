"""
FANTASMA / OBSERVATORIO - Vercel Serverless Entry Point
"""
from http.server import BaseHTTPRequestHandler
import json
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from scoring import run_scoring


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            report = asyncio.run(run_scoring())
            self.wfile.write(json.dumps(report, ensure_ascii=False).encode())
        except Exception as e:
            error = {"error": str(e), "service": "OBSERVATORIO v2"}
            self.wfile.write(json.dumps(error).encode())
