# src/tu_paquete/subGUI.py
import os
import json
import datetime
import sys
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit, QDialog,
    QTreeWidget, QComboBox, QSplitter, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal
from gui.subMessageViewer import SubscriberMessageViewer
from gui.subUtils import JsonTreeDialog
from wamp.subscriber import start_subscriber
from gui.utils import log_to_file  # Reutilizamos log_to_file desde utils.py   

class SubscriberTab(QWidget):
    messageReceived = pyqtSignal(str, str, str, str)  # (realm, topic, timestamp, details)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.realms_topics = {}  # Se carga desde el JSON de configuración
        self.selected_topics_by_realm = {}
        self.current_realm = None
        self.messageReceived.connect(self.onMessageReceived)
        self.initUI()
        self.loadGlobalRealmTopicConfig()

    def initUI(self):
        mainLayout = QHBoxLayout(self)
        # Panel izquierdo: Realms y Topics
        leftLayout = QVBoxLayout()
        lblRealms = QLabel("Realms (checkbox) + Router URL:")
        leftLayout.addWidget(lblRealms)
        self.realmTable = QTableWidget(0, 2)
        self.realmTable.setHorizontalHeaderLabels(["Realm", "Router URL"])
        self.realmTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.realmTable.cellClicked.connect(self.onRealmClicked)
        self.realmTable.itemChanged.connect(self.onRealmItemChanged)
        leftLayout.addWidget(self.realmTable)
        btnRealmLayout = QHBoxLayout()
        self.newRealmEdit = QLineEdit()
        self.newRealmEdit.setPlaceholderText("Nuevo Realm")
        self.btnAddRealm = QPushButton("Agregar Realm")
        self.btnAddRealm.clicked.connect(self.addRealmRow)
        self.btnDelRealm = QPushButton("Borrar Realm")
        self.btnDelRealm.clicked.connect(self.deleteRealmRow)
        btnRealmLayout.addWidget(self.newRealmEdit)
        btnRealmLayout.addWidget(self.btnAddRealm)
        btnRealmLayout.addWidget(self.btnDelRealm)
        leftLayout.addLayout(btnRealmLayout)
        lblTopics = QLabel("Topics (checkbox):")
        leftLayout.addWidget(lblTopics)
        self.topicTable = QTableWidget(0, 1)
        self.topicTable.setHorizontalHeaderLabels(["Topic"])
        self.topicTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.topicTable.itemChanged.connect(self.onTopicChanged)
        leftLayout.addWidget(self.topicTable)
        btnTopicLayout = QHBoxLayout()
        self.newTopicEdit = QLineEdit()
        self.newTopicEdit.setPlaceholderText("Nuevo Topic")
        self.btnAddTopic = QPushButton("Agregar Topic")
        self.btnAddTopic.clicked.connect(self.addTopicRow)
        self.btnDelTopic = QPushButton("Borrar Topic")
        self.btnDelTopic.clicked.connect(self.deleteTopicRow)
        btnTopicLayout.addWidget(self.newTopicEdit)
        btnTopicLayout.addWidget(self.btnAddTopic)
        btnTopicLayout.addWidget(self.btnDelTopic)
        leftLayout.addLayout(btnTopicLayout)
        ctrlLayout = QHBoxLayout()
        self.btnSubscribe = QPushButton("Suscribirse")
        self.btnSubscribe.clicked.connect(self.startSubscription)
        ctrlLayout.addWidget(self.btnSubscribe)
        self.btnReset = QPushButton("Reset Log")
        self.btnReset.clicked.connect(self.resetLog)
        ctrlLayout.addWidget(self.btnReset)
        leftLayout.addLayout(ctrlLayout)
        mainLayout.addLayout(leftLayout, stretch=1)
        # Panel derecho: Viewer de mensajes
        self.viewer = SubscriberMessageViewer(self)
        mainLayout.addWidget(self.viewer, stretch=2)
        self.setLayout(mainLayout)

    def loadGlobalRealmTopicConfig(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "realm_topic_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    realms_dict = {}
                    for item in data:
                        realm = item.get("realm")
                        if realm:
                            realms_dict[realm] = {
                                "router_url": item.get("router_url", "ws://127.0.0.1:60001/ws"),
                                "topics": item.get("topics", [])
                            }
                    data = {"realms": realms_dict}
                self.realms_topics = data.get("realms", {})
                print("Configuración global de realms/topics cargada (suscriptor).")
                self.populateRealmTable()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo cargar realm_topic_config.json:\n{e}")
        else:
            QMessageBox.warning(self, "Advertencia", "No se encontró realm_topic_config.json.")

    def populateRealmTable(self):
        self.realmTable.blockSignals(True)
        self.realmTable.setRowCount(0)
        for realm, info in sorted(self.realms_topics.items()):
            row = self.realmTable.rowCount()
            self.realmTable.insertRow(row)
            itemRealm = QTableWidgetItem(realm)
            itemRealm.setFlags(itemRealm.flags() | Qt.ItemIsUserCheckable)
            itemRealm.setCheckState(Qt.Unchecked)  # Inicia desmarcado
            self.realmTable.setItem(row, 0, itemRealm)
            router_url = info.get("router_url", "ws://127.0.0.1:60001/ws")
            self.realmTable.setItem(row, 1, QTableWidgetItem(router_url))
        self.realmTable.blockSignals(False)
        if self.realmTable.rowCount() > 0:
            self.realmTable.selectRow(0)
            self.onRealmClicked(0, 0)

    def onRealmClicked(self, row, col):
        realm_item = self.realmTable.item(row, 0)
        if realm_item:
            realm = realm_item.text().strip()
            self.current_realm = realm
            topics = self.realms_topics.get(realm, {}).get("topics", [])
            self.topicTable.blockSignals(True)
            self.topicTable.setRowCount(0)
            if realm not in self.selected_topics_by_realm:
                # Por defecto, se inician desmarcados para que el usuario elija
                self.selected_topics_by_realm[realm] = set()
            for t in topics:
                row_idx = self.topicTable.rowCount()
                self.topicTable.insertRow(row_idx)
                t_item = QTableWidgetItem(t)
                t_item.setFlags(t_item.flags() | Qt.ItemIsUserCheckable)
                if t in self.selected_topics_by_realm[realm]:
                    t_item.setCheckState(Qt.Checked)
                else:
                    t_item.setCheckState(Qt.Unchecked)
                self.topicTable.setItem(row_idx, 0, t_item)
            self.topicTable.blockSignals(False)

    def onRealmItemChanged(self, item):
        pass

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

    def addRealmRow(self):
        new_realm = self.newRealmEdit.text().strip()
        if new_realm:
            row = self.realmTable.rowCount()
            self.realmTable.insertRow(row)
            item = QTableWidgetItem(new_realm)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
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
            t_item = QTableWidgetItem(new_topic)
            t_item.setFlags(t_item.flags() | Qt.ItemIsUserCheckable)
            t_item.setCheckState(Qt.Unchecked)
            self.topicTable.setItem(row, 0, t_item)
            self.newTopicEdit.clear()

    def deleteTopicRow(self):
        rows_to_delete = []
        for row in range(self.topicTable.rowCount()):
            t_item = self.topicTable.item(row, 0)
            if t_item and t_item.checkState() != Qt.Checked:
                rows_to_delete.append(row)
        for row in reversed(rows_to_delete):
            self.topicTable.removeRow(row)

    def startSubscription(self):
        """
        Se suscribe SOLO a los topics marcados en cada realm al pulsar "Suscribirse".
        Si existe una sesión previa, se cierra antes de iniciar una nueva.
        """
        global global_session_sub

        # Si hay una sesión previa, cerrarla
        if global_session_sub is not None:
            try:
                global_session_sub.leave()
                print("🔄 Sesión previa cerrada correctamente.")
            except Exception as e:
                print(f"⚠️ Error al cerrar sesión previa: {e}")
            global_session_sub = None

        selected_realms = []
        selected_topics_by_realm = {}

        # Recorrer la tabla de realms para obtener los seleccionados
        for row in range(self.realmTable.rowCount()):
            realm_item = self.realmTable.item(row, 0)
            url_item = self.realmTable.item(row, 1)
            if realm_item and realm_item.checkState() == Qt.Checked:
                realm = realm_item.text().strip()
                router_url = url_item.text().strip() if url_item else "ws://127.0.0.1:60001/ws"
                topics = self.realms_topics.get(realm, {}).get("topics", [])
                # Filtrar SOLO los topics seleccionados que pertenezcan a este realm
                selected_topics = [
                    self.topicTable.item(i, 0).text().strip()
                    for i in range(self.topicTable.rowCount())
                    if self.topicTable.item(i, 0).checkState() == Qt.Checked and
                    self.topicTable.item(i, 0).text().strip() in topics
                ]
                if selected_topics:
                    selected_realms.append((realm, router_url))
                    selected_topics_by_realm[realm] = selected_topics

        if not selected_realms:
            QMessageBox.warning(self, "Advertencia", "No hay realms seleccionados para la suscripción.")
            return

        print(f"✅ Realms seleccionados y sus topics: {selected_topics_by_realm}")

        for realm, router_url in selected_realms:
            topics = selected_topics_by_realm.get(realm, [])
            if topics:
                start_subscriber(router_url, realm, topics, self.handleMessage)
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                subscription_info = {
                    "action": "subscribe",
                    "realm": realm,
                    "router_url": router_url,
                    "topics": topics
                }
                details = json.dumps(subscription_info, indent=2, ensure_ascii=False)
                self.viewer.add_message(realm, ", ".join(topics), timestamp, details)
                print(f"✅ Suscrito correctamente a realm '{realm}' con topics {topics}")
            else:
                print(f"⚠️ No hay topics seleccionados para realm {realm}, no se suscribe.")

    def handleMessage(self, realm, topic, content):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details = json.dumps(content, indent=2, ensure_ascii=False)
        self.messageReceived.emit(realm, topic, timestamp, details)
        log_to_file(timestamp, realm, topic, details)
        print(f"Mensaje recibido en realm '{realm}', topic '{topic}' a las {timestamp}")
        sys.stdout.flush()

    @pyqtSlot(str, str, str, str)
    def onMessageReceived(self, realm, topic, timestamp, details):
        self.viewer.add_message(realm, topic, timestamp, details)

    def resetLog(self):
        self.viewer.table.setRowCount(0)
        self.viewer.messages = []

    def loadProjectFromConfig(self, sub_config):
        # Método a implementar según necesidades
        pass
