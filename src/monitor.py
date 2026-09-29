import requests

url = "https://www.cp.pt/sites/spring/stations"

r = requests.get(url, timeout=20)

print("STATUS:", r.status_code)
print(r.text[:500])
