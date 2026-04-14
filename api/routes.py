from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Importando a função EXATA que você usa no seu main.py antigo
from Orchestrador.orchestrador import handle_command

router = APIRouter()

class ChatRequest(BaseModel):
    texto: str

class ChatResponse(BaseModel):
    resposta: str

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Passa o texto do React Native pro seu orquestrador
        result = handle_command(request.texto)
        return ChatResponse(resposta=result)
    except Exception as e:
        print(f"Erro no processamento: {e}")
        raise HTTPException(status_code=500, detail="Erro interno nos sistemas do Jarvis.")