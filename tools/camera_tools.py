import asyncio
from datetime import datetime
from integrations.camera_service import HAService
from integrations.telegram_bot import send_telegram_photo, send_telegram_video, send_telegram_message
from config import AGENT_NAME, HOME_ASSISTANT_URL

async def tool_camera_capture(entity_id: str, media_type: str) -> str:
    """
    Captura foto ou vídeo via HA e envia pelo Telegram usando o backend como intermediário.
    Usa HAService já existente no projeto — sem criar novas conexões.
    """
    ha = HAService()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cam_slug = entity_id.split(".")[-1]

    if media_type == "photo":
        result = await ha.take_snapshot(entity_id)
        if result.get("status") != "success":
            return f"Falha ao capturar foto de {entity_id}."

        # Aguarda o HA salvar no disco
        await asyncio.sleep(3)

        # Busca o frame atual via proxy para enviar pelo Telegram
        import httpx
        stream_info = await ha.get_live_stream_url(entity_id)
        if stream_info:
            async with httpx.AsyncClient() as client:
                resp = await client.get(stream_info["frame_url"], timeout=10.0)
                if resp.status_code == 200:
                    # Salva temporariamente e envia
                    tmp_path = f"/tmp/{cam_slug}_{timestamp}.jpg"
                    with open(tmp_path, "wb") as f:
                        f.write(resp.content)
                    send_telegram_photo(
                        tmp_path,
                        caption=f"📸 {AGENT_NAME}: Foto da câmera {cam_slug}"
                    )
                    return f"Foto de {entity_id} capturada e enviada ao Telegram."

        return f"Foto salva em {result.get('saved_path')} mas não foi possível enviar ao Telegram."

    elif media_type == "video":
        result = await ha.start_recording(entity_id, duration=30)
        
        if result.get("status") == "recording_started":
            send_telegram_message(
                f"🎥 {AGENT_NAME}: Gravação iniciada. Aguardando {30}s para finalizar..."
            )
            
            await asyncio.sleep(35)
            
            print(f"--- [DEBUG] Buscando vídeo mais recente de {entity_id} ---")
            latest_video = await ha.get_latest_video(entity_id)
            print(f"--- [DEBUG] Vídeo encontrado: {latest_video} ---")
            
            if latest_video:
                import httpx
                from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN
                
                filename = latest_video['title']
                video_url = f"{HOME_ASSISTANT_URL.rstrip('/')}/media/local/edgehome_records/{filename}"
                
                print(f"--- [DEBUG] Baixando de: {video_url} ---")
                
                headers = {"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}"}
                
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(video_url, headers=headers, timeout=60.0)
                        print(f"--- [DEBUG] Status HTTP: {resp.status_code} ---")
                        
                        if resp.status_code == 200:
                            tmp_path = f"/tmp/{filename}"
                            with open(tmp_path, "wb") as f:
                                f.write(resp.content)
                            print(f"--- [DEBUG] Arquivo salvo em: {tmp_path} ---")
                            
                            send_telegram_video(
                                tmp_path,
                                caption=f"🎥 Vídeo da câmera {entity_id}"
                            )
                            return f"Vídeo de {entity_id} capturado e enviado ao Telegram."
                        else:
                            print(f"--- [ERRO] Falha no download. HA retornou: {resp.status_code} ---")
                            print(f"--- [DEBUG] Conteúdo do erro: {resp.text} ---")
                            
                except Exception as e:
                    print(f"--- [ERRO FATAL] Erro ao baixar vídeo: {e} ---")
            else:
                print(f"--- [ERRO] Nenhum vídeo encontrado na galeria ---")
        
        return f"Falha ao iniciar gravação em {entity_id}."

    return f"Tipo de mídia '{media_type}' não reconhecido. Use 'photo' ou 'video'."
