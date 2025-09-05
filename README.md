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
- I completely LLMd the GH pages stuff

## General Architecture / Workflow

