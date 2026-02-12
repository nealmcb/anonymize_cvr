.PHONY: help check format lint typecheck test install clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies using uv"
	@echo "  make check      - Run all quality checks (format, lint, typecheck, test)"
	@echo "  make format     - Format code with black"
	@echo "  make lint       - Lint code with ruff"
	@echo "  make typecheck  - Type check with mypy"
	@echo "  make test       - Run tests with pytest"
	@echo "  make clean      - Clean up generated files"

install:
	uv pip install -e ".[dev]"

format:
	black --check *.py

lint:
	ruff check *.py

typecheck:
	mypy --strict *.py

test:
	pytest

check: format lint typecheck test
	@echo "All checks passed!"

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
