"""Camara falsa para los tests: emite 3 'frames' en formato mpjpeg y termina."""
import sys
for i in range(3):
    jpg = b"\xff\xd8FAKE%d\xff\xd9" % i
    sys.stdout.buffer.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg) + jpg + b"\r\n")
sys.stdout.buffer.flush()
