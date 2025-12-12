.PHONY: test lint help pre-commit build-sse-server test-e2e

test:  ## Run tests using pytest
	uv run pytest

lint:  ## Check code style with ruff
	uv run ruff check .

pre-commit:  ## Run pre-commit hooks on all files
	uv run pre-commit run --all-files

build-sse-server:  ## Build the Go SSE server
	cd tools/sse-server && go mod tidy && go build -o ../../bin/sse-server main.go

test-e2e: build-sse-server ## Run E2E tests
	uv run pytest tests/test_e2e.py

help:  ## Show this help message
	@echo "\033[1;34mlocust-sse plugin development\033[0m"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
