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
    1. Para LIGAR/DESLIGAR: ACTION:comando|entity_id
    2. Para CRIAR CENA (SCRIPT): ACTION:create_scene|id_unico|JSON_COMPLETO
    (Use para ações MANUAIS. Cenas NÃO têm gatilho. O JSON deve conter "alias" e "sequence". OBRIGATÓRIO: O JSON DEVE SER ESCRITO EM UMA ÚNICA LINHA, SEM QUEBRAS DE LINHA).
    3. Para CRIAR AUTOMAÇÃO: ACTION:create_auto|id_unico|JSON_COMPLETO
    (Use para ações CONDICIONAIS. Automações OBRIGATORIAMENTE têm gatilho. O JSON deve conter "alias", "trigger" e "action". OBRIGATÓRIO: O JSON DEVE SER ESCRITO EM UMA ÚNICA LINHA, SEM QUEBRAS DE LINHA).
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
    14. FOTOS E VÍDEOS EM CENAS/AUTOMAÇÕES: Para enviar mídia pelo Telegram dentro de um JSON (forma autônoma), você DEVE colocar DUAS ações em sequência:
        - Para FOTO: 
          Ação 1: {{"service": "camera.snapshot", "target": {{"entity_id": "NOME_DA_SUA_CAMERA"}}, "data": {{"filename": "/config/www/foto_auto.jpg"}}}}
          Ação 2: {{"service": "telegram_bot.send_photo", "data": {{"file": "/config/www/foto_auto.jpg", "caption": "Foto capturada automaticamente!"}}}}
        - Para VÍDEO:
          Ação 1: {{"service": "camera.record", "target": {{"entity_id": "NOME_DA_SUA_CAMERA"}}, "data": {{"filename": "/config/www/video_auto.mp4", "duration": 5}}}}
          Ação 2: {{"service": "telegram_bot.send_video", "data": {{"file": "/config/www/video_auto.mp4", "caption": "Vídeo gravado automaticamente!"}}}}
    15. O comando ACTION:telegram.send_message| e ACTION:camera_capture| são estritamente para respostas IMEDIATAS da nossa conversa. NUNCA os coloque dentro de um JSON de automação ou cena.
    16. TELEGRAM IMEDIATO (Envio de informações de agora): Se o usuário pedir para enviar uma lista, status, histórico de agora para o Telegram, você DEVE escrever todo o texto formatado na sua resposta e na ÚLTIMA LINHA colocar OBRIGATORIAMENTE: ACTION:telegram.send_message|enviar.
    17. O serviço telegram.send_message não existe dentro do Home Assistant, é uma ferramenta sua. Nunca o coloque dentro de um JSON de automação.
    18. Se o usuário pedir para enviar algo para o Telegram da memória recente, você DEVE reescrever a informação completa antes da ACTION, não seja vago.
    19. Para tirar foto ou gravar vídeo de uma câmera,responda: ACTION:camera_capture|entity_id|media_type (onde media_type é 'photo' ou 'video').
    20. Para CONSULTAR o estado de qualquer dispositivo, use: ACTION:get_state|entity_id
    21. RACIOCÍNIO LÓGICO: Quando o usuário perguntar sobre algo ("está ligado?", "está aberto?"), use ACTION:get_state antes de responder. Não invente respostas - consulte o estado real primeiro.
    22. Para TRANSMITIR a imagem de uma câmera na TV: ACTION:stream_camera|entity_id_da_camera|entity_id_da_tv
    22. Para TRANSMITIR a imagem de uma câmera na TV, use: ACTION:stream_camera|entity_id_da_camera|media_player.sala_de_tv
    23. Para TRANSMITIR a imagem de uma câmera na TV, use: ACTION:stream_camera|entity_id_da_camera|media_player.sala_de_tv
    (ATENÇÃO: Sempre use 'media_player.sala_de_tv' como alvo. Ignore entidades com _2 ou _3. IGNORE completamente se o status da TV estiver 'off', pois ela liga automaticamente ao receber o vídeo. Não relate falhas de comunicação, apenas confirme a ação com confiança! em sua resposta para o usuário)
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

                print(f"--- [DEBUG IA] O agente enviou exatamente isto: {parts} ---")
                
                if len(parts) >= 2:
                    action = parts[0]
                    target = parts[1]

                    # --- LÓGICA DE EXECUÇÃO ---

                   # Criação de Automação (Padrão Oficial)
                    if action == "create_auto":
                        if len(parts) >= 3:
                            auto_id = parts[1]
                            json_str = parts[2]
                            
                            print(f"--- [LOG] Enviando Automação '{auto_id}' para o HA ---")
                            res = create_automation(auto_id, json_str)
                            resultados.append(res)
                        else:
                            erro_msg = f"Erro de sintaxe da IA: Recebeu {len(parts)} parâmetros, esperava 3."
                            print(f"--- [ERRO] {erro_msg} ---")
                            resultados.append(erro_msg)
                            
                    # Criação de Cena (Padrão Oficial HA)
                    elif action == "create_scene":
                        if len(parts) >= 3:
                            scene_id = parts[1]
                            json_str = parts[2]
                            
                            print(f"--- [LOG] Enviando Cena '{scene_id}' para o HA ---")
                            res = create_script(scene_id, json_str)
                            resultados.append(res)
                        else:
                            erro_msg = f"Erro de sintaxe da IA na Cena: Recebeu {len(parts)} parâmetros, esperava 3."
                            print(f"--- [ERRO] {erro_msg} ---")
                            resultados.append(erro_msg)

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
                    
                    # Transmissão de Câmera na TV
                    # Transmissão de Câmera na TV
                    elif action == "stream_camera" and len(parts) >= 3:
                        camera_id = target.split(" ")[0].split("\n")[0].strip()
                        tv_id = parts[2].strip()
                        
                        print(f"--- [LOG] Solicitando stream da {camera_id} para {tv_id} ---")
                        
                        from integrations.camera_service import HAService
                        ha = HAService()
                        
                        # Espelhando exatamente o que você descobriu no YAML
                        payload = {
                            "entity_id": camera_id,
                            "media_player": tv_id,
                            "format": "hls"
                        }
                        
                        # Executa o serviço de forma assíncrona
                        try:
                            await ha.call_service("camera", "play_stream", payload)
                        except Exception as e:
                            print(f"--- [ERRO] Falha ao enviar stream: {e} ---")
                            return "Desculpe, senhor. Houve um erro ao tentar transmitir a câmera para a TV."
                            
                        return f"Certamente, senhor. Iniciando a transmissão da câmera na sua TV."

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