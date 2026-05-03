.PHONY: install test lint fmt demo market-service sdk-demo axl-demo axl-demo-external forge-test

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

market-service:
	PYTHONPATH=. python scripts/serve_trade_playback.py

sdk-demo:
	PYTHONPATH=. python examples/seller_sdk_quickstart.py

axl-demo:
	PYTHONPATH=. python scripts/run_axl_demo.py

axl-demo-external:
	PYTHONPATH=. python scripts/run_axl_demo.py --external

forge-test:
	forge test -vv
