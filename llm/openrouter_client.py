from openai import OpenAI
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL

# Configuração do Cliente apontando para o OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

def ask_llm(instrucoes_sistema, comando_usuario):
    """
    Envia as regras no 'role: system' e o comando no 'role: user'.
    Isso força o modelo a obedecer rigorosamente às diretrizes.
    """
    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                # Aqui está a mágica: O contexto pesado entra como regra absoluta (system)
                {"role": "system", "content": instrucoes_sistema},
                # E o comando do usuário entra limpo (user)
                {"role": "user", "content": comando_usuario}
            ],
            timeout=20.0,
            max_tokens=1500 
        )
        
        # Extrai o texto da resposta
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content
        
        return "Erro: O OpenRouter não retornou uma resposta válida."

    except Exception as e:
        error_msg = str(e)
        print(f"Erro ao consultar o OpenRouter: {error_msg}")
        
        if "429" in error_msg:
            return "Desculpe, senhor. Os servidores do OpenRouter estão sob alta carga no momento (limite de cota atingido). Por favor, tente novamente em instantes."
        elif "402" in error_msg:
             return "Senhor, atingimos o limite de créditos ou tokens da nossa conta no OpenRouter."
             
        return "Desculpe, senhor. Tive uma falha de comunicação com meus servidores neurais principais."

# Teste rápido 
if __name__ == "__main__":
    print(f"Testando conexão com o modelo: {OPENROUTER_MODEL}")
    print(ask_llm("Você é um assistente virtual. Responda apenas com uma palavra.", "Diga olá."))
