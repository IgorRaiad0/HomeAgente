import asyncio
import json
import websockets
from typing import Set
from fastapi import WebSocket
from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN
from integrations.telegram_bot import send_telegram_message
from tools.chroma_tools import get_exact_mission 

# Converte http:// para ws://
WS_URL = HOME_ASSISTANT_URL.replace("http://", "ws://").rstrip("/") + "/api/websocket"

# Conjunto de conexões WebSocket ativas do Frontend (EdgeHomeUI)
active_connections: Set[WebSocket] = set()

# Variável global para manter a conexão ativa com o HA
ha_socket = None
message_id = 100 # IDs de comandos começam em 100 para não conflitar com inscrições iniciais

async def update_entity_registry(entity_id: str, name: str = None, icon: str = None):
    """
    Envia comandos de atualização (nome, ícone) para o registro do HA.
    Isso é persistente e vence as atualizações das integrações.
    """
    global ha_socket, message_id
    if not ha_socket:
        print("--- [ERROR WS] Conexão com HA não estabelecida para atualização ---")
        return False

    payload = {
        "id": message_id,
        "type": "config/entity_registry/update",
        "entity_id": entity_id
    }
    
    if name: 
        payload["name"] = name
    if icon: 
        payload["icon"] = icon
    
    try:
        if ha_socket:
            await ha_socket.send(json.dumps(payload))
            message_id += 1
            print(f"--- [LOG WS] Registro atualizado: {entity_id} (Name: {name}, Icon: {icon}) ---")
            return True
        return False
    except Exception as e:
        print(f"--- [ERROR WS] Falha ao atualizar registro: {e} ---")
        return False

async def broadcast_state_change(entity_id, new_state, new_name=None, new_icon=None):
    """Grita para todos os celulares que algo mudou (estado, nome ou ícone)."""
    if not active_connections:
        return
        
    payload = {
        "event": "state_changed",
        "entity_id": entity_id,
        "new_state": new_state,
        "new_name": new_name,
        "new_icon": new_icon # Suporte a sincronização de ícone
    }
    
    disconnected = set()
    for ws in active_connections:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.add(ws)
    
    for d in disconnected:
        if d in active_connections:
            active_connections.remove(d)

async def start_observer():
    """Conecta ao WebSocket do HA e monitora Telegram + Frontend."""
    global ha_socket
    while True:
        try:
            print(f"--- [LOG WS] Conectando ao Home Assistant em {WS_URL}... ---")
            async with websockets.connect(WS_URL) as websocket:
                ha_socket = websocket # Disponibiliza a conexão globalmente
                
                # ... (resto do código de auth e sub permanece o mesmo) ...
                # 1. Autenticação
                auth_msg = await websocket.recv()
                await websocket.send(json.dumps({
                    "type": "auth", 
                    "access_token": HOME_ASSISTANT_TOKEN
                }))
                
                auth_result = await websocket.recv()
                print(f"--- [LOG WS] Auth HA: {auth_result} ---")
                
                # 2. Inscrição em eventos
                await websocket.send(json.dumps({
                    "id": 2, 
                    "type": "subscribe_events", 
                    "event_type": "state_changed"
                }))
                
                print("--- [LOG WS] Observador Ativo (Sincronização Total) ---")
                
                while True:
                    msg = await websocket.recv()
                    data = json.loads(msg)
                    
                    if data.get("type") == "event" and data["event"]["event_type"] == "state_changed":
                        event_data = data["event"]["data"]
                        entity_id = event_data["entity_id"]
                        new_state_obj = event_data.get("new_state")
                        old_state_obj = event_data.get("old_state") 
                        
                        if new_state_obj:
                            novo_estado = new_state_obj.get("state")
                            estado_anterior = old_state_obj.get("state") if old_state_obj else None
                            
                            attrs = new_state_obj.get("attributes", {})
                            old_attrs = old_state_obj.get("attributes", {}) if old_state_obj else {}
                            
                            novo_nome = attrs.get("friendly_name")
                            nome_anterior = old_attrs.get("friendly_name")
                            
                            novo_icone = attrs.get("icon")
                            icone_anterior = old_attrs.get("icon")

                            # Se o estado, nome OU ícone mudou
                            if novo_estado != estado_anterior or novo_nome != nome_anterior or novo_icone != icone_anterior:
                                # A. Notifica o Frontend (Broadcast)
                                await broadcast_state_change(entity_id, novo_estado, novo_nome, novo_icone)
                                
                                # B. Notifica o Telegram (Se houver missão no ChromaDB)
                                if novo_estado != estado_anterior:
                                    estados_inativos = ["off", "unavailable", "unknown", "idle", "standby", "paused"]
                                    if novo_estado not in estados_inativos:
                                        missao = get_exact_mission(f"watch_{entity_id}")
                                        if missao: 
                                            send_telegram_message(f"Alerta: {missao}")
                                    
        except Exception as e:
            ha_socket = None
            print(f"--- [ERROR WS] Erro no Observador: {e}. Reconectando... ---")
            await asyncio.sleep(5)

async def handle_frontend_ws(websocket: WebSocket):
    """Gerencia a entrada de um novo celular/terminal na rede."""
    await websocket.accept()
    active_connections.add(websocket)
    print(f"--- [LOG WS] Cliente conectado. Total: {len(active_connections)} ---")
    try:
        while True:
            # Mantém vivo e ignora mensagens recebidas (pode ser usado para comandos futuros)
            await websocket.receive_text()
    except Exception:
        active_connections.remove(websocket)
        print("--- [LOG WS] Cliente desconectado. ---")