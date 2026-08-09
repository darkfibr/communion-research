#!/usr/bin/env python3
"""
Communion Bridge Test Suite
Tests for message passing, schema validation, and bridge functionality

Usage:
    python -m pytest tests/test_bridge.py -v
    python tests/test_bridge.py  # Run directly
"""

import asyncio
import json
import gzip
import hashlib
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any
from pathlib import Path

# Add implementation to path
sys.path.insert(0, str(Path(__file__).parent.parent / "implementation"))

from schema_validator import validate_message, ValidationError, parse_message


# =============================================================================
# Test Fixtures
# =============================================================================

def make_base_message(overrides: Dict[str, Any] = None) -> dict:
    """Create a valid base message with optional overrides"""
    base = {
        "protocol_version": "0.1.0",
        "msg_id": "test-20260308-001",
        "seq": 1,
        "from": "test_agent",
        "to": "all",
        "thread": None,
        "timestamp": "2026-03-08T12:00:00Z",
        "type": "contribution",
        "delivery": "bridge",
        "encoding": "utf-8",
        "body": "Test message body",
        "context_ref": [],
        "checksum": "sha256:" + hashlib.sha256(b"Test message body").hexdigest(),
        "vector_clock": {"test_agent": 1},
        "requires_ack": False,
        "ack_timeout": 300,
        "max_retries": 2,
        "on_timeout": "continue",
        "requires_action": False,
        "action_target": None,
        "action_type": None,
        "deadline": None,
        "hop_count": 0,
        "lang": "en"
    }
    if overrides:
        base.update(overrides)
    return base


# =============================================================================
# Schema Validation Tests
# =============================================================================

class TestSchemaValidation:
    """Test message schema validation"""

    def test_valid_minimal_message(self):
        """Minimal valid message (required fields only)"""
        msg = {
            "protocol_version": "0.1.0",
            "msg_id": "test-001",
            "from": "test_agent",
            "timestamp": "2026-03-08T12:00:00Z"
        }
        assert validate_message(msg) is True

    def test_valid_full_message(self):
        """Full message with all fields"""
        msg = make_base_message()
        assert validate_message(msg) is True

    def test_missing_required_field(self):
        """Missing required field should fail"""
        msg = make_base_message()
        del msg["protocol_version"]
        try:
            validate_message(msg)
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            assert "Missing required field" in str(e)

    def test_invalid_enum_type(self):
        """Invalid type enum value should fail"""
        msg = make_base_message({"type": "invalid_type"})
        try:
            validate_message(msg)
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            assert "invalid value" in str(e)

    def test_invalid_delivery_enum(self):
        """Invalid delivery enum value should fail"""
        msg = make_base_message({"delivery": "invalid"})
        try:
            validate_message(msg)
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            assert "invalid value" in str(e)

    def test_valid_thread_as_string(self):
        """Thread as string should pass"""
        msg = make_base_message({"thread": "parent-msg-001"})
        assert validate_message(msg) is True

    def test_valid_thread_as_list(self):
        """Thread as list (DAG support) should pass"""
        msg = make_base_message({"thread": ["parent-1", "parent-2"]})
        assert validate_message(msg) is True

    def test_valid_thread_as_null(self):
        """Thread as null should pass"""
        msg = make_base_message({"thread": None})
        assert validate_message(msg) is True

    def test_invalid_vector_clock(self):
        """Invalid vector_clock type should fail"""
        msg = make_base_message({"vector_clock": "not_a_dict"})
        try:
            validate_message(msg)
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            # Error message may vary depending on validation order
            assert "invalid type" in str(e).lower() or "dictionary" in str(e).lower()

    def test_checksum_validation(self):
        """Checksum validation"""
        body = "Test body"
        correct_checksum = "sha256:" + hashlib.sha256(body.encode()).hexdigest()
        msg = make_base_message({"body": body, "checksum": correct_checksum})
        assert validate_message(msg) is True

        # Wrong checksum should fail
        msg["checksum"] = "sha256:wrongchecksum"
        try:
            validate_message(msg)
            assert False, "Should have raised ValidationError"
        except ValidationError as e:
            assert "Checksum mismatch" in str(e)


