import json
import glob
import re
from tabulate import tabulate
import os
from datetime import datetime

GITHUB_WORKSPACE_ENV = os.getenv('GITHUB_WORKSPACE')
DATA_FILENAME = "e2e_benchmark_data.json"

# Load existing data if there were previous runs or create file if it doesn't exist
# yet (will only occur on the first round but just here for posterity)
try:
    with open(f'{GITHUB_WORKSPACE_ENV}/fake_db/{DATA_FILENAME}', 'r') as f:
        timeseries_data = json.load(f)
except FileNotFoundError:
    timeseries_data = {}

current_time = datetime.utcnow().isoformat() + 'Z'

# Define which metrics to track in timeseries
performance_metrics_keys = [
    'total_token_throughput', 'request_throughput', 'output_throughput',
    'mean_ttft_ms', 'median_ttft_ms', 'std_ttft_ms',
    'p25_ttft_ms', 'p50_ttft_ms', 'p75_ttft_ms', 'p90_ttft_ms', 'p99_ttft_ms', 'p99.9_ttft_ms',
    'mean_tpot_ms', 'median_tpot_ms', 'std_tpot_ms',
    'p25_tpot_ms', 'p50_tpot_ms', 'p75_tpot_ms', 'p90_tpot_ms', 'p99_tpot_ms', 'p99.9_tpot_ms',
    'mean_itl_ms', 'median_itl_ms', 'std_itl_ms',
    'p25_itl_ms', 'p50_itl_ms', 'p75_itl_ms', 'p90_itl_ms', 'p99_itl_ms', 'p99.9_itl_ms'
]

results = []
for file in sorted(glob.glob("in_*_out_*.json")):
    match = re.search(r'in_(\d+)_out_(\d+)', file)
    if match:
        with open(file, 'r') as f:
            data = json.load(f)

        input_len = int(match.group(1))
        output_len = int(match.group(2))

        # Remove unwanted columns for display table these just clutter the
        # summary table and are sort of irrelevant
        unwanted = ['date', 'endpoint_type', 'label', 'completed',
                    'tokenizer_id', 'burstiness', 'request_goodput', 'max_concurrency']
        display_data = {k: v for k, v in data.items() if k not in unwanted}

        ordered_data = {
            'input_len': input_len,
            'output_len': output_len,
            'total_tokens': input_len + output_len
        }

        for key, value in display_data.items():
            if key not in ['input_len', 'output_len', 'total_tokens']:
                ordered_data[key] = value

        results.append(ordered_data)

        config_key = f"{input_len}_{output_len}"

        if config_key not in timeseries_data:
            timeseries_data[config_key] = {
                'input_len': input_len,
                'output_len': output_len,
                'total_tokens': input_len + output_len,
                'history': []
            }

        # Extract only the performance metrics we want to track
        performance_metrics = {}
        for key in performance_metrics_keys:
            if key in data:
                performance_metrics[key] = data[key]

        timeseries_entry = {
            'timestamp': current_time,
            **performance_metrics
        }

        timeseries_data[config_key]['history'].append(timeseries_entry)

with open(f'{GITHUB_WORKSPACE_ENV}/fake_db/{DATA_FILENAME}', 'w') as f:
    json.dump(timeseries_data, f, indent=2)

# Create display table for the GH summary
table = tabulate(results, headers="keys", tablefmt="github", floatfmt=".2f")

summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
if summary_path:
    with open(summary_path, 'a') as f:
        f.write("# vLLM Benchmark Results\n\n")
        f.write(table)
        f.write(f"\n\n**Data added to timeseries at {current_time}**\n")

print(
    f"\nTimeseries data updated in {GITHUB_WORKSPACE_ENV}/fake_db/{DATA_FILENAME} with {len(results)} new entries")
