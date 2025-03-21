import sys, os, json, datetime, logging, asyncio, threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QPushButton, QSplitter,
    QGroupBox, QFormLayout, QMessageBox, QLineEdit, QFileDialog, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
from common.utils import log_to_file, JsonDetailDialog
from .pubEditor import PublisherEditorWidget

# Variable global para la configuración de realms y topics
REALMS_TOPICS = {}

def load_realm_topic_config():
    global REALMS_TOPICS
    try:
        # Se asume que el archivo de configuración está en <project_root>/config/realm_topic_config_pub.json
        base_path = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_path, "..", "config", "realm_topic_config_pub.json")
        with open(config_path, "r", encoding="utf-8") as f:
            REALMS_TOPICS = json.load(f)
        print("Configuración de realms y topics cargada desde", config_path)
    except Exception as e:
        print("Error al cargar configuración de realms y topics:", e)
        # Configuración por defecto en caso de error
        REALMS_TOPICS = {
            "default": ["com.ads.midshmi.topic", "com.ads.midshmi.another"],
            "ADS.MIDSHMI": ["com.ads.midshmi.topic", "com.ads.midshmi.special"]
        }
        print("Se usará configuración por defecto.")

# Cargar la configuración al iniciar el módulo
load_realm_topic_config()

global_session = None
global_loop = None

class JSONPublisher(ApplicationSession):
    def __init__(self, config, topic):
        super().__init__(config)
        self.topic = topic

    async def onJoin(self, details):
        global global_session, global_loop
        global_session = self
        global_loop = asyncio.get_event_loop()
        print("Conexión establecida en el publicador (realm:", self.config.realm, ")")
        await asyncio.Future()

def start_publisher(url, realm, topic):
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = ApplicationRunner(url=url, realm=realm)
        runner.run(lambda config: JSONPublisher(config, topic))
    threading.Thread(target=run, daemon=True).start()

def send_message_now(topic, message, delay=0):
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
        log_to_file(timestamp, topic, global_session.config.realm, message_json)
        logging.info(f"Publicado: {timestamp} | Topic: {topic} | Realm: {global_session.config.realm}")
        print("Mensaje enviado en", topic, ":", message)
    asyncio.run_coroutine_threadsafe(_send(), global_loop)

class PublisherMessageViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pubMessages = []
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        # Orden de columnas: Hora, Realm, Topic
        self.table.setHorizontalHeaderLabels(["Hora", "Realm", "Topic"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self.showDetails)
        layout.addWidget(self.table)
        self.setLayout(layout)

    def add_message(self, realm, topic, timestamp, details):
        # Se eliminan saltos de línea para la vista del log
        if isinstance(details, str):
            details = details.replace("\n", " ")
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(timestamp))
        self.table.setItem(row, 1, QTableWidgetItem(realm))
        self.table.setItem(row, 2, QTableWidgetItem(topic))
        self.pubMessages.append(details)

    def showDetails(self, item):
        row = item.row()
        if row < len(self.pubMessages):
            dlg = JsonDetailDialog(self.pubMessages[row], self)
            dlg.exec_()

class PublisherTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.msgWidgets = []
        self.next_id = 1
        self.initUI()

    def initUI(self):
        mainLayout = QVBoxLayout(self)

        # Grupo de botones de acción
        actionGroup = QGroupBox("Acciones")
        actionLayout = QHBoxLayout()
        self.addMsgButton = QPushButton("Agregar Mensaje")
        self.addMsgButton.clicked.connect(self.addMessage)
        self.asyncSendButton = QPushButton("Enviar Mensaje Asincrónico")
        self.asyncSendButton.clicked.connect(self.sendAllAsync)
        self.loadProjectButton = QPushButton("Cargar Proyecto")
        self.loadProjectButton.clicked.connect(self.loadProject)
        self.saveProjectButton = QPushButton("Guardar Proyecto")
        self.saveProjectButton.clicked.connect(self.saveProject)
        actionLayout.addWidget(self.addMsgButton)
        actionLayout.addWidget(self.asyncSendButton)
        actionLayout.addWidget(self.loadProjectButton)
        actionLayout.addWidget(self.saveProjectButton)
        actionGroup.setLayout(actionLayout)
        mainLayout.addWidget(actionGroup)

        # Splitter para áreas de mensajes y log
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
        mainLayout.addWidget(splitter)

        # Grupo de conexión
        connGroup = QGroupBox("Conexión de Publicador")
        connLayout = QHBoxLayout()
        connLayout.addWidget(QLabel("Publicador Global"))
        self.globalStartButton = QPushButton("Iniciar Publicador")
        self.globalStartButton.clicked.connect(self.startPublisher)
        connLayout.addWidget(self.globalStartButton)
        connGroup.setLayout(connLayout)
        mainLayout.addWidget(connGroup)

        mainLayout.addWidget(QLabel("Resumen de mensajes enviados:"))
        mainLayout.addWidget(self.viewer)
        self.setLayout(mainLayout)

    def addMessage(self):
        widget = MessageConfigWidget(self.next_id, parent=self)
        self.msgLayout.addWidget(widget)
        self.msgWidgets.append(widget)
        self.next_id += 1

    def addPublisherLog(self, realm, topic, timestamp, details):
        self.viewer.add_message(realm, topic, timestamp, details)

    def startPublisher(self):
        for widget in self.msgWidgets:
            config = widget.getConfig()
            start_publisher(config["router_url"], config["realm"], config["topic"])
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.addPublisherLog(config["realm"], config["topic"], timestamp, "Publicador iniciado")
            print("Publicador iniciado:", config["realm"], config["topic"])

    def sendAllAsync(self):
        for widget in self.msgWidgets:
            if not widget.message_sent:
                config = widget.getConfig()
                send_message_now(config["topic"], config["content"], delay=0)
                widget.message_sent = True
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sent_message = json.dumps(config["content"], indent=2, ensure_ascii=False)
                self.addPublisherLog(config["realm"], config["topic"], timestamp, sent_message)

    def getProjectConfig(self):
        scenarios = [widget.getConfig() for widget in self.msgWidgets]
        return {"scenarios": scenarios}

    def loadProjectFromConfig(self, pub_config):
        scenarios = pub_config.get("scenarios", [])
        self.msgWidgets = []
        self.next_id = 1
        while self.msgLayout.count():
            item = self.msgLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for scenario in scenarios:
            widget = MessageConfigWidget(self.next_id, parent=self)
            widget.realmCombo.setCurrentText(scenario.get("realm", "default"))
            widget.urlEdit.setText(scenario.get("router_url", "ws://127.0.0.1:60001/ws"))
            widget.topicCombo.setCurrentText(scenario.get("topic", "com.ads.midshmi.topic"))
            widget.editorWidget.jsonPreview.setPlainText(json.dumps(scenario.get("content", {}), indent=2, ensure_ascii=False))
            self.msgLayout.addWidget(widget)
            self.msgWidgets.append(widget)
            self.next_id += 1

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
        QMessageBox.information(self, "Proyecto", "Proyecto cargado correctamente.")

    def saveProject(self):
        project_config = {
            "publisher": self.getProjectConfig()
        }
        filepath, _ = QFileDialog.getSaveFileName(self, "Guardar Proyecto", "", "JSON Files (*.json);;All Files (*)")
        if not filepath:
            return
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(project_config, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Proyecto", "Proyecto guardado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el proyecto:\n{e}")

class MessageConfigWidget(QGroupBox):
    def __init__(self, msg_id, parent=None):
        super().__init__(parent)
        self.msg_id = msg_id
        self.message_sent = False  # Flag para evitar envíos duplicados
        self.setTitle(f"Mensaje #{self.msg_id}")
        self.setCheckable(True)
        self.setChecked(True)
        self.toggled.connect(self.toggleContent)
        self.initUI()

    def initUI(self):
        # Layout general con grupos para aspecto profesional
        mainLayout = QVBoxLayout()

        # Grupo de configuración de conexión
        connGroup = QGroupBox("Configuración de Conexión")
        connLayout = QFormLayout()
        self.realmCombo = QComboBox()
        self.realmCombo.addItems(list(REALMS_TOPICS.keys()))
        self.realmCombo.setMinimumWidth(300)
        self.realmCombo.currentTextChanged.connect(self.updateTopics)
        self.newRealmEdit = QLineEdit()
        self.newRealmEdit.setPlaceholderText("Nuevo realm")
        addRealmButton = QPushButton("Agregar")
        addRealmButton.clicked.connect(self.addRealm)
        realmLayout = QHBoxLayout()
        realmLayout.addWidget(self.realmCombo)
        realmLayout.addWidget(self.newRealmEdit)
        realmLayout.addWidget(addRealmButton)
        connLayout.addRow("Realm:", realmLayout)

        self.urlEdit = QLineEdit("ws://127.0.0.1:60001/ws")
        connLayout.addRow("Router URL:", self.urlEdit)

        self.topicCombo = QComboBox()
        self.topicCombo.setEditable(True)
        self.topicCombo.addItems(REALMS_TOPICS.get(self.realmCombo.currentText(), []))
        connLayout.addRow("Topic:", self.topicCombo)
        connGroup.setLayout(connLayout)
        mainLayout.addWidget(connGroup)

        # Grupo de contenido del mensaje
        contentGroup = QGroupBox("Contenido del Mensaje")
        contentGroupLayout = QVBoxLayout()
        from .pubEditor import PublisherEditorWidget
        self.editorWidget = PublisherEditorWidget(parent=self)
        contentGroupLayout.addWidget(self.editorWidget)
        contentGroup.setLayout(contentGroupLayout)
        mainLayout.addWidget(contentGroup)

        # Botón de envío alineado a la derecha
        btnLayout = QHBoxLayout()
        btnLayout.addStretch()
        self.sendButton = QPushButton("Enviar Mensaje")
        self.sendButton.clicked.connect(self.sendMessage)
        btnLayout.addWidget(self.sendButton)
        mainLayout.addLayout(btnLayout)

        self.setLayout(mainLayout)

    def addRealm(self):
        new_realm = self.newRealmEdit.text().strip()
        if new_realm and new_realm not in [self.realmCombo.itemText(i) for i in range(self.realmCombo.count())]:
            self.realmCombo.addItem(new_realm)
            # Se añade un nuevo realm en la configuración global
            REALMS_TOPICS[new_realm] = []
            self.newRealmEdit.clear()

    def updateTopics(self, realm):
        topics = REALMS_TOPICS.get(realm, [])
        self.topicCombo.clear()
        self.topicCombo.addItems(topics)
        self.topicCombo.setEditable(True)

    def toggleContent(self, checked):
        # Al colapsar se muestra un resumen en el título
        if not checked:
            topic = self.topicCombo.currentText().strip()
            self.setTitle(f"Mensaje #{self.msg_id} - {topic}")
        else:
            self.setTitle(f"Mensaje #{self.msg_id}")

    def sendMessage(self):
        if self.message_sent:
            return
        # Obtener el modo de envío y tiempo desde el editor (se encuentran en el mismo widget)
        if self.editorWidget.onDemandRadio.isChecked():
            delay = 0
        elif self.editorWidget.programadoRadio.isChecked():
            try:
                h, m, s = map(int, self.editorWidget.commonTimeEdit.text().strip().split(":"))
                delay = h * 3600 + m * 60 + s
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Tiempo inválido para modo Programado:\n{e}")
                return
        elif self.editorWidget.tiempoSistemaRadio.isChecked():
            try:
                h, m, s = map(int, self.editorWidget.commonTimeEdit.text().strip().split(":"))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Tiempo inválido para modo Tiempo del Sistema:\n{e}")
                return
            now = datetime.datetime.now()
            scheduled_time = now.replace(hour=h, minute=m, second=s, microsecond=0)
            if scheduled_time < now:
                scheduled_time += datetime.timedelta(days=1)
            delay = (scheduled_time - now).total_seconds()
        else:
            delay = 0

        topic = self.topicCombo.currentText().strip()
        try:
            data = json.loads(self.editorWidget.jsonPreview.toPlainText())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"JSON inválido:\n{e}")
            return
        
        from .pubGUI import send_message_now
        send_message_now(topic, data, delay=delay)
        self.message_sent = True
        publish_time = datetime.datetime.now() + datetime.timedelta(seconds=delay)
        publish_time_str = publish_time.strftime("%Y-%m-%d %H:%M:%S")
        sent_message = json.dumps(data, indent=2, ensure_ascii=False)
        if hasattr(self.parent(), "addPublisherLog"):
            self.parent().addPublisherLog(self.realmCombo.currentText(), topic, publish_time_str, sent_message)

    def getConfig(self):
        return {
            "id": self.msg_id,
            "realm": self.realmCombo.currentText(),
            "router_url": self.urlEdit.text().strip(),
            "topic": self.topicCombo.currentText().strip(),
            "content": json.loads(self.editorWidget.jsonPreview.toPlainText())
        }
