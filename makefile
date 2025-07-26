# FeatureFlagsHQ Python SDK - Development Makefile
.PHONY: help install install-dev test test-unit test-integration test-security lint format type-check security-scan clean build publish docs serve-docs

# Default target
help: ## Show this help message
	@echo "FeatureFlagsHQ Python SDK - Development Commands"
	@echo "================================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation
install: ## Install package for production
	pip install -e .

install-dev: ## Install package with development dependencies
	pip install -e ".[dev,test,docs,security]"
	pre-commit install

# Testing
test: ## Run all tests
	pytest -v --cov=featureflagshq --cov-report=term-missing --cov-report=html

test-unit: ## Run unit tests only
	pytest tests/unit/ -v --cov=featureflagshq --cov-report=term-missing

test-integration: ## Run integration tests only
	pytest tests/integration/ -v

test-security: ## Run security tests
	pytest tests/unit/test_security.py -v
	bandit -r src/featureflagshq/
	safety check

# Code Quality
lint: ## Run all linting
	flake8 src tests
	black --check src tests
	isort --check-only src tests

format: ## Format code
	black src tests examples
	isort src tests examples

type-check: ## Run type checking
	mypy src/featureflagshq

# Security
security-scan: ## Run security scans
	bandit -r src/featureflagshq/
	safety check
	pip-audit

# Build and Release
clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean ## Build package
	python -m build

publish-test: build ## Publish to TestPyPI
	python -m twine upload --repository testpypi dist/*

publish: build ## Publish to PyPI
	python -m twine upload dist/*

# Documentation
docs: ## Build documentation
	cd docs && make html

serve-docs: docs ## Serve documentation locally
	cd docs/_build/html && python -m http.server 8000

# Development
dev-setup: ## Complete development environment setup
	python -m venv venv
	@echo "Virtual environment created. Activate with:"
	@echo "  source venv/bin/activate  # On Unix/macOS"
	@echo "  venv\\Scripts\\activate     # On Windows"
	@echo ""
	@echo "Then run: make install-dev"

check-all: lint type-check test security-scan ## Run all quality checks

# CI/CD helpers
ci-test: ## Run tests for CI environment
	pytest --cov=featureflagshq --cov-report=xml --cov-report=term --junitxml=junit.xml

ci-security: ## Run security checks for CI
	bandit -r src/featureflagshq/ -f json -o bandit-report.json
	safety check --json --output safety-report.json || true

# Version management
version: ## Show current version
	@python -c "from src.featureflagshq._version import __version__; print(__version__)"

bump-patch: ## Bump patch version (1.0.0 -> 1.0.1)
	@echo "Current version: $$(python -c 'from src.featureflagshq._version import __version__; print(__version__)')"
	@echo "Implement version bumping script or use bumpversion tool"

bump-minor: ## Bump minor version (1.0.0 -> 1.1.0)
	@echo "Current version: $$(python -c 'from src.featureflagshq._version import __version__; print(__version__)')"
	@echo "Implement version bumping script or use bumpversion tool"

bump-major: ## Bump major version (1.0.0 -> 2.0.0)
	@echo "Current version: $$(python -c 'from src.featureflagshq._version import __version__; print(__version__)')"
	@echo "Implement version bumping script or use bumpversion tool"

# Examples
run-examples: ## Run example scripts
	@echo "Running basic usage example..."
	@cd examples && python basic_usage.py || echo "Configure credentials first"

# Performance testing
perf-test: ## Run performance tests
	@echo "Running performance benchmarks..."
	pytest tests/performance/ -v --benchmark-only || echo "Install pytest-benchmark for performance tests"

# Docker (optional)
docker-build: ## Build Docker image for testing
	docker build -t featureflagshq-sdk-test .

docker-test: ## Run tests in Docker container
	docker run --rm featureflagshq-sdk-test make test

# Database migrations (if you add persistence layer later)
# migrate: ## Run database migrations
# 	@echo "No migrations needed for current version"

# Monitoring and health checks
health-check: ## Run SDK health checks
	@python -c "import featureflagshq; print('SDK imports successfully')"
	@python -c "from featureflagshq import __version__; print(f'Version: {__version__}')"

# Development database (if needed for integration tests)
setup-test-db: ## Setup test database
	@echo "Setting up test fixtures..."
	@mkdir -p tests/fixtures
	@echo "Test database setup complete"

# Cleanup development environment
clean-all: clean ## Clean everything including virtual environment
	rm -rf venv/
	rm -rf .tox/
	rm -rf node_modules/  # If you add any JS tooling later

# Quick development cycle
dev: format lint type-check test-unit ## Quick development check (format, lint, type-check, unit tests)

# Full quality gate
quality-gate: clean format lint type-check test security-scan ## Full quality gate for CI/CD

# Local development server (if you add a demo server)
serve-demo: ## Serve demo application
	@echo "Demo server not implemented yet"
	@echo "Consider adding a simple Flask/FastAPI demo app in examples/"

# Generate coverage badge
coverage-badge: ## Generate coverage badge
	coverage-badge -o coverage.svg

# Update dependencies
update-deps: ## Update all dependencies
	pip-compile requirements.in
	pip-compile requirements-dev.in
	pip-compile requirements-test.in

# Show package info
info: ## Show package information
	@echo "Package: featureflagshq"
	@echo "Version: $$(python -c 'from src.featureflagshq._version import __version__; print(__version__)')"
	@echo "Description: Official Python SDK for FeatureFlagsHQ"
	@echo "Author: FeatureFlagsHQ Team"
	@echo "License: MIT"
	@echo "Python: >=3.8"
	@echo ""
	@echo "Dependencies:"
	@pip freeze | grep -E "(requests|psutil)"