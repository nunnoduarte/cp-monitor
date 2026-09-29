import requests
 
TOPIC = "comboios-nuno-braga-porto-1972"
 
mensagem = "✅ Monitor de comboios ativo"
 
requests.post(
f"https://ntfy.sh/{TOPIC}",
data=mensagem.encode("utf-8")
)
