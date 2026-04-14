import requests
from datetime import datetime, timedelta
from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN

headers = {"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}", "Content-Type": "application/json"}

def get_entity_history(entity_id, hours=24):
    # Calcula o tempo inicial (ISO 8601)
    start_time = (datetime.now() - timedelta(hours=hours)).isoformat()
    url = f"{HOME_ASSISTANT_URL.rstrip('/')}/api/history/period/{start_time}?filter_entity_id={entity_id}"
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        if not data: return "Nenhum histórico encontrado."
        
        history = data[0]
        ligou_count = sum(1 for state in history if state['state'] == 'on')
        
        return f"A entidade {entity_id} foi ligada {ligou_count} vezes nas últimas {hours} horas."
    except Exception as e:
        return f"Erro ao buscar histórico: {e}"
