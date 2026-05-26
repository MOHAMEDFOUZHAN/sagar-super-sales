with open('d:/Sales/billing-software/app.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'twin' in line.lower():
        print(f"Line {i+1}: {line.strip()}")
