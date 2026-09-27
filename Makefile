.DEFAULT_GOAL := help

.PHONY: test pip build dist-clean publish-test publish help

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

test: ## Run unit tests with verbose output
	python -m unittest discover -s tests -v

pip: ## Install the package locally in editable mode with publishing dependencies
	pip install -e ".[publish]"

build: dist-clean ## Clean previous builds and compile the distribution packages
	python -m build

dist-clean: ## Remove temporary 'dist' and 'build' directories
	python -c "import pathlib, shutil; shutil.rmtree('dist', ignore_errors=True); shutil.rmtree('build', ignore_errors=True)"

publish-test: build ## Upload the distribution packages to TestPyPI
	python scripts/publish.py --repository testpypi

publish: build ## Upload the distribution packages to PyPI (Production)
	python scripts/publish.py
