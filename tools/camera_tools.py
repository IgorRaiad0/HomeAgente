import asyncio
from datetime import datetime
from integrations.camera_service import HAService
from integrations.telegram_bot import send_telegram_photo, send_telegram_video, send_telegram_message
from config import AGENT_NAME, HOME_ASSISTANT_URL

async def tool_camera_capture(entity_id: str, media_type: str) -> str:
    """
    Captura foto ou vídeo via HA e envia pelo Telegram usando o backend como intermediário.
    """
    ha = HAService()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cam_slug = entity_id.split(".")[-1]

    if media_type == "photo":
        print(f"--- [DEBUG] Iniciando captura de FOTO para {entity_id} ---")
        
        # 1. Opcional: Ainda manda salvar na galeria do HA para ficar de histórico (backup)
        await ha.take_snapshot(entity_id)
        
        # 2. Pega a foto diretamente na memória usando a sua própria função get_camera_image!
        try:
            image_bytes = await ha.get_camera_image(entity_id)
            if image_bytes:
                tmp_path = f"/tmp/{cam_slug}_{timestamp}.jpg"
                with open(tmp_path, "wb") as f:
                    f.write(image_bytes)
                
                print(f"--- [DEBUG] Foto salva em {tmp_path}, enviando ao Telegram... ---")
                send_telegram_photo(
                    tmp_path,
                    caption=f" {AGENT_NAME}: Foto da câmera {cam_slug}"
                )
                return f"Foto de {entity_id} enviada com sucesso."
            else:
                print("--- [ERRO] get_camera_image retornou vazio. ---")
        except Exception as e:
            print(f"--- [ERRO] Falha ao pegar frame da câmera: {e} ---")

        return f"Falha ao processar a foto de {entity_id}."

    elif media_type == "video":
        duracao_video = 8  # Grava 8 segundos (Tempo perfeito para automações rápidas)
        tempo_espera = duracao_video + 3  # Espera a gravação + 3s pro HA salvar no disco
        
        print(f"--- [DEBUG] Iniciando gravação de {duracao_video}s em {entity_id} ---")
        result = await ha.start_recording(entity_id, duration=duracao_video)
        
        if result.get("status") == "recording_started":
            send_telegram_message(
                f" {AGENT_NAME}: Câmera ativada. Gravando clipe de {duracao_video}s..."
            )
            
            # A Pausa Mágica para não puxar o vídeo antigo!
            await asyncio.sleep(tempo_espera)
            
            print(f"--- [DEBUG] Buscando vídeo mais recente de {entity_id} ---")
            latest_video = await ha.get_latest_video(entity_id)
            
            if latest_video:
                import httpx
                from config import HOME_ASSISTANT_TOKEN
                
                # Usa a URL da pasta local do HA que permite download via API
                filename = latest_video['title']
                video_url = f"{ha.url}/media/local/edgehome_records/{filename}"
                print(f"--- [DEBUG] Baixando clipe de: {video_url} ---")
                
                headers = {"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}"}
                
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(video_url, headers=headers, timeout=30.0)
                        print(f"--- [DEBUG] Status HTTP: {resp.status_code} ---")
                        
                        if resp.status_code == 200:
                            filename = latest_video['title']
                            tmp_path = f"/tmp/{filename}"
                            with open(tmp_path, "wb") as f:
                                f.write(resp.content)
                            print(f"--- [DEBUG] Arquivo salvo em: {tmp_path}, enviando! ---")
                            
                            send_telegram_video(
                                tmp_path,
                                caption=f"🎥 Vídeo capturado: {cam_slug}"
                            )
                            return f"Vídeo de {entity_id} enviado."
                        else:
                            print(f"--- [ERRO] HA retornou: {resp.status_code} - {resp.text} ---")
                except Exception as e:
                    print(f"--- [ERRO FATAL] Erro na rede ao baixar vídeo: {e} ---")
            else:
                print(f"--- [ERRO] Nenhum vídeo encontrado na galeria após a pausa. ---")
                
        return f"Falha ao finalizar o vídeo de {entity_id}."

    return f"Tipo de mídia '{media_type}' não reconhecido. Use 'photo' ou 'video'."