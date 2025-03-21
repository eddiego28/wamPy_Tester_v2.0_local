import os
import sys
import json
import datetime
import asyncio
import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QLineEdit, QMessageBox, QTextEdit, QTabWidget, QTreeWidget
)
from PyQt5.QtCore import Qt
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
from common.utils import log_to_file
from pubEditor import PublisherEditorWidget

# Variables globales para la sesión del publicador
global_session = None
global_loop = None


# --------------------------------------------------------------------
# JSONPublisher: sesión WAMP para publicar en un realm/topic
# --------------------------------------------------------------------
class JSONPublisher(ApplicationSession):
    def __init__(self, config, topic):
        super().__init__(config)
        self.topic = topic

    async def onJoin(self, details):
        global global_session, global_loop
        global_session = self
        global_loop = asyncio.get_event_loop()
        print(f"✅ Conexión establecida en el publicador (realm: {self.config.realm})")
        await asyncio.Future()  # Mantiene la sesión activa


# --------------------------------------------------------------------
# start_publisher: inicia la sesión en un hilo separado.
# --------------------------------------------------------------------
def start_publisher(url, realm, topic):
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = ApplicationRunner(url=url, realm=realm)
        runner.run(lambda config: JSONPublisher(config, topic))

    threading.Thread(target=run, daemon=True).start()


# --------------------------------------------------------------------
# send_message_now: envía el mensaje con delay (opcional)
# --------------------------------------------------------------------
def send_message_now(topic, message, delay=0):
    global global_session, global_loop
    if global_session is None or global_loop is None:
        print("⚠ No hay sesión activa. Inicia el publicador primero.")
        return

    async def _send():
        if delay > 0:
            await asyncio.sleep(delay)
        global_session.publish(topic, message)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_to_file(timestamp, topic, "publicador", json.dumps(message, indent=2, ensure_ascii=False))
        print(f"📤 Mensaje enviado en {topic}: {message}")

    asyncio.run_coroutine_threadsafe(_send(), global_loop)


# --------------------------------------------------------------------
# PublisherTab: interfaz principal del publicador.
# --------------------------------------------------------------------
class PublisherTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.realms_topics = {}  # Se carga desde el JSON de configuración
        self.initUI()
        self.load_realm_topic_config()

    def initUI(self):
        layout = QVBoxLayout()

        # 🔹 Selección de Realm y Topic
        realm_topic_layout = QHBoxLayout()
        realm_topic_layout.addWidget(QLabel("Seleccionar Realm:"))
        self.realmDropdown = QComboBox()
        self.realmDropdown.addItem("Seleccionar Realm")
        realm_topic_layout.addWidget(self.realmDropdown)

        realm_topic_layout.addWidget(QLabel("Seleccionar Topic:"))
        self.topicDropdown = QComboBox()
        self.topicDropdown.addItem("Seleccionar Topic")
        realm_topic_layout.addWidget(self.topicDropdown)
        layout.addLayout(realm_topic_layout)

        # 🔹 Modo de publicación
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Modo de publicación:"))
        self.modeCombo = QComboBox()
        self.modeCombo.addItems(["On Demand", "Hora de sistema", "Programado"])
        mode_layout.addWidget(self.modeCombo)

        mode_layout.addWidget(QLabel("Hora (HH:MM:SS):"))
        self.timeEdit = QLineEdit("00:00:00")
        mode_layout.addWidget(self.timeEdit)

        layout.addLayout(mode_layout)

        # 🔹 Editor JSON
        self.editorWidget = PublisherEditorWidget(self)
        layout.addWidget(self.editorWidget)

        # 🔹 Botón de enviar mensaje
        self.sendButton = QPushButton("Enviar Mensaje")
        self.sendButton.clicked.connect(self.handle_publish_mode)
        layout.addWidget(self.sendButton)

        self.setLayout(layout)

    # ----------------------------------------------------------------
    # 📥 Cargar configuración de realms y topics desde JSON
    # ----------------------------------------------------------------
    def load_realm_topic_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "realm_topic_config.json")
        if not os.path.exists(config_path):
            print("⚠ Archivo de configuración no encontrado.")
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.realms_topics = {
                item["realm"]: {"router_url": item.get("router_url", "ws://127.0.0.1:60001/ws"), "topics": item.get("topics", [])}
                for item in data.get("realms", [])
            }

            self.realmDropdown.clear()
            self.realmDropdown.addItem("Seleccionar Realm")
            for realm in self.realms_topics.keys():
                self.realmDropdown.addItem(realm)

            self.realmDropdown.currentIndexChanged.connect(self.update_topic_dropdown)

            print("✅ Configuración de realms/topics cargada correctamente.")

        except Exception as e:
            print(f"❌ Error al cargar configuración: {e}")

    # ----------------------------------------------------------------
    # 📥 Actualizar topics disponibles según el realm seleccionado
    # ----------------------------------------------------------------
    def update_topic_dropdown(self):
        selected_realm = self.realmDropdown.currentText()
        self.topicDropdown.clear()
        self.topicDropdown.addItem("Seleccionar Topic")

        if selected_realm in self.realms_topics:
            for topic in self.realms_topics[selected_realm]["topics"]:
                self.topicDropdown.addItem(topic)

    # ----------------------------------------------------------------
    # 📤 Manejo de los tres modos de publicación
    # ----------------------------------------------------------------
    def handle_publish_mode(self):
        selected_realm = self.realmDropdown.currentText()
        selected_topic = self.topicDropdown.currentText()

        if selected_realm == "Seleccionar Realm" or selected_topic == "Seleccionar Topic":
            QMessageBox.warning(self, "Error", "Debes seleccionar un Realm y un Topic antes de enviar.")
            return

        content_text = self.editorWidget.jsonPreview.toPlainText()
        try:
            content = json.loads(content_text)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"El JSON no es válido:\n{e}")
            return

        mode = self.modeCombo.currentText()
        time_str = self.timeEdit.text().strip()
        delay = 0

        if mode == "Programado":
            try:
                h, m, s = map(int, time_str.split(":"))
                delay = h * 3600 + m * 60 + s
            except ValueError:
                QMessageBox.warning(self, "Error", "Formato de tiempo inválido. Usa HH:MM:SS.")
                return

        elif mode == "Hora de sistema":
            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            while current_time != time_str:
                print(f"⏳ Esperando... (Hora actual: {current_time})")
                asyncio.sleep(1)
                current_time = datetime.datetime.now().strftime("%H:%M:%S")

        router_url = self.realms_topics[selected_realm]["router_url"]

        print(f"📢 Publicando en realm={selected_realm}, topic={selected_topic} con delay={delay}s")
        start_publisher(router_url, selected_realm, selected_topic)
        send_message_now(selected_topic, content, delay)
