import requests

url = "https://www.infraestruturasdeportugal.pt/negocios-e-servicos/partidas-chegadas/9429157/00:00/23:59/INTERNACIONAL,ALFA,IC,IR,REGIONAL,URB|SUBUR,ESPECIAL"

headers = {
"User-Agent": "Mozilla/5.0"
}

r = requests.get(url, headers=headers)

print("STATUS:", r.status_code)
print("TAMANHO:", len(r.text))
print(r.text[:500])
