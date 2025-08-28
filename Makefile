.PHONY: build up down reset logs shell

build:
	docker compose build

up:
	docker compose up --build -d

down:
	docker compose down

reset:
	docker compose down -v
	docker compose up --build -d

logs:
	docker compose logs -f app

shell:
	docker compose exec app /bin/bash
