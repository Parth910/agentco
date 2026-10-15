#!/usr/bin/env bash
# AgentCo setup: checks prerequisites, picks a model, starts services.
# Usage: ./setup.sh [--yes] [--model <name>]
set -euo pipefail

cd "$(dirname "$0")"

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
ASSUME_YES=false
MODEL=""

usage() {
  echo "Usage: ./setup.sh [--yes] [--model <name>]"
  echo "  -y, --yes          answer yes to all prompts"
  echo "  -m, --model NAME   use this Ollama model instead of the RAM-based pick"
}

while [ $# -gt 0 ]; do
  case "$1" in
    -y|--yes) ASSUME_YES=true ;;
    -m|--model) MODEL="${2:?--model needs a value}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
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

confirm() {
  $ASSUME_YES && return 0
  local reply
  read -r -p "? $1 [Y/n] " reply
  [[ -z "$reply" || "$reply" =~ ^[Yy] ]]
}

# --- model ------------------------------------------------------------------
ram_gb() {
  case "$(uname -s)" in
    Darwin) echo $(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 )) ;;
    Linux) echo $(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 / 1024 )) ;;
    *) echo 0 ;;
  esac
}

recommend_model() {
  local ram=$1
  if   [ "$ram" -ge 32 ]; then echo "qwen3:14b"
  elif [ "$ram" -ge 16 ]; then echo "qwen3:8b"
  else                         echo "qwen3:4b"
  fi
}

choose_model() {
  if [ -n "$MODEL" ]; then
    ok "Using model from --model: $MODEL"
    return
  fi
  local ram
  ram=$(ram_gb)
  MODEL=$(recommend_model "$ram")
  ok "Detected ${ram} GB RAM → recommended model: $MODEL"
  [ "$ram" -lt 16 ] && warn "Under 16 GB RAM: runs will be slow and the model is limited."
  return 0
}

ensure_model() {
  if ollama show "$MODEL" >/dev/null 2>&1; then
    ok "Model ready ($MODEL)"
    return
  fi
  confirm "Pull $MODEL now? (several GB, one-time download)" \
    || fail "A model is required. Pull it later with: ollama pull $MODEL"
  ollama pull "$MODEL"
  ok "Model ready ($MODEL)"
}

# --- config -----------------------------------------------------------------
set_env() {
  # set_env KEY VALUE: replace the line in .env (portable across macOS/Linux sed)
  local key=$1 value=$2 tmp
  tmp=$(mktemp)
  if grep -q "^${key}=" .env; then
    awk -v k="$key" -v v="$value" -F= '$1==k {print k"="v; next} {print}' .env > "$tmp"
  else
    cat .env > "$tmp"; echo "${key}=${value}" >> "$tmp"
  fi
  mv "$tmp" .env
}

ensure_env() {
  if [ -f .env ]; then
    ok "Using existing .env"
  else
    cp .env.example .env
    ok "Created .env from .env.example"
  fi
  set_env LLM_MODEL "$MODEL"
}

# --- services ---------------------------------------------------------------
api_port() {
  grep -E '^WORKSPACE_API_PORT=' .env | cut -d= -f2 || true
}

start_services() {
  echo "… Starting services (first run builds images, this can take a minute)"
  docker compose up -d --build --wait \
    || fail "Services failed to start. See logs with: docker compose logs"
  ok "Services healthy"
}

report_llm() {
  local port health
  port=$(api_port); port=${port:-8000}
  health=$(curl -fsS "http://localhost:$port/health") || fail "API not responding on port $port"
  if echo "$health" | grep -q '"reachable":true'; then
    if echo "$health" | grep -q '"model_available":true'; then
      ok "API can reach the LLM ($MODEL)"
    else
      warn "API reaches the LLM, but model '$MODEL' is not listed there"
    fi
  else
    warn "API cannot reach Ollama from inside Docker."
    [ "$(uname -s)" = "Linux" ] && warn "On Linux, start Ollama with OLLAMA_HOST=0.0.0.0 so containers can reach it."
  fi
  echo
  green "🚀 AgentCo is ready → http://localhost:$port/health"
  echo "   (The dashboard arrives in milestone M8.)"
}

main() {
  echo "AgentCo setup"
  echo
  check_docker
  check_ollama
  choose_model
  ensure_model
  ensure_env
  start_services
  report_llm
}

main
