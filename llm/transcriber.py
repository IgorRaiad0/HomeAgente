# llm/transcriber.py
from openai import OpenAI
from config import GROQ_API_KEY
import os

# Configuramos o cliente apontando para a Groq
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

def transcrever_audio(caminho_arquivo: str) -> str:
    """
    Envia o arquivo de áudio para a Groq (Whisper V3) e retorna o texto.
    """
    try:
        with open(caminho_arquivo, "rb") as arquivo_audio:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(caminho_arquivo), arquivo_audio),
                model="whisper-large-v3",
                response_format="text", # Retorna apenas a string limpa
                language="pt" # Força o reconhecimento em português
            )
        return transcription.strip()
    except Exception as e:
        print(f"Erro na transcrição: {e}")
        return ""
