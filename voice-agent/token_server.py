"""
Lightweight token server for the AURA voice frontend.
Generates LiveKit access tokens so the browser can join a room.

Run: python token_server.py
Endpoint: GET http://localhost:8082/get-token?room=aura-room&identity=user-123
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from livekit.api import AccessToken, VideoGrants
from dotenv import load_dotenv
import os
import json

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
PORT = 8082


class TokenHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/getToken":
            params = parse_qs(parsed.query)
            room = params.get("room", ["aura-voice-room"])[0]
            identity = params.get("identity", ["aura-user"])[0]

            token = (
                AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
                .with_identity(identity)
                .with_grants(VideoGrants(room_join=True, room=room))
                .to_jwt()
            )

            payload = json.dumps({
                "token": token,
                "url": LIVEKIT_URL,
            })

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(payload.encode())

        elif parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[TokenServer] {args[0]}", flush=True)


if __name__ == "__main__":
    print(f"🔑 AURA Token Server running on http://localhost:{PORT}")
    print(f"   LiveKit URL: {LIVEKIT_URL}")
    HTTPServer(("0.0.0.0", PORT), TokenHandler).serve_forever()
