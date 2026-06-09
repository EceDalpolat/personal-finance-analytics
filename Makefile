.PHONY: up down generate dbt-build dbt-docs logs test

up:            ## docker compose up — full stack
	docker compose up -d --build

down:          ## Stop the stack
	docker compose down

generate:      ## Run mock-data/generate.py — synthetic data into source-db
	docker compose run --rm mock-data python generate.py

dbt-build:     ## dbt seed + run + test
	docker compose run --rm dbt build

dbt-docs:      ## dbt docs generate + serve
	docker compose run --rm --service-ports dbt docs serve

logs:          ## Open Grafana at localhost:3000 (and tail compose logs)
	docker compose logs -f

test:          ## pytest (api + ai-engine)
	docker compose run --rm api pytest
	docker compose run --rm ai-engine pytest
