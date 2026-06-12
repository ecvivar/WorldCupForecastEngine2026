import urllib.request, json

# Check groups
r = urllib.request.urlopen('http://localhost:8000/api/v1/groups')
data = json.loads(r.read())
print(f'Groups count: {len(data)}')
for g in data[:5]:
    print(f'  {g["name"]}: id={g.get("id","?")}')

# Check if first group works with detail endpoint
if data:
    gid = data[0]["id"]
    r = urllib.request.urlopen(f'http://localhost:8000/api/v1/groups/{gid}')
    detail = json.loads(r.read())
    print(f'\nGroup A detail: {detail["name"]}, standings: {len(detail.get("standings", []))}')
    for s in detail.get("standings", []):
        print(f'  {s["team_name"]}: pos={s["position"]}, pts={s["points"]}')

# Check team names for encoding issues
r = urllib.request.urlopen('http://localhost:8000/api/v1/teams?page=1&per_page=100')
teams = json.loads(r.read())
print(f'\nTeam names (first 10):')
for t in teams[:10]:
    print(f'  {t["name"]}')
