import requests

TOPIC = "comboios-nuno-braga-porto-1972"

response = requests.post(
f"https://ntfy.sh/{TOPIC}",
data="Teste Python".encode("utf-8")
)

print("STATUS:", response.status_code)
print(response.text)
