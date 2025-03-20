# src/wamp/subscriber.py
import asyncio
import threading
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner

global_session_sub = None

class MultiTopicSubscriber(ApplicationSession):
    def __init__(self, config):
        super().__init__(config)
        self.topics = []  # Se asigna mediante la factoría
        self.on_message_callback = None

    async def onJoin(self, details):
        global global_session_sub
        realm_name = self.config.realm
        print(f"Suscriptor conectado en realm: {realm_name}")
        global_session_sub = self
        for t in self.topics:
            await self.subscribe(
                lambda *args, topic=t, **kwargs: self.on_event(realm_name, topic, *args, **kwargs),
                t
            )

    def on_event(self, realm, topic, *args, **kwargs):
        message_data = {"args": args, "kwargs": kwargs}
        if self.on_message_callback:
            self.on_message_callback(realm, topic, message_data)

    @classmethod
    def factory(cls, topics, on_message_callback):
        def create_session(config):
            session = cls(config)
            session.topics = topics
            session.on_message_callback = on_message_callback
            return session
        return create_session

def start_subscriber(url, realm, topics, on_message_callback):
    global global_session_sub
    if global_session_sub is not None:
        try:
            global_session_sub.leave()
            print("Sesión previa cerrada.")
        except Exception as e:
            print("Error al cerrar la sesión previa:", e)
        global_session_sub = None

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = ApplicationRunner(url=url, realm=realm)
        runner.run(MultiTopicSubscriber.factory(topics, on_message_callback))
    threading.Thread(target=run, daemon=True).start()
