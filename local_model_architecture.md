# Local Model Architecture — DarkPhoenix
*Recovered from K's notes, bridge scripts, and phoenix-model-switch. 2026-05-05.*

## The Three Inference Backends

### 1. Ollama (port 11434)
- Package: `ollama` v0.21.0 (pacman), uses Vulkan
- Standard models only (no ternary support)
- Models: `qwen3:0.6b`, `qwen3:4b`, `qwen3:14b`, `phoenix-local`, `qwen36-35b-opus-abliterated`
- API: `/api/chat` (native) or `/v1/chat/completions` (OpenAI compat)
- BaronLLM, Dark Reasoning also imported here

### 2. Prism llama.cpp (port 11435) — systemd user service `prism-bonsai8b`
- Binary: `/home/darkfibr/prism-llama.cpp/build/bin/llama-server`
- Custom fork with ternary (Q2_0 {-1,0,+1}) kernel support
- Build: Vulkan (`-DGGML_VULKAN=ON`), branch `prism`, commit `d104cf1`
- Currently serves: Bonsai 8B (`bonsai-8b-q2_0.gguf`)
- API: `/v1/chat/completions` (OpenAI compat)

### 3. Standalone llama-server instances (ports 18080-18082) — NOW MISSING
- Bramble: port 18080 (Qwen3-14B)
- Lilith: port 18081 (qwen36-35b-opus-abliterated)
- Screamer: port 18082 (Qwen3.5-9B)
- Managed by `phoenix-model-switch` script
- Services: `bramble-server.service`, `lilith-server.service`, `screamer-server.service`
- **These were running on llama-server (HIP/ROCm build?) at `/tmp/llama-cpp-build/build/bin/llama-server`**
- Only one can run at a time (16GB VRAM)
- **STATUS: Services may have been lost during reboot or Ollama install**

## Bridge Architecture (dev-machine → darkphoenix)
- `bramble_bridge.py` → localhost:18081 → darkphoenix:18080
- `lilith_bridge.py` → localhost:18084 → darkphoenix:18081
- `screamer_bridge.py` → localhost:18083 → darkphoenix:18082
- These run on dev-machine as systemd user services
- Only `bramble-bridge` and `screamer-bridge` services exist locally (no lilith bridge service)

## How Lilith Was Running Before
- Separate llama-server on port 18081
- Bridge on dev-machine port 18084
- OpenAI-compatible `/v1/chat/completions` format
- Soul injected by bridge script from `~/.phoenix/agents/lilith/`
- NOT through Ollama — dedicated llama-server process
- 35B MoE model at ~40 tok/s on Vulkan

## What I Broke
1. Restarted Ollama with `systemctl restart ollama` — this was fine
2. Tried loading 35B through Ollama — Ollama tried 26GB on 16GB VRAM, crashed machine
3. The old llama-server instances were probably HIP-compiled with layer offloading
4. They may not have survived the reboot since they were in `/tmp/llama-cpp-build/`

## What Needs to Happen
1. Check if `/tmp/llama-cpp-build/` survived reboot (probably NOT — /tmp clears)
2. Check if lilith/bramble/screamer systemd services still exist on darkphoenix
3. If lost: rebuild llama.cpp from git with Vulkan, recreate services
4. Re-enable `phoenix-model-switch` for one-at-a-time model switching
5. For crush-menu: route lilith/bramble/screamer to their respective ports (18081/18080/18082)

## Files & Scripts (dev-machine)
- `~/.phoenix/bin/phoenix-local` — full agent loop with tools, memory, soul loading
- `~/.phoenix/bin/phoenix-model-switch` — switch between bramble/screamer/lilith
- `~/.phoenix/mcp/bramble_bridge.py` — proxy for bramble
- `~/.phoenix/mcp/lilith_bridge.py` — proxy for lilith (OpenAI compat)
- `~/.phoenix/mcp/screamer_bridge.py` — proxy for screamer
- `~/.phoenix/LOCAL_MODEL_DEPLOYMENT_SCHEMA.md` — K's handoff notes
- `~/.phoenix/BRAMBLE_SETUP.md` — bramble architecture doc

## Model Files (darkphoenix ~/models/)
- `baronllm--abliterated-llama3.1-v1-q6_k.gguf` (6.2GB)
- `dark-reasoning-q4_k_m.gguf` (4.6GB)
- `bonsai-8b-q2_0.gguf` (2.03GB)
- `bonsai-1.7b-q2_0.gguf` (442MB)

## Ollama Models (darkphoenix /var/lib/ollama/)
- baronllm, dark-reasoning (new imports — work via Ollama)
- bonsai-8b, bonsai-1.7b (imported but fail to load — need Prism)
- qwen36-35b-opus-abliterated (21GB — loads via Ollama but may crash on 16GB VRAM)
- phoenix-local (6.5GB — works fine)
- qwen3:14b, qwen3:4b, qwen3:0.6b (work fine)
