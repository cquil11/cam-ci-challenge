#!/usr/bin/env python3

# This is a simple modification of https://github.com/vllm-project/vllm/blob/main/vllm/benchmarks/latency.py

import argparse
import dataclasses
import json
import os
import time
from typing import Any, Optional

import numpy as np
from tqdm import tqdm

import vllm.envs as envs
from vllm.benchmarks.lib.utils import (convert_to_pytorch_benchmark_format,
                                       write_to_json)
from vllm.engine.arg_utils import EngineArgs
from vllm.inputs import PromptType
from vllm.sampling_params import BeamSearchParams
from vllm import LLM, SamplingParams


def save_to_pytorch_benchmark_format(args: argparse.Namespace,
                                     results: dict[str, Any],
                                     batch_size: int) -> None:
    pt_records = convert_to_pytorch_benchmark_format(
        args=args,
        metrics={"latency": results["latencies"]},
        extra_info={k: results[k]
                    for k in ["avg_latency", "percentiles"]})
    if pt_records:
        output_json = f"{args.output_json}{batch_size}.json"
        pt_file = f"{os.path.splitext(output_json)[0]}.pytorch.json"
        write_to_json(pt_file, pt_records)


def add_cli_args(parser: argparse.ArgumentParser):
    parser.add_argument("--input-len", type=int, default=32)
    parser.add_argument("--output-len", type=int, default=128)
    parser.add_argument("--bs-start", type=int, required=True)
    parser.add_argument("--bs-end", type=int, required=True) 
    parser.add_argument("--bs-step", type=int, default=1)
    parser.add_argument(
        "--n",
        type=int,
        default=1,
        help="Number of generated sequences per prompt.",
    )
    parser.add_argument("--use-beam-search", action="store_true")
    parser.add_argument(
        "--num-iters-warmup",
        type=int,
        default=10,
        help="Number of iterations to run for warmup.",
    )
    parser.add_argument("--num-iters",
                        type=int,
                        default=30,
                        help="Number of iterations to run.")
    parser.add_argument(
        "--profile",
        action="store_true",
        help="profile the generation process of a single batch",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        required=True,
        help="Base path for JSON output files",
    )
    parser.add_argument(
        "--disable-detokenize",
        action="store_true",
        help=("Do not detokenize responses (i.e. do not include "
              "detokenization time in the latency measurement)"),
    )

    parser = EngineArgs.add_cli_args(parser)
    parser.set_defaults(enable_prefix_caching=False)


def benchmark_batch_size(llm, args: argparse.Namespace, batch_size: int) -> dict[str, Any]:
    sampling_params = SamplingParams(
        n=args.n,
        temperature=1.0,
        top_p=1.0,
        ignore_eos=True,
        max_tokens=args.output_len,
        detokenize=not args.disable_detokenize,
    )
    
    dummy_prompt_token_ids = np.random.randint(10000,
                                               size=(batch_size, args.input_len))
    dummy_prompts: list[PromptType] = [{
        "prompt_token_ids": batch
    } for batch in dummy_prompt_token_ids.tolist()]

    def llm_generate():
        if not args.use_beam_search:
            llm.generate(dummy_prompts,
                         sampling_params=sampling_params,
                         use_tqdm=False)
        else:
            llm.beam_search(
                dummy_prompts,
                BeamSearchParams(
                    beam_width=args.n,
                    max_tokens=args.output_len,
                    ignore_eos=True,
                ),
            )

    def run_to_completion(profile_dir: Optional[str] = None):
        if profile_dir:
            llm.start_profile()
            llm_generate()
            llm.stop_profile()
        else:
            start_time = time.perf_counter()
            llm_generate()
            end_time = time.perf_counter()
            latency = end_time - start_time
            return latency

    for _ in tqdm(range(args.num_iters_warmup), desc="Warmup iterations"):
        run_to_completion(profile_dir=None)

    if args.profile:
        profile_dir = envs.VLLM_TORCH_PROFILER_DIR
        run_to_completion(profile_dir=profile_dir)
        return {}

    latencies = []
    for _ in tqdm(range(args.num_iters), desc="Profiling iterations"):
        latencies.append(run_to_completion(profile_dir=None))
    
    latencies = np.array(latencies)
    percentages = [10, 25, 50, 75, 90, 99]
    percentiles = np.percentile(latencies, percentages)
    
    print(f"Batch size: {batch_size}")
    print(f"Avg latency: {np.mean(latencies)} seconds")
    for percentage, percentile in zip(percentages, percentiles):
        print(f"{percentage}% percentile latency: {percentile} seconds")

    return {
        "avg_latency": np.mean(latencies),
        "latencies": latencies.tolist(),
        "percentiles": dict(zip(percentages, percentiles.tolist())),
    }


def main(args: argparse.Namespace):
    if args.profile and not envs.VLLM_TORCH_PROFILER_DIR:
        raise OSError(
            "The environment variable 'VLLM_TORCH_PROFILER_DIR' is not set. "
            "Please set it to a valid path to use torch profiler.")
    
    if args.bs_end < args.bs_start:
        raise ValueError("bs-end must be >= bs-start")
    if args.bs_step <= 0:
        raise ValueError("bs-step must be > 0")
    
    batch_sizes = list(range(args.bs_start, args.bs_end + 1, args.bs_step))
    
    engine_args = EngineArgs.from_cli_args(args)

    llm = LLM(**dataclasses.asdict(engine_args))
    assert llm.llm_engine.model_config.max_model_len >= (
        args.input_len + args.output_len), (
        "Please ensure that max_model_len is greater than"
        " the sum of input_len and output_len.")
    
    for i, batch_size in enumerate(batch_sizes):
        if i > 0:
            time.sleep(5)
            
        results = benchmark_batch_size(llm, args, batch_size)
        
        if results:
            output_json = f"{args.output_json}{batch_size}.json"
            with open(output_json, "w") as f:
                json.dump(results, f, indent=4)
            save_to_pytorch_benchmark_format(args, results, batch_size)


if __name__ == "__main__":
    from vllm.utils import FlexibleArgumentParser
    
    parser = FlexibleArgumentParser()
    add_cli_args(parser)
    args = parser.parse_args()
    main(args)