from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
from pathlib import Path

# Define o caminho do .env relativo a este arquivo
ENV_FILE = Path(__file__).parent / ".env"

class Settings(BaseSettings):
    # Procura as variáveis no arquivo .env ou no ambiente do sistema
    # O Pydantic valida automaticamente se as obrigatórias foram preenchidas
    
    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL: str = "qwen/qwen3-next-80b-a3b-instruct:free"
    
    HOME_ASSISTANT_URL: str
    HOME_ASSISTANT_TOKEN: str
    
    CHROMADB_URL: str = "http://localhost:6333"
    
    TELEGRAM_TOKEN: str
    TELEGRAM_CHAT_ID: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Cria a instância global de configurações
try:
    settings = Settings()
except Exception as e:
    print(f"Erro ao carregar configurações: {e}")
    # Opcional: você pode optar por encerrar o app aqui se as configs forem críticas
    raise

# Re-exportamos as variáveis para manter compatibilidade com o restante do projeto
# Assim, arquivos que fazem 'from config import GEMINI_API_KEY' continuam funcionando.
OPENROUTER_API_KEY = settings.OPENROUTER_API_KEY
OPENROUTER_MODEL = settings.OPENROUTER_MODEL

HOME_ASSISTANT_URL = settings.HOME_ASSISTANT_URL
HOME_ASSISTANT_TOKEN = settings.HOME_ASSISTANT_TOKEN

CHROMADB_URL = settings.CHROMADB_URL

TELEGRAM_TOKEN = settings.TELEGRAM_TOKEN
TELEGRAM_CHAT_ID = settings.TELEGRAM_CHAT_ID

if __name__ == "__main__":
    print("Configurações carregadas com sucesso via Pydantic!")
    print(f"OpenRouter Model: {OPENROUTER_MODEL}")
    print(f"Home Assistant URL: {HOME_ASSISTANT_URL}")
