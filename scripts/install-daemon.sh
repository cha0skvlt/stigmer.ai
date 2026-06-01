#!/usr/bin/env bash
# Install kaban.ai auto-start (systemd on Linux, launchd on macOS).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SCOPE="user"
START_NOW=1
LABEL="ai.kaban.ai"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Install kaban.ai to start after boot (Linux) or login (macOS).

Options:
  --system    Linux only: install system-wide unit (requires sudo)
  --no-start  Register service but do not start it now
  -h, --help  Show this help

After install:
  Linux (user):  systemctl --user status kaban
                 loginctl enable-linger "\$USER"
  macOS:         launchctl print gui/\$(id -u)/$LABEL

Remove: make uninstall-daemon
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --system) SCOPE="system" ;;
    --no-start) START_NOW=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

if [[ ! -f "$ROOT/.env" ]]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
fi

if [[ ! -f "$ROOT/docker-compose.yml" ]]; then
  echo "ERROR: docker-compose.yml not found in $ROOT" >&2
  exit 1
fi

chmod +x "$ROOT/scripts/kaban.ai"
mkdir -p "$ROOT/logs"

OS="$(uname -s)"
render() {
  local src="$1" dest="$2"
  sed \
    -e "s|@KABAN_ROOT@|$ROOT|g" \
    -e "s|@SYSTEMD_WANTED_BY@|${SYSTEMD_WANTED_BY:-default.target}|g" \
    "$src" >"$dest"
}

install_linux() {
  local unit_src="$ROOT/scripts/kaban.service.in"
  local unit_dest

  if [[ "$SCOPE" == "system" ]]; then
    unit_dest="/etc/systemd/system/kaban.service"
    SYSTEMD_WANTED_BY="multi-user.target"
    render "$unit_src" "/tmp/kaban.service"
    echo "==> Installing system unit (sudo required): $unit_dest"
    sudo cp "/tmp/kaban.service" "$unit_dest"
    sudo systemctl daemon-reload
    sudo systemctl enable kaban.service
    if [[ "$START_NOW" == "1" ]]; then
      sudo systemctl start kaban.service
      sudo systemctl status kaban.service --no-pager || true
    fi
    cat <<EOF

Installed (system). kaban.ai starts after Docker at boot.

  sudo systemctl status kaban
  sudo journalctl -u kaban -f

Logs: $ROOT/logs/kaban.ai.log
EOF
  else
    unit_dest="$HOME/.config/systemd/user/kaban.service"
    mkdir -p "$HOME/.config/systemd/user"
    SYSTEMD_WANTED_BY="default.target"
    render "$unit_src" "$unit_dest"
    systemctl --user daemon-reload
    systemctl --user enable kaban.service
    if [[ "$START_NOW" == "1" ]]; then
      systemctl --user start kaban.service
      systemctl --user status kaban.service --no-pager || true
    fi
    cat <<EOF

Installed (user). Start at boot without login:

  loginctl enable-linger "\$USER"

Commands:
  systemctl --user status kaban
  systemctl --user restart kaban
  journalctl --user -u kaban -f

Logs: $ROOT/logs/kaban.ai.log
EOF
  fi
}

install_macos() {
  if [[ "$SCOPE" == "system" ]]; then
    echo "WARN: --system is ignored on macOS (LaunchAgent at login)" >&2
  fi
  local plist_dest="$HOME/Library/LaunchAgents/${LABEL}.plist"
  render "$ROOT/scripts/ai.kaban.ai.plist.in" "$plist_dest"

  # Remove legacy agents from earlier installs
  launchctl bootout "gui/$(id -u)/ai.kaban.stack" >/dev/null 2>&1 || true
  rm -f "$HOME/Library/LaunchAgents/ai.kaban.stack.plist"
  rm -f "$HOME/Library/LaunchAgents/com.kaban.ai.plist"

  launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$plist_dest"
  if [[ "$START_NOW" == "1" ]]; then
    launchctl kickstart -k "gui/$(id -u)/${LABEL}" || true
  fi

  cat <<EOF

Installed (macOS). kaban.ai starts at login — shown as "kaban.ai" in Login Items.

  launchctl print gui/$(id -u)/${LABEL}
  launchctl kickstart -k gui/$(id -u)/${LABEL}

Logs:
  $ROOT/logs/kaban.ai.log
  $ROOT/logs/kaban.ai.out.log
EOF
}

case "$OS" in
  Linux) install_linux ;;
  Darwin) install_macos ;;
  *)
    echo "Unsupported OS: $OS (use Linux or macOS)" >&2
    exit 1
    ;;
esac

echo "Project root: $ROOT"
