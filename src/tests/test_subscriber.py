# tests/test_subscriber.py
import time
from src.wamp.subscriber import start_subscriber

def dummy_on_message(realm, topic, message):
    print("Mensaje dummy recibido:", realm, topic, message)

def test_start_subscriber():
    """
    Se prueba que iniciar el suscriptor no arroje excepciones.
    """
    try:
        start_subscriber("ws://127.0.0.1:60001/ws", "TestRealm", ["TestTopic"], dummy_on_message)
        time.sleep(1)
    except Exception as e:
        assert False, f"start_subscriber falló: {e}"
