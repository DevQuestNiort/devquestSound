import { createServer } from "http";
import { spawn } from "child_process";
import { existsSync, readdirSync, statSync } from "fs";
import { join, extname } from "path";

const PORT = Number(process.env.PORT) || 80;
const MUSIC_DIR = process.env.MUSIC_DIR || "./music";
const ALSA_DEVICE = process.env.ALSA_DEVICE || "plughw:1,0";

const state = {
  process: null,
  currentFile: null,
  isPlaying: false,
  isPaused: false,
};

function stopPlayer() {
  if (state.process) {
    state.process.kill("SIGTERM");
    state.process = null;
  }
  state.isPlaying = false;
  state.isPaused = false;
  state.currentFile = null;
}

function playFile(filePath) {
  if (!existsSync(filePath)) {
    return { ok: false, error: `Fichier introuvable : ${filePath}` };
  }

  stopPlayer();

  const player = spawn("mpg123", ["-q", "-a", ALSA_DEVICE, filePath], {
    stdio: ["ignore", "pipe", "pipe"],
  });

  player.on("error", (err) => {
    console.error("Erreur lecteur:", err.message);
    state.isPlaying = false;
    state.process = null;
    state.currentFile = null;
  });

  player.on("exit", (code) => {
    if (code !== null && code !== 0 && code !== 2) {
      console.error(`mpg123 s'est arrêté avec le code ${code}`);
    }
    state.isPlaying = false;
    state.isPaused = false;
    state.process = null;
    state.currentFile = null;
  });

  state.process = player;
  state.currentFile = filePath;
  state.isPlaying = true;
  state.isPaused = false;

  return { ok: true };
}

function listMusicFiles(dir, base = "") {
  const files = [];
  try {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const rel = base ? `${base}/${entry}` : entry;
      if (statSync(full).isDirectory()) {
        files.push(...listMusicFiles(full, rel));
      } else if ([".mp3", ".MP3"].includes(extname(entry))) {
        files.push(rel);
      }
    }
  } catch {}
  return files.sort();
}

function json(res, data, status = 200) {
  const body = JSON.stringify(data, null, 2);
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(body);
}

function html(res, body) {
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(body);
}

async function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => (data += chunk));
    req.on("end", () => {
      try { resolve(JSON.parse(data)); }
      catch { reject(new Error("JSON invalide")); }
    });
  });
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost`);
  const path = url.pathname;
  const method = req.method;

  // GET /api/status
  if (path === "/api/status" && method === "GET") {
    return json(res, {
      isPlaying: state.isPlaying,
      isPaused: state.isPaused,
      currentFile: state.currentFile,
    });
  }

  // GET /api/list
  if (path === "/api/list" && method === "GET") {
    return json(res, { files: listMusicFiles(MUSIC_DIR), musicDir: MUSIC_DIR });
  }

  // POST /api/play
  if (path === "/api/play" && method === "POST") {
    let body;
    try { body = await readBody(req); }
    catch { return json(res, { error: "Body JSON invalide" }, 400); }

    if (!body.file) return json(res, { error: "Champ 'file' requis" }, 400);

    const filePath = body.file.startsWith("/")
      ? body.file
      : join(MUSIC_DIR, body.file);

    const result = playFile(filePath);
    if (!result.ok) return json(res, { error: result.error }, 404);
    return json(res, { ok: true, playing: filePath });
  }

  // POST /api/stop
  if (path === "/api/stop" && method === "POST") {
    stopPlayer();
    return json(res, { ok: true });
  }

  // POST /api/pause
  if (path === "/api/pause" && method === "POST") {
    if (!state.process) return json(res, { error: "Rien en cours de lecture" }, 400);
    if (state.isPaused) {
      state.process.kill("SIGCONT");
      state.isPaused = false;
      return json(res, { ok: true, paused: false });
    } else {
      state.process.kill("SIGSTOP");
      state.isPaused = true;
      return json(res, { ok: true, paused: true });
    }
  }

  // POST /api/volume
  if (path === "/api/volume" && method === "POST") {
    let body;
    try { body = await readBody(req); }
    catch { return json(res, { error: "Body JSON invalide" }, 400); }

    const vol = Number(body.volume);
    if (isNaN(vol) || vol < 0 || vol > 100)
      return json(res, { error: "Volume doit être entre 0 et 100" }, 400);

    const amixer = spawn("amixer", ["-D", ALSA_DEVICE, "sset", "PCM", `${vol}%`]);
    amixer.on("error", () => {});
    return json(res, { ok: true, volume: vol });
  }

  // GET / — interface web
  if (path === "/" && method === "GET") {
    const files = listMusicFiles(MUSIC_DIR);
    const fileOptions = files.map((f) => `<option value="${f}">${f}</option>`).join("\n");

    return html(res, `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>🎵 Pi Zero Player</title>
  <style>
    body { font-family: monospace; max-width: 600px; margin: 40px auto; padding: 0 16px; background: #111; color: #eee; }
    h1 { color: #7df; }
    select, input[type=range], button { width: 100%; margin: 6px 0; padding: 8px; font-size: 1em; box-sizing: border-box; }
    button { background: #2a6; color: #fff; border: none; cursor: pointer; border-radius: 4px; }
    button:hover { background: #3b7; }
    button.danger { background: #a22; }
    button.danger:hover { background: #c33; }
    #status { background: #222; padding: 12px; border-radius: 4px; margin: 12px 0; white-space: pre; font-size: 0.85em; }
    label { display: block; margin-top: 12px; color: #aaa; }
  </style>
</head>
<body>
  <h1>🎵 Pi Zero Player</h1>
  <div id="status">Chargement…</div>
  <label>Fichier MP3 :</label>
  <select id="fileSelect">
    ${fileOptions || '<option value="">— aucun fichier trouvé —</option>'}
  </select>
  <button onclick="play()">▶ Lire</button>
  <button onclick="pause()">⏸ Pause / Reprendre</button>
  <button class="danger" onclick="stop()">⏹ Stop</button>
  <label>Volume : <span id="volLabel">80</span>%</label>
  <input type="range" id="vol" min="0" max="100" value="80" oninput="document.getElementById('volLabel').textContent=this.value">
  <button onclick="setVolume()">🔊 Appliquer le volume</button>
  <script>
    async function api(method, path, body) {
      const r = await fetch(path, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      return r.json();
    }
    async function refreshStatus() {
      const s = await api('GET', '/api/status');
      document.getElementById('status').textContent = JSON.stringify(s, null, 2);
    }
    async function play() {
      const file = document.getElementById('fileSelect').value;
      if (!file) return alert('Sélectionne un fichier');
      await api('POST', '/api/play', { file });
      refreshStatus();
    }
    async function pause() { await api('POST', '/api/pause'); refreshStatus(); }
    async function stop() { await api('POST', '/api/stop'); refreshStatus(); }
    async function setVolume() {
      const vol = parseInt(document.getElementById('vol').value);
      await api('POST', '/api/volume', { volume: vol });
    }
    setInterval(refreshStatus, 2000);
    refreshStatus();
  </script>
</body>
</html>`);
  }

  json(res, { error: "Route introuvable" }, 404);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`🎵 Pi Zero Player démarré sur http://0.0.0.0:${PORT}`);
  console.log(`📁 Dossier musique : ${MUSIC_DIR}`);
  console.log(`🔊 Sortie ALSA     : ${ALSA_DEVICE}`);
});
