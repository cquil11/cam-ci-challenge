## Initial Setup

1. Create runner on ubuntu@209.20.158.80 following the standard instructions on gh settings page
2. Manually test `vllm/vllm-openai:v0.10.1.1` by pulling and then 
    ```
    docker run --runtime nvidia --gpus all   -v ~/.cache/huggingface:/root/.cache/huggingface   --env "HUGGING_FACE_HUB_TOKEN=$HF_TOKEN"   --env "VLLM_LOGGING_LEVEL=DEBUG"   -p 8000:8000
    --ipc=host   5a0ce40a0a32   --model Qwen/Qwen3-0.6B
    ```
  - For some reason, the container was getting a `Platform not detected error`, I checked to make sure the nvidia container toolkit was installed (it was)
  - Apparently the fix is to create the file `/etc/docker/daemon.json` and add a default runtime (https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html#configuring-docker)
    ```
    {
    "runtimes": {
        "nvidia": {
            "path": "nvidia-container-runtime",
            "runtimeArgs": []
        }
    },
    "default-runtime": "nvidia"
    }
    ```
3. Now it works, and we can run the benchmarks
   
## Notes

- Originally I was using `vllm bench latency` which invokes https://github.com/vllm-project/vllm/blob/main/vllm/benchmarks/latency.py, the only annoying part about this is it has to spin up an entirely new engine for each batch size which almost doubles the time of the benchmark
  - Just made simple changes in `.github/scripts/custom_latency.py` that spins up one engine and then runs each batch size sequentially (this could of course be generalized for other parameters)
  - Allows to run the original script with `--bs-start`, `--bs-end`, and `--bs-step` which specify the start, end, and step batch sizes, respectively
- `data.json` is acting as our DB, probably not ideal to use GH for this, but for this challenge it serves its purpose
- I completely LLMd vibe coded the GH pages stuff

## General Architecture / Workflow

The workflow `vLLM E2E Benchmark` contains three sequential jobs:
  1. The `benchmark-latency` job conducts the original latency-only benchmark laid out in the CI Challenge Doc. This runs the script `.github/scripts/custom_latency.py` which is similar to the script invoked by `vllm bench latency`. As mentioned above, the original script invokes a fresh vLLM engine for each set of parameters to be tested -- this is not ideal. The `custom_latency.py` script makes some simple changes to create the engine *once* and then run all of the batch sizes against that engine (this reduces the time by approximately 40%).
     - After collecting the results for all batch sizes 1-8 (which are all saved to a JSON in the environment), we invoke the `.github/scripts/latency_to_table.py` script in order to convert the individual statistics for each batch size into a single "data point" for the run, uniquely identified by a UTC timestamp. This data point is then tabulated and printed to the GitHub Actions Summary page.
     - Then, the `.github/scripts/merge_data_points.py` script is invoked in order to merge the current data point with all of the existing data points in `fake_db/data.json` (which acts as a DB for the latency runs). 
        > [!NOTE] 
        I am just now realizing that it is probably not necessary to *re-merge* all of the individual data points each run. Instead you could simply get the current data point and then add it to the existing list of all data points. This would also allow to not have to store all individual data points in `benchmark_history`.
     - The merged data points will then be pushed back to the `ci-bench` branch which in turn invokes the GH page deployment action, and updates the data on the page accordingly.
2. The `benchmark-online` works in a similar fashion, except it runs a more robust online benchmark which measures overall throughput, total latency, TPOT, TTFT, and ITL. In order to do this, we use the built-in `vllm bench serve` command.
     - Unlike the script run in the previous job, the  `vllm bench serve` command doesn't spin up a vLLM engine itself -- instead it assumed there is already one running. Therefore, as the first step of this job we simply `vllm serve` the model in the background and loop until the server is up.
     - Then, we can actually run the benchmark. We are using a random dataset in order to control the input and output sequences. The following combinations of input/output sequence lengths were chosen to try and simulate real workflows:
        ```bash
        input_lens=(300 500 800 1000 2000)
        output_lens=(100 200 300 200 400)
        ```
     - We then loop through all pairs and run the benchmark, choosing the other parameters such as request rate and number of requests as follows:
        ```bash
        input_len=${input_lens[$i]}
        output_len=${output_lens[$i]}
        # Let's assume a single H100 is capable of approx. 5k tps throughput
        # under reasonable latency for Llama 3.1 8B Instruct
        # Therefore we can calculate request rate roughly by 5000 / (input_len + output_len)
        request_rate=$(python3 -c "print(round(5000 / ($input_len + $output_len), 2))")
        # Now assume we want each benchmark to run for roughly 3 minutes, so we calculate
        # the number of total requests to be approx.  60 * 3 * request_rate
        run_duration_mins=3
        number_requests=$(python3 -c "import math; print(round(3 * 60 * $request_rate))")
        ```
     - Finally, each result is saved to a JSON file and the `.github/scripts/e2e_benchmark_postprocess.py` scripts performs some post-processing on the collected data. This script is also responsible for merging the currently collected data with the "DB" data located in `fake_db/e2e_benchmark_data.json`. After merging, the data is pushed back to `origin` which triggers the GH pages deployment action which in turn makes the data visible on the website.
     - Note that this job must run sequentially with respect to the `benchmark-latency` job, since they both require the GPU.
  3. The `notify-on-failure` job only runs if either of the other two jobs failed. When it runs, it sends a simple Slack notification to the shared channel.