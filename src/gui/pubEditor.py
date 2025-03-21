import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTabWidget,
    QPlainTextEdit, QTreeWidget, QTreeWidgetItem, QPushButton, QMessageBox
)

class PublisherEditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        # Campo para configurar el tiempo (usado para programar envíos)
        timeLayout = QHBoxLayout()
        timeLayout.addWidget(QLabel("Tiempo (HH:MM:SS):"))
        self.commonTimeEdit = QLineEdit("00:00:00")
        timeLayout.addWidget(self.commonTimeEdit)
        layout.addLayout(timeLayout)
        
        # Widget con pestañas para editar el JSON
        self.tabWidget = QTabWidget()
        
        # Pestaña de edición en texto JSON
        self.jsonTab = QWidget()
        jsonLayout = QVBoxLayout()
        self.jsonPreview = QPlainTextEdit()
        self.jsonPreview.setPlainText("{}")
        jsonLayout.addWidget(self.jsonPreview)
        self.jsonTab.setLayout(jsonLayout)
        self.tabWidget.addTab(self.jsonTab, "JSON")
        
        # Pestaña con árbol para editar el JSON
        self.treeTab = QWidget()
        treeLayout = QVBoxLayout()
        self.jsonTree = QTreeWidget()
        self.jsonTree.setHeaderLabels(["Clave", "Valor"])
        treeLayout.addWidget(self.jsonTree)
        self.updateButton = QPushButton("Actualizar campos")
        self.updateButton.clicked.connect(self.updateJsonFromTree)
        treeLayout.addWidget(self.updateButton)
        self.treeTab.setLayout(treeLayout)
        self.tabWidget.addTab(self.treeTab, "Árbol JSON")
        
        self.tabWidget.currentChanged.connect(self.onTabChanged)
        layout.addWidget(self.tabWidget)
        self.setLayout(layout)
    
    def onTabChanged(self, index):
        if self.tabWidget.tabText(index) == "Árbol JSON":
            self.loadTreeFromJson()
    
    def loadTreeFromJson(self):
        self.jsonTree.clear()
        try:
            data = json.loads(self.jsonPreview.toPlainText())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"JSON inválido:\n{e}")
            return
        self.addItems(self.jsonTree.invisibleRootItem(), data)
        self.jsonTree.expandAll()
    
    def addItems(self, parent, data):
        if isinstance(data, dict):
            for key, value in data.items():
                item = QTreeWidgetItem([str(key), ""])
                parent.addChild(item)
                self.addItems(item, value)
        elif isinstance(data, list):
            for index, value in enumerate(data):
                item = QTreeWidgetItem([str(index), ""])
                parent.addChild(item)
                self.addItems(item, value)
        else:
            parent.setText(1, str(data))
    
    def updateJsonFromTree(self):
        root = self.jsonTree.invisibleRootItem()
        data = self.treeToJson(root)
        self.jsonPreview.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))
    
    def treeToJson(self, parent):
        count = parent.childCount()
        if count == 0:
            return parent.text(1)
        keys = [parent.child(i).text(0) for i in range(count)]
        if all(key.isdigit() for key in keys):
            lst = []
            for i in range(count):
                child = parent.child(i)
                lst.append(self.treeToJson(child))
            return lst
        else:
            d = {}
            for i in range(count):
                child = parent.child(i)
                d[child.text(0)] = self.treeToJson(child)
            return d
