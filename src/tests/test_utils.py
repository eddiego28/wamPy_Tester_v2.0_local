# tests/test_utils.py
import os
import json
from src.tu_paquete.utils import log_to_file, JsonTreeDialog
from PyQt5.QtWidgets import QApplication
import sys

def test_log_to_file(tmp_path):
    """
    Prueba la función log_to_file escribiendo en un archivo temporal.
    """
    timestamp = "2025-03-20 12:00:00"
    realm = "TestRealm"
    topic = "TestTopic"
    message_json = json.dumps({"key": "value"})
    
    # Simula el directorio de logs
    log_folder = "logs"
    log_file = os.path.join(log_folder, "log.txt")
    if os.path.exists(log_file):
        os.remove(log_file)
    
    log_to_file(timestamp, realm, topic, message_json)
    assert os.path.exists(log_file)
    
    with open(log_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert timestamp in content and realm in content and topic in content

def test_json_tree_dialog(qtbot):
    """
    Prueba la creación del diálogo que muestra el JSON en forma de árbol.
    Requiere el fixture 'qtbot' de pytest-qt.
    """
    data = {"key": "value", "list": [1, 2, 3]}
    dlg = JsonTreeDialog(data)
    dlg.show()
    qtbot.addWidget(dlg)
    # Se verifica que el árbol tenga al menos un elemento
    assert dlg.tree.topLevelItemCount() > 0
