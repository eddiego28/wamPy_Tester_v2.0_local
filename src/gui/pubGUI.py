#!/usr/bin/env python3
import sys, os, json, datetime, asyncio, threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QTextEdit, QPushButton, QApplication, QHeaderView, QScrollArea, QSplitter, QDialog
)
from PyQt5.QtCore import Qt
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
from common.utils import log_to_file, JsonDetailDialog  # JsonDetailDialog se usará para ver el detalle del JSON
from pubEditor import PublisherEditorWidget  # Editor JSON

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
# JsonTreeDialog: muestra el JSON en formato de árbol (una columna)
# ---------------------------
class JsonTreeDialog(QDialog):
    def __init__(self, json_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detalle JSON - Árbol")
        self.resize(600, 400)
        layout = QVBoxLayout(self)
        from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels(["JSON"])
        self.tree.header().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tree)
        self.setLayout(layout)
        self.buildTree(json_data, self.tree.invisibleRootItem())
        self.tree.expandAll()

    def buildTree(self, data, parent):
        from PyQt5.QtWidgets import QTreeWidgetItem
        if isinstance(data, dict):
            for key, value in data.items():
                text = f"{key}: {value}" if not isinstance(value, (dict, list)) else f"{key}:"
                item = QTreeWidgetItem([text])
                parent.addChild(item)
                self.buildTree(value, item)
        elif isinstance(data, list):
            for index, value in enumerate(data):
                text = f"[{index}]: {value}" if not isinstance(value, (dict, list)) else f"[{index}]:"
                item = QTreeWidgetItem([text])
                parent.addChild(item)
                self.buildTree(value, item)
        else:
            item = QTreeWidgetItem([str(data)])
            parent.addChild(item)

# ---------------------------
# PublisherMessageViewer: visor de mensajes enviados
# ---------------------------
class PublisherMessageViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pubMessages = []
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Hora", "Realm", "Topic"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self.showDetails)
        layout.addWidget(self.table)
        self.setLayout(layout)
    
    def add_message(self, realm, topic, timestamp, details):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(timestamp))
        self.table.setItem(row, 1, QTableWidgetItem(realm))
        self.table.setItem(row, 2, QTableWidgetItem(topic))
        self.pubMessages.append(details)
    
    def showDetails(self, item):
        row = item.row()
        if row < len(self.pubMessages):
            dlg = JsonTreeDialog(json.loads(self.pubMessages[row]), self)
            dlg.exec_()

