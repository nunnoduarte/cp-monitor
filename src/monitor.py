import requests

url = "https://www.infraestruturasdeportugal.pt/negocios-e-servicos/partidas-chegadas/9429157/00:00/23:59/INTERNACIONAL,ALFA,IC,IR,REGIONAL,URB|SUBUR,ESPECIAL"

r = requests.get(url)

print("STATUS:", r.status_code)
print(r.text[:5000])
