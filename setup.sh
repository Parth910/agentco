#!/usr/bin/env bash
# AgentCo setup: checks prerequisites, picks a model, starts services.
# Usage: ./setup.sh [--yes]
set -euo pipefail

cd "$(dirname "$0")"

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
ASSUME_YES=false

for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=true ;;
    -h|--help)
      echo "Usage: ./setup.sh [--yes]"
      echo "  -y, --yes    answer yes to all prompts"
      exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

# --- output helpers ---------------------------------------------------------
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
red() { printf '\033[31m%s\033[0m\n' "$*"; }
ok() { green "✔ $*"; }
warn() { yellow "! $*"; }
fail() { red "✘ $*"; exit 1; }

# --- checks -----------------------------------------------------------------
check_docker() {
  command -v docker >/dev/null 2>&1 \
    || fail "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
  docker info >/dev/null 2>&1 \
    || fail "Docker is installed but not running. Start Docker Desktop and re-run ./setup.sh"
  docker compose version >/dev/null 2>&1 \
    || fail "'docker compose' not available. Update Docker Desktop."
  ok "Docker running"
}

check_ollama() {
  command -v ollama >/dev/null 2>&1 \
    || fail "Ollama not found. Install it: https://ollama.com/download"
  curl -fsS "$OLLAMA_URL/api/version" >/dev/null 2>&1 \
    || fail "Ollama is installed but not running. Start the Ollama app (or run 'ollama serve') and re-run ./setup.sh"
  ok "Ollama running"
}

main() {
  echo "AgentCo setup"
  echo
  check_docker
  check_ollama
}

main
