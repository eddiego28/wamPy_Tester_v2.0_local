# src/tu_paquete/pubMessageConfigWidget.py
import json, datetime
from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QLineEdit, QPushButton, QComboBox
)
from PyQt5.QtCore import Qt
from gui.pubEditor import PublisherEditorWidget
from gui.wamp.publisher import start_publisher, send_message_now

class MessageConfigWidget(QGroupBox):
    def __init__(self, msg_id, parent=None):
        super().__init__(parent)
        self.msg_id = msg_id
        self.realms_topics = {}  # Configuración global de realms (se actualizará)
        self.selected_topics_by_realm = {}  # Conserva la selección de topics para cada realm
        self.current_realm = None
        self.publisherTab = None  # Se asigna desde PublisherTab al agregar este widget
        self.initUI()

    def initUI(self):
        self.setTitle(f"Mensaje #{self.msg_id}")
        self.setCheckable(True)
        self.setChecked(True)
        self.toggled.connect(self.toggleContent)
        layout = QVBoxLayout(self)

        # Layout horizontal: panel izquierdo (tablas) y derecho (editor JSON y controles)
        hLayout = QHBoxLayout()
        # Panel izquierdo
        leftPanel = QVBoxLayout()
        self.realmTable = QTableWidget(0, 2)
        self.realmTable.setHorizontalHeaderLabels(["Realm", "Router URL"])
        self.realmTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        leftPanel.addWidget(QLabel("Realms (checkbox):"))
        leftPanel.addWidget(self.realmTable)
        self.topicTable = QTableWidget(0, 1)
        self.topicTable.setHorizontalHeaderLabels(["Topic"])
        self.topicTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        leftPanel.addWidget(QLabel("Topics (checkbox):"))
        leftPanel.addWidget(self.topicTable)
        # Conecta clic en realm y cambios en topic
        self.realmTable.cellClicked.connect(self.onRealmClicked)
        self.topicTable.itemChanged.connect(self.onTopicChanged)
        hLayout.addLayout(leftPanel, stretch=1)
        # Panel derecho: editor JSON y controles
        rightPanel = QVBoxLayout()
        self.editorWidget = PublisherEditorWidget(self)
        rightPanel.addWidget(QLabel("Editor JSON:"))
        rightPanel.addWidget(self.editorWidget)
        modeLayout = QHBoxLayout()
        modeLayout.addWidget(QLabel("Modo:"))
        self.modeCombo = QComboBox()
        self.modeCombo.addItems(["Programado", "Hora de sistema", "On demand"])
        modeLayout.addWidget(self.modeCombo)
        modeLayout.addWidget(QLabel("Tiempo (HH:MM:SS):"))
        self.timeEdit = QLineEdit("00:00:00")
        modeLayout.addWidget(self.timeEdit)
        rightPanel.addLayout(modeLayout)
        hLayout.addLayout(rightPanel, stretch=1)
        layout.addLayout(hLayout)

        # Botones para agregar/borrar realms y topics (debajo del panel izquierdo)
        btnLayout = QHBoxLayout()
        self.newRealmEdit = QLineEdit()
        self.newRealmEdit.setPlaceholderText("Nuevo Realm")
        self.btnAddRealm = QPushButton("Agregar Realm")
        self.btnAddRealm.clicked.connect(self.addRealmRow)
        self.btnDelRealm = QPushButton("Borrar Realm")
        self.btnDelRealm.clicked.connect(self.deleteRealmRow)
        btnLayout.addWidget(self.newRealmEdit)
        btnLayout.addWidget(self.btnAddRealm)
        btnLayout.addWidget(self.btnDelRealm)
        self.newTopicEdit = QLineEdit()
        self.newTopicEdit.setPlaceholderText("Nuevo Topic")
        self.btnAddTopic = QPushButton("Agregar Topic")
        self.btnAddTopic.clicked.connect(self.addTopicRow)
        self.btnDelTopic = QPushButton("Borrar Topic")
        self.btnDelTopic.clicked.connect(self.deleteTopicRow)
        btnLayout.addWidget(self.newTopicEdit)
        btnLayout.addWidget(self.btnAddTopic)
        btnLayout.addWidget(self.btnDelTopic)
        layout.addLayout(btnLayout)

        # Botón de enviar mensaje
        self.sendButton = QPushButton("Enviar")
        self.sendButton.clicked.connect(self.sendMessage)
        layout.addWidget(self.sendButton)

        self.setLayout(layout)

    def toggleContent(self, checked):
        self.setFlat(not checked)

    def addRealmRow(self):
        new_realm = self.newRealmEdit.text().strip()
        if new_realm:
            row = self.realmTable.rowCount()
            self.realmTable.insertRow(row)
            item = QTableWidgetItem(new_realm)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.realmTable.setItem(row, 0, item)
            self.realmTable.setItem(row, 1, QTableWidgetItem("ws://127.0.0.1:60001/ws"))
            self.newRealmEdit.clear()

    def deleteRealmRow(self):
        rows_to_delete = []
        for row in range(self.realmTable.rowCount()):
            item = self.realmTable.item(row, 0)
            if item and item.checkState() != Qt.Checked:
                rows_to_delete.append(row)
        for row in reversed(rows_to_delete):
            self.realmTable.removeRow(row)

    def addTopicRow(self):
        new_topic = self.newTopicEdit.text().strip()
        if new_topic:
            row = self.topicTable.rowCount()
            self.topicTable.insertRow(row)
            item = QTableWidgetItem(new_topic)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.topicTable.setItem(row, 0, item)
            self.newTopicEdit.clear()
            if self.current_realm:
                self.selected_topics_by_realm.setdefault(self.current_realm, set()).add(new_topic)

    def deleteTopicRow(self):
        rows_to_delete = []
        for row in range(self.topicTable.rowCount()):
            item = self.topicTable.item(row, 0)
            if item and item.checkState() != Qt.Checked:
                rows_to_delete.append(row)
        for row in reversed(rows_to_delete):
            t_item = self.topicTable.item(row, 0)
            if t_item and self.current_realm:
                self.selected_topics_by_realm[self.current_realm].discard(t_item.text().strip())
            self.topicTable.removeRow(row)

    def onRealmClicked(self, row, col):
        realm_item = self.realmTable.item(row, 0)
        if realm_item:
            realm = realm_item.text().strip()
            self.current_realm = realm
            topics = self.publisherTab.realms_topics.get(realm, {}).get("topics", [])
            self.topicTable.blockSignals(True)
            self.topicTable.setRowCount(0)
            if realm not in self.selected_topics_by_realm:
                self.selected_topics_by_realm[realm] = set()
            for t in topics:
                row_idx = self.topicTable.rowCount()
                self.topicTable.insertRow(row_idx)
                t_item = QTableWidgetItem(t)
                t_item.setFlags(t_item.flags() | Qt.ItemIsUserCheckable)
                t_item.setCheckState(Qt.Checked if t in self.selected_topics_by_realm[realm] else Qt.Unchecked)
                self.topicTable.setItem(row_idx, 0, t_item)
            self.topicTable.blockSignals(False)

    def onTopicChanged(self, item):
        if not self.current_realm:
            return
        realm = self.current_realm
        selected = set()
        for row in range(self.topicTable.rowCount()):
            t_item = self.topicTable.item(row, 0)
            if t_item and t_item.checkState() == Qt.Checked:
                selected.add(t_item.text().strip())
        self.selected_topics_by_realm[realm] = selected

    def updateRealmsTopics(self, realms_topics):
        self.realms_topics = realms_topics
        self.realmTable.blockSignals(True)
        self.realmTable.setRowCount(0)
        for realm, info in sorted(realms_topics.items()):
            row = self.realmTable.rowCount()
            self.realmTable.insertRow(row)
            item = QTableWidgetItem(realm)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.realmTable.setItem(row, 0, item)
            router_url = info.get("router_url", "ws://127.0.0.1:60001/ws")
            self.realmTable.setItem(row, 1, QTableWidgetItem(router_url))
        self.realmTable.blockSignals(False)
        if self.realmTable.rowCount() > 0:
            self.realmTable.selectRow(0)
            self.onRealmClicked(0, 0)

    def getRouterURL(self):
        if self.realmTable.rowCount() > 0:
            return self.realmTable.item(0, 1).text().strip()
        return "ws://127.0.0.1:60001/ws"

    def sendMessage(self):
        realms = []
        for r in range(self.realmTable.rowCount()):
            r_item = self.realmTable.item(r, 0)
            if r_item and r_item.checkState() == Qt.Checked:
                realms.append(r_item.text().strip())
        all_topics = {}
        for realm in realms:
            all_topics[realm] = list(self.selected_topics_by_realm.get(realm, []))
        content_text = self.editorWidget.jsonPreview.toPlainText()
        try:
            content = json.loads(content_text)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"JSON inválido:\n{e}")
            return
        mode = self.modeCombo.currentText()
        time_str = self.timeEdit.text().strip()
        delay = 0
        if mode == "Programado":
            try:
                h, m, s = map(int, time_str.split(":"))
                delay = h * 3600 + m * 60 + s
            except:
                delay = 0
        for realm in realms:
            router_url = None
            for r in range(self.realmTable.rowCount()):
                r_item = self.realmTable.item(r, 0)
                if r_item and r_item.text().strip() == realm:
                    router_url = self.realmTable.item(r, 1).text().strip()
                    break
            if router_url is None:
                router_url = "ws://127.0.0.1:60001/ws"
            topics = all_topics.get(realm, [])
            if topics:
                for topic in topics:
                    start_publisher(router_url, realm, topic)
                    send_message_now(topic, content, delay)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_info = {
            "action": "publish",
            "realms": realms,
            "topics": all_topics,
            "mode": mode,
            "time": time_str,
            "content": content
        }
        details = json.dumps(log_info, indent=2, ensure_ascii=False)
        self.publisherTab.viewer.add_message(", ".join(realms), ", ".join([", ".join(all_topics[r]) for r in realms]), timestamp, details)
        print(f"Mensaje publicado en realms {realms} con topics {all_topics} a las {timestamp}")

    def getConfig(self):
        realms = []
        for r in range(self.realmTable.rowCount()):
            r_item = self.realmTable.item(r, 0)
            if r_item and r_item.checkState() == Qt.Checked:
                realms.append(r_item.text().strip())
        topics = {}
        for realm in realms:
            topics[realm] = list(self.selected_topics_by_realm.get(realm, []))
        content_text = self.editorWidget.jsonPreview.toPlainText()
        try:
            content = json.loads(content_text)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"JSON inválido:\n{e}")
            return {}
        mode = self.modeCombo.currentText()
        time_str = self.timeEdit.text().strip()
        return {
            "realms": realms,
            "topics": topics,
            "content": content,
            "mode": mode,
            "time": time_str,
            "router_url": self.realmTable.item(0,1).text().strip() if self.realmTable.rowCount() > 0 else "ws://127.0.0.1:60001/ws"
        }
