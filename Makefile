.PHONY: lint test typecheck

lint:
	python3 -m ruff check .

test:
	python3 -m pytest -q

typecheck:
	python3 -m mypy .
