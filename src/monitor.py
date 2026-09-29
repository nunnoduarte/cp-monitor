import requests

url = "https://www.cp.pt/sites/spring/station/trains"

params = {
"stationId": "94-29157"
}

r = requests.get(url, params=params)

print("URL:", r.url)
print("STATUS:", r.status_code)
print(r.text[:1000])
