.PHONY: up down logs mock dbt-build dbt-test

up:            ## Tüm stack'i ayağa kaldır
	docker compose up -d --build

down:          ## Stack'i kapat
	docker compose down

logs:          ## Logları izle
	docker compose logs -f

mock:          ## Sentetik veriyi üret ve source-db'ye bas
	docker compose run --rm mock-data python generate.py

dbt-build:     ## dbt seed + run + test
	docker compose run --rm dbt build

dbt-test:      ## Sadece dbt testleri
	docker compose run --rm dbt test
