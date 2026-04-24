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

def create_automation(automation_id, json_payload_str):
    url = f"{HOME_ASSISTANT_URL.rstrip('/')}/api/config/automation/config/{automation_id}"
    try:
        # Limpa qualquer lixo ou formatação (ex: ```json) da IA
        payload_clean = clean_json(json_payload_str)
        
        # Converte a string JSON para um dicionário Python
        payload = json.loads(payload_clean)
        
        # Força o modo "single" por segurança, caso a IA esqueça
        if "mode" not in payload:
            payload["mode"] = "single"
            
        print(f"--- [DEBUG HA] Criando automação {automation_id} ---")
        
        # O Home Assistant usa POST neste endpoint para criar e atualizar configs
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        
        # Pega o alias de dentro do JSON da IA (ou usa o ID se ela não mandar)
        alias = payload.get("alias", automation_id)
        return f"Automação '{alias}' criada com sucesso no Padrão Oficial!"
        
    except json.JSONDecodeError as e:
        return f"Erro ao decodificar o JSON gerado pela IA: {e}\nPayload: {json_payload_str}"
    except Exception as e:
        return f"Erro na comunicação com Home Assistant: {e}\nPayload: {json_payload_str}"

def create_script(script_id, json_sequence_str):
    url = f"{HOME_ASSISTANT_URL.rstrip('/')}/api/config/script/config/{script_id}"
    try:
        # Limpa qualquer formatação markdown da IA
        seq_clean = clean_json(json_sequence_str)
        
        # Converte para dicionário
        payload = json.loads(seq_clean)
        
        # Força o modo "single"
        if "mode" not in payload:
            payload["mode"] = "single"
            
        print(f"--- [DEBUG HA] Criando cena/script {script_id} ---")
        
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        
        alias = payload.get("alias", script_id)
        return f"Cena '{alias}' criada com sucesso no Padrão Oficial!"
        
    except json.JSONDecodeError as e:
        return f"Erro ao decodificar o JSON da Cena gerado pela IA: {e}\nPayload: {json_sequence_str}"
    except Exception as e:
        return f"Erro na comunicação com Home Assistant: {e}\nPayload: {json_sequence_str}"


