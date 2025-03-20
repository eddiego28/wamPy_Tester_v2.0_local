# tests/test_publisher.py
import time
from src.wamp.publisher import start_publisher, send_message_now

def test_start_publisher():
    """
    Se prueba que iniciar el publicador no arroje excepciones.
    """
    try:
        start_publisher("ws://127.0.0.1:60001/ws", "TestRealm", "TestTopic")
        # Se espera un momento para que se inicie el hilo
        time.sleep(1)
    except Exception as e:
        assert False, f"start_publisher falló: {e}"

def test_send_message_now():
    """
    Se prueba que enviar un mensaje sin una sesión activa maneje la situación sin excepción.
    """
    try:
        send_message_now("TestTopic", {"key": "value"}, delay=0)
    except Exception as e:
        assert False, f"send_message_now arrojó excepción: {e}"
