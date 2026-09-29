import requests

urls = [
"https://www.cp.pt/sites/spring/stations",
"https://www.cp.pt/sites/spring/station/trains?stationId=94-29157"
]

for url in urls:
r = requests.get(url, timeout=20)

print()
print("URL:", url)
print("STATUS:", r.status_code)
print(r.text[:500])
