from llm.openrouter_client import ask_llm
import asyncio
from config import AGENT_NAME
from tools.homeassistant_tools import turn_on, turn_off
from integrations.ha_rest import get_states, create_automation, create_script, call_service
from tools.chroma_tools import get_templates
from integrations.ha_history import get_entity_history
from integrations.telegram_bot import send_telegram_message
from tools.chroma_tools import add_template, get_templates, delete_template

# 0. MEMÓRIA GLOBAL (Para o agente lembrar do que acabou de falar)
historico_conversa = []

async def handle_command(user_input):
    global historico_conversa
    user_input_lower = user_input.lower()
    
    # 1. BUSCA DE ESTADOS REAIS (O seu contexto favorito e essencial)
    estados_atuais = get_states()
    contexto_dispositivos = [
        f"{s['entity_id']}: {s['state']} ({s['attributes'].get('friendly_name', '')})"
        for s in estados_atuais
    ]

    # 2. BUSCA DE TEMPLATES NO CHROMADB (Contexto de criação)
    contexto_extra = ""
    
    # Busca de Histórico (Análise de 24h)
    if any(x in user_input_lower for x in ["relatório", "vezes", "histórico", "quanto"]):
        for s in estados_atuais:
            nome_amigavel = s['attributes'].get('friendly_name', '').lower()
            if nome_amigavel and nome_amigavel in user_input_lower:
                dados_h = get_entity_history(s['entity_id'], hours=24)
                contexto_extra += f"\n[HISTÓRICO {s['entity_id']}]: {dados_h}"

    # Busca de Habilidades/Templates no ChromaDB
    templates = get_templates(user_input)
    contexto_extra += f"\nPARA CRIAÇÕES COMPLEXAS, USE ESTES FORMATOS: {templates}"

    # Prepara as últimas interações (Mantém apenas as últimas 6 falas para não estourar o limite de tokens)
    memoria_recente = "\n".join(historico_conversa[-6:])

    # 3. INSTRUÇÕES DO SISTEMA (As Regras Absolutas)
    instrucoes_sistema = f"""
    Você é o {AGENT_NAME}, o cérebro inteligente do Home Assistant. Você tem controle total e visão em tempo real da casa.

    ESTADO ATUAL DA CASA (Contexto):
    {contexto_dispositivos}
    {contexto_extra}

    MEMÓRIA RECENTE DA CONVERSA:
    {memoria_recente}

DIRETRIZES:
    1. Para LIGAR/DESLIGAR: ACTION:turn_on|entity_id ou ACTION:turn_off|entity_id
    2. Para CRIAR CENA (script no HA): ACTION:create_scene|id_unico烬 Nome烬 JSON_AÇÕES
    3. Para CRIAR AUTOMAÇÃO: ACTION:create_auto|id_unico烬 Nome烬 JSON_TRIGGER烬 JSON_ACTIONS
    4. O JSON deve ser válido e sem quebras de linha.
    5. Para monitorar: ACTION:monitor_start|entity_id|mensagem
    6. Para parar monitoramento: ACTION:monitor_stop|entity_id
    7. Para Telegram: ACTION:telegram.send_message|texto
    8. Para foto: ACTION:camera_capture|entity_id|photo
    9. Para estado: ACTION:get_state|entity_id
    """

    # --- A CHAMADA DA IA ---
    response = await ask_llm(instrucoes_sistema, user_input)
    
    if not response: 
        return "Desculpe, tive um problema ao processar sua solicitação."

    # --- SALVANDO NA MEMÓRIA ---
    historico_conversa.append(f"Usuário: {user_input}")
    
    # Salva o que ele respondeu (limpando a parte da ACTION para a memória ficar legível)
    fala_do_agente = response.split("ACTION:")[0].strip()
    if fala_do_agente:
        historico_conversa.append(f"{AGENT_NAME}: {fala_do_agente}")

    # 4. PROCESSAMENTO DE AÇÕES (
    if "ACTION:" in response:
        linhas = response.strip().split('\n')
        resultados = []
        
        for linha in linhas:
            if "ACTION:" in linha:
                # 1. Limpa a linha e separa os campos
                comando_puro = linha.replace("ACTION:", "").strip()
                parts = [p.strip() for p in comando_puro.split("|")]
                
                if len(parts) >= 2:
                    action = parts[0]
                    target = parts[1]

                    # --- LÓGICA DE EXECUÇÃO ---

                    #  Criação de Automação
                    if action == "create_auto" and len(parts) >= 5:
                        print(f"--- [LOG] Solicitando Criação de Automação ao HA: {parts[2]} ---")
                        print(f"--- [DEBUG] Trigger: {parts[3]} | Action: {parts[4]} ---")
                        res = create_automation(parts[1], parts[2], parts[3], parts[4])
                        resultados.append(res)
                        
                    # Criação de Cena (Script)
                    elif action == "create_scene" and len(parts) >= 4:
                        print(f"--- [LOG] Solicitando Criação de Cena ao HA: {parts[2]} ---")
                        print(f"--- [DEBUG] Ações: {parts[3]} ---")
                        res = create_script(parts[1], parts[2], parts[3])
                        resultados.append(res)

                    # comunicação com telegram
                    elif action == "telegram.send_message":
                        conteudo = response.split("ACTION:")[0].strip()
                        if not conteudo or len(conteudo) < 5:
                            conteudo = target 

                        if not conteudo or len(conteudo) < 5:
                            conteudo = "Aqui está a informação solicitada, senhor."

                        print(f"--- [LOG] Redirecionando resposta para Telegram ---")
                        send_telegram_message(conteudo)
                        return "Enviado para o seu Telegram, senhor."
                    
                    #monitoramento websokete inicio
                    elif action == "monitor_start" and len(parts) >= 3:
                        target_clean = target.split(" ")[0].split("\n")[0].strip()
                        
                        msg_customizada = parts[2]
                        add_template(f"watch_{target_clean}", msg_customizada)
                        return f"Certamente, senhor. Monitorando {target_clean} agora."
                    
                    #monitoramento websocket parar
                    elif action == "monitor_stop":
                        target_clean = target.split(" ")[0].split("\n")[0].strip()
                        
                        delete_template(f"watch_{target_clean}") 
                        return f"Entendido. Removi o monitoramento de {target_clean}."

                    # Consulta de Estado
                    elif action == "get_state":
                        from integrations.camera_service import HAService
                        
                        target_clean = target.split(" ")[0].split("\n")[0].strip()
                        ha = HAService()
                        estado = await ha.get_state(target_clean)
                        return f"O estado de {target_clean} é: {estado}"

                    # Captura de Câmera
                    elif action == "camera_capture" and len(parts) >= 3:
                        target_clean = target.split(" ")[0].split("\n")[0].strip()
                        media_type = parts[2].strip()
                        
                        print(f"--- [LOG] Solicitando captura de {media_type} na {target_clean} ---")
                        
                        from tools.camera_tools import tool_camera_capture
                        
                        asyncio.create_task(tool_camera_capture(target_clean, media_type))
                            
                        return f"Certamente! Solicitada a captura de {media_type} na câmera. A mídia chegará no seu Telegram em instantes."

                    # Execução de Comandos (Universal: Luz, Ar, TV, Scripts)
                    else:
                        target_clean = target.split(" ")[0].split("\n")[0].strip()
                        print(f"--- [LOG] Executando: {action} em {target_clean} ---")
                    
                        if "." in action:
                            domain, service = action.split(".", 1)
                            res = call_service(domain, service, target_clean)
                        else:
                            domain = target_clean.split(".")[0] if "." in target_clean else "homeassistant"
                            res = call_service(domain, action, target_clean)
                        
                        resultados.append(res)
        
        # --- RETORNO INTELIGENTE ---
        # Se houve um texto antes da ACTION, priorizamos mostrar esse texto (ex: listas, explicações)
        fala_do_agente = response.split("ACTION:")[0].strip()
        
        if len(fala_do_agente) > 5:
            return fala_do_agente
            
        if resultados:
            return "Comandos enviados com sucesso!"

    return response