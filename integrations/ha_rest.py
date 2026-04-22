import requests
import json
from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN

headers = {
    "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
    "Content-Type": "application/json",
}

def get_states():
    try:
        r = requests.get(f"{HOME_ASSISTANT_URL.rstrip('/')}/api/states", headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Erro get_states: {e}")
        return []

def call_service(domain, service, entity_id, params=None):
    """
    Versão unificada e corrigida com suporte a parâmetros extras.
    """
    entity_id = entity_id.strip()
    real_domain = entity_id.split('.')[0] if '.' in entity_id else domain
    
    url = f"{HOME_ASSISTANT_URL.rstrip('/')}/api/services/{real_domain}/{service}"
    payload = {"entity_id": entity_id}
    if params:
        payload.update(params)
    
    print(f"--- [DEBUG HA] URL: {url} | Payload: {payload} ---")
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        error_msg = f"Erro no POST: {e}"
        print(error_msg)
        return {"error": error_msg}


def clean_json(text):
    """Limpa o lixo que a IA pode mandar junto com o JSON."""
    return text.replace("```json", "").replace("```", "").replace("'", '"').strip()

def create_automation(automation_id, name, trigger_str, action_str):
    url = f"{HOME_ASSISTANT_URL.rstrip('/')}/api/config/automation/config/{automation_id}"
    try:
        # Limpando as strings antes de converter
        trigger_clean = clean_json(trigger_str)
        action_clean = clean_json(action_str)
        
        payload = {
            "alias": name,
            "trigger": json.loads(trigger_clean),
            "action": json.loads(action_clean),
            "mode": "single"
        }
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        return f"Automação '{name}' criada com sucesso!"
    except Exception as e:
        return f"Erro ao criar automação: {e}\nJSON recebido: {action_str}"

def create_script(script_id, name, sequence_str):
    url = f"{HOME_ASSISTANT_URL.rstrip('/')}/api/config/script/config/{script_id}"
    try:
        # Limpando a string da sequência
        seq_clean = clean_json(sequence_str)
        
        payload = {
            "alias": name,
            "sequence": json.loads(seq_clean),
            "mode": "single"
        }
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        return f"Cena/Script '{name}' criado!"
    except Exception as e:
        return f"Erro ao criar cena: {e}\nJSON recebido: {sequence_str}"
    


