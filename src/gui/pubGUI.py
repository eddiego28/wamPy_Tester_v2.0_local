#!/usr/bin/env python3
import sys, os, json, datetime, asyncio, threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QTextEdit, QPushButton, QApplication, QHeaderView, QSplitter, QScrollArea
)
from PyQt5.QtCore import Qt
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
from common.utils import log_to_file  # Se espera que log_to_file(timestamp, realm, topic, message_json) esté definido
from pubEditor import PublisherEditorWidget  # Editor JSON (se espera que lo tengas definido)

# Variables globales para la sesión del publicador
global_session = None
global_loop = None

# Función para cargar la configuración (se asume que está en config/realm_topic_config.json)
def load_config():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "realm_topic_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        QMessageBox.warning(None, "Advertencia", "No se encontró realm_topic_config.json.")
        return {}

# ---------------------------
# Lógica WAMP del publicador
# ---------------------------
class JSONPublisher(ApplicationSession):
    def __init__(self, config, topic):
        super().__init__(config)
        self.topic = topic

    async def onJoin(self, details):
        global global_session, global_loop
        global_session = self
        global_loop = asyncio.get_event_loop()
        print("Conexión establecida en el publicador (realm:", self.config.realm, ")")
        await asyncio.Future()  # Mantiene la sesión activa

def start_publisher(url, realm, topic):
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = ApplicationRunner(url=url, realm=realm)
        runner.run(lambda config: JSONPublisher(config, topic))
    threading.Thread(target=run, daemon=True).start()

def send_message_now(realm, topic, message, delay=0):
    global global_session, global_loop
    if global_session is None or global_loop is None:
        print("No hay sesión activa. Inicia el publicador primero.")
        return
    async def _send():
        if delay > 0:
            await asyncio.sleep(delay)
        if isinstance(message, dict):
            global_session.publish(topic, **message)
        else:
            global_session.publish(topic, message)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message_json = json.dumps(message, indent=2, ensure_ascii=False)
        log_to_file(timestamp, realm, topic, message_json)
        print(f"Mensaje enviado en realm '{realm}', topic '{topic}':", message)
    asyncio.run_coroutine_threadsafe(_send(), global_loop)

def compute_delay(mode, time_str):
    now = datetime.datetime.now()
    if mode == "Programado":
        try:
            h, m, s = map(int, time_str.split(":"))
            return h * 3600 + m * 60 + s
        except Exception as e:
            print("Error interpretando duración:", e)
            return 0
    elif mode == "Hora de sistema":
        try:
            h, m, s = map(int, time_str.split(":"))
            target = now.replace(hour=h, minute=m, second=s, microsecond=0)
            if target < now:
                target += datetime.timedelta(days=1)
            return (target - now).total_seconds()
        except Exception as e:
            print("Error interpretando hora de sistema:", e)
            return 0
    elif mode == "Enviar instantáneo":
        return 0
    else:
        return 0