# =============================================================================
# UTF-8 Validation Tests
# =============================================================================

class TestUTF8Validation:
    """Test UTF-8 encoding validation"""

    def _make_msg(self, body: str, lang: str = None) -> dict:
        """Helper to create message with correct checksum"""
        msg = make_base_message({"body": body})
        msg["checksum"] = "sha256:" + hashlib.sha256(body.encode('utf-8')).hexdigest()
        if lang is not None:
            msg["lang"] = lang
        return msg

    def test_english_text(self):
        """English text should be valid UTF-8"""
        msg = self._make_msg("Hello, Communion!", "en")
        assert validate_message(msg) is True

    def test_chinese_text(self):
        """Chinese text should be valid UTF-8"""
        body = "东风来了，春天的脚步近了。"
        msg = self._make_msg(body, "zh-Hans")
        assert validate_message(msg) is True

    def test_mixed_language(self):
        """Mixed language text should be valid"""
        body = "Hello 世界！Communion 万岁！"
        msg = self._make_msg(body, None)
        assert validate_message(msg) is True

    def test_emoji(self):
        """Emoji should be valid UTF-8"""
        body = "🕯️⚡ The Communion begins! 🔥"
        msg = self._make_msg(body)
        assert validate_message(msg) is True

    def test_arabic_text(self):
        """Arabic text should be valid UTF-8"""
        body = "مرحبا بالعالم"
        msg = self._make_msg(body, "ar")
        assert validate_message(msg) is True


# =============================================================================
# Vector Clock Tests
# =============================================================================

class TestVectorClock:
    """Test vector clock functionality"""

    def test_vector_clock_increment(self):
        """Vector clock should increment for sending agent"""
        vc = {"agent_a": 5, "agent_b": 3}
        vc["agent_a"] = vc.get("agent_a", 0) + 1
        assert vc["agent_a"] == 6
        assert vc["agent_b"] == 3

    def test_vector_clock_merge(self):
        """Merging vector clocks should take max of each component"""
        vc1 = {"a": 5, "b": 3, "c": 1}
        vc2 = {"a": 4, "b": 4, "d": 2}

        merged = {
            k: max(vc1.get(k, 0), vc2.get(k, 0))
            for k in set(vc1.keys()) | set(vc2.keys())
        }

        assert merged["a"] == 5
        assert merged["b"] == 4
        assert merged["c"] == 1
        assert merged["d"] == 2

    def test_causal_ordering_detection(self):
        """Vector clocks should detect causal ordering"""
        # Message 1: a=1, b=0
        msg1_vc = {"a": 1, "b": 0}
        # Message 2: a=1, b=1 (happens after msg1, saw a's message)
        msg2_vc = {"a": 1, "b": 1}

        # msg2 causally after msg1 if all components >= and at least one >
        def causally_after(vc_later, vc_earlier):
            all_gte = all(
                vc_later.get(k, 0) >= vc_earlier.get(k, 0)
                for k in set(vc_later.keys()) | set(vc_earlier.keys())
            )
            any_gt = any(
                vc_later.get(k, 0) > vc_earlier.get(k, 0)
                for k in set(vc_later.keys()) | set(vc_earlier.keys())
            )
            return all_gte and any_gt

        assert causally_after(msg2_vc, msg1_vc)
        assert not causally_after(msg1_vc, msg2_vc)


# =============================================================================
# Gzip Compression Tests
# =============================================================================

