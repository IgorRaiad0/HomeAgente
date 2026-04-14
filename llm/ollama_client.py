import requests
from config import OLLAMA_URL, OLLAMA_MODEL

def ask_llm(prompt):
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data["response"]
    except requests.exceptions.RequestException as e:
        return f"Erro ao acessar o Ollama: verifique se ele está rodando. (Detalhes: {e})"