import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message):
    # A URL precisa do prefixo /bot antes do token
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": str(message)[:4000] # Limite de segurança do Telegram, sem Markdown
    }
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status() 
        return r.json()
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")
        # Print extra para debugar caso a URL ou Token estejam com espaço em branco
        print(f"URL Tentada: {url}") 
        return None

def send_telegram_photo(photo_path, caption=""):
    # Corrigido para garantir o prefixo /bot igual ao de mensagens
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    try:
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': str(caption)[:1024]} # Legendas tem limite menor
            r = requests.post(url, files=files, data=data, timeout=20)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"Erro ao enviar foto: {e}")
        return None