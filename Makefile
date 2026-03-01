.PHONY: setup ci lint test coverage typecheck security hooks run

setup:
	python3 -m pip install -r requirements.txt
	python3 -m pip install -r requirements-dev.txt

ci: setup lint typecheck security coverage

lint:
	python3 -m ruff check .

test:
	python3 -m pytest -q

coverage:
	python3 -m pytest --cov=. --cov-report=term-missing --cov-fail-under=80 -q

typecheck:
	python3 -m mypy .

security:
	python3 -m bandit -r routes server.py middleware.py state.py cleanup.py -ll -s B104

hooks:
	pre-commit install

run:
	python3 server.py
