Python
import requests

urls = [
"https://www.cp.pt/sites/spring/stations",
"https://www.cp.pt/sites/spring/station/trains?stationId=94-29157"
]

for url in urls:
try:
r = requests.get(url, timeout=20)

print("\nURL:", url)
print("STATUS:", r.status_code)
print(r.text[:500])

except Exception as e:
print("ERRO:", e)
