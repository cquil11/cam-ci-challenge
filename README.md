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
3. Now it works
   