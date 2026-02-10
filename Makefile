# Define the directories and patterns to remove
CACHE_PATTERNS := **/ __pycache__ \
                  **/.pytest_cache \
                  **/.ipynb_checkpoints \
                  **/.DS_Store \
                  **/*.pyc \
                  **/*.pyo \
                  **/*.pyd \
                  **/.mypy_cache \
                  **/.sass-cache \
                  **/.eslintcache \
                  dist/ \
                  build/ \
                  *.egg-info/

.PHONY: clean help
clean:
	@echo "Cleaning up cache files..."
	@# Remove directories and files based on patterns
	@for pattern in $(CACHE_PATTERNS); do \
		find . -name "$$pattern" -prune -exec rm -rf {} + 2>/dev/null || true; \
	done
	@echo "Cleanup complete."
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'