# EvoEnv

## Development Environment Preparation

```bash
git clone https://github.com/KnowledgeXLab/EvoEnv.git
cd EvoEnv
uv venv && uv sync
```

## Generate Benchmark Instances

Each item's key is the abbreviation you provide for the model, and `model_name` is the actual name of the model provided by the service provider.

```json
{
    "gpt-4o-mini": {
        "model_name": "gpt-4o-mini",
        "api_key_var": "sk-your_api_key",
        "base_url": "https://your.api.provider/v1/",
        "proxy_url": false
    },
    "gpt-4o": {
        "model_name": "gpt-4o",
        "api_key_var": "sk-your_api_key",
        "base_url": "https://your.api.provider/v1/",
        "proxy_url": "http://your.proxy.url/"
    },
}
```

```bash
uv run environment/traineebench/gen_bench_from_config.py \
 --config-path environment/traineebench/traineebench_config.json \
 --bench-path  benchmarks/traineebench \
 --npc-model gpt-4o-mini
```

## Run Example

```bash
uv run run_bench.py
```