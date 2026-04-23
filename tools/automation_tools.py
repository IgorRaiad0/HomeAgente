"""
Ferramentas de automação para o Home Assistant.
Cria automações reais no HA via API REST.
"""
from typing import Optional, List, Dict, Any
from integrations.camera_service import HAService

async def tool_create_ha_automation(
    alias: str,
    trigger_entity: str,
    action_type: str,
    camera_entity: Optional[str] = None,
    telegram_message: Optional[str] = None
) -> str:
    """Cria uma automação real no Home Assistant."""
    from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN
    import httpx
    
    automation_id = alias.lower().replace(" ", "_")
    actions_list: List[Dict[str, Any]] = []
    
    if camera_entity and action_type in ["photo", "video"]:
        if action_type == "photo":
            actions_list.append({
                "service": "camera.snapshot",
                "data": {
                    "entity_id": camera_entity,
                    "filename": f"/media/edgehome_snaps/auto_{automation_id}.jpg"
                }
            })
        else:
            actions_list.append({
                "service": "camera.record",
                "data": {
                    "entity_id": camera_entity,
                    "filename": f"/media/edgehome_records/auto_{automation_id}.mp4",
                    "duration": 30
                }
            })
    
    if telegram_message:
        actions_list.append({
            "service": "notify.persistent_notification",
            "data": {
                "message": telegram_message,
                "title": f"🔔 {alias}"
            }
        })
    
    automation_data = {
        "alias": alias,
        "id": automation_id,
        "trigger": [
            {
                "platform": "state",
                "entity_id": trigger_entity
            }
        ],
        "action": actions_list
    }
    
    url = f"{HOME_ASSISTANT_URL.rstrip('/')}/api/config/automation/config/{automation_id}"
    headers = {
        "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.put(url, headers=headers, json=automation_data, timeout=15.0)
            
            if resp.status_code in [200, 201]:
                print(f"--- [AUTOMATION] Criada: {alias} ---")
                return f"✅ Automação '{alias}' criada com sucesso no Home Assistant!"
            else:
                print(f"--- [ERRO] Automação falhou: {resp.status_code} - {resp.text} ---")
                return f"Erro ao criar automação: {resp.status_code}"
    except Exception as e:
        print(f"--- [ERRO] Automação: {e} ---")
        return f"Erro: {e}"


async def tool_delete_ha_automation(alias: str) -> str:
    """Deleta uma automação do Home Assistant."""
    from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN
    import httpx
    
    automation_id = alias.lower().replace(" ", "_")
    url = f"{HOME_ASSISTANT_URL.rstrip('/')}/api/config/automation/config/{automation_id}"
    headers = {"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}"}
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=headers, timeout=10.0)
            
            if resp.status_code in [200, 204]:
                return f"✅ Automação '{alias}' deletada."
            else:
                return f"Erro ao deletar: {resp.status_code}"
    except Exception as e:
        return f"Erro: {e}"


async def tool_list_ha_automations() -> str:
    """Lista todas as automações do Home Assistant."""
    from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN
    import httpx
    
    url = f"{HOME_ASSISTANT_URL.rstrip('/')}/api/config/automation/config"
    headers = {"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}"}
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10.0)
            
            if resp.status_code == 200:
                automations = resp.json()
                if not automations:
                    return "Nenhuma automação encontrada."
                
                lista = []
                for auto in automations:
                    alias_name = auto.get("alias", "Sem nome")
                    triggers = auto.get("trigger", [])
                    trigger_desc = ", ".join([
                        f"{t.get('platform', '?')}" for t in triggers
                    ]) if triggers else "sem gatilho"
                    lista.append(f"- {alias_name} ({trigger_desc})")
                
                return "📋 Automações no HA:\n" + "\n".join(lista)
            else:
                return f"Erro ao listar: {resp.status_code}"
    except Exception as e:
        return f"Erro: {e}"