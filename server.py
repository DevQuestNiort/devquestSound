#!/usr/bin/env python3
import os
import json
import signal
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path

PORT       = int(os.environ.get("PORT", 80))
MUSIC_DIR  = os.environ.get("MUSIC_DIR", "./music")
ALSA_DEV   = os.environ.get("ALSA_DEVICE", "plughw:1,0")

state = {
    "process":     None,
    "currentFile": None,
    "isPlaying":   False,
    "isPaused":    False,
}

# ---------------------------------------------------------------------------
# Lecteur
# ---------------------------------------------------------------------------

def stop_player():
    if state["process"]:
        try:
            state["process"].terminate()
            state["process"].wait(timeout=2)
        except Exception:
            pass
        state["process"] = None
    state["isPlaying"]   = False
    state["isPaused"]    = False
    state["currentFile"] = None


def play_file(file_path):
    if not os.path.isfile(file_path):
        return {"ok": False, "error": f"Fichier introuvable : {file_path}"}

    stop_player()

    proc = subprocess.Popen(
        ["mpg123", "-q", "-a", ALSA_DEV, file_path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    state["process"]     = proc
    state["currentFile"] = file_path
    state["isPlaying"]   = True
    state["isPaused"]    = False
    return {"ok": True}


def check_player():
    """Met à jour l'état si mpg123 a terminé tout seul."""
    if state["process"] and state["process"].poll() is not None:
        state["process"]     = None
        state["isPlaying"]   = False
        state["isPaused"]    = False
        state["currentFile"] = None


def list_music():
    files = []
    base = Path(MUSIC_DIR)
    if base.is_dir():
        for p in sorted(base.rglob("*.mp3")):
            files.append(str(p.relative_to(base)))
    return files


# ---------------------------------------------------------------------------
# Serveur HTTP
# ---------------------------------------------------------------------------

PAGE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>🎵 Pi Zero Player</title>
  <style>
    body {{ font-family: monospace; max-width: 600px; margin: 40px auto; padding: 0 16px; background: #111; color: #eee; }}
    h1 {{ color: #7df; }}
    select, input[type=range], button {{ width: 100%; margin: 6px 0; padding: 8px; font-size: 1em; box-sizing: border-box; }}
    button {{ background: #2a6; color: #fff; border: none; cursor: pointer; border-radius: 4px; }}
    button:hover {{ background: #3b7; }}
    button.danger {{ background: #a22; }}
    button.danger:hover {{ background: #c33; }}
    #status {{ background: #222; padding: 12px; border-radius: 4px; margin: 12px 0; white-space: pre; font-size: 0.85em; }}
    label {{ display: block; margin-top: 12px; color: #aaa; }}
  </style>
</head>
<body>
  <h1>🎵 Pi Zero Player</h1>
  <div id="status">Chargement…</div>
  <label>Fichier MP3 :</label>
  <select id="fileSelect">
    {options}
  </select>
  <button onclick="play()">▶ Lire</button>
  <button onclick="pause()">⏸ Pause / Reprendre</button>
  <button class="danger" onclick="stop()">⏹ Stop</button>
  <label>Volume : <span id="volLabel">80</span>%</label>
  <input type="range" id="vol" min="0" max="100" value="80"
         oninput="document.getElementById('volLabel').textContent=this.value">
  <button onclick="setVolume()">🔊 Appliquer le volume</button>
  <script>
    async function api(method, path, body) {{
      const r = await fetch(path, {{
        method,
        headers: body ? {{'Content-Type': 'application/json'}} : {{}},
        body: body ? JSON.stringify(body) : undefined,
      }});
      return r.json();
    }}
    async function refreshStatus() {{
      const s = await api('GET', '/api/status');
      document.getElementById('status').textContent = JSON.stringify(s, null, 2);
    }}
    async function play() {{
      const file = document.getElementById('fileSelect').value;
      if (!file) return alert('Sélectionne un fichier');
      await api('POST', '/api/play', {{ file }});
      refreshStatus();
    }}
    async function pause() {{ await api('POST', '/api/pause'); refreshStatus(); }}
    async function stop()  {{ await api('POST', '/api/stop');  refreshStatus(); }}
    async function setVolume() {{
      const vol = parseInt(document.getElementById('vol').value);
      await api('POST', '/api/volume', {{ volume: vol }});
    }}
    setInterval(refreshStatus, 2000);
    refreshStatus();
  </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    # -- helpers -------------------------------------------------------------

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw)

    # -- GET -----------------------------------------------------------------

    def do_GET(self):
        path = urlparse(self.path).path
        check_player()

        if path == "/api/status":
            return self.send_json({
                "isPlaying":   state["isPlaying"],
                "isPaused":    state["isPaused"],
                "currentFile": state["currentFile"],
            })

        if path == "/api/list":
            return self.send_json({"files": list_music(), "musicDir": MUSIC_DIR})

        if path == "/":
            files = list_music()
            options = "\n".join(f'<option value="{f}">{f}</option>' for f in files) \
                      or '<option value="">— aucun fichier trouvé —</option>'
            body = PAGE_HTML.format(options=options).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_json({"error": "Route introuvable"}, 404)

    # -- POST ----------------------------------------------------------------

    def do_POST(self):
        path = urlparse(self.path).path
        check_player()

        if path == "/api/play":
            try:
                body = self.read_json()
            except Exception:
                return self.send_json({"error": "Body JSON invalide"}, 400)

            if not body.get("file"):
                return self.send_json({"error": "Champ 'file' requis"}, 400)

            file_path = body["file"] if body["file"].startswith("/") \
                        else os.path.join(MUSIC_DIR, body["file"])

            result = play_file(file_path)
            if not result["ok"]:
                return self.send_json({"error": result["error"]}, 404)
            return self.send_json({"ok": True, "playing": file_path})

        if path == "/api/stop":
            stop_player()
            return self.send_json({"ok": True})

        if path == "/api/pause":
            if not state["process"]:
                return self.send_json({"error": "Rien en cours de lecture"}, 400)
            if state["isPaused"]:
                os.kill(state["process"].pid, signal.SIGCONT)
                state["isPaused"] = False
                return self.send_json({"ok": True, "paused": False})
            else:
                os.kill(state["process"].pid, signal.SIGSTOP)
                state["isPaused"] = True
                return self.send_json({"ok": True, "paused": True})

        if path == "/api/volume":
            try:
                body = self.read_json()
            except Exception:
                return self.send_json({"error": "Body JSON invalide"}, 400)

            vol = body.get("volume")
            if vol is None or not (0 <= int(vol) <= 100):
                return self.send_json({"error": "Volume doit être entre 0 et 100"}, 400)

            subprocess.Popen(
                ["amixer", "-D", ALSA_DEV, "sset", "PCM", f"{int(vol)}%"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return self.send_json({"ok": True, "volume": int(vol)})

        self.send_json({"error": "Route introuvable"}, 404)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(MUSIC_DIR, exist_ok=True)
    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🎵 Pi Zero Player démarré sur http://0.0.0.0:{PORT}")
    print(f"📁 Dossier musique : {MUSIC_DIR}")
    print(f"🔊 Sortie ALSA     : {ALSA_DEV}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
        stop_player()
