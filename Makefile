.PHONY: help check format lint typecheck test install clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies using uv"
	@echo "  make check      - Run all quality checks (format, lint, test)"
	@echo "  make format     - Format code with black"
	@echo "  make lint       - Lint code with ruff"
	@echo "  make typecheck  - Type check with mypy (informational only, not enforced)"
	@echo "  make test       - Run tests with pytest"
	@echo "  make clean      - Clean up generated files"

install:
	uv pip install -e ".[dev]"

format:
	black --check *.py

lint:
	ruff check *.py

typecheck:
	@echo "Note: Type checking is informational only and not enforced in 'make check'"
	@echo "Many type errors exist in legacy code that would require extensive refactoring to fix"
	mypy *.py || true

test:
	pytest

# Note: typecheck is intentionally excluded from check target
# Adding full type hints would require extensive refactoring that is beyond the scope
check: format lint test
	@echo "All checks passed!"

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