# ---------------------------
# Interfaz del Publicador
# ---------------------------
class PublisherGUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.configData = load_config()  # Configuración global de realms y topics
        self.initUI()
    
    def initUI(self):
        mainLayout = QVBoxLayout(self)
        
        # Selección de Realm
        realmLayout = QHBoxLayout()
        realmLayout.addWidget(QLabel("Seleccione Realm:"))
        self.realmCombo = QComboBox()
        self.realmCombo.addItems(list(self.configData.keys()))
        self.realmCombo.currentIndexChanged.connect(self.updateTopics)
        realmLayout.addWidget(self.realmCombo)
        mainLayout.addLayout(realmLayout)
        
        # Tabla de Topics (checkboxes)
        mainLayout.addWidget(QLabel("Seleccione Topics:"))
        self.topicsTable = QTableWidget(0, 1)
        self.topicsTable.setHorizontalHeaderLabels(["Topic"])
        self.topicsTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        mainLayout.addWidget(self.topicsTable)
        
        # Editor JSON para contenido del mensaje
        mainLayout.addWidget(QLabel("Contenido del Mensaje (JSON):"))
        self.editor = PublisherEditorWidget(self)
        mainLayout.addWidget(self.editor)
        
        # Modo y tiempo
        modeLayout = QHBoxLayout()
        modeLayout.addWidget(QLabel("Modo:"))
        self.modeCombo = QComboBox()
        self.modeCombo.addItems(["Programado", "Hora de sistema", "Enviar instantáneo"])
        modeLayout.addWidget(self.modeCombo)
        modeLayout.addWidget(QLabel("Tiempo (HH:MM:SS):"))
        self.timeEdit = QLineEdit("00:00:00")
        modeLayout.addWidget(self.timeEdit)
        mainLayout.addLayout(modeLayout)
        
        # Botón de Publicar
        btnLayout = QHBoxLayout()
        self.publishButton = QPushButton("Publicar")
        self.publishButton.clicked.connect(self.publishMessage)
        btnLayout.addWidget(self.publishButton)
        mainLayout.addLayout(btnLayout)
        
        # Log de mensajes enviados (en una QTableWidget)
        mainLayout.addWidget(QLabel("Log de mensajes enviados:"))
        self.logTable = QTableWidget(0, 3)
        self.logTable.setHorizontalHeaderLabels(["Hora", "Realm", "Topic"])
        self.logTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.logTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.logTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.logTable.itemDoubleClicked.connect(self.showLogDetail)
        mainLayout.addWidget(self.logTable)
        
        self.setLayout(mainLayout)
        self.updateTopics()
    
    def updateTopics(self):
        self.topicsTable.setRowCount(0)
        realm = self.realmCombo.currentText()
        topics = self.configData.get(realm, {}).get("topics", [])
        for i, topic in enumerate(topics):
            self.topicsTable.insertRow(i)
            item = QTableWidgetItem(topic)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.topicsTable.setItem(i, 0, item)
    
    def getSelectedTopics(self):
        selected = []
        for row in range(self.topicsTable.rowCount()):
            item = self.topicsTable.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected
    
    def publishMessage(self):
        realm = self.realmCombo.currentText()
        selectedTopics = self.getSelectedTopics()
        if not selectedTopics:
            QMessageBox.warning(self, "Advertencia", "Seleccione al menos un topic.")
            return
        try:
            content = json.loads(self.editor.jsonPreview.toPlainText())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"JSON inválido:\n{e}")
            return
        mode = self.modeCombo.currentText()
        time_str = self.timeEdit.text().strip()
        delay = compute_delay(mode, time_str)
        router_url = self.configData.get(realm, {}).get("router_url", "ws://127.0.0.1:60001/ws")
        
        # Antes de iniciar, cerramos cualquier sesión activa
        global global_session
        if global_session is not None:
            try:
                global_session.leave()
                print("Sesión previa cerrada.")
            except Exception as e:
                print("Error al cerrar sesión previa:", e)
            global_session = None
        
        # Para cada topic seleccionado, iniciar sesión y enviar mensaje
        for topic in selectedTopics:
            print(f"Iniciando publicador: realm '{realm}', topic '{topic}', URL: {router_url}")
            start_publisher(router_url, realm, topic)
            send_message_now(realm, topic, content, delay=delay)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.addLogRow(timestamp, realm, ", ".join(selectedTopics))
        QMessageBox.information(self, "Información", f"Mensaje publicado en realm '{realm}', topics: {', '.join(selectedTopics)}")
    
    def addLogRow(self, timestamp, realm, topics):
        row = self.logTable.rowCount()
        self.logTable.insertRow(row)
        self.logTable.setItem(row, 0, QTableWidgetItem(timestamp))
        self.logTable.setItem(row, 1, QTableWidgetItem(realm))
        self.logTable.setItem(row, 2, QTableWidgetItem(topics))
    
    def showLogDetail(self, item):
        row = item.row()
        timestamp = self.logTable.item(row, 0).text()
        realm = self.logTable.item(row, 1).text()
        topics = self.logTable.item(row, 2).text()
        details = f"Timestamp: {timestamp}\nRealm: {realm}\nTopics: {topics}"
        dlg = QDialog(self)
        dlg.setWindowTitle("Detalle de Log")
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(details))
        dlg.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PublisherGUI()
    window.setWindowTitle("Publicador")
    window.resize(600, 500)
    window.show()
    sys.exit(app.exec_())
