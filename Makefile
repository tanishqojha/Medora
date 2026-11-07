.PHONY: test lint typecheck harness eval web-check
test:
	cd api && uv run pytest -q
	uv run --project api python safety_harness/run.py
lint:
	cd api && uv run ruff check medora tests ../worker ../scripts ../eval ../safety_harness
typecheck:
	cd api && uv run mypy medora ../worker/worker.py
harness:
	uv run --project api python safety_harness/run.py
eval:
	uv run --project api python eval/run_eval.py
	uv run --project api python eval/run_llm_eval.py
web-check:
	cd web && npm run lint && npx tsc --noEmit
