import os
import glob
from datetime import datetime

# Caminho base do armazenamento local em HomeAgente/data/media
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STORAGE_PATH = os.path.join(BASE_DIR, "data", "media")

class MediaManager:
    @staticmethod
    def get_path(camera_id: str, media_type: str) -> str:
        """Retorna o diretório exato para hoje, e cria a pasta se não existir."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = os.path.join(STORAGE_PATH, media_type, camera_id, date_str)
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def save_snapshot(camera_id: str, content: bytes) -> dict:
        """Salva a imagem JPEG extraída da câmera no disco."""
        timestamp = datetime.now().strftime("%H%M%S")
        date_str = datetime.now().strftime("%Y-%m-%d")
        folder = MediaManager.get_path(camera_id, "snapshots")
        
        filename = f"snap_{timestamp}.jpg"
        full_path = os.path.join(folder, filename)
        
        with open(full_path, "wb") as f:
            f.write(content)
            
        # O "url_path" será usado para o FastAPI servir a URL correta estática (ex: /api/media/snapshots/cam/2026-04/snap.jpg)
        url_path = f"snapshots/{camera_id}/{date_str}/{filename}"
        
        return {
            "filename": filename, 
            "path": full_path,
            "url": f"/api/media/{url_path}",
            "type": "image"
        }

    @staticmethod
    def list_media(camera_id: str):
        """Retorna uma lista de todas as fotos e (futuros vídeos) ordenados cronologicamente."""
        media_list = []
        
        # Pasta da câmera
        cam_snapshots_path = os.path.join(STORAGE_PATH, "snapshots", camera_id)
        
        if os.path.exists(cam_snapshots_path):
            # Procura todos os jpgs recursivamente nas pastas de datas
            pattern = os.path.join(cam_snapshots_path, "**", "*.jpg")
            files = glob.glob(pattern, recursive=True)
            
            for file_path in files:
                # Modificação / timestamp
                created_ts = os.path.getmtime(file_path)
                created_dt = datetime.fromtimestamp(created_ts)
                
                # Extraindo o 'url_path' (Pega a parte a partir de "snapshots/")
                parts = file_path.split(f"{os.sep}media{os.sep}")
                if len(parts) > 1:
                   relative_part = parts[-1]
                else: 
                   continue

                media_list.append({
                    "id": os.path.basename(file_path),
                    "url": f"/api/media/{relative_part.replace(os.sep, '/')}",
                    "date": created_dt.isoformat(),
                    "type": "image"
                })

        # Processar .mp4 tb no futuro para a pasta "recordings" ... (mesma analogia)
        cam_recordings_path = os.path.join(STORAGE_PATH, "recordings", camera_id)
        if os.path.exists(cam_recordings_path):
            pattern = os.path.join(cam_recordings_path, "**", "*.mp4")
            files = glob.glob(pattern, recursive=True)
            for file_path in files:
                created_ts = os.path.getmtime(file_path)
                created_dt = datetime.fromtimestamp(created_ts)
                parts = file_path.split(f"{os.sep}media{os.sep}")
                if len(parts) > 1:
                   relative_part = parts[-1]
                else: 
                   continue

                media_list.append({
                    "id": os.path.basename(file_path),
                    "url": f"/api/media/{relative_part.replace(os.sep, '/')}",
                    "date": created_dt.isoformat(),
                    "type": "video"
                })

        # Ordenar do mais novo pro mais antigo
        media_list.sort(key=lambda x: x["date"], reverse=True)
        return {"data": media_list}
