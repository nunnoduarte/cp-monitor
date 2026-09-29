import requests
from datetime import datetime
 
TOPIC = "comboios-nuno-braga-porto-1972"
 
mensagem = (
    f"✅ Monitor ativo\n"
    f"Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
)
 
requests.post(
    f"https://ntfy.sh/{TOPIC}",
    data=mensagem.encode("utf-8")
)
