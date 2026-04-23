"""
LLM Router — suporta múltiplos providers.
Para trocar de provider, basta alterar LLM_PROVIDER no .env:
  openrouter | gemini | grok | groq | anthropic
"""
from openai import OpenAI, AsyncOpenAI
import anthropic
from config import (
    LLM_PROVIDER,
    OPENROUTER_API_KEY, OPENROUTER_MODEL,
    GEMINI_API_KEY, GEMINI_MODEL,
    GROK_API_KEY, GROK_MODEL,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
)

# ---------------------------------------------------------------------------
# Configuração de cada provider
# ---------------------------------------------------------------------------
_PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY,
        "model": OPENROUTER_MODEL,
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": GEMINI_API_KEY,
        "model": GEMINI_MODEL,
    },
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "api_key": GROK_API_KEY,
        "model": GROK_MODEL,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "model": "llama-3.3-70b-versatile",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "api_key": ANTHROPIC_API_KEY,
        "model": ANTHROPIC_MODEL,
    },
}

def _get_cfg(provider: str = LLM_PROVIDER) -> dict:
    """Retorna a configuração do provider selecionado."""
    cfg = _PROVIDERS.get(provider)
    if not cfg:
        raise ValueError(f"Provider '{provider}' não reconhecido. Opções: {list(_PROVIDERS.keys())}")
    if not cfg["api_key"]:
        raise ValueError(f"API key para '{provider}' não configurada no .env")
    return cfg

def _sync_client(provider: str = LLM_PROVIDER):
    """Cria cliente síncrono (exceto para Anthropic que usa SDK próprio)."""
    if provider == "anthropic":
        return None  # Anthropic usa SDK próprio
    cfg = _get_cfg(provider)
    return OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])

def _async_client(provider: str = LLM_PROVIDER):
    """Cria cliente assíncrono."""
    if provider == "anthropic":
        return "anthropic"
    cfg = _get_cfg(provider)
    return AsyncOpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])

def _anthropic_client():
    """Cria cliente Anthropic nativo."""
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------
async def ask_llm(instrucoes_sistema: str, comando_usuario: str, provider: str = LLM_PROVIDER) -> str:
    """
    Chamada síncrona para texto livre (roda em thread pool para não bloquear o event loop).
    """
    import asyncio
    import concurrent.futures
    
    def _call_sync():
        return _ask_llm_sync(instrucoes_sistema, comando_usuario, provider)
    
    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor()
    result = await loop.run_in_executor(executor, _call_sync)
    executor.shutdown(wait=False)
    return result

def _ask_llm_sync(instrucoes_sistema: str, comando_usuario: str, provider: str = LLM_PROVIDER) -> str:
    """Implementação síncrona."""
    if provider == "anthropic":
        return _ask_anthropic(instrucoes_sistema, comando_usuario)
    
    cfg = _get_cfg(provider)
    client = _sync_client(provider)
    try:
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": instrucoes_sistema},
                {"role": "user", "content": comando_usuario},
            ],
            timeout=30.0,
            max_tokens=1500,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        err = str(e)
        print(f"[LLM/{provider}] Erro: {err}")
        if "429" in err:
            return "Desculpe, limite de requisições atingido. Tente novamente em instantes."
        if "402" in err or "insufficient" in err.lower():
            return "Créditos insuficientes neste provider. Troque LLM_PROVIDER no .env."
        return "Falha de comunicação com o LLM."

def _ask_anthropic(system: str, user: str) -> str:
    """Chamada para Anthropic (formato diferente)."""
    try:
        client = _anthropic_client()
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=1500,
        )
        return response.content[0].text
    except Exception as e:
        err = str(e)
        print(f"[LLM/anthropic] Erro: {err}")
        if "429" in err:
            return "Desculpe, limite de requisições atingido. Tente novamente em instantes."
        if "insufficient" in err.lower():
            return "Créditos insuficientes neste provider. Troque LLM_PROVIDER no .env."
        return "Falha de comunicação com o LLM."

async def chat_with_tools(user_text: str, tools_schema: list, provider: str = LLM_PROVIDER):
    """Chamada assíncrona com tools (function calling)."""
    if provider == "anthropic":
        return None  # Anthropic usa formato diferente
    
    cfg = _get_cfg(provider)
    try:
        response = await _async_client(provider).chat.completions.create(
            model=cfg["model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é o assistente inteligente da casa. "
                        "Use as ferramentas fornecidas para atender aos pedidos do usuário."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
            tools=tools_schema,
            tool_choice="auto",
            timeout=30.0,
        )
        return response.choices[0].message
    except Exception as e:
        print(f"[LLM/{provider}] Erro no chat_with_tools: {e}")
        return None

if __name__ == "__main__":
    print(f"Provider ativo: {LLM_PROVIDER}")
    print(ask_llm("Responda apenas com uma palavra.", "Diga olá."))