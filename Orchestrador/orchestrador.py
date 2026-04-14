from llm.openrouter_client import ask_llm
from tools.homeassistant_tools import turn_on, turn_off
from integrations.ha_rest import get_states, create_automation, create_script, call_service
from tools.chroma_tools import get_templates
from integrations.ha_history import get_entity_history
from integrations.telegram_bot import send_telegram_message
from tools.chroma_tools import add_template, get_templates, delete_template

# 0. MEMÓRIA GLOBAL (Para o Jarvis lembrar do que acabou de falar)
historico_conversa = []

def handle_command(user_input):
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
    Você é o cérebro do Home Assistant. Você tem controle total e visão em tempo real da casa.

    ESTADO ATUAL DA CASA (Contexto):
    {contexto_dispositivos}
    {contexto_extra}

    MEMÓRIA RECENTE DA CONVERSA:
    {memoria_recente}

    DIRETRIZES:
    1. Para LIGAR/DESLIGAR: ACTION:comando|entity_id
    2. Para CRIAR CENA: ACTION:create_scene|id_unico|Nome Amigável|JSON_LISTA_DE_ACOES
    3. Para CRIAR AUTOMAÇÃO: ACTION:create_auto|id_unico|Nome|JSON_TRIGGER|JSON_ACTION
    4. Use o símbolo "|" para separar as partes da ACTION, nunca ":" após o comando.
    5. Se o usuário for vago ("elas", "as luzes"), use o contexto para decidir.
    6. Se o usuário quiser ATIVAR uma cena já existente, responda: ACTION::script.turn_on|script.nome_da_cena
    7. Se o usuário pedir para ser notificado sobre um evento futuro (ex: 'me avise quando...'), responda: ACTION:monitor_start|entity_id|mensagem_de_alerta
    8. Para PARAR de monitorar: ACTION:monitor_stop|entity_id
    9. Para enviar QUALQUER informação, lista ou relatório ao Telegram: ACTION:telegram.send_message|Texto formatado aqui
    10. Se o usuário solicitar uma informação (lista, status, histórico) e mencionar "Telegram", você DEVE usar ACTION:telegram.send_message| seguido de todo o texto informativo formatado de forma amigável.
    11. Não diga "Não consigo enviar", pois você tem a ferramenta telegram.send_message para isso. Se for enviar uma lista, escreva a lista inteira na sua resposta e depois coloque a ACTION no final.
    12. TELEGRAM E MEMÓRIA: Se o usuário pedir para enviar algo para o Telegram (como uma lista ou relatório que você acabou de falar na memória recente), VOCÊ NÃO PODE apenas dizer "Aqui está a lista". Você DEVE REESCREVER a lista inteira, com todos os tópicos e dados na sua resposta atual, e na ÚLTIMA LINHA colocar ACTION:telegram.send_message|enviar.
    >>> REGRAS ESTRITAS DE NOTIFICAÇÃO E TELEGRAM <<<
    13. MONITORAMENTO (Avisos futuros): Se o usuário pedir "me avise quando...", "me notifique sempre que...", VOCÊ DEVE USAR APENAS: ACTION:monitor_start|entity_id|Sua mensagem personalizada aqui. 
    14. NUNCA use create_auto para enviar mensagens ou notificações. Automações são só para controlar dispositivos.
    15. Para PARAR de monitorar/avisar: ACTION:monitor_stop|entity_id
    16. TELEGRAM IMEDIATO (Envio de informações de agora): Se o usuário pedir para enviar uma lista, status, histórico de agora para o Telegram, você DEVE escrever todo o texto formatado na sua resposta e na ÚLTIMA LINHA colocar OBRIGATORIAMENTE: ACTION:telegram.send_message|enviar.
    17. O serviço telegram.send_message não existe dentro do Home Assistant, é uma ferramenta sua. Nunca o coloque dentro de um JSON de automação.
    18. Se o usuário pedir para enviar algo para o Telegram da memória recente, você DEVE reescrever a informação completa antes da ACTION, não seja vago.
    """

    # --- A CHAMADA DA IA ---
    # Agora enviamos as duas informações separadas!
    response = ask_llm(instrucoes_sistema, user_input)
    
    if not response: 
        return "Desculpe, tive um problema ao processar sua solicitação."

    # --- SALVANDO NA MEMÓRIA ---
    historico_conversa.append(f"Usuário: {user_input}")
    
    # Salva o que ele respondeu (limpando a parte da ACTION para a memória ficar legível)
    fala_do_jarvis = response.split("ACTION:")[0].strip()
    if fala_do_jarvis:
        historico_conversa.append(f"Bimo: {fala_do_jarvis}")

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
        fala_do_jarvis = response.split("ACTION:")[0].strip()
        
        if len(fala_do_jarvis) > 5:
            return fala_do_jarvis
            
        if resultados:
            return "Comandos enviados com sucesso!"

    return response