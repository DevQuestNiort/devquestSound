#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/DevQuestNiort/devquestSound.git"
INSTALL_DIR="/home/pi/player"

# --- Clone du dépôt si mode standalone (curl | bash) ---
if [ "${1:-}" != "--continue" ] && [ ! -f "${0%/*}/server.py" ]; then
  echo "=== Installation du DevQuest Sound Player ==="
  echo "Mode standalone détecté — clonage du dépôt…"
  echo ""

  if ! command -v git &>/dev/null; then
    echo "Installation de git…"
    apt update && apt install -y git
  fi

  if [ -d "$INSTALL_DIR" ]; then
    echo "Le répertoire $INSTALL_DIR existe déjà, mise à jour…"
    cd "$INSTALL_DIR"
    git pull
  else
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
  fi

  echo ""
  echo "Lancement de l'installation interactive…"
  exec bash "$INSTALL_DIR/install.sh" --continue
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="/etc/systemd/system/player.service"

echo "=== Installation du DevQuest Sound Player ==="
echo "Ce script va créer le service systemd, l'activer et le démarrer."
echo "Appuyez sur Entrée pour conserver les valeurs par défaut."
echo ""

# --- PLAYER_PASSWORD ---
read -rp "Mot de passe du player (vide = pas d'authentification) : " PLAYER_PASSWORD

# --- TELEGRAM_BOT_TOKEN ---
read -rp "Token du bot Telegram (optionnel, laisser vide pour désactiver) : " TELEGRAM_BOT_TOKEN

# --- TELEGRAM_CHAT_ID ---
read -rp "Chat ID Telegram (optionnel, laisser vide pour désactiver) : " TELEGRAM_CHAT_ID

# --- MUSIC_DIR ---
DEFAULT_MUSIC_DIR="$SCRIPT_DIR/music"
read -rp "Répertoire des fichiers audio [${DEFAULT_MUSIC_DIR}] : " MUSIC_DIR
MUSIC_DIR="${MUSIC_DIR:-$DEFAULT_MUSIC_DIR}"

# --- ALSA_DEVICE (détection + test) ---
echo "Détection des périphériques audio ALSA :"
ALSA_DEVICE=""
if command -v aplay &>/dev/null; then
  APLAY_OUTPUT=$(aplay -l 2>/dev/null || true)
else
  APLAY_OUTPUT=""
fi

if [ -n "$APLAY_OUTPUT" ]; then
  echo "$APLAY_OUTPUT"
  echo ""
  # Extraire les lignes avec des cartes
  DEVICES=$(echo "$APLAY_OUTPUT" | grep -E '^card [0-9]+' || true)
  DEVICE_COUNT=$(echo "$DEVICES" | grep -c 'card' 2>/dev/null || echo 0)
  if [ "$DEVICE_COUNT" -ge 1 ]; then
    echo "Périphériques détectés :"
    echo "$APLAY_OUTPUT" | grep -E '(^card |^  )' || true
    echo ""
    read -rp "Copiez le nom du périphérique ALSA (ex: plughw:1,0) ou laissez vide par défaut [plughw:1,0] : " ALSA_DEVICE
  fi
else
  echo "  (aucune carte ALSA détectée avec aplay -l)"
  echo "  Vous pouvez spécifier manuellement un périphérique."
  echo ""
fi
ALSA_DEVICE="${ALSA_DEVICE:-plughw:1,0}"

