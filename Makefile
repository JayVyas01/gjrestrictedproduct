# The offline demo stack (docker-compose.demo.yml). `make` alone lists the targets.
# Only demo-build needs the internet; every other target runs with --pull never / --no-build.

COMPOSE := docker compose --env-file .env.demo -f docker-compose.demo.yml
UP := $(COMPOSE) up -d --wait --pull never --no-build
CSP := default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'

.DEFAULT_GOAL := help
.PHONY: help demo-data demo-env demo-build demo demo-seed demo-reset demo-stop demo-logs demo-check need-env

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

demo-env: ## Create .env.demo with fresh keys, if missing (prints no secrets), and demo-data/
	@python3 docker/make-demo-env.py
	@$(MAKE) --no-print-directory demo-data

# The demo CSV files land here (bind-mounted into the backend). World-writable because the
# container runs as uid 10001, which on Linux owns nothing on the host; the data is synthetic.
demo-data:
	@mkdir -p demo-data && chmod 0777 demo-data

need-env: demo-data
	@test -f .env.demo || { echo "No .env.demo: run 'make demo-env' first."; exit 1; }

demo-build: demo-env ## Online, once: pull Postgres and build the backend and web images
	$(COMPOSE) pull db
	$(COMPOSE) build --pull

demo: need-env ## Start the stack offline and wait until it is healthy
	$(UP)
	@echo "Open http://localhost:8080 in Chrome"

demo-seed: need-env ## Seed the demo story (first run after `make demo`; empty database only)
	$(COMPOSE) exec -T backend python manage.py seed_demo

demo-reset: need-env ## Recreate the database from scratch, start offline and seed
	$(COMPOSE) down -v
	$(UP)
	$(COMPOSE) exec -T backend python manage.py seed_demo
	@echo "Open http://localhost:8080 in Chrome"

demo-stop: need-env ## Stop the stack (keeps the data)
	$(COMPOSE) stop

demo-logs: need-env ## Follow the logs of all services
	$(COMPOSE) logs -f --tail=200

demo-check: ## Check the health endpoint and the CSP header through Caddy
	@curl -fsS http://localhost:8080/api/health | grep -q '"ok"' || { echo "Health check failed"; exit 1; }
	@curl -fsSI http://localhost:8080/ | tr -d '\r' | grep -qixF "content-security-policy: $(CSP)" \
		|| { echo "CSP header missing or different"; exit 1; }
	@echo OK
