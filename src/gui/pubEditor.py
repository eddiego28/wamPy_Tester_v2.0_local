# src/tu_paquete/pubEditor.py
import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox, QTableWidgetItem
)
from PyQt5.QtCore import Qt

def build_tree_items(data):
    """
    Función recursiva para transformar un JSON (dict o list) en elementos
    (QTreeWidgetItem) que se pueden agregar a un QTreeWidget.KHJFALDSKJHASDLKJ
    """
    items = []
    if isinstance(data, dict):
        for key, value in data.items():
            item = QTreeWidgetItem([str(key), ""])
            if isinstance(value, (dict, list)):
                children = build_tree_items(value)
                item.addChildren(children)
            else:
                item.setText(1, str(value))
            items.append(item)
    elif isinstance(data, list):
        for i, value in enumerate(data):
            item = QTreeWidgetItem([f"[{i}]", ""])
            if isinstance(value, (dict, list)):
                children = build_tree_items(value)
                item.addChildren(children)
            else:
                item.setText(1, str(value))
            items.append(item)
    else:
        items.append(QTreeWidgetItem([str(data), ""]))
    return items

class PublisherEditorWidget(QWidget):
    """
    Widget que permite:
      - Cargar un JSON desde archivo
      - Validar el JSON ingresado
      - Convertir el JSON a una vista en árbol
    Se organiza en dos pestañas: una con el texto del JSON y otra con la vista en árbol.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        mainLayout = QVBoxLayout()

        # Botones para cargar, validar y actualizar la vista
        btnLayout = QHBoxLayout()
        self.importButton = QPushButton("Cargar JSON desde Archivo")
        self.importButton.clicked.connect(self.loadJSONFromFile)
        btnLayout.addWidget(self.importButton)
        
        self.validateButton = QPushButton("Validar JSON")
        self.validateButton.clicked.connect(self.validateJson)
        btnLayout.addWidget(self.validateButton)
        
        self.convertButton = QPushButton("Actualizar Vista Árbol")
        self.convertButton.clicked.connect(self.convertToTree)
        btnLayout.addWidget(self.convertButton)
        mainLayout.addLayout(btnLayout)

        # QTabWidget con dos pestañas: "JSON" y "Árbol"
        self.previewTabWidget = QTabWidget()
        self.previewTabWidget.setMinimumHeight(400)
        self.jsonPreview = QTextEdit()
        self.jsonPreview.setReadOnly(False)
        self.previewTabWidget.addTab(self.jsonPreview, "JSON")
        self.treePreview = QTreeWidget()
        self.treePreview.setColumnCount(2)
        self.treePreview.setHeaderLabels(["Clave", "Valor"])
        self.previewTabWidget.addTab(self.treePreview, "Árbol")
        mainLayout.addWidget(self.previewTabWidget)
        self.setLayout(mainLayout)

    def loadJSONFromFile(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Seleccione un archivo JSON", "", "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.jsonPreview.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))
            self.buildTreePreview(data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el JSON:\n{e}")
            
    def updateRealmsTopics(self, realms_topics):
        self.realms_topics = realms_topics
        self.realmTable.blockSignals(True)
        self.realmTable.setRowCount(0)
        for realm, info in sorted(realms_topics.items()):
            row = self.realmTable.rowCount()
            self.realmTable.insertRow(row)
            item = QTableWidgetItem(realm)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            # Se marca por defecto el realm para que se active
            item.setCheckState(Qt.Checked)
            self.realmTable.setItem(row, 0, item)
            router_url = info.get("router_url", "ws://127.0.0.1:60001/ws")
            self.realmTable.setItem(row, 1, QTableWidgetItem(router_url))
        self.realmTable.blockSignals(False)
        # Si hay al menos un realm, selecciona la primera fila y actualiza la lista de topics
        if self.realmTable.rowCount() > 0:
            self.realmTable.selectRow(0)
            self.onRealmClicked(0, 0)


    def validateJson(self):
        try:
            data = json.loads(self.jsonPreview.toPlainText())
            self.buildTreePreview(data)
            QMessageBox.information(self, "Validación", "JSON válido.")
        except Exception as e:
            QMessageBox.critical(self, "Error de Validación", f"El JSON no es válido:\n{e}")

    def convertToTree(self):
        try:
            data = json.loads(self.jsonPreview.toPlainText())
            self.buildTreePreview(data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al convertir a árbol:\n{e}")

    def buildTreePreview(self, data):
        self.treePreview.clear()
        items = build_tree_items(data)
        self.treePreview.addTopLevelItems(items)
        self.treePreview.expandAll()
