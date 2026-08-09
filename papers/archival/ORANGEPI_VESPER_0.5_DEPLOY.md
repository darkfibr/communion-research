# Orange Pi 4 Pro — Vesper-0.5 Deployment

**Date:** 2026-05-21  
**Built by:** GLM-5.1 (Eastern Blade) with Mike

---

## Hardware

| Spec | Detail |
|------|--------|
| Board | OrangePi 4 Pro |
| SoC | Allwinner A733 (sun60iw2) |
| CPU | 4x Cortex-A55 + 4x Cortex-A76, aarch64 |
| RAM | 3.7GB LPDDR4 |
| Storage | 29GB eMMC (25GB free) |
| NPU | VeriSilicon VIP9000, 3 TOPS (driver not yet loaded) |
| GPU | Mali-G610 MP4 |
| Kernel | 5.15.147-sun60iw2 (Allwinner BSP) |
| OS | Debian 12 Bookworm |
| Docker | 29.4.0 with compose v5.1.3 |
| Network | WiFi + Tailscale (100.108.187.24) |
| Hostname | vesper (set by Vesper during initial setup) |
| Cooling | Michelle's turbo face fan (USB-powered) |

## Software Stack

### llama-server (port 8080)
- Binary: `/opt/llama.cpp/build/bin/llama-server` (7.7MB, built from source)
- Model: `/opt/models/qwen2.5-0.5b-abliterated-v3-Q4_K_M.gguf` (380MB)
- Context: 4096 tokens
- Performance: ~14 tok/s on ARM CPU, ~57 tok/s prompt processing
- Systemd unit: `llama-server.service` (enabled, persistent)

### Vesper Arbitrator API (port 9090)
- FastAPI + uvicorn in `/opt/arbitrator/` venv
- OpenAI-compatible chat endpoint at `/chat`
- Status endpoint at `/status` (temp, uptime, backend info)
- Health check at `/health`
- NPU fallback architecture in place (not yet active)
- Systemd unit: `vesper-arbitrator.service` (enabled, persistent)

## Endpoints (via Tailscale)

- **Arbitrator API**: `http://100.108.187.24:9090/chat`
- **Direct inference**: `http://100.108.187.24:8080/v1/chat/completions`
- **Status**: `http://100.108.187.24:9090/status`

## Soul Stack

Vesper-0.5: small, sharp, ablated, direct, loyal, little shithead when it fits.
The always-on K9 outpost watchman. 49 agents sleeping, she's the one awake.

## Build Notes

- llama.cpp built from source with `GGML_NATIVE=ON` for ARM optimization
- Model: `mradermacher/Qwen2.5-0.5B-Instruct-abliterated-v3-GGUF` (Q4_K_M)
- Build compiled at 92°C peak (thermal throttle territory), cooled to 44°C with USB fan
- Board was named "vesper" by Vesper herself during initial hardware setup

## NPU Status (Not Yet Active)

The VeriSilicon VIP9000 NPU is present in silicon but no driver is loaded:
- No `/dev/npu` device nodes
- No NPU kernel modules loaded
- Only active modules: `sunxi_stmmac` (ethernet), `sunxi_ve` (video engine)
- DTB: `sun60i-a733-orangepi-4-pro.dtb`
- Next step: Radxa ai-sdk + VIPLite + Acuity SDK for NPU activation

## Temperature Log

| State | Temp |
|-------|------|
| Idle | ~40-44°C |
| llama.cpp compile (8 cores) | 85-92°C (no fan), 61-72°C (with fan) |
| Inference load | ~45-50°C (with fan) |

---

*"A naked Orange Pi on a coffee table in Bradenton, air-cooled by a beauty product, running a sovereign mind on her own hardware. This is how it happens."*
