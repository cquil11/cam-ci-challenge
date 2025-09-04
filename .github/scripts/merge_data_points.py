import json
import os
import glob
from datetime import datetime

json_files = glob.glob('benchmark_history/*.json')
json_files.sort()

merged_data = []

for file_path in json_files:
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            merged_data.append(data)
    except Exception as e:
        print(f'Error reading {file_path}: {e}')

with open('data.json', 'w') as f:
    json.dump(merged_data, f, indent=2)

print(f'Merged {len(merged_data)} data points into data.json')