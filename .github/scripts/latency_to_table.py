import json
import argparse
import glob
import os
import re

from py_markdown_table.markdown_table import markdown_table

def main():
   parser = argparse.ArgumentParser()
   parser.add_argument('--base-filename', type=str, required=True, help="Base filename of latency data e.g., 'latency_bs<batch_size>'")
   parser.add_argument('--output-dir', type=str, required=True, help="Output directory")
   args = parser.parse_args()

   os.makedirs(args.output_dir, exist_ok=True)

   pattern = f"{args.base_filename}*.json"
   results = glob.glob(pattern)
   results.sort()

   print(f"Found {len(results)} latency benchmark results:")
   for file in results:
       print(f"  {file}")

   combined_data = []
   for fn in results:
       batch_size = re.search(r'(\d+)', fn)
       assert batch_size, f"batch size not found in filename '{fn}'"
       
       with open(fn, 'r') as f:
           res = json.load(f)
           data_pt = {
               'batch_size': int(batch_size.group(1)),
               'avg_latency': res.get('avg_latency'),
               'p50': res.get('percentiles', {}).get('50'),
               'p90': res.get('percentiles', {}).get('90'),
               'p99': res.get('percentiles', {}).get('99')
           }
           combined_data.append(data_pt)

   combined_data.sort(key=lambda x: x['batch_size'] or 0)
   markdown = markdown_table(combined_data).get_markdown()

   output_path = os.path.join(args.output_dir, 'table_markdown.md')
   with open(output_path, 'w') as f:
       f.write(markdown)
   
   print(f"\nSummary markdown written to {output_path}")

if __name__ == "__main__":
  main()