# --- Test sonore ---
if command -v mpg123 &>/dev/null || command -v speaker-test &>/dev/null; then
  echo ""
  read -rp "Tester la sortie audio avec \"${ALSA_DEVICE}\" ? [y/N] : " TEST_AUDIO
  if [ "$TEST_AUDIO" = "y" ] || [ "$TEST_AUDIO" = "Y" ]; then
    if command -v speaker-test &>/dev/null; then
      echo "Test avec speaker-test (bip sonore, Ctrl+C pour arrêter)..."
      speaker-test -c 2 -l 1 -D "$ALSA_DEVICE" 2>/dev/null && echo " OK" || echo " Échec du test"
    elif command -v mpg123 &>/dev/null; then
      TEST_FILE=$(find "$SCRIPT_DIR/music" -name '*.mp3' 2>/dev/null | head -1)
      if [ -n "$TEST_FILE" ]; then
        echo "Test avec mpg123 sur \"$(basename "$TEST_FILE")\"..."
        mpg123 -q -a "$ALSA_DEVICE" "$TEST_FILE" && echo " OK" || echo " Échec du test"
      else
        echo "Aucun fichier MP3 trouvé pour le test."
      fi
    fi
    echo ""
    read -rp "Le son était-il correct ? [Y/n] : " SOUND_OK
    if [ "$SOUND_OK" != "n" ] && [ "$SOUND_OK" != "N" ]; then
      echo "Périphérique confirmé : ${ALSA_DEVICE}"
    else
      read -rp "Entrez un autre périphérique ALSA (ex: plughw:0,0) : " ALSA_DEVICE
      ALSA_DEVICE="${ALSA_DEVICE:-plughw:0,0}"
    fi
  fi
fi

# --- PORT ---
read -rp "Port d'écoute [80] : " PORT
PORT="${PORT:-80}"

# --- AUDIO_SCALE ---
read -rp "Échelle audio [65536] : " AUDIO_SCALE
AUDIO_SCALE="${AUDIO_SCALE:-65536}"

# --- USER ---
read -rp "Utilisateur d'exécution du service [root] : " SERVICE_USER
SERVICE_USER="${SERVICE_USER:-root}"

echo ""
echo "=== Récapitulatif ==="
echo "  Répertoire d'installation : $SCRIPT_DIR"
echo "  Musique                   : $MUSIC_DIR"
echo "  Périphérique ALSA         : $ALSA_DEVICE"
echo "  Port                      : $PORT"
echo "  Utilisateur               : $SERVICE_USER"
echo "  Auth password             : $(if [ -n "$PLAYER_PASSWORD" ]; then echo "***"; else echo "désactivée"; fi)"
echo "  Telegram Bot Token        : $(if [ -n "$TELEGRAM_BOT_TOKEN" ]; then echo "***"; else echo "désactivé"; fi)"
echo "  Telegram Chat ID          : $(if [ -n "$TELEGRAM_CHAT_ID" ]; then echo "***"; else echo "désactivé"; fi)"
echo ""

if [ "$(id -u)" -ne 0 ]; then
  echo "Attention : ce script doit être exécuté en tant que root (sudo) pour créer le service systemd."
  read -rp "Continuer quand même ? [y/N] : " CONFIRM
  if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Installation annulée."
    exit 1
  fi
fi

echo "Création du service systemd…"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=DevQuest Sound Player
After=network.target sound.target

[Service]
User=${SERVICE_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=/usr/bin/env python3 ${SCRIPT_DIR}/server.py
Restart=on-failure
RestartSec=5
Environment=PORT=${PORT}
Environment=MUSIC_DIR=${MUSIC_DIR}
Environment=ALSA_DEVICE=${ALSA_DEVICE}
Environment=AUDIO_SCALE=${AUDIO_SCALE}
EOF

if [ -n "$PLAYER_PASSWORD" ]; then
  echo "Environment=PLAYER_PASSWORD=${PLAYER_PASSWORD}" >> "$SERVICE_FILE"
fi

if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
  echo "Environment=TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}" >> "$SERVICE_FILE"
fi

if [ -n "$TELEGRAM_CHAT_ID" ]; then
  echo "Environment=TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}" >> "$SERVICE_FILE"
fi

cat >> "$SERVICE_FILE" <<EOF

[Install]
WantedBy=multi-user.target
EOF

echo "Service systemd créé : $SERVICE_FILE"
echo "Rechargement de systemd…"

systemctl daemon-reload
systemctl enable player
systemctl start player

echo ""
echo "=== Installation terminée ! ==="
echo "Statut du service :"
systemctl status player --no-pager
