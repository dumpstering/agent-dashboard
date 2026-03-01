.PHONY: setup ci lint test typecheck security

setup:
	python3 -m pip install -r requirements.txt
	python3 -m pip install -r requirements-dev.txt

ci: setup lint typecheck security test

lint:
	python3 -m ruff check .

test:
	python3 -m pytest -q

typecheck:
	python3 -m mypy .

security:
	python3 -m bandit -r routes server.py middleware.py state.py cleanup.py -ll -s B104
