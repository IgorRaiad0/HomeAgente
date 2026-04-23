from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import httpx
import re
from pydantic import BaseModel
from integrations.ha_rest import get_states, call_service
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import shutil
import os
from llm.transcriber import transcrever_audio
from config import AGENT_NAME

# Importando a função EXATA que você usa no seu main.py antigo
from Orchestrador.orchestrador import handle_command

router = APIRouter()

class ChatRequest(BaseModel):
    texto: str

class ChatResponse(BaseModel):
    resposta: str

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        result = await handle_command(request.texto)
        return ChatResponse(resposta=result)
    except Exception as e:
        print(f"Erro no processamento: {e}")
        raise HTTPException(status_code=500, detail="Erro interno nos sistemas do agente.")

@router.post("/voice", response_model=ChatResponse)
async def voice_endpoint(file: UploadFile = File(...)):
    """
    Recebe um arquivo de áudio do celular, transcreve com Whisper 
    e joga o texto no orquestrador.
    """
    if not file:
        raise HTTPException(status_code=400, detail="Nenhum áudio recebido.")

    # 1. Salva o áudio temporariamente na máquina
    caminho_temp = f"temp_{file.filename}"
    try:
        with open(caminho_temp, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"--- [LOG] Áudio recebido e salvo em {caminho_temp} ---")

        # 2. Envia para a Groq transcrever
        texto_usuario = transcrever_audio(caminho_temp)
        print(f"--- [LOG] O {AGENT_NAME} ouviu: '{texto_usuario}' ---")

        if not texto_usuario:
             return ChatResponse(resposta="Desculpe, não consegui entender o áudio.")

        # 3. Envia o texto para o seu Orquestrador pensar e agir
        resposta_agente = await handle_command(texto_usuario)
        
        # 4. Apaga o arquivo temporário para não lotar o PC
        # os.remove(caminho_temp)

        return ChatResponse(resposta=resposta_agente)

    except Exception as e:
        if os.path.exists(caminho_temp):
            os.remove(caminho_temp)
        print(f"Erro no processamento de voz: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar o comando de voz.")

@router.get("/routines")
def get_routines():
    """
    Retorna Automações e Cenas separadas, mas num mesmo endpoint.
    Injeta o campo 'description' a partir do metadata.json ou dos atributos.
    """
    try:
        from api.metadata import get_entity_metadata
        todos_estados = get_states()
        
        automacoes = []
        cenas = []
        
        for estado in todos_estados:
            e_id = estado['entity_id']
            metadata = get_entity_metadata(e_id)
            desc_local = metadata.get("description")
            desc_ha = estado.get('attributes', {}).get('description')
            
            # Adiciona o description ao payload de forma limpa
            estado['description'] = desc_local if desc_local else desc_ha
            
            if e_id.startswith('automation.'):
                automacoes.append(estado)
            elif e_id.startswith(('scene.', 'script.')):
                cenas.append(estado)
                
        return {"data": {"automations": automacoes, "scenes": cenas}}
    except Exception as e:
        print(f"Erro ao buscar rotinas: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar rotinas.")

@router.get("/devices")
def get_devices():
    try:
        todos_estados = get_states()
        # Para dispositivos, pegamos luzes, switches, ar condicionado (climate), media_players, etc.
        # Excluímos automações, sensores invisíveis e configurações do sistema.
        prefixos_validos = ('light.', 'switch.', 'climate.', 'media_player.', 'fan.', 'lock.', 'cover.')
        dispositivos = [estado for estado in todos_estados if estado['entity_id'].startswith(prefixos_validos)]
        return {"data": dispositivos}
    except Exception as e:
        print(f"Erro ao buscar dispositivos: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar dispositivos.")

