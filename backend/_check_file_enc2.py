with open('backend/docker-entrypoint.sh', 'rb') as f:
    content = f.read()
# Find lines with non-ASCII chars or specific patterns
lines = content.split(b'\n')
for i, line in enumerate(lines):
    if i >= 60 and i <= 105:  # around the OFFICIAL_GROUPS section
        print(f'{i+1}: {line[:120]}')
