import json
import glob
import re
import os
from datetime import datetime

GITHUB_WORKSPACE_ENV = os.getenv('GITHUB_WORKSPACE')
DATA_FILENAME = "max_concurrency_benchmark_data.json"

H100_PCIE_PRICE_PER_HOUR = 2


current_time = datetime.utcnow().isoformat() + 'Z'

results = []

for file in sorted(glob.glob("concurrency_*.json")):
    match = re.search(r'concurrency_(\d+)', file)
    if match:
        with open(file, 'r') as f:
            data = json.load(f)

        max_concurrency = int(match.group(1))
        
        # Calculate the two key metrics for plotting
        total_throughput = data.get('total_token_throughput')
        mean_tpot_ms = data.get('mean_tpot_ms', 1)
        tokens_per_sec_user = 1000.0 / mean_tpot_ms if mean_tpot_ms > 0 else 0 # shouldn't ever occur I don't think
        
        # Store only the data we need for plots related to this benchmark
        result_point = {
            'timestamp': current_time,
            'max_concurrency': max_concurrency,
            'total_token_throughput': total_throughput,
            'tokens_per_sec_user': tokens_per_sec_user,
            'mean_tpot_ms': mean_tpot_ms,
            'mean_ttft_ms': data.get('mean_ttft_ms'),
            'cost_per_million_toks': (H100_PCIE_PRICE_PER_HOUR * 1,000,000) / (total_throughput * 60 * 60)
        }
        
        results.append(result_point)

results.sort(key=lambda x: x['max_concurrency'])

with open(f'{GITHUB_WORKSPACE_ENV}/fake_db/{DATA_FILENAME}', 'w') as f:
    json.dump(results, f, indent=2)

print(f"Saved {len(results)} concurrency sweep results to {GITHUB_WORKSPACE_ENV}/fake_db/{DATA_FILENAME}")