import requests

TOPIC = "comboios-nuno-braga-porto-1972"

response = requests.post(
f"https://ntfy.sh/{TOPIC}",
data="Teste GitHub".encode("utf-8"),
headers={"User-Agent": "GitHubActions"}
)

print("STATUS:", response.status_code)
print("RESPOSTA:", response.text)
