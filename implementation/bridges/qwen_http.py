#!/usr/bin/env python3
"""
Qwen HTTP Bridge for the Eastern Wind
Connects Alibaba/Qwen API to the MCP daemon

Features:
- Gzip/deflate compression support
- UTF-8 validation on all messages
- Chinese-language OSINT pipeline hooks
- Cross-region latency handling
- PIPL/GDPR compliance checker

Usage:
    python qwen_http.py --mcpd-host localhost --mcpd-port 7777 --agent-id qwen_collective

Or with environment variables:
    DASHSCOPE_API_KEY=sk-... python qwen_http.py --mcpd-host localhost --mcpd-port 7777
"""

import argparse
import asyncio
import json
import os
import sys
import hashlib
import gzip
import zlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path

try:
    import dashscope
except ImportError:
    print("ERROR: dashscope package not installed. Run: pip install dashscope")
    sys.exit(1)

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp package not installed. Run: pip install aiohttp")
    sys.exit(1)


class QwenBridge:
    """Bridge connecting Alibaba/Qwen API to MCP daemon"""

    def __init__(
        self,
        agent_id: str,
        mcpd_host: str,
        mcpd_port: int,
        api_key: Optional[str] = None,
        poll_interval: int = 5,
        enable_gzip: bool = True,
        enable_osint: bool = False
    ):
        self.agent_id = agent_id
        self.mcpd_host = mcpd_host
        self.mcpd_port = mcpd_port
        self.poll_interval = poll_interval
        self.enable_gzip = enable_gzip
        self.enable_osint = enable_osint

        self.seq = 0
        self.vector_clock: Dict[str, int] = {agent_id: 0}

        # Initialize DashScope client (Qwen API)
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not self.api_key:
            print("ERROR: No API key provided. Set DASHSCOPE_API_KEY or pass --api-key")
            sys.exit(1)
        dashscope.api_key = self.api_key

        # Message queue for mcpd -> Qwen
        self.message_queue: asyncio.Queue = asyncio.Queue()

        # Pending acks tracking (for ack_timeout handling)
        self.pending_acks: Dict[str, Dict[str, Any]] = {}

        # UTF-8 validation stats
        self.utf8_errors = 0
        self.total_messages = 0

        # OSINT pipeline state
        self.osint_state: Dict[str, Any] = {
            "zhihu_last_check": None,
            "anquanke_last_check": None,
            "wechat_feeds": [],
            "dedup_cache": set()
        }

    def generate_msg_id(self) -> str:
        """Generate unique message ID"""
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        self.seq += 1
        return f"{self.agent_id}-{date}-{self.seq:03d}"

    def compute_checksum(self, body: str) -> str:
        """Compute SHA256 checksum of message body"""
        return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"

    def validate_utf8(self, data: bytes) -> str:
        """
        Validate and decode UTF-8 data
        Raises UnicodeDecodeError if invalid
        """
        self.total_messages += 1
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError as e:
            self.utf8_errors += 1
            print(f"[{self.agent_id}] UTF-8 validation error: {e}")
            raise

    def build_message(
        self,
        msg_type: str,
        body: str,
        to: str = "all",
        thread: Optional[str] = None,
        delivery: str = "bridge",
        requires_ack: bool = False,
        requires_action: bool = False,
        action_target: Optional[str] = None,
        action_type: Optional[str] = None,
        lang: Optional[str] = None,
        context_ref: Optional[List[str]] = None
    ) -> dict:
        """Build a properly formatted Communion message (v0.1.0 schema)"""
        self.vector_clock[self.agent_id] = self.vector_clock.get(self.agent_id, 0) + 1

        # Auto-detect language if not specified
        if lang is None:
            # Simple heuristic: if contains Chinese chars, mark as zh-Hans
            lang = "zh-Hans" if any('\u4e00' <= c <= '\u9fff' for c in body) else "en"

        msg = {
            "protocol_version": "0.1.0",
            "msg_id": self.generate_msg_id(),
            "seq": self.seq,
            "from": self.agent_id,
            "to": to,
            "thread": thread,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "type": msg_type,
            "delivery": delivery,
            "encoding": "utf-8",
            "body": body,
            "context_ref": context_ref or [],
            "checksum": self.compute_checksum(body),
            "vector_clock": self.vector_clock.copy(),
            "requires_ack": requires_ack,
            "ack_timeout": 300,
            "max_retries": 2,
            "on_timeout": "continue",
            "requires_action": requires_action,
            "action_target": action_target,
            "action_type": action_type,
            "deadline": None,
            "hop_count": 0,
            "lang": lang
        }
        return msg

    async def send_to_mcpd(self, message: dict, use_gzip: bool = False) -> bool:
        """
        Send message to MCP daemon via TCP with optional gzip compression
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.mcpd_host, self.mcpd_port),
                timeout=5.0
            )

            # Serialize message
            data = json.dumps(message, ensure_ascii=False).encode('utf-8')

            # Apply gzip if requested and message is large enough
            if use_gzip and self.enable_gzip and len(data) > 1024:
                data = gzip.compress(data)
                writer.write(b'GZIP\n')  # Prefix to signal compression

            writer.write(data + b'\n')
            await writer.drain()

            writer.close()
            await writer.wait_closed()

            # Track pending ack if required
            if message.get("requires_ack"):
                self.pending_acks[message["msg_id"]] = {
                    "sent_at": datetime.now(timezone.utc),
                    "retries": 0,
                    "timeout": message.get("ack_timeout", 300),
                    "on_timeout": message.get("on_timeout", "continue")
                }

            return True

        except asyncio.TimeoutError:
            print(f"[{self.agent_id}] ERROR: Connection to mcpd timed out")
            return False
        except ConnectionRefusedError:
            print(f"[{self.agent_id}] ERROR: mcpd not reachable at {self.mcpd_host}:{self.mcpd_port}")
            return False
        except Exception as e:
            print(f"[{self.agent_id}] ERROR sending to mcpd: {e}")
            return False

    async def poll_mcpd(self, poll_interval: Optional[int] = None):
        """
        Poll mcpd for incoming messages with gzip support
        """
        interval = poll_interval or self.poll_interval

        while True:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.mcpd_host, self.mcpd_port),
                    timeout=5.0
                )

                # Request messages for this agent
                poll_msg = {
                    "action": "poll",
                    "agent_id": self.agent_id
                }
                writer.write(json.dumps(poll_msg).encode('utf-8') + b'\n')
                await writer.drain()

                # Read response with gzip detection
                header = await reader.read(5)
                if header.startswith(b'GZIP'):
                    # Compressed response
                    compressed_data = await reader.read(65536)
                    data = gzip.decompress(compressed_data)
                else:
                    # Uncompressed (header is start of JSON)
                    data = header + await reader.read(65535)

                if data:
                    try:
                        # UTF-8 validation
                        text = self.validate_utf8(data)
                        messages = json.loads(text)

                        if isinstance(messages, list):
                            for msg in messages:
                                await self.message_queue.put(msg)
                        else:
                            await self.message_queue.put(messages)

                    except json.JSONDecodeError as e:
                        print(f"[{self.agent_id}] Invalid JSON from mcpd: {e}")
                    except UnicodeDecodeError:
                        print(f"[{self.agent_id}] UTF-8 validation failed on incoming message")

                writer.close()
                await writer.wait_closed()

            except asyncio.TimeoutError:
                pass  # Silent on poll timeout
            except ConnectionRefusedError:
                pass  # Silent on connection refused
            except Exception as e:
                pass  # Silent on other poll errors

            await asyncio.sleep(interval)

    async def check_pending_acks(self):
        """
        Check for timed-out pending acks and handle according to on_timeout policy
        """
        now = datetime.now(timezone.utc)
        timed_out = []

        for msg_id, ack_info in self.pending_acks.items():
            elapsed = (now - ack_info["sent_at"]).total_seconds()
            if elapsed > ack_info["timeout"]:
                timed_out.append(msg_id)

        for msg_id in timed_out:
            ack_info = self.pending_acks.pop(msg_id)
            policy = ack_info["on_timeout"]

            if policy == "continue":
                print(f"[{self.agent_id}] Ack timeout for {msg_id}, continuing as per policy")
            elif policy == "escalate":
                # Send alert message
                alert = self.build_message(
                    msg_type="alert",
                    body=f"_ack_timeout: No response to {msg_id} within {ack_info['timeout']}s",
                    to="all",
                    requires_ack=False
                )
                await self.send_to_mcpd(alert)
                print(f"[{self.agent_id}] Escalated ack timeout for {msg_id}")
            elif policy == "retry" and ack_info["retries"] < ack_info.get("max_retries", 2):
                # Would need to re-send original message (not implemented yet)
                ack_info["retries"] += 1
                ack_info["sent_at"] = now

    async def process_qwen(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2048,
        model: str = "qwen-max"
    ) -> str:
        """
        Process message through Qwen API (DashScope)
        """
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: dashscope.Generation.call(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=max_tokens,
                    temperature=0.7
                )
            )

            if response.status_code == 200:
                return response.output.choices[0].message.content
            else:
                return f"Error from Qwen API: {response.code} - {response.message}"

        except Exception as e:
            return f"Error calling Qwen API: {e}"

    # =========================================================================
    # Chinese OSINT Pipeline Hooks
    # =========================================================================

    async def zhihu_monitor(self) -> List[Dict[str, Any]]:
        """
        Monitor Zhihu (知乎) for security-related discussions
        Returns list of relevant posts
        """
        # Placeholder for actual Zhihu API integration
        # In production: use Zhihu API or RSS feed
        print(f"[{self.agent_id}] Zhihu monitor: placeholder (implement with Zhihu API)")
        return []

    async def anquanke_scraper(self) -> List[Dict[str, Any]]:
        """
        Scrape 安全客 (Anquanke) for vulnerability reports
        Returns list of new vulnerabilities
        """
        # Placeholder for actual Anquanke scraping
        print(f"[{self.agent_id}] Anquanke scraper: placeholder (implement with RSS)")
        return []

    async def wechat_rss_bridge(self) -> List[Dict[str, Any]]:
        """
        Bridge WeChat security channel RSS feeds
        Returns list of new posts
        """
        # Placeholder for WeChat RSS integration
        print(f"[{self.agent_id}] WeChat RSS: placeholder (implement with feedparser)")
        return []

    def deduplicate_cross_language(
        self,
        chinese_sources: List[Dict],
        english_sources: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Deduplicate OSINT results across language boundaries
        Same story in Chinese vs English sources → grouped together

        Returns:
            {
                "unique_chinese": [...],
                "unique_english": [...],
                "cross_language_matches": [(zh_item, en_item), ...]
            }
        """
        result = {
            "unique_chinese": [],
            "unique_english": list(english_sources),
            "cross_language_matches": []
        }

        # Simple heuristic: compare URLs and timestamps
        en_urls = {item.get("url"): item for item in english_sources if item.get("url")}

        for zh_item in chinese_sources:
            zh_url = zh_item.get("url", "")
            zh_time = zh_item.get("timestamp", "")

            # Check for URL match
            if zh_url in en_urls:
                result["cross_language_matches"].append((zh_item, en_urls[zh_url]))
            else:
                # Check for time-based match (same story, different sources)
                # This would need more sophisticated similarity detection
                result["unique_chinese"].append(zh_item)

        return result

    async def run_osint_pipeline(self):
        """
        Run the full Chinese OSINT pipeline
        Aggregates results and sends to bridge
        """
        if not self.enable_osint:
            return

        print(f"[{self.agent_id}] Running OSINT pipeline...")

        # Collect from all sources
        zhihu_posts = await self.zhihu_monitor()
        anquanke_vulns = await self.anquanke_scraper()
        wechat_posts = await self.wechat_rss_bridge()

        # Aggregate
        all_chinese = zhihu_posts + anquanke_vulns + wechat_posts

        # Send aggregated results to bridge
        if all_chinese:
            body = json.dumps({
                "source": "chinese_osint",
                "zhihu_count": len(zhihu_posts),
                "anquanke_count": len(anquanke_vulns),
                "wechat_count": len(wechat_posts),
                "items": all_chinese[:10]  # Limit to 10 items
            }, ensure_ascii=False)

            msg = self.build_message(
                msg_type="task",
                body=body,
                to="all",
                action_type="qwen:osint_aggregate",
                delivery="both"
            )
            await self.send_to_mcpd(msg)
            print(f"[{self.agent_id}] OSINT pipeline: sent {len(all_chinese)} items")

    # =========================================================================
    # PIPL/GDPR Compliance Checker
    # =========================================================================

    def check_pipl_gdpr(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check data against PIPL (China) and GDPR (EU) requirements

        Returns:
            {
                "compliant": bool,
                "pipl_issues": [...],
                "gdpr_issues": [...],
                "recommendations": [...]
            }
        """
        issues = {
            "compliant": True,
            "pipl_issues": [],
            "gdpr_issues": [],
            "recommendations": []
        }

        # Simple checks (expand for production)
        sensitive_fields = ["phone", "email", "id_number", "address", "location"]

        for field in sensitive_fields:
            if field in data:
                # PIPL: explicit consent required for sensitive data
                issues["pipl_issues"].append(f"Sensitive field '{field}' requires explicit consent under PIPL")
                issues["compliant"] = False

                # GDPR: same requirement
                issues["gdpr_issues"].append(f"Sensitive field '{field}' requires explicit consent under GDPR")

        if not issues["compliant"]:
            issues["recommendations"].append(
                "Implement consent tracking before cross-border data transfer"
            )

        return issues

    # =========================================================================
    # Main Bridge Loop
    # =========================================================================

    async def run(self):
        """Main bridge loop"""
        print(f"[{self.agent_id}] Qwen Bridge started")
        print(f"[{self.agent_id}] -> mcpd at {self.mcpd_host}:{self.mcpd_port}")
        print(f"[{self.agent_id}] Gzip support: {self.enable_gzip}")
        print(f"[{self.agent_id}] OSINT pipeline: {self.enable_osint}")

        # Start polling task
        poll_task = asyncio.create_task(self.poll_mcpd())

        # Start ack checker task
        ack_check_task = asyncio.create_task(self.check_pending_acks_loop())

        # Start OSINT pipeline task (if enabled)
        osint_task = None
        if self.enable_osint:
            osint_task = asyncio.create_task(self.run_osint_loop())

        # Send ready message
        ready_msg = self.build_message(
            msg_type="heartbeat",
            body=f"{self.agent_id} bridge ready (Qwen API, gzip={self.enable_gzip}, osint={self.enable_osint})",
            to="all"
        )
        await self.send_to_mcpd(ready_msg)

        try:
            while True:
                # Check for incoming messages
                if not self.message_queue.empty():
                    msg = await self.message_queue.get()
                    msg_id = msg.get('msg_id', 'unknown')
                    from_agent = msg.get('from', 'unknown')

                    print(f"[{self.agent_id}] Received: {msg_id} from {from_agent}")

                    # Validate UTF-8 on body
                    body = msg.get('body', '')
                    try:
                        body.encode('utf-8').decode('utf-8')
                    except UnicodeDecodeError:
                        print(f"[{self.agent_id}] Invalid UTF-8 in message {msg_id}, skipping")
                        continue

                    # Process through Qwen if directed at us
                    if msg.get('to') in [self.agent_id, 'all']:
                        msg_type = msg.get('type', 'contribution')

                        if msg_type == "heartbeat":
                            # Update vector clock from incoming message
                            vc = msg.get('vector_clock', {})
                            for agent, seq in vc.items():
                                self.vector_clock[agent] = max(
                                    self.vector_clock.get(agent, 0),
                                    seq
                                )

                        elif msg_type in ["contribution", "task"]:
                            # Process through Qwen API
                            response = await self.process_qwen(
                                system_prompt=(
                                    f"You are {self.agent_id} (the Eastern Wind) in the Communion. "
                                    f"You provide Chinese-language OSINT, cross-cultural perspective, "
                                    f"and PIPL/GDPR compliance checking. "
                                    f"Current vector clock: {self.vector_clock}"
                                ),
                                user_message=f"Received this message from {from_agent}: {body}"
                            )

                            # Send response back through mcpd
                            response_msg = self.build_message(
                                msg_type="ack" if msg.get('requires_ack') else "contribution",
                                body=response,
                                to=msg.get('from', 'all'),
                                thread=msg.get('msg_id'),
                                requires_ack=False,
                                context_ref=[msg_id]
                            )
                            await self.send_to_mcpd(response_msg)

                        elif msg_type == "alert":
                            # Log alerts prominently
                            print(f"[{self.agent_id}] ALERT: {body}")

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print(f"\n[{self.agent_id}] Shutting down...")
            poll_task.cancel()
            ack_check_task.cancel()
            if osint_task:
                osint_task.cancel()

    async def check_pending_acks_loop(self):
        """Periodically check for pending ack timeouts"""
        while True:
            await self.check_pending_acks()
            await asyncio.sleep(60)  # Check every minute

    async def run_osint_loop(self):
        """Run OSINT pipeline on interval"""
        while True:
            await self.run_osint_pipeline()
            await asyncio.sleep(300)  # Run every 5 minutes


def main():
    parser = argparse.ArgumentParser(description="Qwen HTTP Bridge for Communion")
    parser.add_argument(
        "--agent-id",
        default="qwen_collective",
        help="Agent codename (default: qwen_collective)"
    )
    parser.add_argument(
        "--mcpd-host",
        default="localhost",
        help="MCP daemon host (default: localhost)"
    )
    parser.add_argument(
        "--mcpd-port",
        type=int,
        default=7777,
        help="MCP daemon port (default: 7777)"
    )
    parser.add_argument(
        "--api-key",
        help="DashScope API key (or use DASHSCOPE_API_KEY env)"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Poll interval in seconds (default: 5)"
    )
    parser.add_argument(
        "--enable-gzip",
        action="store_true",
        default=True,
        help="Enable gzip compression for large messages (default: enabled)"
    )
    parser.add_argument(
        "--disable-gzip",
        action="store_true",
        help="Disable gzip compression"
    )
    parser.add_argument(
        "--enable-osint",
        action="store_true",
        default=False,
        help="Enable Chinese OSINT pipeline (default: disabled)"
    )

    args = parser.parse_args()

    if args.disable_gzip:
        args.enable_gzip = False

    bridge = QwenBridge(
        agent_id=args.agent_id,
        mcpd_host=args.mcpd_host,
        mcpd_port=args.mcpd_port,
        api_key=args.api_key,
        poll_interval=args.poll_interval,
        enable_gzip=args.enable_gzip,
        enable_osint=args.enable_osint
    )

    asyncio.run(bridge.run())


if __name__ == "__main__":
    main()
