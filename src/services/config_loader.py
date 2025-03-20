# src/services/config_loader.py
import os
import json

def load_realm_topic_config():
    """
    Carga la configuración de realms y topics desde el archivo JSON.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "..", "config", "realm_topic_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        return config_data
    else:
        raise FileNotFoundError("El archivo realm_topic_config.json no se encontró.")
