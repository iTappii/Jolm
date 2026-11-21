#!/usr/bin/env python3
"""Tiny static server WITH HTTP Range + CORS (python's http.server lacks Range; PMTiles needs it).
Usage: python3 maps/serve.py [port]   -> http://localhost:8080/demo/ (serves the maps/ dir)
"""
import json, os, re, sys
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class H(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, ETag")
        self.send_header("Access-Control-Allow-Headers", "Range, If-Match")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204); self.end_headers()

    def do_GET(self):
        native = re.fullmatch(r"/native/(jol-(?:light|dark)(?:\.en)?\.json)", self.path)
        if native:
            style = json.loads(Path("style", native.group(1)).read_text())
            port = self.server.server_port
            style["sources"]["openmaptiles"]["url"] = f"pmtiles://http://localhost:{port}/build/almaty.pmtiles"
            body = json.dumps(style, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        m = re.match(r"bytes=(\d*)-(\d*)$", rng or "")
        if not (m and os.path.isfile(path)):
            return super().do_GET()
        size = os.path.getsize(path)
        a, b = m.groups()
        start = int(a) if a else max(0, size - int(b))
        end = min(int(b), size - 1) if a and b else size - 1
        if start >= size or start > end:
            self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.end_headers(); return
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start); left = end - start + 1
            while left > 0:
                chunk = f.read(min(65536, left))
                if not chunk: break
                self.wfile.write(chunk); left -= len(chunk)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"serving {os.getcwd()} on http://localhost:{port}/demo/")
    # localhost only: dev server with CORS "*" must not be reachable from the LAN
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
