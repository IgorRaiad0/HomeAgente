import threading
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Importa a sua API
from api.routes import router as api_router
# Importa o seu observador
from integrations.ha_websocket import start_observer

# ---------------------------------------------------------
# GERENCIADOR DE TAREFAS DE FUNDO
# ---------------------------------------------------------
def run_websocket():
    """Roda o observador do Home Assistant em um loop separado."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_observer())

@asynccontextmanager
async def lifespan(app: FastAPI):
    # O que acontece ao LIGAR o servidor:
    print("Iniciando observador WebSocket em segundo plano...")
    observer_thread = threading.Thread(target=run_websocket, daemon=True)
    observer_thread.start()
    
    yield # Aqui o servidor web fica rodando
    
    # O que acontece ao DESLIGAR o servidor (Ctrl+C):
    print("Desligando sistemas...")

# ---------------------------------------------------------
# CONFIGURAÇÃO DO SERVIDOR WEB (FASTAPI)
# ---------------------------------------------------------
app = FastAPI(title="Jarvis Central API", version="1.0", lifespan=lifespan)

# CORS (Permite o React Native conversar com o Python)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Acopla as rotas da IA
app.include_router(api_router, prefix="/api", tags=["Jarvis Interface"])

@app.get("/")
async def root():
    return {"status": "Sistemas Online. API e Monitoramento operando perfeitamente."}

if __name__ == "__main__":
    # Permite rodar executando "python main.py" direto
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 