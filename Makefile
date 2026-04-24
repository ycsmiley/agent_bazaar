.PHONY: install test lint fmt demo forge-test

install:
	python -m pip install -e '.[dev]'

test:
	pytest -q

lint:
	ruff check .

fmt:
	ruff format .

demo:
	bash scripts/run_demo.sh

forge-test:
	forge test -vv
