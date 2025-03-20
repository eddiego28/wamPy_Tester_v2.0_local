# src/tu_paquete/pubGUI.py
import os, json, datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSplitter, QMessageBox
)
from PyQt5.QtCore import Qt
from gui.pubMessageConfigWidget import MessageConfigWidget
from gui.pubMessageViewer import PublisherMessageViewer
from services.config_loader import load_realm_topic_config

class PublisherTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.msgWidgets = []
        self.next_id = 1
        self.realms_topics = {}   # Se carga desde el JSON de configuración
        self.realm_configs = {}   # Se carga desde el mismo JSON
        self.initUI()
        self.loadGlobalRealmTopicConfig()

    def initUI(self):
        layout = QVBoxLayout()
        # Barra de herramientas
        toolbar = QHBoxLayout()
        btnAgregar = QPushButton("Agregar mensaje")
        btnAgregar.clicked.connect(self.addMessage)
        toolbar.addWidget(btnAgregar)
        btnEliminar = QPushButton("Eliminar mensaje")
        btnEliminar.clicked.connect(self.deleteSelectedMessage)
        toolbar.addWidget(btnEliminar)
        btnCargarProj = QPushButton("Cargar Proyecto")
        btnCargarProj.clicked.connect(self.loadProject)
        toolbar.addWidget(btnCargarProj)
        btnRecargarRT = QPushButton("Recargar Realm/Topic")
        btnRecargarRT.clicked.connect(self.loadGlobalRealmTopicConfig)
        toolbar.addWidget(btnRecargarRT)
        btnEnviarTodos = QPushButton("Enviar Mensaje a Todos")
        btnEnviarTodos.clicked.connect(self.sendAllAsync)
        toolbar.addWidget(btnEnviarTodos)
        layout.addLayout(toolbar)
        # Área de mensajes: QSplitter para separar lista y visor
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
        splitter.setSizes([500, 200])
        layout.addWidget(splitter)
        # Botón global para iniciar el publicador (sesión vacía)
        connLayout = QHBoxLayout()
        connLayout.addWidget(QLabel("Publicador Global"))
        self.globalStartButton = QPushButton("Iniciar Publicador")
        self.globalStartButton.clicked.connect(self.startPublisher)
        connLayout.addWidget(self.globalStartButton)
        layout.addLayout(connLayout)
        layout.addWidget(QLabel("Resumen de mensajes enviados:"))
        layout.addWidget(self.viewer)
        self.setLayout(layout)

    def loadGlobalRealmTopicConfig(self):
        try:
            data = load_realm_topic_config()
            # Si la configuración viene como lista, la transformamos a diccionario.
            if isinstance(data, list):
                realms_dict = {}
                for item in data:
                    realm = item.get("realm")
                    if realm:
                        realms_dict[realm] = {
                            "router_url": item.get("router_url", "ws://127.0.0.1:60001"),
                            "topics": item.get("topics", [])
                        }
                data = {"realms": realms_dict}
            self.realms_topics = data.get("realms", {})
            print("Configuración global de realms/topics cargada (publicador).")
            # Actualizamos la interfaz de este tab (por ejemplo, rellenando las tablas)
            for widget in self.msgWidgets:
                widget.updateRealmsTopics(self.realms_topics)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar la configuración:\n{e}")

    def addMessage(self):
        widget = MessageConfigWidget(self.next_id, self)
        widget.publisherTab = self  # Asigna la referencia para acceder al visor
        if self.realms_topics:
            widget.updateRealmsTopics(self.realms_topics)
        self.msgLayout.addWidget(widget)
        self.msgWidgets.append(widget)
        self.next_id += 1

    def deleteSelectedMessage(self):
        if self.msgWidgets:
            self.removeMessage(self.msgWidgets[-1])

    def removeMessage(self, widget):
        if widget in self.msgWidgets:
            self.msgWidgets.remove(widget)
            widget.setParent(None)
            widget.deleteLater()

    def startPublisher(self):
    """Inicia el publicador con los mensajes configurados."""
    if not self.msgWidgets:
        QMessageBox.warning(self, "Advertencia", "No hay mensajes configurados para publicar.")
        return

    # Se toma la configuración del primer mensaje (puedes modificar para iterar sobre todos)
    config = self.msgWidgets[0].getConfig()

    # Depuración: imprimir estructuras de realms y topics
    print(f"🔎 Estructura de realms en config: {config.get('realms')}")
    print(f"🔎 Estructura de topics en config: {config.get('topics')}")

    # Validar que exista al menos un realm y que para cada realm haya topics configurados
    if not config or not config.get("realms") or all(len(config["topics"].get(r, [])) == 0 for r in config["realms"]):
        QMessageBox.warning(self, "Advertencia", "No hay realms o topics configurados para el publicador.")
        print("❌ No se encontraron realms o topics para publicar.")
        return

    all_realms = []
    all_topics = []

    # Se asume que config["realms"] es una lista de nombres y config["topics"] es un diccionario
    realms_data = config["realms"]
    topics_data = config["topics"]

    print(f"📌 Realms procesados: {realms_data}")

    # Iterar sobre cada realm configurado
    for realm in realms_data:
        # Obtener la URL del router para el realm usando self.realm_configs
        realm_info = self.realm_configs.get(realm, {"router_url": "ws://127.0.0.1:60001/ws"})
        router_url = realm_info.get("router_url", "ws://127.0.0.1:60001/ws")
        topics = topics_data.get(realm, [])
        if not isinstance(topics, list):
            print(f"⚠️ Error: topics en {realm} no es una lista. Valor recibido: {topics}")
            topics = []  # Forzamos a lista vacía

        if topics:
            all_realms.append(realm)
            all_topics.append(f"{realm}: {', '.join(topics)}")
            # Para cada topic en el realm, se inicia el publicador
            for topic in topics:
                start_publisher(router_url, realm, topic)

    # Registrar el inicio del publicador en el visor (log)
    if all_realms and all_topics:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_info = {
            "action": "start_publisher",
            "realms": all_realms,
            "topics": all_topics
        }
        details = json.dumps(log_info, indent=2, ensure_ascii=False)
        self.viewer.add_message(all_realms, all_topics, timestamp, details)
        print(f"✅ Publicador iniciado en realms {all_realms} con topics {all_topics} a las {timestamp}")
    else:
        QMessageBox.warning(self, "Advertencia", "No hay realms o topics configurados para el publicador.")


    def sendAllAsync(self):
        for widget in self.msgWidgets:
            config = widget.getConfig()
            for realm in config.get("realms", []):
                router_url = self.realm_configs.get(realm, widget.getRouterURL())
                topics = list(config.get("topics", {}).get(realm, []))
                from tu_paquete.wamp.publisher import send_message_now
                for topic in topics:
                    send_message_now(topic, config.get("content", {}), delay=0)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sent_message = json.dumps(config.get("content", {}), indent=2, ensure_ascii=False)
            realms_str = ", ".join(config.get("realms", []))
            topics_str = "; ".join([f"{r}: {', '.join(config.get('topics', {}).get(r, []))}" for r in config.get("realms", [])])
            self.viewer.add_message(realms_str, topics_str, timestamp, sent_message)
            print(f"Mensaje publicado en realms {config.get('realms', [])} y topics {config.get('topics', {})} a las {timestamp}")

    def getProjectConfig(self):
        scenarios = [widget.getConfig() for widget in self.msgWidgets]
        return {"scenarios": scenarios, "realm_configs": self.realm_configs}

    def loadProject(self):
        # Método dummy para evitar error; implementar según tus necesidades.
        pass
