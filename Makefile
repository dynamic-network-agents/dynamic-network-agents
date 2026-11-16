.PHONY: install test lint run clean

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check src tests

run:
	uv run python -m src.agents.main

clean:
	rm -rf build dist *.egg-info .pytest_cache htmlcov
