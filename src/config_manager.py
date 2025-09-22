import os
import json
from src.utils import resource_path # <-- 1. Importar la utilidad

CONFIG_FILE = resource_path("config.json") 

def load_config():
    """Reads the 'config.json' file and returns its data as a dictionary. 
    Returns empty dict if missing or corrupted."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except:
            return {}
    else:
        return {}


def save_config(config):
    """Saves the given config dictionary into 'config.json'."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)