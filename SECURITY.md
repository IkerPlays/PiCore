# Seguridad

## Cómo avisar de un fallo

Si encuentras un fallo de seguridad, **no abras un *issue* público**. Usa **«Report a vulnerability»** en la pestaña *Security* del repositorio (aviso privado de GitHub). Incluye qué has visto, cómo reproducirlo y qué impacto crees que tiene. Responderé lo antes posible; es un proyecto personal, sin plazos garantizados.

## Qué se considera sensible

PiCore corre en una Raspberry Pi en tu casa, con acceso a cosas privadas. Lo más delicado:

- **El Modo Dev:** su consola ejecuta órdenes reales con tu usuario. Solo funciona dentro del modo Dev, desde la propia Pi y con una cabecera que ninguna web externa puede enviar; se puede apagar con `[dev] enabled = false`.
- **Las notas, la cámara y los temporizadores:** la API solo responde a la propia máquina para estas rutas.
- **Las acciones que cambian cosas** (modo, Wi-Fi, Pi-hole, apagar...): exigen la cabecera `X-PCPI` y cliente local.
- **Los secretos:** la contraseña de Pi-hole y las claves viven en `/etc/pcpi/pcpi.conf` de tu Pi. **Nunca los subas al repositorio** (ni el enlace secreto de tu calendario `.ics`).

Las defensas están descritas en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) y probadas en `tests/test_security.py`.

## Límites que conviene saber

- Nada de esto se ha probado todavía en una Raspberry Pi real.
- El servidor está pensado para escuchar en `127.0.0.1`. Si lo expones a tu red, solo se permiten desde fuera las rutas públicas de lectura.
- La demo web (Netlify) es un sitio estático sin servidor ni secretos: no ejecuta nada real.
