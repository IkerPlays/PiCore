.PHONY: test emulate lint mini-preview
test:        ## Ejecuta todos los tests
	python3 -m unittest discover tests -v
emulate:     ## Arranca el emulador en http://127.0.0.1:8080 (escribe ordenes de voz en la terminal)
	python3 tools/emulate.py
lint:        ## Comprueba los scripts de shell y Python
	./tools/lint-shell.sh
	python3 -m py_compile home/*.py voice/*.py stats/*.py tools/*.py training/*.py bin/pcpi-wifi bin/pcpi-backup bin/pcpi-update bin/pcpi-config

mini-preview: ## Genera preview.png con el diseno de la mini pantalla (sin hardware)
	python3 stats/miniscreen.py --backend png --once --out preview.png
