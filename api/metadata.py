import json
import os

METADATA_FILE = os.path.join("data", "metadata.json")

def load_metadata():
    if not os.path.exists(METADATA_FILE):
        return {}
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao ler metadata.json: {e}")
        return {}

def save_metadata(data):
    try:
        os.makedirs("data", exist_ok=True)
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar metadata.json: {e}")

def get_entity_metadata(entity_id: str):
    data = load_metadata()
    return data.get(entity_id, {})

def update_entity_metadata(entity_id: str, updates: dict):
    data = load_metadata()
    if entity_id not in data:
        data[entity_id] = {}
        
    for key, value in updates.items():
        if value is None:
            data[entity_id].pop(key, None)
        else:
            data[entity_id][key] = value
            
    # Remove se ficar vazio
    if not data[entity_id]:
        del data[entity_id]
        
    save_metadata(data)

def delete_entity_metadata(entity_id: str):
    data = load_metadata()
    if entity_id in data:
        del data[entity_id]
        save_metadata(data)