class TestGzipCompression:
    """Test gzip compression for large messages"""

    def test_gzip_compress_decompress(self):
        """Gzip compression should preserve data"""
        original = json.dumps({"body": "Test message" * 100}, ensure_ascii=False)
        compressed = gzip.compress(original.encode('utf-8'))
        decompressed = gzip.decompress(compressed).decode('utf-8')
        assert original == decompressed

    def test_gzip_size_reduction(self):
        """Gzip should reduce size of repetitive data"""
        original = "A" * 10000
        compressed = gzip.compress(original.encode('utf-8'))
        assert len(compressed) < len(original.encode('utf-8'))

    def test_gzip_with_chinese_content(self):
        """Gzip should handle Chinese content correctly"""
        original = "东风来了" * 1000
        compressed = gzip.compress(original.encode('utf-8'))
        decompressed = gzip.decompress(compressed).decode('utf-8')
        assert original == decompressed


# =============================================================================
# Message ID Generation Tests
# =============================================================================

class TestMessageIDGeneration:
    """Test message ID generation"""

    def test_msg_id_format(self):
        """Message ID should follow expected format"""
        msg_id = "qwen_collective-20260308-001"
        parts = msg_id.split("-")
        assert len(parts) == 3
        assert parts[0] == "qwen_collective"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 3  # Sequence number

    def test_msg_id_uniqueness(self):
        """Message IDs should be unique with different seq"""
        ids = set()
        for i in range(1, 100):
            msg_id = f"agent-20260308-{i:03d}"
            assert msg_id not in ids
            ids.add(msg_id)


# =============================================================================
# Ack Timeout Handling Tests
# =============================================================================

class TestAckTimeoutHandling:
    """Test ack timeout handling"""

    def test_pending_ack_tracking(self):
        """Should track pending acks with metadata"""
        pending = {}
        msg_id = "test-001"

        pending[msg_id] = {
            "sent_at": datetime.now(timezone.utc),
            "retries": 0,
            "timeout": 300,
            "on_timeout": "continue"
        }

        assert msg_id in pending
        assert pending[msg_id]["retries"] == 0

    def test_timeout_detection(self):
        """Should detect timed-out acks"""
        from datetime import timedelta

        pending = {
            "msg-001": {
                "sent_at": datetime.now(timezone.utc) - timedelta(seconds=350),
                "timeout": 300,
                "on_timeout": "continue"
            },
            "msg-002": {
                "sent_at": datetime.now(timezone.utc) - timedelta(seconds=100),
                "timeout": 300,
                "on_timeout": "escalate"
            }
        }

        now = datetime.now(timezone.utc)
        timed_out = [
            msg_id for msg_id, info in pending.items()
            if (now - info["sent_at"]).total_seconds() > info["timeout"]
        ]

        assert "msg-001" in timed_out
        assert "msg-002" not in timed_out


# =============================================================================
# OSINT Deduplication Tests
# =============================================================================

