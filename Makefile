.PHONY: install test lint format run dashboard clean

install:
	pip install -e ".[dev]"
	cd dashboard-ui && npm install

test:
	pytest tests/ --cov=. --cov-report=term-missing

lint:
	ruff check .
	cd dashboard-ui && pnpm lint

format:
	black .
	isort .
	cd dashboard-ui && pnpm prettier --write .

run:
	python -m cli --run

dashboard:
	python -m cli --dashboard

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
