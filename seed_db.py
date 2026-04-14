# seed_db.py
from tools.chroma_tools import add_template

print("--- [CHROMA] Iniciando injeção de Habilidades no Jarvis... ---")

# 1. Template de Automação (Agendamento de Horário)
auto_template = """
{
  "trigger": {"platform": "time", "at": "18:00:00"},
  "action": {"service": "light.turn_on", "target": {"entity_id": "light.sala"}}
}
"""
add_template("automacao", auto_template)

# 2. Template de Cena/Script (Lista de ações sequenciais)
scene_template = """
[
  {"service": "light.turn_off", "target": {"entity_id": "all"}},
  {"service": "light.turn_on", "target": {"entity_id": "light.quarto"}}
]
"""
add_template("criar_cena", scene_template)

# 3. Template para Notificações (Gatilho de Estado)
notif_template = """
{
  "trigger": {"platform": "state", "entity_id": "light.sala", "from": "off", "to": "on"},
  "action": {"service": "notify.mobile_app_iphone", "data": {"message": "Jarvis: A luz da sala foi ligada!"}}
}
"""
add_template("notificacao", notif_template)

# 4. Template para Mídia/Câmera (Gravação e Snapshot)
camera_template = """
{
  "action": "camera.record",
  "target": {"entity_id": "camera.terraco"},
  "data": {"duration": 10, "lookback": 0, "filename": "/config/www/snapshot.mp4"}
}
"""
add_template("camera", camera_template)

print("--- [CHROMA] Todas as habilidades (Luzes, Cenas, Notificações e Câmeras) foram injetadas! ---")
