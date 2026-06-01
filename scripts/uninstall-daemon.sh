#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OS="$(uname -s)"
LABEL="ai.kaban.ai"

stop_stack() {
  if [[ -x "$ROOT/scripts/kaban.ai" ]]; then
    KABAN_DAEMON_QUIET=1 "$ROOT/scripts/kaban.ai" stop || true
  elif [[ -x "$ROOT/scripts/daemon.sh" ]]; then
    KABAN_DAEMON_QUIET=1 "$ROOT/scripts/daemon.sh" stop || true
  fi
}

case "$OS" in
  Linux)
    if systemctl --user is-active kaban.service >/dev/null 2>&1; then
      systemctl --user stop kaban.service || true
    fi
    if systemctl --user is-enabled kaban.service >/dev/null 2>&1; then
      systemctl --user disable kaban.service || true
    fi
    rm -f "$HOME/.config/systemd/user/kaban.service"
    systemctl --user daemon-reload || true

    if systemctl is-active kaban.service >/dev/null 2>&1; then
      sudo systemctl stop kaban.service || true
    fi
    if systemctl is-enabled kaban.service >/dev/null 2>&1; then
      sudo systemctl disable kaban.service || true
    fi
    if [[ -f /etc/systemd/system/kaban.service ]]; then
      sudo rm -f /etc/systemd/system/kaban.service
      sudo systemctl daemon-reload || true
    fi
    ;;
  Darwin)
    launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
    launchctl bootout "gui/$(id -u)/ai.kaban.stack" >/dev/null 2>&1 || true
    rm -f "$HOME/Library/LaunchAgents/${LABEL}.plist"
    rm -f "$HOME/Library/LaunchAgents/ai.kaban.stack.plist"
    rm -f "$HOME/Library/LaunchAgents/com.kaban.ai.plist"
    ;;
  *)
    echo "Unsupported OS: $OS" >&2
    exit 1
    ;;
esac

stop_stack
echo "kaban.ai daemon removed."
