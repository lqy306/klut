.PHONY: all run debug ext clean

all:
	@echo "klut — Kirigami 3D LUT Viewer"
	@echo ""
	@echo "Usage:"
	@echo "  python3 main.py              # Start GUI"
	@echo "  python3 main.py --debug      # Debug mode"
	@echo "  python3 main.py --lang en    # English UI"
	@echo ""
	@echo "Build:"
	@echo "  make ext                     # Package extensions as .klutx"
	@echo "  make clean                   # Clean build artifacts"

run:
	python3 main.py

debug:
	python3 main.py --debug

ext:
	@echo "Building extension packages..."
	@mkdir -p dist
	@for d in extensions/*/; do \
	  if [ -f "$$d/manifest.json" ]; then \
	    name=$$(basename "$$d"); \
	    echo "  $$name → dist/$$name.lutx"; \
	    (cd "$$d" && zip -qr "../../dist/$$name.lutx" .); \
	  fi; \
	done
	@echo "Done."

clean:
	rm -rf build/ dist/ __pycache__ */__pycache__ */*/__pycache__
	find . -name "*.pyc" -delete
