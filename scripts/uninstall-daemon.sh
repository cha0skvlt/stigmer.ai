#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OS="$(uname -s)"
LABEL="ai.stigmer"

stop_stack() {
  if [[ -x "$ROOT/scripts/stigmer" ]]; then
    STIGMER_DAEMON_QUIET=1 "$ROOT/scripts/stigmer" stop || true
  elif [[ -x "$ROOT/scripts/daemon.sh" ]]; then
    STIGMER_DAEMON_QUIET=1 "$ROOT/scripts/daemon.sh" stop || true
  fi
}

case "$OS" in
  Linux)
    if systemctl --user is-active stigmer.service >/dev/null 2>&1; then
      systemctl --user stop stigmer.service || true
    fi
    if systemctl --user is-enabled stigmer.service >/dev/null 2>&1; then
      systemctl --user disable stigmer.service || true
    fi
    rm -f "$HOME/.config/systemd/user/stigmer.service"
    systemctl --user daemon-reload || true

    if systemctl is-active stigmer.service >/dev/null 2>&1; then
      sudo systemctl stop stigmer.service || true
    fi
    if systemctl is-enabled stigmer.service >/dev/null 2>&1; then
      sudo systemctl disable stigmer.service || true
    fi
    if [[ -f /etc/systemd/system/stigmer.service ]]; then
      sudo rm -f /etc/systemd/system/stigmer.service
      sudo systemctl daemon-reload || true
    fi
    ;;
  Darwin)
    launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
    rm -f "$HOME/Library/LaunchAgents/${LABEL}.plist"
    ;;
  *)
    echo "Unsupported OS: $OS" >&2
    exit 1
    ;;
esac

stop_stack
echo "stigmer.ai daemon removed."
