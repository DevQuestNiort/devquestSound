# 🎵 Pi Zero MP3 Player

Serveur HTTP léger en **Python 3** pour lire des MP3 sur la sortie son d'un Raspberry Pi Zero 1W.  
Aucune dépendance Python — uniquement la bibliothèque standard.

---

## Prérequis sur le Pi Zero

```bash
# 1. Installer mpg123 (lecteur MP3 ultra-léger)
sudo apt update && sudo apt install -y mpg123

# 2. Vérifier que python3 est disponible (déjà présent sur Raspbian)
python3 --version

# 3. Vérifier que l'audio fonctionne sur l'adaptateur USB
aplay -D plughw:1,0 /usr/share/sounds/alsa/Front_Center.wav
```

> **Sortie audio :** Le Pi Zero 1W n'a pas de jack audio natif.
> Options :
> - **USB audio** (adaptateur ~3€) → `plughw:1,0` ✅ recommandé
> - **PWM GPIO** (jack DIY sur GPIO 12/13 ou 18/19) → activer avec `dtoverlay=audremap`
> - **HDMI** (si connecté à un écran avec son)
>
> Voir la section *Configuration audio* ci-dessous.

---

## Installation

```bash
# Copier le serveur sur le Pi
scp server.py pi@<IP_DU_PI>:~/player/

# Sur le Pi : créer le dossier musique
mkdir -p ~/player/music

# Copier vos MP3 dans music/
scp mes_musiques/*.mp3 pi@<IP_DU_PI>:~/player/music/
```

---

## Lancer manuellement

```bash
cd ~/player
sudo python3 server.py
```

```
🎵 Pi Zero Player démarré sur http://0.0.0.0:80
📁 Dossier musique : ./music
🔊 Sortie ALSA     : plughw:1,0
```

Puis ouvrir `http://<IP_DU_PI>` dans un navigateur.

---

## Utilisation

### Interface web
Ouvrir `http://<IP_DU_PI>` dans un navigateur.

### API REST

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/status` | État actuel du lecteur |
| GET | `/api/list` | Liste des MP3 disponibles |
| POST | `/api/play` | Lire un fichier `{"file": "mon.mp3"}` |
| POST | `/api/stop` | Arrêter la lecture |
| POST | `/api/pause` | Pause / Reprendre |
| POST | `/api/volume` | Volume ALSA `{"volume": 80}` |

#### Exemples curl

```bash
# Lister les fichiers
curl http://pi.local/api/list

# Lire un MP3
curl -X POST http://pi.local/api/play \
  -H 'Content-Type: application/json' \
  -d '{"file": "chanson.mp3"}'

# Stop
curl -X POST http://pi.local/api/stop

# Pause / Reprendre
curl -X POST http://pi.local/api/pause

# Volume à 70%
curl -X POST http://pi.local/api/volume \
  -H 'Content-Type: application/json' \
  -d '{"volume": 70}'
```

---

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `PORT` | `80` | Port du serveur |
| `MUSIC_DIR` | `./music` | Dossier contenant les MP3 |
| `ALSA_DEVICE` | `plughw:1,0` | Périphérique ALSA de sortie |

```bash
MUSIC_DIR=/home/pi/musique ALSA_DEVICE=plughw:2,0 sudo python3 server.py
```

---

## Installer comme service systemd

Le service permet au player de démarrer automatiquement au boot et de redémarrer en cas d'erreur.

### 1. Créer le fichier de service

```bash
sudo nano /etc/systemd/system/player.service
```

Coller le contenu suivant (adapter `WorkingDirectory` si besoin) :

```ini
[Unit]
Description=Pi Zero MP3 Player
After=network.target sound.target

[Service]
User=root
WorkingDirectory=/home/pi/player
ExecStart=/usr/bin/python3 server.py
Restart=on-failure
RestartSec=5
Environment=MUSIC_DIR=/home/pi/player/music
Environment=ALSA_DEVICE=plughw:1,0
Environment=PLAYER_PASSWORD=monmotdepasse
Environment=PORT=80

[Install]
WantedBy=multi-user.target
```

### 2. Activer et démarrer le service

```bash
# Recharger systemd pour prendre en compte le nouveau fichier
sudo systemctl daemon-reload

# Activer le service au démarrage
sudo systemctl enable player

# Démarrer immédiatement
sudo systemctl start player

# Vérifier que tout fonctionne
sudo systemctl status player
```

### 3. Commandes utiles

```bash
# Voir les logs en temps réel
sudo journalctl -u player -f

# Redémarrer le service (après modif du script par ex.)
sudo systemctl restart player

# Arrêter le service
sudo systemctl stop player

# Désactiver le démarrage automatique
sudo systemctl disable player
```

---

## Configuration audio Pi Zero

### Option 1 – Adaptateur USB audio (recommandé)
```bash
# Lister les cartes son détectées
aplay -l

# Tester la carte USB (généralement card 1)
aplay -D plughw:1,0 /usr/share/sounds/alsa/Front_Center.wav
```

### Option 2 – PWM GPIO (jack DIY)
Ajouter dans `/boot/config.txt` :
```
dtoverlay=audremap,pins_12_13=on   # GPIO 12 & 13
# ou
dtoverlay=audremap,pins_18_19=on   # GPIO 18 & 19
```

### Option 3 – HDMI
```bash
sudo raspi-config
# → System → Audio → HDMI
```



## Configurer wi-fi

wpa_supplicant.conf

```
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
network={
  ssid="YOURSSID"
  scan_ssid=1
  psk="YOURPASSWORD"
  key_mgmt=WPA-PSK
}
```