@router.post("/devices/execute")
async def execute_device_command(payload: dict):
    """
    Payload esperado: {"entity_id": "light.sala", "service": "toggle", "params": {}}
    """
    entity_id = payload.get("entity_id")
    service = payload.get("service")
    params = payload.get("params", {})

    if not entity_id or not service:
        raise HTTPException(status_code=400, detail="entity_id e service são obrigatórios.")

    try:
        domain = entity_id.split('.')[0]
        print(f"--- [LOG] Executando {service} em {entity_id} ---")
        
        res = call_service(domain, service, entity_id, params)
        
        if "error" in res:
            raise HTTPException(status_code=500, detail=res["error"])

        # Retorna sucesso e o novo estado provável
        return {
            "status": "success",
            "entity_id": entity_id,
            "new_state": "on" if "on" in service else "off" 
        }
    except Exception as e:
        print(f"Erro ao executar comando: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def get_device_base_name(entity_id: str):
    """
    Extrai a raiz do nome de forma agressiva.
    Ex: 'light.living_room_main_switch' -> 'living_room'
    Ex: 'sensor.backup_last_successful_automatic_backup' -> 'backup'
    """
    import re
    # Remove o domínio (parte antes do ponto)
    name_part = entity_id.split(".")[-1]
    
    # 1. Regex de Sufixos Muito Abrangente (Limpeza de Cauda)
    sufixos = [
        r"_led", r"_battery", r"_status", r"_mode", r"_vibration", r"_motion", 
        r"_current", r"_voltage", r"_power", r"_wifi", r"_signal_level", 
        r"_last_boot", r"_ip", r"_mac", r"_firmware", r"_rssi", r"_state",
        r"_update", r"_available", r"_linkquality", r"_target_temp", r"_current_temp",
        r"_detection", r"_automatic_backup", r"_manager", r"_next_scheduled",
        r"_last_successful", r"_last_attempted", r"_intensity", r"_sensitivity",
        r"_duration", r"_count", r"_version", r"_uptime", r"_energy", r"_humidity",
        r"_temperature", r"_illuminance", r"_pressure", r"_battery_low", r"_tamper"
    ]
    regex_sufixos = r"(" + "|".join(sufixos) + r")+$"
    
    # Limpa sufixos repetidamente até estabilizar
    prev_name = ""
    while prev_name != name_part:
        prev_name = name_part
        name_part = re.sub(regex_sufixos, "", name_part)
    
    # 2. Lógica de Segmentos (Se o nome for longo, pega os 2 primeiros termos)
    parts = name_part.split("_")
    if len(parts) > 2:
        return "_".join(parts[:2])
    
    return name_part

@router.post("/devices/update")
async def update_device(data: dict):
    """
    Atualiza dados de uma entidade no HA de forma PERMANENTE (Nome, Ícone) e salva Descrição local.
    """
    try:
        from integrations.ha_websocket import update_entity_registry
        from api.metadata import update_entity_metadata
        
        entity_id = data.get("entity_id")
        name = data.get("name")
        icon = data.get("icon")
        description = data.get("description")
        
        if not entity_id:
            raise HTTPException(status_code=400, detail="entity_id é obrigatório.")

        # Salva descrição localmente (se passado como key explícita)
        if "description" in data:
            update_entity_metadata(entity_id, {"description": description})

        # Somente chama o websocket se houver alteração de nome ou ícone
        # Se for SÓ descrição, pula a chamada ao HA
        if name or icon:
            success = await update_entity_registry(entity_id, name=name, icon=icon)
            if not success:
                raise HTTPException(status_code=503, detail="Não foi possível enviar comando de renomeação via WebSocket.")
        
        return {"status": "success"}
    except Exception as e:
        print(f"Erro ao atualizar dispositivo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/routines/{entity_id}")
def delete_routine(entity_id: str):
    try:
        import requests
        from integrations.ha_rest import HOME_ASSISTANT_URL, headers
        from api.metadata import delete_entity_metadata

        domain = entity_id.split('.')[0]
        if domain not in ['automation', 'scene', 'script']:
             raise HTTPException(status_code=400, detail="Apenas automações e cenas podem ser excluídas por esta rota.")

        # O ID da automação para deleção geralmente é o object_id no config
        object_id = entity_id.split('.')[1]
        
        url = f"{HOME_ASSISTANT_URL.rstrip('/')}/api/config/{domain}/config/{object_id}"
        r = requests.delete(url, headers=headers)
        
        # Consideramos 404 como successo também (já que não existe) 
        if r.status_code in [200, 204, 404]:
            delete_entity_metadata(entity_id)
            print(f"--- [LOG] Rotina excluída: {entity_id} ---")
            return {"status": "success"}
        else:
            print(f"--- [ERRO] Falha ao excluir rotina no HA: {r.status_code} - {r.text} ---")
            raise HTTPException(status_code=r.status_code, detail=f"Falha ao deletar no HA: {r.text}")

    except Exception as e:
         print(f"Erro ao deletar rotina: {e}")
         raise HTTPException(status_code=500, detail=str(e))

# Alias para manter retrocompatibilidade temporária com o frontend
@router.post("/devices/rename")
async def rename_device_alias(data: dict):
    return await update_device(data)

# ---- CONTROLLERS DE CÂMERA E MÍDIA ----

@router.get("/camera/{entity_id}/stream")
async def camera_stream(entity_id: str):
    try:
        from integrations.camera_service import HAService
        ha = HAService()
        data = await ha.get_live_stream_url(entity_id)
        if not data:
            raise HTTPException(status_code=503, detail="Stream não disponível para esta câmera.")
        return data
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro ao obter stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/camera/{entity_id}/proxy_stream")
async def proxy_mjpeg_stream(entity_id: str):
    """Faz proxy do MJPEG stream do HA para evitar CORS no navegador."""
    from fastapi.responses import StreamingResponse
    from integrations.camera_service import HAService
    import httpx

    ha = HAService()
    data = await ha.get_live_stream_url(entity_id)
    if not data:
        raise HTTPException(status_code=503, detail="Stream não disponível.")

    async def stream_generator():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", data["stream_url"]) as resp:
                async for chunk in resp.aiter_bytes(4096):
                    yield chunk

    return StreamingResponse(
        stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=ffmpeg"
    )

@router.post("/camera/{entity_id}/snapshot")
async def take_snapshot(entity_id: str):
    try:
        from integrations.camera_service import HAService
        ha = HAService()
        result = await ha.take_snapshot(entity_id)
        return result
    except Exception as e:
        print(f"Erro ao tirar snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/camera/{entity_id}/record")
async def toggle_recording(entity_id: str, payload: dict):
    try:
        from integrations.camera_service import HAService
        ha = HAService()
        duration = payload.get("duration", 30)
        result = await ha.start_recording(entity_id, duration)
        return result
    except Exception as e:
        print(f"Erro ao gravar: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/camera/media/proxy")
async def proxy_ha_media(path: str):
    """Proxy autenticado para mídias do HA (evita expor token no frontend)."""
    from fastapi.responses import StreamingResponse
    from integrations.camera_service import HAService
    ha = HAService()
    ha_url = f"{ha.url}/media/local/{path}"
    media_type = "video/mp4" if path.endswith(".mp4") else "image/jpeg"

    async def stream():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", ha_url, headers=ha.headers) as resp:
                async for chunk in resp.aiter_bytes(8192):
                    yield chunk

    return StreamingResponse(stream(), media_type=media_type)

@router.get("/camera/{entity_id}/gallery")
async def get_camera_gallery(entity_id: str):
    try:
        from integrations.camera_service import HAService
        ha = HAService()
        media = await ha.get_camera_gallery(entity_id)
        return {"media": media}
    except Exception as e:
        print(f"Erro ao buscar galeria: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/media/{file_path:path}")
async def serve_media(file_path: str):
    from api.media_manager import STORAGE_PATH
    import os
    
    full_path = os.path.join(STORAGE_PATH, file_path)
    
    # Prevenção de Path Traversal
    if not os.path.abspath(full_path).startswith(os.path.abspath(STORAGE_PATH)):
         raise HTTPException(status_code=403, detail="Acesso negado.")
         
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
        
    return FileResponse(full_path)

@router.get("/devices/grouped")
async def get_grouped_devices():
    """
    Retorna dispositivos agrupados por uma heurística de prefixos e sufixos.
    Inclui categorização por Área (se disponível) ou padrão.
    """
    try:
        raw_entities = get_states()
        grouped = {}

        # Domínios que geralmente não são "dispositivos" físicos para o usuário final
        dominios_ignorar = [
            "automation", "scene", "script", "zone", "person", "sun", 
            "updater", "conversation", "event", "update", "tts", "notify"
        ]

        for entity in raw_entities:
            e_id = entity["entity_id"]
            domain = e_id.split(".")[0]
            
            if domain in dominios_ignorar:
                continue

            # 1. Define a "Chave do Pacote" (Heurística de Raiz)
            base_name = get_device_base_name(e_id)
            # Agrupa também pelo primeiro termo se for muito comum (ex: backup, supervisor)
            parts = base_name.split("_")
            group_key = parts[0] if parts[0] in ["backup", "supervisor", "hassio"] else base_name

            if group_key not in grouped:
                # Tenta pegar a categoria (Área)
                category = entity.get("attributes", {}).get("area_id", "Geral")
                
                grouped[group_key] = {
                    "id": group_key,
                    "name": "", 
                    "icon": "mdi:package-variant", 
                    "category": category,
                    "main_entity": None,
                    "entities": []
                }

            # 2. Dados da Entidade
            entity_data = {
                "entity_id": e_id,
                "domain": domain,
                "state": entity["state"],
                "name": entity.get("attributes", {}).get("friendly_name", e_id),
                "attributes": entity.get("attributes", {})
            }
            grouped[group_key]["entities"].append(entity_data)

            # 3. Eleição do Líder
            current_main = grouped[group_key]["main_entity"]
            prio_map = {"camera": 10, "light": 9, "switch": 8, "climate": 7, "fan": 6, "lock": 5}
            curr_prio = prio_map.get(domain, 0)
            main_prio = prio_map.get(current_main["domain"] if current_main else "", -1)

            # Desempate: prefere entidade disponível (não unavailable)
            curr_available = entity["state"] != "unavailable"
            main_available = (current_main["state"] != "unavailable") if current_main else False

            should_replace = (
                not current_main
                or curr_prio > main_prio
                or (curr_prio == main_prio and curr_available and not main_available)
            )

            if should_replace:
                grouped[group_key]["main_entity"] = entity_data
                grouped[group_key]["name"] = entity_data["name"]
                grouped[group_key]["icon"] = entity_data["attributes"].get("icon", "mdi:cube-outline")

        # Filtra e ordena
        result = [g for g in grouped.values() if g["main_entity"]]
        result.sort(key=lambda x: (x["category"], x["name"]))
        
        return result
    except Exception as e:
        print(f"Erro ao agrupar dispositivos: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao agrupar dispositivos.")

@router.get("/integrations")
def get_integrations():
    # Nota: A API REST padrão do HA não retorna "integrações" diretamente como retorna entidades.
    # Por enquanto, podemos retornar um resumo ou os domínios ativos.
    try:
        todos_estados = get_states()
        dominios = list(set([estado['entity_id'].split('.')[0] for estado in todos_estados]))
        return {"data": dominios}
    except Exception as e:
        print(f"Erro ao buscar integrações: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar integrações.")