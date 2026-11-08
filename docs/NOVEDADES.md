# Novedades de PiCore (resumen por temas)

El detalle paso a paso, con fechas, está en el [registro de cambios](../CHANGELOG.md). Esto es la versión corta. Recuerda: **nada se ha probado todavía en una Raspberry Pi real**; todo lo de abajo está probado con tests automáticos, un «Pi virtual» y el simulador.

## Ajustes desde la pantalla (sin editar archivos)

- **Ciudad** del tiempo: se busca por nombre con el teclado en pantalla.
- **Pi-hole:** «Conectar Pi-hole» guarda la contraseña y la prueba al momento.
- **Salvapantallas y modo noche:** activar, minutos de espera, horas y brillo de noche (hoja Sistema).
- Las alertas de la hoja Sistema traen su botón («Elegir ciudad», «Conectar Pi-hole», «Abrir Wi-Fi»).
- El servidor solo escribe una lista cerrada de ajustes y valida cada valor.

## Voz (Whisper, sin nube)

Además de la hora, el tiempo, los modos, la música y el brillo, ahora entiende:

- **Temporizadores con nombre** («para la pasta»), «añade un minuto», «avísame en veinte minutos», alarmas **diarias**.
- **Notas y listas:** «toma nota…», «lee mi última nota», «añade leche a la lista de la compra», «cuántas notas tengo».
- **Información:** el tiempo de **mañana**, la hora en otras ciudades, el próximo evento, cuánto espacio libre queda, la temperatura de la Pi, la wifi, qué canción suena, cuánto falta para Navidad.
- **Otras:** «repite», «qué puedes hacer», «tira un dado», «cara o cruz», «dime un número al azar entre 1 y 10», «cuéntame un chiste», «deletrea hola».
- **Cuentas y unidades:** «cuánto es 12 por 5», «el 20 por ciento de 50», «cuántos kilómetros son 10 millas», «pasa 20 grados a fahrenheit».
- **Fechas:** «qué hora será dentro de veinte minutos», «en qué año estamos», «qué día cae el 25 de diciembre», «cuántos días tiene febrero».
- **Cortesía:** «cómo te llamas», «me oyes», «buenas noches».

La lista completa está en el [tutorial](TUTORIAL.md#qué-puedes-pedir). La palabra de activación por defecto es «Hey Jarvis».

## Modo Iker y Musix

- Notas: **fijar** arriba, **duplicar**, contador (con tiempo de lectura) y Ctrl+P.
- MP3 Player: **repetir** (todo / una / nada) y **búsqueda** cuando hay muchas canciones.
- Temporizadores: botón **+1 min**.
- Modo Dev: el historial de la consola se recuerda y hay más órdenes rápidas.

## La web (picoreweb.netlify.app)

- **Portada** que explica qué es, para qué sirve, cómo funciona, cómo instalarlo y preguntas frecuentes, con tema claro/oscuro.
- **Simulador** con barra de **voz escrita**, **visita guiada** de 15 pasos, atajos de teclado y botón «Copiar enlace».

## Calidad

- Más de 660 tests, incluida la comprobación de que el JavaScript de todas las páginas es válido y una tabla de frases de voz para detectar solapes.
- `make rapido` (≈3 min) para comprobar sin abrir el navegador.

## Efectos y web

- **Toda la interfaz:** destello al tocar, tarjetas que se hunden al pulsarlas y cifras de ancho fijo (se apaga con «reducir movimiento»).
- **Portada web:** secciones que aparecen al hacer scroll, barra de progreso, botón «Volver arriba», pestañas con flechas del teclado y barra superior fija.
- **Simulador:** tecla «?» para ver los atajos, y se puede añadir a la pantalla de inicio del móvil.
- **Regenerar capturas:** `make capturas`.
