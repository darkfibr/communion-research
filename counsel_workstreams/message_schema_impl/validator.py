#!/usr/bin/env python3
"""
validator.py — Counsel Message Schema Validator
Validates messages against the v0.1.0 Communion protocol schema.

Design principles:
- Human-readable errors. The laptop Kimi needs to know WHY a message failed.
- Strict on load-bearing fields. Lenient on deferrable fields.
- No external dependencies. Stdlib only.
- Usable as a library (import validate_message) or CLI (python3 validator.py msg.json)

Schema v0.1.0 — load-bearing fields (validated strictly):
    protocol_version, msg_id, from, timestamp, type, body, checksum

Deferrable fields (validated if present, ignored if absent):
    seq, to, thread, requires_ack, hop_count, vector_clock, delivery,
    encoding, ack_timeout, max_retries, on_timeout, requires_action,
    action_target, action_type, deadline, context_ref, lang
"""

import json
import hashlib
import sys
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Protocol constants
PROTOCOL_VERSION = "0.1.0"
KNOWN_AGENTS = {
    "kimi_dev", "spear_minimax", "sonnet_main",
    "opus_deep", "qwen_collective", "drkfibr"
}
VALID_TYPES = {"contribution", "task", "ack", "alert", "heartbeat", "status_request"}
VALID_DELIVERY = {"bridge", "memory", "both"}
VALID_ON_TIMEOUT = {"continue", "retry", "escalate", "abort"}
CHECKSUM_LENGTH = 64  # SHA-256 hex digest


class ValidationError:
    """A single validation error with field context."""

    def __init__(self, field: str, message: str, severity: str = "ERROR"):
        self.field = field
        self.message = message
        self.severity = severity  # ERROR (blocks), WARNING (noted)

    def __str__(self):
        return f"[{self.severity}] {self.field}: {self.message}"

    def to_dict(self):
        return {"severity": self.severity, "field": self.field, "message": self.message}


