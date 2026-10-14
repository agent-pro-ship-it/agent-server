import urllib.request
import json

key = 'rnd_CSn5m8HP6CrRADxDjmsgdNwjVhdu'
url = 'https://api.render.com/v1/services/srv-davqiunlk1mc73c63nkg/deploys'

payload = json.dumps({"clearCache": "do_not_clear"}).encode('utf-8')
headers = {
    'Authorization': f'Bearer {key}',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))
    print("New Deploy Triggered:", data)
