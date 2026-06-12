with open('backend/docker-entrypoint.sh', 'rb') as f:
    content = f.read()
# Look for lines with team names
lines = content.split(b'\n')
for i, line in enumerate(lines):
    if b'Mexico' in line or b'Belgica' in line or b'Canada' in line or b'Sudafrica' in line:
        print(f'Line {i+1}: {line[:120]}')
