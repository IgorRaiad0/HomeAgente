import asyncio
import json
import websockets
from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN
from integrations.telegram_bot import send_telegram_message
from tools.chroma_tools import get_exact_mission 

# Converte http:// para ws://
WS_URL = HOME_ASSISTANT_URL.replace("http://", "ws://").rstrip("/") + "/api/websocket"

async def start_observer():
    """Conecta ao WebSocket e monitora apenas o que foi solicitado no ChromaDB."""
    try:
        async with websockets.connect(WS_URL) as websocket:
            # 1. Autenticação
            await websocket.send(json.dumps({
                "type": "auth", 
                "access_token": HOME_ASSISTANT_TOKEN
            }))
            
            # 2. Inscrição em eventos
            await websocket.send(json.dumps({
                "id": 1, 
                "type": "subscribe_events", 
                "event_type": "state_changed"
            }))
            
            print("---Observador Inteligente Ativo (Vigiando com busca exata) ---")
            
            while True:
                msg = await websocket.recv()
                data = json.loads(msg)
                
                if data.get("type") == "event":
                    event_data = data["event"]["data"]
                    entity_id = event_data["entity_id"]
                    new_state_obj = event_data.get("new_state")
                    old_state_obj = event_data.get("old_state") 
                    
                    if new_state_obj:
                        novo_estado = new_state_obj.get("state")
                        estado_anterior = old_state_obj.get("state") if old_state_obj else None
                        
                        # 1. Ignora se for apenas uma mudança de atributo (ex: mudou a temperatura, mas já estava gelando)
                        if novo_estado == estado_anterior:
                            continue

                        # 2. LISTA DE EXCLUSÃO (O padrão global do Home Assistant para coisas inativas)
                        estados_inativos = ["off", "unavailable", "unknown", "idle", "standby", "paused"]
                        
                        # Se o dispositivo mudou de estado, e o novo estado NÃO é inativo, ele foi ligado/acionado!
                        if novo_estado not in estados_inativos:

                            print(f"--- [DEBUG WS] Detecção: {entity_id} mudou para '{novo_estado}' ---")
                            
                            # PERGUNTA AO CHROMADB: "Tenho uma missão EXATA para este dispositivo?"
                            missao = get_exact_mission(f"watch_{entity_id}")
                            if missao: 
                                print(f"--- [DEBUG WS] Missão Encontrada! Enviando Telegram... ---")
                                send_telegram_message(f"Alerta: {missao}")
                                
    except Exception as e:
        print(f"Erro no Observador: {e}")
        await asyncio.sleep(5)