# ---------------------------
# PublisherTab: interfaz principal del publicador
# ---------------------------
class PublisherTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.msgWidgets = []  # Lista de mensajes configurados
        self.next_id = 1
        self.realms_topics = load_config()  # Configuración global (ya en el formato adecuado)
        # Se asume que self.realms_topics es un diccionario: { realm: { "router_url": ..., "topics": [...] }, ... }
        self.realm_configs = { realm: info.get("router_url", "ws://127.0.0.1:60001/ws")
                               for realm, info in self.realms_topics.items() }
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()
        # Barra de herramientas para agregar mensajes
        topLayout = QHBoxLayout()
        self.addMsgButton = QPushButton("Agregar mensaje")
        self.addMsgButton.clicked.connect(self.addMessage)
        topLayout.addWidget(self.addMsgButton)
        self.asyncSendButton = QPushButton("Enviar Mensaje Asincrónico")
        self.asyncSendButton.clicked.connect(self.sendAllAsync)
        topLayout.addWidget(self.asyncSendButton)
        self.loadProjectButton = QPushButton("Cargar Proyecto")
        self.loadProjectButton.clicked.connect(self.loadProject)
        topLayout.addWidget(self.loadProjectButton)
        layout.addLayout(topLayout)
        
        # Área de mensajes configurados y visor de logs
        splitter = QSplitter(Qt.Vertical)
        self.msgArea = QScrollArea()
        self.msgArea.setWidgetResizable(True)
        self.msgContainer = QWidget()
        self.msgLayout = QVBoxLayout()
        self.msgContainer.setLayout(self.msgLayout)
        self.msgArea.setWidget(self.msgContainer)
        splitter.addWidget(self.msgArea)
        self.viewer = PublisherMessageViewer(self)
        splitter.addWidget(self.viewer)
        splitter.setSizes([500, 300])
        layout.addWidget(splitter)
        
        # Botón global para iniciar el publicador (cierra sesión previa)
        connLayout = QHBoxLayout()
        connLayout.addWidget(QLabel("Publicador Global"))
        self.globalStartButton = QPushButton("Iniciar Publicador")
        self.globalStartButton.clicked.connect(self.startPublisher)
        connLayout.addWidget(self.globalStartButton)
        layout.addLayout(connLayout)
        
        layout.addWidget(QLabel("Resumen de mensajes enviados:"))
        layout.addWidget(self.viewer)
        self.setLayout(layout)
    
    def addMessage(self):
        from pubEditor import PublisherEditorWidget  # Asegúrate de que la ruta sea correcta
        widget = MessageConfigWidget(self.next_id, parent=self)
        widget.publisherTab = self  # Para que el widget acceda a la configuración global
        widget.updateRealmsTopics(self.realms_topics)
        self.msgLayout.addWidget(widget)
        self.msgWidgets.append(widget)
        self.next_id += 1
    
    def startPublisher(self):
        # Cierra la sesión previa si existe
        global global_session
        if global_session is not None:
            try:
                global_session.leave()
                print("Sesión previa cerrada.")
            except Exception as e:
                print("Error al cerrar sesión previa:", e)
            global_session = None
        
        if not self.msgWidgets:
            QMessageBox.warning(self, "Advertencia", "No hay mensajes configurados para publicar.")
            return
        
        # Publicar TODOS los mensajes configurados
        for widget in self.msgWidgets:
            config = widget.getConfig()  # Se espera que devuelva un diccionario con: id, realm, router_url, topic, content, mode, time
            if not config.get("realm") or not config.get("topic"):
                print(f"Mensaje {config.get('id')} sin realm o topic configurado.")
                continue
            print(f"Iniciando publicador para mensaje {config.get('id')}: realm '{config.get('realm')}', topic '{config.get('topic')}', URL: {config.get('router_url')}")
            start_publisher(config["router_url"], config["realm"], config["topic"])
            delay = compute_delay(config.get("mode", "On demand"), config.get("time", "00:00:00"))
            send_message_now(config["realm"], config["topic"], config["content"], delay=delay)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_info = {
                "action": "publish",
                "id": config.get("id"),
                "realm": config.get("realm"),
                "topic": config.get("topic"),
                "content": config.get("content")
            }
            details = json.dumps(log_info, indent=2, ensure_ascii=False)
            self.viewer.add_message(config.get("realm"), config.get("topic"), timestamp, details)
            print(f"Mensaje {config.get('id')} publicado.")
    
    def sendAllAsync(self):
        for widget in self.msgWidgets:
            if not widget.message_sent:
                config = widget.getConfig()
                send_message_now(config["realm"], config["topic"], config["content"], delay=0)
                widget.message_sent = True
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sent_message = json.dumps(config["content"], indent=2, ensure_ascii=False)
                self.viewer.add_message(config.get("realm"), config.get("topic"), timestamp, sent_message)
                print(f"Mensaje {config.get('id')} publicado de forma asíncrona.")
    
    def getProjectConfig(self):
        scenarios = [widget.getConfig() for widget in self.msgWidgets]
        return {"scenarios": scenarios}
    
    def loadProject(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Seleccione Archivo de Proyecto", "", "JSON Files (*.json);;All Files (*)")
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                project = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el proyecto:\n{e}")
            return
        pub_config = project.get("publisher", {})
        self.loadProjectFromConfig(pub_config)
        from subscriber.subGUI import SubscriberTab
        sub_config = project.get("subscriber", {})
        if hasattr(self.parent(), "subscriberTab"):
            self.parent().subscriberTab.loadProjectFromConfig(sub_config)
        QMessageBox.information(self, "Proyecto", "Proyecto cargado correctamente.")
    
    def loadProjectFromConfig(self, pub_config):
        scenarios = pub_config.get("scenarios", [])
        self.msgWidgets = []
        self.next_id = 1
        while self.msgLayout.count():
            item = self.msgLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for scenario in scenarios:
            from pubEditor import PublisherEditorWidget
            widget = MessageConfigWidget(self.next_id, parent=self)
            widget.realmCombo.setCurrentText(scenario.get("realm", "default"))
            widget.urlEdit.setText(scenario.get("router_url", "ws://127.0.0.1:60001/ws"))
            widget.topicEdit.setText(scenario.get("topic", "com.ads.midshmi.topic"))
            widget.editorWidget.jsonPreview.setPlainText(json.dumps(scenario.get("content", {}), indent=2, ensure_ascii=False))
            self.msgLayout.addWidget(widget)
            self.msgWidgets.append(widget)
            self.next_id += 1
    
    def getProjectConfig(self):
        scenarios = [widget.getConfig() for widget in self.msgWidgets]
        return {"scenarios": scenarios}

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
    elif mode == "On demand":
        return 0
    else:
        return 0


