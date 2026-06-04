# 🎵 DevQuest Sound Player

Serveur HTTP léger en **Python 3** pour lire des MP3 sur la sortie son d'un Raspberry Pi.  
Aucune dépendance Python — uniquement la bibliothèque standard.

---

## Prérequis

```bash
# 1. Installer mpg123 (lecteur MP3 ultra-léger)
sudo apt update && sudo apt install -y mpg123

# 2. Vérifier que python3 est disponible
python3 --version

# 3. Vérifier que l'audio fonctionne
aplay -D plughw:1,0 /usr/share/sounds/alsa/Front_Center.wav
```

> **Sortie audio :** Sur Pi Zero 1W (pas de jack audio natif), utiliser un adaptateur USB,
> PWM GPIO ou HDMI. Voir la section *Configuration audio* ci-dessous.

---

## Installation

### Installation rapide (recommandée)

Depuis le Pi, une seule commande suffit — le script clone le dépôt puis lance l'interactif :

```bash
curl -fsSL https://raw.githubusercontent.com/DevQuestNiort/devquestSound/main/install.sh | sudo bash
```

### Installation depuis un clone

```bash
# Copier tout le projet sur le Pi
scp -r . pi@<IP_DU_PI>:~/player/

# Sur le Pi
cd ~/player
sudo ./install.sh
```

Le script `install.sh` vous guide pas à pas :

1. **Mot de passe** – authentification facultative de l'interface web
2. **Telegram** – token et chat ID (optionnels, pour notification au démarrage)
3. **Dossier musique** – chemin vers les MP3
4. **Sortie audio** – détection automatique des cartes ALSA + test sonore
5. **Port** – port d'écoute du serveur
6. **Utilisateur** – utilisateur système qui exécutera le service

Le script crée le service systemd, l'active au démarrage et le lance immédiatement.

### Installation manuelle

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
🎵 DevQuest Sound Player démarré sur http://0.0.0.0:80
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
| GET | `/api/status` | État, fichier en cours, volume |
| GET | `/api/list` | Liste des MP3 disponibles |
| POST | `/api/play` | Lire un fichier `{"file": "mon.mp3"}` |
| POST | `/api/stop` | Arrêter la lecture |
| POST | `/api/pause` | Pause / Reprendre |
| POST | `/api/volume` | Volume (0-100) via mpg123 `{"volume": 80}` |

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
| `AUDIO_SCALE` | `65536` | Amplification logicielle mpg123 (max 65536) |
| `PLAYER_PASSWORD` | `""` (désactivé) | Mot de passe pour l'interface |
| `TELEGRAM_BOT_TOKEN` | `""` (désactivé) | Token du bot Telegram |
| `TELEGRAM_CHAT_ID` | `""` (désactivé) | Chat ID destinataire Telegram |

```bash
MUSIC_DIR=/home/pi/musique ALSA_DEVICE=plughw:2,0 sudo python3 server.py
```

### Notification Telegram au démarrage

Si `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` sont définis, le serveur envoie un message avec l'IP locale et le port au démarrage.

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl... \
TELEGRAM_CHAT_ID=987654321 \
sudo python3 server.py
```

---

## Service systemd

Le service permet au player de démarrer automatiquement au boot et de redémarrer en cas d'erreur.  
Le script `install.sh` le crée, l'active et le lance automatiquement.

Commandes utiles :

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

### Configuration manuelle

Si vous préférez créer le service à la main :

```bash
sudo nano /etc/systemd/system/player.service
```

```ini
[Unit]
Description=DevQuest Sound Player
After=network.target sound.target

[Service]
User=root
WorkingDirectory=/home/pi/player
ExecStart=/usr/bin/python3 server.py
Restart=on-failure
RestartSec=5
Environment=PORT=80
Environment=MUSIC_DIR=/home/pi/player/music
Environment=ALSA_DEVICE=plughw:1,0
Environment=AUDIO_SCALE=65536
# Environment=PLAYER_PASSWORD=monmotdepasse
# Environment=TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
# Environment=TELEGRAM_CHAT_ID=987654321

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now player
```

---

## Configuration audio

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
