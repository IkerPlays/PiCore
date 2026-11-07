.PHONY: test rapido emulate demo lint mini-preview
test:        ## Ejecuta todos los tests
	python3 -m unittest discover tests -v
rapido:      ## Tests que no abren navegador: ~3 min en vez de ~8 (627 tests)
	python3 -m unittest -q $(addprefix tests.,$(filter-out test_ui_smoke test_pi_virtual test_loading_ui test_screensaver test_web_demo,$(basename $(notdir $(wildcard tests/test_*.py)))))
emulate:     ## Arranca el emulador en http://127.0.0.1:8080 (escribe ordenes de voz en la terminal)
	python3 tools/emulate.py
demo:        ## Demo web en http://127.0.0.1:8081 (la misma que se despliega en Netlify; sin Python en el servidor)
	python3 tools/serve_web_demo.py
lint:        ## Comprueba los scripts de shell y Python
	./tools/lint-shell.sh
	python3 -m py_compile home/*.py voice/*.py stats/*.py tools/*.py training/*.py bin/pcpi-wifi bin/pcpi-backup bin/pcpi-update bin/pcpi-config
	@if python3 -c "import pyflakes" 2>/dev/null; then python3 -m pyflakes home/*.py voice/*.py tools/*.py tests/*.py bin/pcpi-config && echo "pyflakes OK"; else echo "(pyflakes no esta instalado: pip install pyflakes; se omite)"; fi

mini-preview: ## Genera preview.png con el diseno de la mini pantalla (sin hardware)
	python3 stats/miniscreen.py --backend png --once --out preview.png
