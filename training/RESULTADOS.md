# Resultados del entrenamiento de «Oye Pi»

> **Conclusión corta: no he conseguido un «Oye Pi» fiable.** Con solo voces sintéticas como ejemplos positivos, todos los métodos probados se activan demasiado con voz real o fallan demasiado. **El predeterminado sigue siendo `hey_jarvis`** (modelo preentrenado de openWakeWord). El modelo `models/wake/oye_pi_experimental.onnx` se deja solo para probarlo con tu voz; **no lo uses como predeterminado.**

## Cómo se midió

Todo con el detector real (`openwakeword.Model` en streaming) sobre datos **que el modelo no vio al entrenar**:

- **Falsas activaciones por hora:** 4,1 h de voz humana real en español (FLEURS), con antirrebote de 2 s.
- **Acierto («recall»):** 288 locuciones de «oye pi» de 2 voces Piper reservadas, dentro de ruido o voz ajena (y, como referencia, 144 de voces de entrenamiento).
- **Frases parecidas aceptadas:** «oye pepe», «pipa», «hoy», órdenes habituales… (154 clips).

Referencia: un detector usable necesita **≲ 1 falsa activación por hora** con un acierto alto.

## Resultados

| Método | Umbral | Falsas act./hora (voz real) | Acierto voces nuevas | Frases parecidas aceptadas |
|---|---|---|---|---|
| **v1** (`oye_pi_experimental.onnx`): negativos recortados + 1 ronda de *mining* | 0,5 | **75** | 0,48 | 0,20 |
| | 0,7 | 53 | 0,43 | 0,15 |
| | 0,9 | 26 | 0,36 | 0,10 |
| **v2**: ventanas densas de voz real (312.000) + *mining* | 0,5 | **96** | 0,41 | 0,20 |
| | 0,9 | 26 | 0,25 | 0,10 |
| v2 + *mining* con validación cruzada, 2 variantes (medido sobre embeddings) | 0,5–0,9 | 14–30 | 0,20–0,39 | 0,01–0,10 |
| **Vosk con gramática** («oye pi» + `[unk]`) | n/a | **29** | 0,30 | 0,14 |
| **Vosk de vocabulario abierto** buscando el texto | n/a | 0 | 0,01 | 0,01 |
| *(referencia)* `hey_jarvis` de openWakeWord | 0,5 | no medido aquí; modelo entrenado por sus autores con miles de horas de negativos | | |

Los informes completos están en [`results/`](results/).

## Por qué falla

- **Todos los positivos son sintéticos.** Con 9 voces de Piper, el modelo aprende lo que tienen en común esas voces y generaliza mal a otras, y todavía peor a una voz humana real (el acierto cae de ~0,85 con voces de entrenamiento a ~0,45 con voces no vistas).
- **Pocos negativos reales.** 9 h de voz de FLEURS son poco frente a las miles de horas con las que se entrenan los modelos oficiales. Cualquier palabra rara en esas 9 h puede activarlo.
- **El «oye pi» sintético se parece mucho a ruido de voz.** Es una frase muy corta (3 sílabas), difícil de distinguir de otras.
- **El resultado es muy inestable** entre ejecuciones (23–96 falsas/h con la misma configuración), señal de que el modelo está al límite de lo que le dan los datos.

## Cómo conseguir un «Oye Pi» bueno

1. **Grabar tu voz real** con `pcpi-record-wake 60` (variando tono, distancia y ruido; mejor si también graba alguien más de casa) y reentrenar con `--real-pos` (ver [README](README.md)). Es lo que más cambia las cosas, y **no lo he podido probar**.
2. **Usar el pipeline oficial de openWakeWord** (cuaderno de entrenamiento automático) con GPU: genera decenas de miles de ejemplos sintéticos y los mezcla con unas 2.000 h de negativos y respuestas de sala reales. Es la forma de entrenar con calidad.
3. Mientras tanto: **`hey_jarvis`** (predeterminado), `alexa` u otro de los modelos incluidos.
