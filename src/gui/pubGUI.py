# publisher/pubGUI.py
import sys, os, json, datetime, logging, asyncio, threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QPushButton, QSplitter,
    QGroupBox, QFormLayout, QMessageBox, QLineEdit, QFileDialog, QComboBox, QRadioButton
)
from PyQt5.QtCore import Qt, QTimer
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
from common.utils import log_to_file, JsonDetailDialog
from .pubEditor import PublisherEditorWidget

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
        self.table.setHorizontalHeaderLabels(["Hora", "Topic", "Realm"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self.showDetails)
        layout.addWidget(self.table)
        self.setLayout(layout)
        # Se eliminó la restricción de altura para ver todo el log

    def add_message(self, realm, topic, timestamp, details):
        # Se quitan los saltos de línea para la vista del log (el detalle se mostrará en árbol)
        if isinstance(details, str):
            details = details.replace("\n", " ")
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(timestamp))
        self.table.setItem(row, 1, QTableWidgetItem(topic))
        self.table.setItem(row, 2, QTableWidgetItem(realm))
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
        layout = QVBoxLayout()
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
        from .pubEditor import PublisherEditorWidget
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
            # No se registra aquí "Publicador iniciado" para evitar duplicados.
            if widget.editorWidget.commonTimeEdit.text().strip() != "00:00:00":
                try:
                    h, m, s = map(int, widget.editorWidget.commonTimeEdit.text().strip().split(":"))
                    delay = h * 3600 + m * 60 + s
                except:
                    delay = 0
                QTimer.singleShot(delay * 1000, widget.sendMessage)

    def sendAllAsync(self):
        for widget in self.msgWidgets:
            # Evitar el envío duplicado si ya se envió de forma individual
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
            from .pubEditor import PublisherEditorWidget
            widget = MessageConfigWidget(self.next_id, parent=self)
            widget.realmCombo.setCurrentText(scenario.get("realm", "default"))
            widget.urlEdit.setText(scenario.get("router_url", "ws://127.0.0.1:60001/ws"))
            widget.topicEdit.setText(scenario.get("topic", "com.ads.midshmi.topic"))
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
        from subscriber.subGUI import SubscriberTab
        sub_config = project.get("subscriber", {})
        if hasattr(self.parent(), "subscriberTab"):
            self.parent().subscriberTab.loadProjectFromConfig(sub_config)
        QMessageBox.information(self, "Proyecto", "Proyecto cargado correctamente.")

class MessageConfigWidget(QGroupBox):
    def __init__(self, msg_id, parent=None):
        super().__init__(parent)
        self.msg_id = msg_id
        self.message_sent = False  # Flag para evitar duplicados
        self.setTitle(f"Mensaje #{self.msg_id}")
        self.setCheckable(True)
        self.setChecked(True)
        self.toggled.connect(self.toggleContent)
        self.initUI()

    def initUI(self):
        self.contentWidget = QWidget()
        contentLayout = QVBoxLayout()
        formLayout = QFormLayout()
        
        # Aumentar tamaño del box de realm
        self.realmCombo = QComboBox()
        self.realmCombo.addItems(["default", "ADS.MIDSHMI"])
        self.realmCombo.setMinimumWidth(300)
        self.newRealmEdit = QLineEdit()
        self.newRealmEdit.setPlaceholderText("Nuevo realm")
        addRealmButton = QPushButton("Agregar realm")
        addRealmButton.clicked.connect(self.addRealm)
        realmLayout = QHBoxLayout()
        realmLayout.addWidget(self.realmCombo)
        realmLayout.addWidget(self.newRealmEdit)
        realmLayout.addWidget(addRealmButton)
        formLayout.addRow("Realm:", realmLayout)
        
        self.urlEdit = QLineEdit("ws://127.0.0.1:60001/ws")
        formLayout.addRow("Router URL:", self.urlEdit)
        self.topicEdit = QLineEdit("com.ads.midshmi.topic")
        formLayout.addRow("Topic:", self.topicEdit)
        contentLayout.addLayout(formLayout)
        
        from .pubEditor import PublisherEditorWidget
        self.editorWidget = PublisherEditorWidget(parent=self)
        contentLayout.addWidget(self.editorWidget)
        
        # Selección de modo de envío, colocada justo encima del campo de tiempo
        timeModeLayout = QHBoxLayout()
        timeModeLayout.addWidget(QLabel("Modo de envío:"))
        self.onDemandRadio = QRadioButton("On-Demand")
        self.programadoRadio = QRadioButton("Programado")
        self.tiempoSistemaRadio = QRadioButton("Tiempo del Sistema")
        self.onDemandRadio.setChecked(True)
        timeModeLayout.addWidget(self.onDemandRadio)
        timeModeLayout.addWidget(self.programadoRadio)
        timeModeLayout.addWidget(self.tiempoSistemaRadio)
        contentLayout.addLayout(timeModeLayout)
        
        self.sendButton = QPushButton("Enviar")
        self.sendButton.clicked.connect(self.sendMessage)
        # Habilitar/deshabilitar botón según el campo de tiempo
        if self.editorWidget.commonTimeEdit.text().strip() == "00:00:00":
            self.sendButton.setEnabled(True)
        else:
            self.sendButton.setEnabled(False)
        contentLayout.addWidget(self.sendButton)
        
        self.contentWidget.setLayout(contentLayout)
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.contentWidget)
        self.setLayout(mainLayout)

    def addRealm(self):
        new_realm = self.newRealmEdit.text().strip()
        if new_realm and new_realm not in [self.realmCombo.itemText(i) for i in range(self.realmCombo.count())]:
            self.realmCombo.addItem(new_realm)
            self.newRealmEdit.clear()

    def toggleContent(self, checked):
        self.contentWidget.setVisible(checked)
        if not checked:
            topic = self.topicEdit.text().strip()
            time_val = self.editorWidget.commonTimeEdit.text()
            self.setTitle(f"Mensaje #{self.msg_id} - {topic} - {time_val}")
        else:
            self.setTitle(f"Mensaje #{self.msg_id}")

    def sendMessage(self):
        if self.message_sent:
            return  # Evita el envío duplicado
        if self.onDemandRadio.isChecked():
            delay = 0
        elif self.programadoRadio.isChecked():
            try:
                h, m, s = map(int, self.editorWidget.commonTimeEdit.text().strip().split(":"))
                delay = h * 3600 + m * 60 + s
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Tiempo inválido para modo Programado:\n{e}")
                return
        elif self.tiempoSistemaRadio.isChecked():
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

        topic = self.topicEdit.text().strip()
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

    def getConfig(self): #jlaksjdflñkdsj
        return {
            "id": self.msg_id,
            "realm": self.realmCombo.currentText(),
            "router_url": self.urlEdit.text().strip(),
            "topic": self.topicEdit.text().strip(),
            "content": json.loads(self.editorWidget.jsonPreview.toPlainText())
        }