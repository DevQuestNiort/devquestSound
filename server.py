#!/usr/bin/env python3
import hashlib
import json
import os
import secrets
import signal
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("PORT", 80))
MUSIC_DIR = os.environ.get("MUSIC_DIR", "./music")
ALSA_DEV = os.environ.get("ALSA_DEVICE", "plughw:1,0")
PASSWORD = os.environ.get("PLAYER_PASSWORD", "")
AUDIO_SCALE = int(os.environ.get("AUDIO_SCALE", 65536))

# Sessions actives : token -> True
sessions = set()

state = {
    "process": None,
    "currentFile": None,
    "isPlaying": False,
    "isPaused": False,
}

CATEGORIES = [
    {
        "label": "Conférences",
        "color": "#ff6b35",
        "buttons": [
            {
                "id": "conferences",
                "key": "1",
                "icon": "🎤",
                "label": "Conférences",
                "hint": "Début / reprise — aléatoire",
                "files": [
                    "DevQuest-MessageConferences01.mp3",
                    "DevQuest-MessageConferences02.mp3",
                    "DevQuest-MessageConferences03.mp3",
                    "DevQuest-MessageConferences04.mp3",
                ],
            }
        ],
    },
    {
        "label": "Repas",
        "color": "#f9c74f",
        "buttons": [
            {
                "id": "repas",
                "key": "2",
                "icon": "🍽️",
                "label": "Repas",
                "hint": "C'est l'heure — aléatoire",
                "files": [
                    "DevQuest-MessageRepas01.mp3",
                    "DevQuest-MessageRepas02.mp3",
                    "DevQuest-MessageRepas03.mp3",
                    "DevQuest-MessageRepas04.mp3",
                ],
            },
            {
                "id": "repas-dernier",
                "key": "3",
                "icon": "⏱️",
                "label": "Dernier appel repas",
                "hint": "Annonce finale",
                "color": "#fb8500",
                "files": ["DevQuest-MessageRepas05-DERNIER.mp3"],
            },
        ],
    },
    {
        "label": "Collation",
        "color": "#a78bfa",
        "buttons": [
            {
                "id": "collation",
                "key": "4",
                "icon": "☕",
                "label": "Collation",
                "hint": "Pause snack — aléatoire",
                "files": [
                    "DevQuest-MessageCollation01.mp3",
                    "DevQuest-MessageCollation02.mp3",
                ],
            }
        ],
    },
    {
        "label": "Auberge",
        "color": "#4ecdc4",
        "buttons": [
            {
                "id": "auberge-open",
                "key": "5",
                "icon": "🍺",
                "label": "Auberge ouverte",
                "hint": "Aléatoire",
                "files": [
                    "DevQuest-MessageAubergeouverte01.mp3",
                    "DevQuest-MessageAubergeouverte02.mp3",
                    "DevQuest-MessageAubergeouverte03.mp3",
                ],
            },
            {
                "id": "auberge-close",
                "key": "6",
                "icon": "🔒",
                "label": "Auberge fermée",
                "hint": "Aléatoire",
                "color": "#e63946",
                "files": [
                    "DevQuest-MessageAubergeFerme01.mp3",
                    "DevQuest-MessageAubergeFerme02.mp3",
                    "DevQuest-MessageAubergeFerme03.mp3",
                ],
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def get_session_token(headers):
    cookie = headers.get("Cookie", "")
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith("session="):
            return part[len("session=") :]
    return None


def is_authenticated(headers):
    if not PASSWORD:
        return True
    return get_session_token(headers) in sessions


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
    state["isPlaying"] = False
    state["isPaused"] = False
    state["currentFile"] = None


def play_file(file_path):
    if not os.path.isfile(file_path):
        return {"ok": False, "error": f"Fichier introuvable : {file_path}"}
    stop_player()
    proc = subprocess.Popen(
        ["mpg123", "-q", "-a", ALSA_DEV, "--scale", str(AUDIO_SCALE), file_path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    state["process"] = proc
    state["currentFile"] = file_path
    state["isPlaying"] = True
    state["isPaused"] = False
    return {"ok": True}


def check_player():
    if state["process"] and state["process"].poll() is not None:
        state["process"] = None
        state["isPlaying"] = False
        state["isPaused"] = False
        state["currentFile"] = None


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

LOGIN_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DevQuest Player — Connexion</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0d0f;color:#e8e8e8;font-family:'Inter',system-ui,sans-serif;
     display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#16161a;border:1px solid #2a2a30;border-radius:16px;padding:40px 36px;
      width:340px;text-align:center}
h1{font-size:20px;font-weight:600;margin-bottom:6px;letter-spacing:.3px}
p{font-size:13px;color:#888;margin-bottom:28px}
input{width:100%;padding:12px 14px;background:#1e1e24;border:1px solid #333;border-radius:8px;
      color:#e8e8e8;font-size:15px;outline:none;margin-bottom:14px}
input:focus{border-color:#555}
button{width:100%;padding:12px;background:#e8e8e8;color:#111;border:none;border-radius:8px;
       font-size:15px;font-weight:600;cursor:pointer}
button:hover{background:#fff}
.err{color:#e63946;font-size:13px;margin-top:10px;display:none}
</style>
</head>
<body>
<div class="card">
  <h1>🎵 DevQuest Player</h1>
  <p>Entrez le mot de passe pour continuer</p>
  <input type="password" id="pw" placeholder="Mot de passe" onkeydown="if(event.key==='Enter')login()">
  <button onclick="login()">Connexion</button>
  <div class="err" id="err">Mot de passe incorrect</div>
</div>
<script>
async function login(){
  const pw=document.getElementById('pw').value;
  const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
  const d=await r.json();
  if(d.ok){location.href='/';}
  else{const e=document.getElementById('err');e.style.display='block';}
}
</script>
</body>
</html>"""


def build_page_html():
    cats_js = json.dumps(CATEGORIES)
    return (
        """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>DevQuest Player</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0d0f;color:#e8e8e8;font-family:'Inter',system-ui,sans-serif;min-height:100vh;
     padding:16px 12px 90px;-webkit-tap-highlight-color:transparent}
header{display:flex;align-items:center;justify-content:space-between;max-width:960px;margin:0 auto 20px;
       padding-bottom:14px;border-bottom:1px solid #1e1e24}
header h1{font-size:16px;font-weight:600;letter-spacing:.3px}
.logout{font-size:12px;padding:6px 12px;border:1px solid #2a2a30;border-radius:6px;
        cursor:pointer;background:none;color:#888;white-space:nowrap}
.logout:hover{color:#ccc;border-color:#444}
main{max-width:960px;margin:0 auto;display:flex;flex-direction:column;gap:20px}
.section-label{font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
               color:#555;margin-bottom:8px;padding-left:2px;display:flex;align-items:center;gap:8px}
.section-label::after{content:'';flex:1;height:1px;background:#1e1e24}
.btn-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.btn-card{background:#16161a;border:1px solid #1e1e24;border-radius:14px;padding:16px 18px;
          cursor:pointer;text-align:left;transition:border-color .15s,background .15s,transform .1s;
          position:relative;overflow:hidden;-webkit-user-select:none;user-select:none;
          -webkit-touch-callout:none}
.btn-card:active{transform:scale(0.98)}
@media(hover:hover){.btn-card:hover{background:#1c1c22;border-color:#333}}
.btn-card.active{border-color:var(--accent);background:#1a1a20}
.btn-card.active::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--accent)}
.badge{display:inline-flex;align-items:center;font-size:11px;font-weight:700;padding:3px 8px;
       border-radius:5px;margin-bottom:10px;letter-spacing:.5px}
.card-row{display:flex;align-items:flex-start;gap:12px}
.icon{font-size:24px;line-height:1;flex-shrink:0;margin-top:1px}
.card-body{flex:1;min-width:0}
.card-title{font-size:15px;font-weight:600;color:#e8e8e8;margin-bottom:3px}
.card-hint{font-size:11px;color:#555;font-family:monospace}
.count-pill{position:absolute;top:12px;right:12px;font-size:11px;font-weight:700;
            padding:3px 8px;border-radius:6px;border:1px solid #2a2a30;color:#555}
.btn-card.active .count-pill{color:var(--accent);border-color:var(--accent)}
.dots{display:flex;gap:5px;margin-top:12px}
.dot{width:7px;height:7px;border-radius:50%;background:#2a2a30}
.dot.on{background:var(--accent)}
/* now playing bar */
#bar{position:fixed;bottom:0;left:0;right:0;background:#111118;border-top:1px solid #1e1e24;
     padding:0 12px;padding-bottom:env(safe-area-inset-bottom);z-index:100}
.bar-inner{max-width:960px;margin:0 auto;display:flex;align-items:center;gap:10px;height:60px}
.np-label{font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;
          color:#333;flex-shrink:0;width:58px}
.bar-on .np-label{color:#555}
.np-file{flex:1;min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;
         font-size:11px;color:#444;font-family:monospace}
.bar-on .np-file{color:#888}
/* volume */
.vol-wrap{display:flex;align-items:center;gap:6px;flex-shrink:0}
.vol-icon{font-size:14px;cursor:pointer;user-select:none;padding:4px}
#vol-sl{-webkit-appearance:none;appearance:none;height:3px;border-radius:2px;
         background:#2a2a30;outline:none;cursor:pointer;width:70px}
#vol-sl::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;
  width:16px;height:16px;border-radius:50%;background:#e8e8e8;cursor:pointer}
#vol-sl::-moz-range-thumb{width:16px;height:16px;border-radius:50%;
  background:#e8e8e8;border:none;cursor:pointer}
#vol-pct{font-size:10px;color:#444;font-family:monospace;min-width:26px;text-align:right}
.stop-btn{background:#1e1e24;border:none;border-radius:8px;color:#777;
          font-size:18px;width:36px;height:36px;cursor:pointer;flex-shrink:0;
          display:flex;align-items:center;justify-content:center}
.stop-btn:active{background:#2a2a30}
/* mobile: stack volume below on very small screens */
@media(max-width:400px){
  .vol-wrap{display:none}
  #bar{padding-bottom:calc(env(safe-area-inset-bottom) + 2px)}
}
@media(max-width:520px){
  #vol-sl{width:55px}
  .btn-grid{grid-template-columns:1fr}
  .card-title{font-size:14px}
}
</style>
</head>
<body>
<header>
  <h1>🎵 DevQuest Player</h1>
  <button class="logout" onclick="logout()">Déconnexion</button>
</header>
<main id="main">Chargement…</main>
<div id="bar">
  <div class="bar-inner">
    <span class="np-label" id="np-label">ARRÊTÉ</span>
    <span class="np-file" id="np-file">—</span>
    <div class="vol-wrap">
      <span class="vol-icon" id="vol-icon" onclick="toggleMute()">🔊</span>
      <input type="range" id="vol-sl" min="0" max="100" value="80" step="1" oninput="onVol(this.value)">
      <span id="vol-pct">80%</span>
    </div>
    <button class="stop-btn" onclick="stop()" title="Stop">⏹</button>
  </div>
</div>
<script>
const CATS="""
        + cats_js
        + """;
let currentId=null,volTimer=null,lastVol=80,muted=false,volBefore=80;

function render(){
  const main=document.getElementById('main');
  main.innerHTML='';
  CATS.forEach(cat=>{
    const sec=document.createElement('div');
    const color=cat.color;
    sec.innerHTML='<div class="section-label" style="color:'+color+'">'+cat.label+'</div>';
    const grid=document.createElement('div');
    grid.className='btn-grid';
    cat.buttons.forEach(btn=>{
      const accent=btn.color||color;
      const card=document.createElement('div');
      card.className='btn-card';
      card.id='card-'+btn.id;
      card.style.setProperty('--accent',accent);
      const count=btn.files.length;
      const rv=parseInt(accent.slice(1,3),16);
      const gv=parseInt(accent.slice(3,5),16);
      const bv=parseInt(accent.slice(5,7),16);
      const bg='rgba('+rv+','+gv+','+bv+',0.15)';
      card.innerHTML=
        '<div class="badge" style="background:'+bg+';color:'+accent+'">'+count+' / '+count+'</div>'+
        '<div class="card-row">'+
          '<div class="icon">'+btn.icon+'</div>'+
          '<div class="card-body">'+
            '<div class="card-title">'+btn.label+'</div>'+
            '<div class="card-hint">'+btn.hint+'</div>'+
          '</div>'+
        '</div>'+
        '<span class="count-pill">'+count+'</span>'+
        '<div class="dots">'+btn.files.map(()=>'<div class="dot"></div>').join('')+'</div>';
      card.onclick=()=>playRandom(btn);
      grid.appendChild(card);
    });
    sec.appendChild(grid);
    main.appendChild(sec);
  });
}

async function playRandom(btn){
  const file=btn.files[Math.floor(Math.random()*btn.files.length)];
  currentId=btn.id;
  document.querySelectorAll('.btn-card').forEach(c=>c.classList.remove('active'));
  const card=document.getElementById('card-'+btn.id);
  if(card)card.classList.add('active');
  await api('POST','/api/play',{file});
  refreshStatus();
}

async function stop(){
  await api('POST','/api/stop');
  currentId=null;
  document.querySelectorAll('.btn-card').forEach(c=>c.classList.remove('active'));
  refreshStatus();
}

function onVol(val){
  val=parseInt(val);lastVol=val;muted=(val===0);
  document.getElementById('vol-pct').textContent=val+'%';
  document.getElementById('vol-icon').textContent=val===0?'🔇':val<50?'🔉':'🔊';
  clearTimeout(volTimer);
  volTimer=setTimeout(()=>api('POST','/api/volume',{volume:val}),300);
}

function toggleMute(){
  const sl=document.getElementById('vol-sl');
  if(muted){sl.value=volBefore;onVol(volBefore);}
  else{volBefore=lastVol;sl.value=0;onVol(0);}
  muted=!muted;
}

async function logout(){await fetch('/api/logout',{method:'POST'});location.href='/login';}

async function api(method,path,body){
  const r=await fetch(path,{method,
    headers:body?{'Content-Type':'application/json'}:{},
    body:body?JSON.stringify(body):undefined});
  if(r.status===401){location.href='/login';return{};}
  return r.json();
}

async function refreshStatus(){
  const s=await api('GET','/api/status');
  const bar=document.getElementById('bar');
  document.getElementById('np-file').textContent=s.isPlaying&&s.currentFile
    ?s.currentFile.split('/').pop():'—';
  document.getElementById('np-label').textContent=
    s.isPlaying?(s.isPaused?'EN PAUSE':'EN COURS'):'ARRÊTÉ';
  if(s.isPlaying)bar.classList.add('bar-on');
  else{bar.classList.remove('bar-on');currentId=null;
    document.querySelectorAll('.btn-card').forEach(c=>c.classList.remove('active'));}
}

document.addEventListener('keydown',e=>{
  CATS.forEach(cat=>cat.buttons.forEach(btn=>{if(e.key===btn.key)playRandom(btn);}));
});

render();
setInterval(refreshStatus,2000);
refreshStatus();
</script>
</body>
</html>"""
    )


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html, status=200, extra_headers=None):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length))

    def require_auth(self):
        if not is_authenticated(self.headers):
            self.send_json({"error": "Non autorisé"}, 401)
            return False
        return True

    def do_GET(self):
        path = urlparse(self.path).path
        check_player()

        if path == "/login":
            return self.send_html(LOGIN_HTML)

        if path == "/":
            if not is_authenticated(self.headers):
                return self.redirect("/login")
            return self.send_html(build_page_html())

        if path == "/api/status":
            if not self.require_auth():
                return
            return self.send_json(
                {
                    "isPlaying": state["isPlaying"],
                    "isPaused": state["isPaused"],
                    "currentFile": state["currentFile"],
                }
            )

        if path == "/api/list":
            if not self.require_auth():
                return
            files = []
            base = Path(MUSIC_DIR)
            if base.is_dir():
                for p in sorted(base.rglob("*.mp3")):
                    files.append(str(p.relative_to(base)))
            return self.send_json({"files": files, "musicDir": MUSIC_DIR})

        self.send_json({"error": "Route introuvable"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        check_player()

        if path == "/api/login":
            try:
                body = self.read_json()
            except Exception:
                return self.send_json({"error": "JSON invalide"}, 400)
            if not PASSWORD or body.get("password") == PASSWORD:
                token = secrets.token_hex(32)
                sessions.add(token)
                cookie = f"session={token}; HttpOnly; Path=/; Max-Age=86400"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Set-Cookie", cookie)
                resp = json.dumps({"ok": True}).encode()
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_json({"ok": False, "error": "Mot de passe incorrect"}, 401)
            return

        if path == "/api/logout":
            token = get_session_token(self.headers)
            if token in sessions:
                sessions.discard(token)
            cookie = "session=; HttpOnly; Path=/; Max-Age=0"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Set-Cookie", cookie)
            resp = json.dumps({"ok": True}).encode()
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
            return

        if not self.require_auth():
            return

        if path == "/api/play":
            try:
                body = self.read_json()
            except Exception:
                return self.send_json({"error": "Body JSON invalide"}, 400)
            if not body.get("file"):
                return self.send_json({"error": "Champ 'file' requis"}, 400)
            file_path = (
                body["file"]
                if body["file"].startswith("/")
                else os.path.join(MUSIC_DIR, body["file"])
            )
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
                return self.send_json({"error": "Volume entre 0 et 100"}, 400)
            subprocess.Popen(
                ["amixer", "-D", ALSA_DEV, "sset", "Speaker", f"{int(vol)}%"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return self.send_json({"ok": True, "volume": int(vol)})

        self.send_json({"error": "Route introuvable"}, 404)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(MUSIC_DIR, exist_ok=True)
    if PASSWORD:
        print(f"🔒 Authentification activée (PLAYER_PASSWORD défini)")
    else:
        print(f"⚠️  Pas de mot de passe — définir PLAYER_PASSWORD pour sécuriser")
    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🎵 Pi Zero Player démarré sur http://0.0.0.0:{PORT}")
    print(f"📁 Dossier musique : {MUSIC_DIR}")
    print(f"🔊 Sortie ALSA     : {ALSA_DEV}")
    print(f"📢 Amplification   : {AUDIO_SCALE} (max 65536)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
        stop_player()