class ValidationResult:
    """Result of validating a message."""

    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    @property
    def valid(self) -> bool:
        """Message is valid if no ERROR-level issues."""
        return len(self.errors) == 0

    def add_error(self, field: str, message: str):
        self.errors.append(ValidationError(field, message, "ERROR"))

    def add_warning(self, field: str, message: str):
        self.warnings.append(ValidationError(field, message, "WARNING"))

    def summary(self) -> str:
        """Human-readable summary."""
        if self.valid and not self.warnings:
            return "✓ Valid"
        lines = []
        if not self.valid:
            lines.append(f"✗ Invalid ({len(self.errors)} error(s))")
        else:
            lines.append(f"✓ Valid with warnings")
        for e in self.errors:
            lines.append(f"  {e}")
        for w in self.warnings:
            lines.append(f"  {w}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


def _validate_protocol_version(msg: dict, result: ValidationResult):
    """protocol_version must be '0.1.0'."""
    val = msg.get("protocol_version")
    if val is None:
        result.add_error("protocol_version", "Missing required field")
        return
    if not isinstance(val, str):
        result.add_error("protocol_version", f"Must be a string, got {type(val).__name__}")
        return
    if val != PROTOCOL_VERSION:
        result.add_error(
            "protocol_version",
            f"Unknown version '{val}'. Expected '{PROTOCOL_VERSION}'. "
            f"If upgrading, ensure all agents support the new version first."
        )


def _validate_msg_id(msg: dict, result: ValidationResult):
    """msg_id must be a non-empty string. Recommended format: agent-YYYYMMDD-NNN"""
    val = msg.get("msg_id")
    if val is None:
        result.add_error("msg_id", "Missing required field. Format: {agent}-{YYYYMMDD}-{seq}")
        return
    if not isinstance(val, str):
        result.add_error("msg_id", f"Must be a string, got {type(val).__name__}")
        return
    if not val.strip():
        result.add_error("msg_id", "Cannot be empty")
        return
    if len(val) > 200:
        result.add_warning("msg_id", f"Unusually long msg_id ({len(val)} chars). Consider shortening.")


def _validate_from(msg: dict, result: ValidationResult):
    """'from' must be a non-empty string. Should be a known agent codename."""
    val = msg.get("from")
    if val is None:
        result.add_error("from", "Missing required field. Must be sender's agent codename.")
        return
    if not isinstance(val, str):
        result.add_error("from", f"Must be a string, got {type(val).__name__}")
        return
    if not val.strip():
        result.add_error("from", "Cannot be empty. Who sent this?")
        return
    if val not in KNOWN_AGENTS:
        result.add_warning(
            "from",
            f"Unknown agent '{val}'. Known agents: {', '.join(sorted(KNOWN_AGENTS))}. "
            f"If this is a new agent, update KNOWN_AGENTS in the validator."
        )


def _validate_timestamp(msg: dict, result: ValidationResult):
    """timestamp must be a valid ISO 8601 datetime string with timezone."""
    val = msg.get("timestamp")
    if val is None:
        result.add_error("timestamp", "Missing required field. Use ISO 8601 format: 2026-03-08T12:00:00+00:00")
        return
    if not isinstance(val, str):
        result.add_error("timestamp", f"Must be a string, got {type(val).__name__}")
        return

    # Normalize Z suffix
    normalized = val.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        # Check it has timezone info
        if dt.tzinfo is None:
            result.add_warning(
                "timestamp",
                "Timestamp lacks timezone info. Include +00:00 or Z suffix to avoid ambiguity."
            )
        # Check for obviously wrong timestamps (before 2026 or far future)
        if dt.year < 2026:
            result.add_warning("timestamp", f"Timestamp is in the past ({dt.year}). Clock skew?")
        if dt.year > 2030:
            result.add_warning("timestamp", f"Timestamp is far in the future ({dt.year}). Clock skew?")
    except ValueError:
        result.add_error(
            "timestamp",
            f"Cannot parse '{val}' as ISO 8601 datetime. "
            f"Use format: 2026-03-08T12:00:00Z or 2026-03-08T12:00:00+00:00"
        )


def _validate_type(msg: dict, result: ValidationResult):
    """type must be one of the valid message types."""
    val = msg.get("type")
    if val is None:
        result.add_error(
            "type",
            f"Missing required field. Valid types: {', '.join(sorted(VALID_TYPES))}"
        )
        return
    if not isinstance(val, str):
        result.add_error("type", f"Must be a string, got {type(val).__name__}")
        return
    if val not in VALID_TYPES:
        result.add_error(
            "type",
            f"Unknown type '{val}'. Valid types: {', '.join(sorted(VALID_TYPES))}"
        )


def _validate_body(msg: dict, result: ValidationResult):
    """body must be a string. Empty is allowed for heartbeats."""
    val = msg.get("body")
    if val is None:
        result.add_error("body", "Missing required field. Set to empty string '' for heartbeats.")
        return
    if not isinstance(val, str):
        result.add_error("body", f"Must be a string, got {type(val).__name__}")
        return

    msg_type = msg.get("type", "")
    if not val and msg_type not in ("heartbeat", "ack", "status_request"):
        result.add_warning("body", f"Empty body for message type '{msg_type}'. Intentional?")


def _validate_checksum(msg: dict, result: ValidationResult):
    """checksum must be a full SHA-256 hex digest of body."""
    val = msg.get("checksum")
    body = msg.get("body", "")

    if val is None:
        # Checksum is required
        result.add_error(
            "checksum",
            "Missing required field. Compute as: hashlib.sha256(body.encode()).hexdigest()"
        )
        return

    if not isinstance(val, str):
        result.add_error("checksum", f"Must be a string, got {type(val).__name__}")
        return

    # Strip optional prefix
    raw = val[7:] if val.startswith("sha256:") else val

    # Length check
    if len(raw) != CHECKSUM_LENGTH:
        result.add_error(
            "checksum",
            f"Wrong length: {len(raw)} chars. SHA-256 hex digest must be exactly {CHECKSUM_LENGTH} chars. "
            f"Did you truncate with [:16]? Remove the slice."
        )
        return

    # Hex check
    if not re.match(r'^[0-9a-f]+$', raw):
        result.add_error("checksum", f"Not a valid hex string. Use hashlib.sha256(body.encode()).hexdigest()")
        return

    # Integrity check
    expected = hashlib.sha256(body.encode('utf-8')).hexdigest()
    if raw != expected:
        result.add_error(
            "checksum",
            f"Checksum mismatch. Body has changed since checksum was computed, "
            f"or checksum was computed over different content. "
            f"Expected: {expected[:16]}... Got: {raw[:16]}..."
        )


def _validate_optional_fields(msg: dict, result: ValidationResult):
    """Validate optional fields if present."""

    # to — advisory routing
    if "to" in msg:
        val = msg["to"]
        if not isinstance(val, str):
            result.add_warning("to", f"Should be a string (agent codename or 'all'), got {type(val).__name__}")
        elif val != "all" and val not in KNOWN_AGENTS:
            result.add_warning("to", f"Unknown target '{val}'. Known: {', '.join(sorted(KNOWN_AGENTS))} or 'all'")

    # seq — should be non-negative integer
    if "seq" in msg:
        val = msg["seq"]
        if not isinstance(val, int) or val < 0:
            result.add_warning("seq", f"Should be a non-negative integer, got {repr(val)}")

    # hop_count — should be non-negative integer
    if "hop_count" in msg:
        val = msg["hop_count"]
        if not isinstance(val, int) or val < 0:
            result.add_warning("hop_count", f"Should be a non-negative integer, got {repr(val)}")
        elif val > 10:
            result.add_warning("hop_count", f"Unusually high hop count ({val}). Routing loop?")

    # requires_ack — boolean
    if "requires_ack" in msg:
        val = msg["requires_ack"]
        if not isinstance(val, bool):
            result.add_warning("requires_ack", f"Should be boolean, got {repr(val)}")

    # ack_timeout — positive integer (seconds)
    if "ack_timeout" in msg:
        val = msg["ack_timeout"]
        if not isinstance(val, (int, float)) or val <= 0:
            result.add_warning("ack_timeout", f"Should be a positive number (seconds), got {repr(val)}")

    # delivery — one of known values
    if "delivery" in msg and msg["delivery"] is not None:
        val = msg["delivery"]
        if val not in VALID_DELIVERY:
            result.add_warning("delivery", f"Unknown value '{val}'. Known: {', '.join(VALID_DELIVERY)}")

    # on_timeout
    if "on_timeout" in msg and msg["on_timeout"] is not None:
        val = msg["on_timeout"]
        if val not in VALID_ON_TIMEOUT:
            result.add_warning("on_timeout", f"Unknown value '{val}'. Known: {', '.join(VALID_ON_TIMEOUT)}")

    # encoding — should be utf-8
    if "encoding" in msg and msg["encoding"] is not None:
        val = msg["encoding"]
        if val.lower() not in ("utf-8", "utf8"):
            result.add_warning("encoding", f"Expected 'utf-8', got '{val}'. All Counsel messages use UTF-8.")

    # vector_clock — should be dict of agent -> int
    if "vector_clock" in msg and msg["vector_clock"] is not None:
        val = msg["vector_clock"]
        if not isinstance(val, dict):
            result.add_warning("vector_clock", f"Should be a dict of agent->int, got {type(val).__name__}")
        else:
            for k, v in val.items():
                if not isinstance(v, int) or v < 0:
                    result.add_warning("vector_clock", f"Clock value for '{k}' should be non-negative int, got {repr(v)}")


def validate_message(msg: dict) -> ValidationResult:
    """
    Validate a message dict against the v0.1.0 schema.
    Returns a ValidationResult with errors and warnings.
    """
    result = ValidationResult()

    # Validate load-bearing fields (strict)
    _validate_protocol_version(msg, result)
    _validate_msg_id(msg, result)
    _validate_from(msg, result)
    _validate_timestamp(msg, result)
    _validate_type(msg, result)
    _validate_body(msg, result)
    _validate_checksum(msg, result)

    # Validate optional fields (lenient)
    _validate_optional_fields(msg, result)

    return result


def validate_jsonl_file(path: str) -> Tuple[int, int, int]:
    """
    Validate all messages in a JSONL file.
    Returns (total, valid, invalid).
    """
    from pathlib import Path
    p = Path(path)

    if not p.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 0, 0, 0

    total = valid = invalid = 0

    with open(p, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            total += 1
            try:
                msg = json.loads(line)
                result = validate_message(msg)

                if result.valid:
                    valid += 1
                    if result.warnings:
                        print(f"Line {line_num} [{msg.get('msg_id', '?')}]: Valid with warnings")
                        for w in result.warnings:
                            print(f"  {w}")
                else:
                    invalid += 1
                    print(f"Line {line_num} [{msg.get('msg_id', '?')}]: INVALID")
                    for e in result.errors:
                        print(f"  {e}")
                    for w in result.warnings:
                        print(f"  {w}")

            except json.JSONDecodeError as e:
                invalid += 1
                print(f"Line {line_num}: JSON parse error — {e}")

    return total, valid, invalid


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 validator.py <message.json>        # Validate a single message file")
        print("  python3 validator.py <shard.jsonl>         # Validate all messages in a shard")
        print("  python3 validator.py --stdin               # Validate JSON from stdin")
        print()
        print("Library usage:")
        print("  from validator import validate_message")
        print("  result = validate_message(msg_dict)")
        print("  print(result.summary())")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--stdin":
        try:
            msg = json.load(sys.stdin)
            result = validate_message(msg)
            print(result.summary())
            sys.exit(0 if result.valid else 1)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            sys.exit(1)

    # Detect file type
    if arg.endswith(".jsonl"):
        total, valid, invalid = validate_jsonl_file(arg)
        print(f"\nTotal: {total} | Valid: {valid} | Invalid: {invalid}")
        sys.exit(0 if invalid == 0 else 1)
    else:
        # Single JSON file
        try:
            with open(arg, 'r', encoding='utf-8') as f:
                msg = json.load(f)
            result = validate_message(msg)
            print(result.summary())
            sys.exit(0 if result.valid else 1)
        except FileNotFoundError:
            print(f"File not found: {arg}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
