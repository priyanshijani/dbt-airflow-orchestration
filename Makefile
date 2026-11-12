# Thin wrappers over docker compose. Every target prints the raw command, so Windows
# users without `make` can copy it straight into a terminal.
COMPOSE = docker compose
AIRFLOW = $(COMPOSE) exec airflow

.PHONY: dbt env up down reset ps logs generate regenerate release simulate-day smoke

env:            ## create .env from the template if it doesn't exist
	@test -f .env || cp .env.example .env

up: env         ## build and start the stack
	$(COMPOSE) up -d --build

down:           ## stop the stack (keeps data)
	$(COMPOSE) down

reset:          ## stop and DELETE all data volumes
	$(COMPOSE) down -v

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

generate:       ## generate the synthetic universe into data/generated/ (skip if committed seed exists)
	$(AIRFLOW) python -c "from generators import config, run; (config.LANDING_DIR / 'manifest.csv').exists() or run.main()"

regenerate:     ## rebuild data/generated/ from scratch (deterministic, SEED in .env)
	$(AIRFLOW) python -m generators.run

release:        ## load sources up to the initial simulated date (Jan 18, 2026)
	$(AIRFLOW) python -m generators.release

simulate-day:   ## advance the simulated clock by one day
	$(AIRFLOW) python -m generators.release --next-day

smoke:          ## run the infrastructure smoke-test DAG end to end
	$(AIRFLOW) airflow dags test smoke_test

dbt:            ## run dbt without Airflow, e.g. make dbt ARGS="build --select staging"
	docker compose run --rm --no-deps --entrypoint /opt/airflow/dbt-venv/bin/dbt airflow $(ARGS) --project-dir /opt/project/dbt --profiles-dir /opt/project/dbt --no-use-colors
