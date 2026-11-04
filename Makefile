.PHONY: test emulate lint
test:        ## Ejecuta todos los tests
	python3 -m unittest discover tests -v
emulate:     ## Arranca el emulador en http://127.0.0.1:8080 (escribe ordenes de voz en la terminal)
	python3 tools/emulate.py
lint:        ## Comprueba los scripts de shell y Python
	bash -n install.sh uninstall.sh bin/*
	python3 -m py_compile home/server.py voice/*.py tools/*.py training/*.py
