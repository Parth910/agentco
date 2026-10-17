# AgentCo: friendly entry points. The real logic lives in ./setup.sh and ./agentco.
# Run `make` or `make help` to see all targets.

.DEFAULT_GOAL := help
.PHONY: help setup start stop restart status logs launch llm-test tools-demo test

# Optional: make setup MODEL=qwen2.5:3b CONTEXT=8192 YES=1
SETUP_ARGS := $(if $(MODEL),--model $(MODEL)) $(if $(CONTEXT),--context $(CONTEXT)) $(if $(YES),--yes)

help: ## Show this help
	@echo "AgentCo"
	@echo
	@echo "Usage: make <target>"
	@echo
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo
	@echo "Options for setup:"
	@echo "  MODEL=<name>   use a specific Ollama model   (make setup MODEL=qwen2.5:3b)"
	@echo "  CONTEXT=<n>    context window in tokens          (make setup CONTEXT=8192)"
	@echo "  YES=1          answer yes to all prompts"

setup: ## First-time setup: check tools, pull model, start services
	@./setup.sh $(SETUP_ARGS)

start: ## Start all services (rebuilds if code changed)
	@./agentco start

stop: ## Stop all services
	@./agentco stop

restart: stop start ## Restart all services

status: ## Show services, Ollama and LLM status
	@./agentco status

logs: ## Follow service logs (Ctrl+C to exit)
	@./agentco logs

launch: ## Launch the team on an idea: make launch IDEA="..."
	@[ -n "$(IDEA)" ] || { echo 'Usage: make launch IDEA="A social feed for college students"'; exit 1; }
	@./agentco launch --idea "$(IDEA)"

llm-test: ## Check the LLM works (chat + structured output)
	@./agentco llm-test

tools-demo: ## Watch the LLM use workspace tools as different roles
	@./agentco tools-demo

test: ## Run unit tests (in Docker, no local Python needed)
	@./agentco test
