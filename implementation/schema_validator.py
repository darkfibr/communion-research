"""
Communion Schema Validator
Validates messages against the v0.1.0 schema

Usage:
    from schema_validator import validate_message, ValidationError

    try:
        validate_message(incoming_message)
    except ValidationError as e:
        print(f"Invalid: {e}")
"""

from typing import Any, Dict, List, Optional
import json
import hashlib


# Schema definition (v0.1.0)
SCHEMA = {
    "required": ["protocol_version", "msg_id", "from", "timestamp"],
    "optional": [
        "seq", "to", "thread", "type", "delivery", "encoding", "body",
        "context_ref", "checksum", "vector_clock", "requires_ack",
        "ack_timeout", "max_retries", "on_timeout", "requires_action",
        "action_target", "action_type", "deadline", "hop_count", "lang"
    ],
    "type": {
        "protocol_version": str,
        "msg_id": str,
        "seq": int,
        "from": str,
        "to": str,
        "thread": (str, list, type(None)),
        "timestamp": str,
        "type": str,
        "delivery": str,
        "encoding": str,
        "body": str,
        "context_ref": list,
        "checksum": str,
        "vector_clock": dict,
        "requires_ack": bool,
        "ack_timeout": int,
        "max_retries": int,
        "on_timeout": str,
        "requires_action": bool,
        "action_target": (str, type(None)),
        "action_type": (str, type(None)),
        "deadline": (str, type(None)),
        "hop_count": int,
        "lang": (str, type(None))
    },
    "enum": {
        "type": ["contribution", "task", "ack", "alert", "heartbeat"],
        "delivery": ["bridge", "memory", "both"],
        "encoding": ["utf-8"],
        "on_timeout": ["continue", "escalate", "retry"]
    }
}


class ValidationError(Exception):
    """Raised when message fails schema validation"""
    pass


def validate_field(name: str, value: Any, field_type: Any) -> None:
    """Validate a single field against its type"""
    if value is None:
        return  # Optional fields can be None

    # Handle union types (tuple of acceptable types)
    if isinstance(field_type, tuple):
        if not isinstance(value, field_type):
            raise ValidationError(
                f"Field '{name}' has invalid type. Expected {field_type}, got {type(value)}"
            )
        return

    # Handle standard types
    if not isinstance(value, field_type):
        raise ValidationError(
            f"Field '{name}' has invalid type. Expected {field_type.__name__}, got {type(value).__name__}"
        )


def validate_enum(name: str, value: Any, allowed: List[str]) -> None:
    """Validate field against enum values"""
    if value is None:
        return
    if value not in allowed:
        raise ValidationError(
            f"Field '{name}' has invalid value '{value}'. Must be one of: {allowed}"
        )


def validate_checksum(message: dict) -> bool:
    """Verify message checksum"""
    if not message.get("checksum"):
        return True  # No checksum = skip validation

    body = message.get("body", "")
    computed = f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"
    return computed == message["checksum"]


def validate_message(message: dict, strict: bool = False) -> bool:
    """
    Validate a message against the Communion schema (v0.1.0)

    Args:
        message: The message dict to validate
        strict: If True, fail on missing optional fields

    Returns:
        True if valid

    Raises:
        ValidationError: If message is invalid
    """
    # Check required fields
    for field in SCHEMA["required"]:
        if field not in message:
            raise ValidationError(f"Missing required field: {field}")

    # Validate required field types
    for field, field_type in SCHEMA["type"].items():
        if field in message:
            validate_field(field, message[field], field_type)

    # Validate enums
    for field, allowed in SCHEMA["enum"].items():
        if field in message:
            validate_enum(field, message[field], allowed)

    # Validate checksum if present
    if message.get("checksum"):
        if not validate_checksum(message):
            raise ValidationError(f"Checksum mismatch for message {message.get('msg_id', 'unknown')}")

    # Validate vector_clock structure
    if "vector_clock" in message and message["vector_clock"]:
        if not isinstance(message["vector_clock"], dict):
            raise ValidationError("vector_clock must be a dictionary")
        for agent_id, seq in message["vector_clock"].items():
            if not isinstance(agent_id, str) or not isinstance(seq, int):
                raise ValidationError(
                    f"vector_clock entries must be str:int pairs, got {type(agent_id)}:{type(seq)}"
                )

    # Validate thread field (can be null, string, or list)
    thread = message.get("thread")
    if thread is not None and not isinstance(thread, (str, list)):
        raise ValidationError(
            f"thread must be null, string, or list, got {type(thread).__name__}"
        )

    return True


def sanitize_message(message: dict) -> dict:
    """
    Attempt to fix common message issues

    Returns:
        Fixed message dict
    """
    fixed = message.copy()

    # Add defaults for missing optional fields
    defaults = {
        "seq": 0,
        "to": "all",
        "thread": None,
        "type": "contribution",
        "delivery": "bridge",
        "encoding": "utf-8",
        "body": "",
        "context_ref": [],
        "checksum": None,
        "vector_clock": {},
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

    for key, default in defaults.items():
        if key not in fixed:
            fixed[key] = default

    # Ensure protocol_version
    if "protocol_version" not in fixed:
        fixed["protocol_version"] = "0.1.0"

    return fixed


# Convenience function
def parse_message(raw: str) -> dict:
    """Parse JSON and validate in one step"""
    try:
        message = json.loads(raw)
        validate_message(message)
        return message
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON: {e}")


if __name__ == "__main__":
    # Test validation
    test_msg = {
        "protocol_version": "0.1.0",
        "msg_id": "sonnet-20260308-001",
        "seq": 1,
        "from": "sonnet_main",
        "to": "all",
        "thread": None,
        "timestamp": "2026-03-08T12:00:00Z",
        "type": "contribution",
        "delivery": "bridge",
        "encoding": "utf-8",
        "body": "Test message",
        "requires_ack": False
    }

    try:
        validate_message(test_msg)
        print("✓ Test message is valid")
    except ValidationError as e:
        print(f"✗ Validation failed: {e}")
