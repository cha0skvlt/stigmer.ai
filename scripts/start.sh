#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

log() { printf '==> %s\n' "$*"; }
warn() { printf '!! %s\n' "$*" >&2; }
die() { warn "$*"; exit 1; }

load_env() {
  if [[ ! -f .env ]]; then
    log "Creating .env from .env.example"
    cp .env.example .env
  fi
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
}

wait_for() {
  local url="$1" label="$2" tries="${3:-60}"
  for ((i = 1; i <= tries; i++)); do
    if curl -sf "$url" >/dev/null 2>&1; then
      log "$label is ready"
      return 0
    fi
    sleep 1
  done
  die "$label did not become ready: $url"
}

ensure_docker() {
  if docker info >/dev/null 2>&1; then
    log "Docker is running"
    return 0
  fi

  warn "Docker is not running"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    if [[ -d /Applications/OrbStack.app ]]; then
      log "Starting OrbStack..."
      open -a OrbStack
    elif [[ -d /Applications/Docker.app ]]; then
      log "Starting Docker Desktop..."
      open -a Docker
    else
      die "Install OrbStack or Docker Desktop, then run make start again"
    fi
  else
    die "Start Docker manually, then run make start again"
  fi

  for ((i = 1; i <= 90; i++)); do
    if docker info >/dev/null 2>&1; then
      log "Docker is ready"
      return 0
    fi
    sleep 1
  done
  die "Docker did not start in time"
}

is_ollama_mode() {
  local url="${OPENAI_BASE_URL:-}"
  local key="${OPENAI_API_KEY:-}"

  [[ "$key" == "ollama" ]] && return 0
  [[ "$url" == *":11434"* ]] && return 0
  [[ "$url" == *"localhost"* && "$url" == *"11434"* ]] && return 0
  [[ "$url" == *"127.0.0.1"* && "$url" == *"11434"* ]] && return 0
  return 1
}

ollama_host_url() {
  printf '%s\n' "http://127.0.0.1:11434"
}

ensure_ollama() {
  local base
  base="$(ollama_host_url)"

  if curl -sf "$base/api/tags" >/dev/null 2>&1; then
    log "Ollama is already running"
    return 0
  fi

  warn "Ollama is not responding"
  if command -v ollama >/dev/null 2>&1; then
    log "Starting ollama serve..."
    nohup ollama serve >/tmp/stigmer-ollama.log 2>&1 &
  elif [[ "$(uname -s)" == "Darwin" && -d /Applications/Ollama.app ]]; then
    log "Starting Ollama app..."
    open -a Ollama
  else
    die "Ollama not found. Install from https://ollama.com or fix OPENAI_BASE_URL for an external API"
  fi

  wait_for "$base/api/tags" "Ollama" 90
}

ensure_ollama_model() {
  local model="${OPENAI_MODEL:?OPENAI_MODEL is not set in .env}"

  if command -v ollama >/dev/null 2>&1; then
    if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$model"; then
      log "Model already available: $model"
      return 0
    fi
  else
    local base
    base="$(ollama_host_url)"
    if curl -sf "$base/api/tags" | grep -Fq "\"name\":\"${model}\""; then
      log "Model already available: $model"
      return 0
    fi
  fi

  command -v ollama >/dev/null 2>&1 || die "ollama CLI not found; install it to pull $model"

  log "Pulling model: $model"
  ollama pull "$model"
  log "Model ready: $model"
}

verify_external_api() {
  local base="${OPENAI_BASE_URL:?OPENAI_BASE_URL is not set in .env}"
  local key="${OPENAI_API_KEY:-}"

  [[ -n "$key" && "$key" != "ollama" ]] || die "Set OPENAI_API_KEY in .env for external AI provider"

  base="${base%/}"
  log "Checking external AI API: $base"

  if curl -sf "$base/models" -H "Authorization: Bearer $key" >/dev/null 2>&1; then
    log "External AI API connection OK"
    return 0
  fi

  warn "Could not verify external API via GET /models"
  warn "Continuing anyway — if AI commands fail, check OPENAI_BASE_URL, OPENAI_API_KEY, and OPENAI_MODEL"
}

start_stack() {
  log "Building and starting Docker stack..."
  docker compose up --build -d
  wait_for "http://localhost:8080/api/health" "STIGMER AI stack" 90
}

print_summary() {
  cat <<EOF

STIGMER AI is running.

  UI:      http://localhost:8080
  Health:  http://localhost:8080/api/health
  Model:   ${OPENAI_MODEL:-n/a}
  API:     ${OPENAI_BASE_URL:-n/a}

Useful commands:
  make logs
  make health
  make stop
  make restart

EOF
}

main() {
  load_env
  ensure_docker

  if is_ollama_mode; then
    log "Mode: local Ollama"
    ensure_ollama
    ensure_ollama_model
  else
    log "Mode: external AI API"
    verify_external_api
  fi

  start_stack
  print_summary
}

main "$@"
