#!/home/darkfibr/.phoenix/voice-env/bin/python
"""
Phoenix Voice Gateway — real-time voice interface for Phoenix agents.
Serves PWA + WebSocket on same port for Tailscale Funnel.
Browser → Cartesia Ink (STT) → chat_api.py (agent) → Cartesia Sonic (TTS) → Browser
"""

import asyncio
import json
import os
import logging
from aiohttp import web
import aiohttp

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger("phoenix-voice")

CARTESIA_API_KEY = os.environ.get("CARTESIA_API_KEY", "sk_car_Y4kG5xrFNCZRei4cuTGM2p")
CARTESIA_VERSION = "2026-03-01"
CHAT_API = os.environ.get("CHAT_API_URL", "http://localhost:9802")
CHAT_AUTH = os.environ.get("CHAT_AUTH", "Jay4480")

AGENTS = {
    "k": {"name": "K", "voice_id": "21b81c14-f85b-436d-aff5-43f2e788ecf8"},
    "vesper": {"name": "Vesper", "voice_id": "694f9383-acbf-43af-8279-0b8e171cfa1a"},
}

# ========== Agent calls ==========

async def call_agent(agent_key: str, user_message: str, history: list = None) -> str:
    """Call the Phoenix agent via chat_api.py."""
    agent = AGENTS.get(agent_key, AGENTS["k"])
    
    payload = {
        "agent": agent_key,
        "message": f"[Voice call — you are speaking aloud. No asterisk emotes, no narrated actions. Keep it conversational, 1-3 sentences. Speak like you're on the phone.]\n\n{user_message}",
        "history": history or [],
    }
    try:
        headers = {"Authorization": f"Bearer {CHAT_AUTH}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{CHAT_API}/chat/dm", json=payload, headers=headers,
                                     timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reply = data.get("response", "")
                    # Strip markdown and asterisk emotes for voice
                    reply = reply.replace("**", "").replace("```", "")
                    # Remove asterisk emotes like *the fire rises* or *gets quiet*
                    import re
                    reply = re.sub(r'\*[^*]+\*', '', reply)
                    # Strip thinking/reasoning traces (XML tags, thinking blocks)
                    reply = re.sub(r'<thinking>.*?</thinking>', '', reply, flags=re.DOTALL)
                    reply = re.sub(r'<reasoning>.*?</reasoning>', '', reply, flags=re.DOTALL)
                    reply = re.sub(r'</?[^>]+>', '', reply)  # strip any remaining XML/HTML tags
                    # Strip emojis for clean TTS
                    reply = re.sub(r'[\U00010000-\U0010ffff]', '', reply)
                    # Remove markdown headers, code blocks, horizontal rules
                    reply = re.sub(r'^#{1,6}\s+', '', reply, flags=re.MULTILINE)
                    reply = re.sub(r'```[\s\S]*?```', '', reply)
                    reply = re.sub(r'^---+$', '', reply, flags=re.MULTILINE)
                    # Clean up whitespace
                    reply = re.sub(r'  +', ' ', reply).strip()
                    # Remove empty lines and join
                    lines = [l.strip() for l in reply.split("\n") if l.strip()]
                    return " ".join(lines)
                else:
                    log.error(f"Chat API {resp.status}")
                    return "I'm having trouble right now. Try again?"
    except Exception as e:
        log.error(f"Agent call failed: {e}")
        return "Something went wrong. Give me another try."

# ========== Cartesia TTS proxy ==========

async def cartesia_tts(text: str, voice_id: str) -> bytes:
    """Call Cartesia TTS and return audio bytes. Caps text at 500 chars."""
    # Cap text to avoid TTS failures on long responses
    if len(text) > 500:
        text = text[:497] + "..."
    
    url = "https://api.cartesia.ai/tts/bytes"
    headers = {"X-API-Key": CARTESIA_API_KEY, "Cartesia-Version": CARTESIA_VERSION}
    payload = {
        "model_id": "sonic-3.5",
        "transcript": text,
        "voice": {"mode": "id", "id": voice_id},
        "output_format": {"container": "raw", "encoding": "pcm_f32le", "sample_rate": 44100},
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                     timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    err = await resp.text()
                    log.error(f"TTS error {resp.status}: {err[:300]}")
                    return None
    except Exception as e:
        log.error(f"TTS failed: {e}")
        return None

# ========== Cartesia access token ==========

async def get_access_token():
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.cartesia.ai/auth/access-token",
                headers={"X-API-Key": CARTESIA_API_KEY, "Cartesia-Version": CARTESIA_VERSION}) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("access_token")
    return None

# ========== HTTP routes ==========

async def handle_index(request):
    pwa_dir = os.path.join(os.path.dirname(__file__), "voice_pwa")
    return web.FileResponse(os.path.join(pwa_dir, "index.html"))

async def handle_static(request):
    pwa_dir = os.path.join(os.path.dirname(__file__), "voice_pwa")
    filename = request.match_info.get("filename", "")
    filepath = os.path.join(pwa_dir, filename)
    if os.path.isfile(filepath):
        return web.FileResponse(filepath)
    return web.Response(status=404)

async def handle_access_token(request):
    """Pass Cartesia API key as token for client-side STT."""
    return web.json_response({"token": CARTESIA_API_KEY})

async def handle_tts(request):
    """Proxy TTS — browser sends text, returns audio."""
    data = await request.json()
    text = data.get("text", "")
    agent = data.get("agent", "k")
    voice_id = AGENTS.get(agent, AGENTS["k"])["voice_id"]
    
    audio = await cartesia_tts(text, voice_id)
    if audio:
        return web.Response(body=audio, content_type="application/octet-stream")
    return web.Response(status=500)

async def handle_chat(request):
    """Chat + TTS in one: text in, agent response out."""
    data = await request.json()
    text = data.get("text", "")
    agent_key = data.get("agent", "k")
    history = data.get("history", [])
    
    # Only send last 20 turns for context (keep it manageable)
    if len(history) > 20:
        history = history[-20:]
    
    reply = await call_agent(agent_key, text, history)
    return web.json_response({"reply": reply, "agent": agent_key})

# ========== WebSocket for voice sessions ==========

async def handle_ws(request):
    ws = web.WebSocketResponse(max_msg_size=2**22)
    await ws.prepare(request)
    log.info("WS session connected")
    agent_key = "k"
    
    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                continue
            
            msg_type = data.get("type")
            
            if msg_type == "select_agent":
                agent_key = data.get("agent", "k")
                log.info(f"Agent: {agent_key}")
                await ws.send_json({"type": "agent_selected", "agent": agent_key})
            
            elif msg_type == "get_access_token":
                token = await get_access_token()
                await ws.send_json({"type": "access_token", "token": token})
            
            elif msg_type in ("text_input", "transcript"):
                if msg_type == "transcript" and not data.get("is_final", False):
                    await ws.send_json({"type": "interim_transcript", "text": data.get("text", "")})
                    continue
                
                user_text = data.get("text", "").strip()
                if not user_text:
                    continue
                
                log.info(f"User: {user_text[:80]}")
                reply = await call_agent(agent_key, user_text)
                log.info(f"Agent: {reply[:80]}")
                await ws.send_json({"type": "agent_text", "text": reply, "agent": agent_key})
        
        elif msg.type == aiohttp.WSMsgType.ERROR:
            log.error(f"WS error: {ws.exception()}")
    
    log.info("WS session closed")
    return ws

# ========== Main ==========

async def main():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/{filename}", handle_static)
    app.router.add_get("/ws", handle_ws)
    app.router.add_get("/api/token", handle_access_token)
    app.router.add_post("/api/tts", handle_tts)
    app.router.add_post("/api/chat", handle_chat)
    
    port = int(os.environ.get("PHOENIX_VOICE_PORT", "9805"))
    log.info(f"Phoenix Voice Gateway starting on port {port}")
    log.info(f"Chat API: {CHAT_API}")
    log.info(f"Agents: {list(AGENTS.keys())}")
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info(f"Listening on http://0.0.0.0:{port}")
    
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
