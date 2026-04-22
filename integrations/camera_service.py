import httpx
import json
from datetime import datetime
from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN

class HAService:
    def __init__(self):
        self.url = HOME_ASSISTANT_URL.rstrip('/')
        self.headers = {"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}"}

    async def get_live_stream_url(self, entity_id: str) -> dict | None:
        """Retorna a URL do proxy MJPEG e o token de acesso da câmera."""
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{self.url}/api/states/{entity_id}",
                headers=self.headers,
                timeout=10.0
            )
            if res.status_code == 200:
                attrs = res.json().get("attributes", {})
                token = attrs.get("access_token")
                if token:
                    return {
                        "frame_url": f"{self.url}/api/camera_proxy/{entity_id}?token={token}",
                        "stream_url": f"{self.url}/api/camera_proxy_stream/{entity_id}?token={token}",
                        "type": "mjpeg"
                    }
        return None

    async def take_snapshot(self, entity_id: str) -> dict:
        """Manda o próprio HA tirar a foto e salvar na sua pasta /media."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ha_filename = f"/media/edgehome_snaps/{entity_id}_{timestamp}.jpg"
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.url}/api/services/camera/snapshot",
                headers=self.headers,
                json={"entity_id": entity_id, "filename": ha_filename},
                timeout=15.0
            )
            if res.status_code == 200:
                return {"status": "success", "saved_path": ha_filename}
        return {"status": "error", "message": "Falha ao acionar snapshot no HA"}

    async def start_recording(self, entity_id: str, duration: int = 30) -> dict:
        """Manda o HA gravar um vídeo e salvar na sua pasta /media."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ha_filename = f"/media/edgehome_records/{entity_id}_{timestamp}.mp4"
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.url}/api/services/camera/record",
                headers=self.headers,
                json={"entity_id": entity_id, "filename": ha_filename, "duration": duration},
                timeout=15.0
            )
        return {"status": "recording_started", "saved_path": ha_filename}

    async def get_camera_gallery(self, entity_id: str) -> list:
        """Busca fotos e vídeos no HA via WebSocket dedicado."""
        import websockets
        import asyncio

        ws_url = self.url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
        cam_id = entity_id.split(".")[-1]
        folders = ["edgehome_snaps", "edgehome_records"]
        all_media = []

        try:
            async with websockets.connect(ws_url) as ws:
                await ws.recv()  # auth_required
                await ws.send(json.dumps({"type": "auth", "access_token": HOME_ASSISTANT_TOKEN}))
                if json.loads(await ws.recv()).get("type") != "auth_ok":
                    return []

                for idx, folder in enumerate(folders):
                    await ws.send(json.dumps({
                        "id": idx + 1,
                        "type": "media_source/browse_media",
                        "media_content_id": f"media-source://media_source/local/{folder}"
                    }))
                    data = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
                    if not data.get("success"):
                        continue
                    for item in data.get("result", {}).get("children", []):
                        if cam_id not in item.get("title", ""):
                            continue
                        all_media.append({
                            "title": item["title"],
                            "url": f"/api/camera/media/proxy?path={folder}/{item['title']}",
                            "type": "video" if item["title"].endswith(".mp4") else "image"
                        })

        except Exception as e:
            print(f"--- [ERROR] Galeria WebSocket: {e} ---")

        all_media.sort(key=lambda x: x["title"], reverse=True)
        return all_media

    async def call_service(self, domain, service, data):
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.url}/api/services/{domain}/{service}",
                headers=self.headers,
                json=data,
                timeout=15.0
            )
            res.raise_for_status()
            try:
                return res.json()
            except:
                return {"status": "success"}

    async def get_camera_image(self, entity_id):
        """Captura o frame atual diretamente do stream do HA e retorna em bytes."""
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{self.url}/api/camera_proxy/{entity_id}",
                headers=self.headers,
                timeout=15.0
            )
            res.raise_for_status()
            return res.content