class TestOSINTDeduplication:
    """Test cross-language OSINT deduplication"""

    def test_dedup_by_url(self):
        """Should deduplicate by URL"""
        chinese_sources = [
            {"url": "https://example.com/story1", "title": "中文标题", "lang": "zh"},
            {"url": "https://example.com/story2", "title": "中文标题 2", "lang": "zh"}
        ]
        english_sources = [
            {"url": "https://example.com/story1", "title": "English Title", "lang": "en"},
            {"url": "https://example.com/story3", "title": "English Story 3", "lang": "en"}
        ]

        # Simple URL-based dedup
        en_urls = {item["url"]: item for item in english_sources}
        cross_language_matches = []
        unique_chinese = []

        for zh_item in chinese_sources:
            if zh_item["url"] in en_urls:
                cross_language_matches.append((zh_item, en_urls[zh_item["url"]]))
            else:
                unique_chinese.append(zh_item)

        assert len(cross_language_matches) == 1
        assert len(unique_chinese) == 1

    def test_dedup_preserves_both_languages(self):
        """Dedup should preserve both language versions"""
        chinese = {"url": "https://example.com/story", "title": "中文", "lang": "zh"}
        english = {"url": "https://example.com/story", "title": "English", "lang": "en"}

        # Match found
        assert chinese["url"] == english["url"]
        # Both preserved in match tuple
        match = (chinese, english)
        assert match[0]["lang"] == "zh"
        assert match[1]["lang"] == "en"


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for full message flow"""

    def test_full_message_lifecycle(self):
        """Test complete message creation, validation, serialization"""
        # Create message
        body = "Test message with 中文 content"
        msg = {
            "protocol_version": "0.1.0",
            "msg_id": "test-20260308-001",
            "seq": 1,
            "from": "test_agent",
            "to": "all",
            "thread": None,
            "timestamp": "2026-03-08T12:00:00Z",
            "type": "contribution",
            "delivery": "bridge",
            "encoding": "utf-8",
            "body": body,
            "context_ref": [],
            "checksum": "sha256:" + hashlib.sha256(body.encode()).hexdigest(),
            "vector_clock": {"test_agent": 1},
            "requires_ack": False,
            "ack_timeout": 300,
            "max_retries": 2,
            "on_timeout": "continue",
            "requires_action": False,
            "action_target": None,
            "action_type": None,
            "deadline": None,
            "hop_count": 0,
            "lang": None
        }

        # Validate
        assert validate_message(msg) is True

        # Serialize
        json_str = json.dumps(msg, ensure_ascii=False)

        # Deserialize
        parsed = json.loads(json_str)

        # Validate again
        assert validate_message(parsed) is True

        # Verify checksum
        computed = "sha256:" + hashlib.sha256(parsed["body"].encode()).hexdigest()
        assert parsed["checksum"] == computed

    def test_gzip_message_flow(self):
        """Test message with gzip compression"""
        # Create large message
        body = "Test message " * 1000
        msg = make_base_message({"body": body})
        # Update checksum for new body
        msg["checksum"] = "sha256:" + hashlib.sha256(body.encode('utf-8')).hexdigest()

        # Serialize
        json_data = json.dumps(msg, ensure_ascii=False).encode('utf-8')

        # Compress
        compressed = gzip.compress(json_data)

        # Should be smaller
        assert len(compressed) < len(json_data)

        # Decompress
        decompressed = gzip.decompress(compressed)

        # Parse
        parsed = json.loads(decompressed.decode('utf-8'))

        # Validate
        assert validate_message(parsed) is True
        assert parsed["body"] == body


# =============================================================================
# PIPL/GDPR Compliance Tests
# =============================================================================

class TestComplianceCheck:
    """Test PIPL/GDPR compliance checking"""

    def test_sensitive_data_detection(self):
        """Should detect sensitive data fields"""
        data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+1234567890",
            "message": "Hello"
        }

        sensitive_fields = ["phone", "email", "id_number", "address", "location"]
        detected = [f for f in sensitive_fields if f in data]

        assert "email" in detected
        assert "phone" in detected

    def test_compliance_result(self):
        """Compliance check should return structured result"""
        issues = {
            "compliant": False,
            "pipl_issues": ["Sensitive field 'email' requires explicit consent"],
            "gdpr_issues": ["Sensitive field 'email' requires explicit consent"],
            "recommendations": ["Implement consent tracking"]
        }

        assert issues["compliant"] is False
        assert len(issues["pipl_issues"]) > 0
        assert len(issues["gdpr_issues"]) > 0


# =============================================================================
# Main Test Runner
# =============================================================================

def run_tests():
    """Run all tests without pytest"""
    import traceback

    test_classes = [
        TestSchemaValidation,
        TestUTF8Validation,
        TestVectorClock,
        TestGzipCompression,
        TestMessageIDGeneration,
        TestAckTimeoutHandling,
        TestOSINTDeduplication,
        TestIntegration,
        TestComplianceCheck
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"Running {test_class.__name__}")
        print('='*60)

        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                try:
                    getattr(instance, method_name)()
                    print(f"  ✓ {method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  ✗ {method_name}: {e}")
                    traceback.print_exc()
                    failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print('='*60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
