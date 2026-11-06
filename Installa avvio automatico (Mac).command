#!/bin/bash
# Avvio automatico su Mac (al login, senza finestra del Terminale)
cd "$(dirname "$0")"
DIR="$(pwd)"
PY="$(command -v python3)"
PLIST="$HOME/Library/LaunchAgents/it.officina.gestionale.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>it.officina.gestionale</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$DIR/app.py</string><string>--silenzioso</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
EOF
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"
cat > "$HOME/Desktop/Gestionale Officina.webloc" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>URL</key><string>http://127.0.0.1:8765/</string></dict></plist>
EOF
echo "Fatto! Il gestionale parte da solo al login. Icona sul Desktop: Gestionale Officina"
echo "Per toglierlo: launchctl unload \"$PLIST\" && rm \"$PLIST\""
