import requests

TOPIC = "comboios-nuno-braga-porto-1972"

response = requests.post(
f"https://ntfy.sh/{TOPIC}",
data="Teste".encode("utf-8")
)

print("STATUS:", response.status_code)
print("RESPOSTA:")
print(response.text)
