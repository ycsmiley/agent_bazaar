.PHONY: install test lint fmt demo trace trade-playback forge-test

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

trace:
	PYTHONPATH=. python scripts/generate_market_trace.py

trade-playback:
	PYTHONPATH=. python scripts/serve_trade_playback.py

forge-test:
	forge test -vv
