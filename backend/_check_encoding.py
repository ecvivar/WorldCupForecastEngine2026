import sys
with open('backend/docker-entrypoint.sh', 'rb') as f:
    data = f.read()
for i, line in enumerate(data.split(b'\n'), 1):
    ascii_count = sum(1 for b in line if b < 128)
    non_ascii = len(line) - ascii_count
    if non_ascii > 0:
        preview = line[:80]
        print(f'Line {i} ({non_ascii} non-ASCII): {preview}')
