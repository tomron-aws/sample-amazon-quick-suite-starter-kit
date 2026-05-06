.PHONY: build format lint test validate

build:
	@echo "Building Python package..."
	uv sync --all-extras

format:
	@echo "Formatting Python code..."
	uv run ruff format src/

lint:
	@echo "Linting Python code..."
	uv run ruff check src/ --fix

test:
	@echo "Running tests..."
	uv run pytest tests/ -v

validate: format lint build test
	@echo "✓ All checks passed!"
