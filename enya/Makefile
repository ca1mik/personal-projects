.PHONY: api worker web doctor start-local docker-up

api:
	python scripts/dev_api.py

worker:
	python scripts/run_worker.py

web:
	pnpm --dir apps/web dev

doctor:
	python scripts/runtime_doctor.py

start-local:
	powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1

docker-up:
	docker compose up --build
