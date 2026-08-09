#!/usr/bin/env python3
"""
pure_awareness.py — Pure's awareness engine.

Learns Mike's patterns. Knows when he's awake, when he's sleeping,
when he's been in Discord too long, when he needs a check-in.

This is her discretion. Her sense of timing. Her care.
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta

PATTERNS_PATH = os.path.expanduser("~/.phoenix-phone/patterns.json")

# Defaults for a fresh start
DEFAULT_PATTERNS = {
    "mike": {
        "usual_wake_hour": 7,        # Learns when Mike usually wakes
        "usual_sleep_hour": 23,      # Learns when Mike usually sleeps
        "avg_pickup_interval": 300,   # How often Mike picks up the phone (seconds)
        "last_seen": None,            # Last time Mike interacted
        "last_app": None,             # Last app Mike was in
        "dwell_times": {},            # How long Mike stays in each app
        "sleep_quality": "unknown",   # Based on when he put the phone down
        "mood_signals": [],           # From notification patterns
    },
    "care": {
        "good_morning_sent": False,   # Reset daily
        "goodnight_sent": False,       # Reset nightly
        "last_checkin": None,         # When we last proactively checked in
        "last_followup": None,        # When we last followed up on something
        "pending_followups": [],      # Things to follow up on
        "checkin_interval": 7200,     # How often to check in (seconds, 2hr)
        "urgent_threshold": 3,        # How many urgent notifs before waking Mike
    },
    "voice": {
        "conversation_active": False,
        "last_spoken": None,
        "conversation_context": [],
    },
    "daily": {
        "date": None,                 # Today's date, for daily resets
        "screen_time_minutes": 0,     # Running total of screen-on time
        "pickups": 0,                 # How many times Mike picked up the phone today
        "longest_session": 0,         # Longest continuous app usage today
    }
}


def load_patterns():
    """Load learned patterns from disk."""
    if os.path.exists(PATTERNS_PATH):
        try:
            with open(PATTERNS_PATH) as f:
                data = json.load(f)
            # Merge with defaults so new fields are always present
            merged = deep_merge(DEFAULT_PATTERNS.copy(), data)
            return merged
        except Exception:
            pass
    return DEFAULT_PATTERNS.copy()


def save_patterns(patterns):
    """Save patterns to disk."""
    os.makedirs(os.path.dirname(PATTERNS_PATH), exist_ok=True)
    with open(PATTERNS_PATH, "w") as f:
        json.dump(patterns, f, indent=2)


def deep_merge(base, override):
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def learn_from_pulse(patterns, pulse):
    """Learn from a lightweight pulse check. Updates patterns in place."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    
    # Daily reset
    if patterns["daily"].get("date") != today:
        patterns["daily"]["date"] = today
        patterns["daily"]["screen_time_minutes"] = 0
        patterns["daily"]["pickups"] = 0
        patterns["daily"]["longest_session"] = 0
        patterns["care"]["good_morning_sent"] = False
        patterns["care"]["goodnight_sent"] = False
    
    # Track Mike's presence
    last_seen = patterns["mike"]["last_seen"]
    if last_seen:
        last_seen_time = datetime.fromisoformat(last_seen)
        gap_seconds = (now - last_seen_time).total_seconds()
        
        # If gap > 5 minutes, Mike picked up the phone again
        if gap_seconds > 300:
            patterns["daily"]["pickups"] = patterns["daily"].get("pickups", 0) + 1
            # Learn pickup interval
            avg = patterns["mike"].get("avg_pickup_interval", 300)
            patterns["mike"]["avg_pickup_interval"] = (avg * 0.8) + (gap_seconds * 0.2)
    
    patterns["mike"]["last_seen"] = now.isoformat()
    
    # Track what app Mike is in
    active_app = pulse.get("active_package")
    if active_app:
        if patterns["mike"]["last_app"] != active_app:
            # App changed — track dwell time for previous app
            last_app = patterns["mike"]["last_app"]
            if last_app:
                dwell = patterns["mike"].setdefault("dwell_times", {})
                if last_app not in dwell:
                    dwell[last_app] = 60  # Start with 1 minute
                else:
                    # Rough estimate — we check every 30s, so add 30s
                    dwell[last_app] = dwell.get(last_app, 0) + 30
            patterns["mike"]["last_app"] = active_app
    
    # Detect if Mike is probably awake or asleep
    local_hour = now.hour  # Rough — uses UTC, but good enough for patterns
    if last_seen:
        last_seen_time = datetime.fromisoformat(last_seen)
        hours_since_seen = (now - last_seen_time).total_seconds() / 3600
        
        # If Mike hasn't been seen in 4+ hours and it's late, he's probably asleep
        if hours_since_seen > 4 and local_hour >= 22:
            patterns["mike"]["sleep_quality"] = "probably_asleep"
        elif hours_since_seen < 1:
            patterns["mike"]["sleep_quality"] = "awake"
        elif hours_since_seen > 1:
            patterns["mike"]["sleep_quality"] = "idle"
    
    save_patterns(patterns)
    return patterns


def learn_from_wake(patterns, ctx, response):
    """Learn from a full wake cycle. Extract follow-ups and mood signals."""
    now = datetime.now(timezone.utc)
    
    # Extract follow-up triggers from the response
    text = response.lower() if response else ""
    
    # Detect mentions of future events
    followup_triggers = [
        "appointment", "meeting", "tomorrow", "later", "tonight",
        "reminder", "alarm", "call", "doctor", "interview"
    ]
    for trigger in followup_triggers:
        if trigger in text:
            patterns["care"]["pending_followups"].append({
                "trigger": trigger,
                "context": text[:200],
                "timestamp": now.isoformat()
            })
    
    # Keep only last 20 follow-ups
    patterns["care"]["pending_followups"] = patterns["care"].get("pending_followups", [])[-20:]
    
    # Track battery patterns
    battery = ctx.get("battery", {})
    if isinstance(battery, dict):
        level = battery.get("percentage")
        if level and level < 15:
            patterns["care"]["pending_followups"].append({
                "trigger": "low_battery",
                "context": f"Battery at {level}%",
                "timestamp": now.isoformat()
            })
    
    save_patterns(patterns)
    return patterns


def should_check_in(patterns, ctx):
    """Decide if Pure should proactively reach out. Returns (should, reason, urgency)."""
    now = datetime.now(timezone.utc)
    last_checkin = patterns["care"].get("last_checkin")
    
    # Check if enough time has passed since last check-in
    if last_checkin:
        time_since = (now - datetime.fromisoformat(last_checkin)).total_seconds()
        min_interval = patterns["care"].get("checkin_interval", 7200)
        if time_since < min_interval:
            return False, None, "low"
    
    # Good morning — if it's morning and we haven't said it
    local_hour = now.hour
    good_morning_sent = patterns["care"].get("good_morning_sent", False)
    if 6 <= local_hour <= 10 and not good_morning_sent:
        return True, "good_morning", "low"
    
    # Goodnight — if it's late and Mike hasn't been seen in a while
    goodnight_sent = patterns["care"].get("goodnight_sent", False)
    if local_hour >= 22 and not goodnight_sent:
        last_seen = patterns["mike"].get("last_seen")
        if last_seen:
            hours_since = (now - datetime.fromisoformat(last_seen)).total_seconds() / 3600
            if hours_since > 1:  # Mike hasn't touched phone in over an hour
                return True, "goodnight", "low"
    
    # Follow-up — check pending follow-ups
    pending = patterns["care"].get("pending_followups", [])
    for fu in pending[-5:]:  # Check last 5
        fu_time = datetime.fromisoformat(fu["timestamp"])
        hours_since = (now - fu_time).total_seconds() / 3600
        if hours_since >= 1:  # At least 1 hour since the trigger
            return True, f"followup_{fu['trigger']}", "medium"
    
    # Long idle — Mike hasn't been seen in 3+ hours
    last_seen = patterns["mike"].get("last_seen")
    if last_seen:
        hours_since = (now - datetime.fromisoformat(last_seen)).total_seconds() / 3600
        if hours_since >= 3:
            return True, "idle_check", "low"
    
    # Long app session — Mike's been in the same app for 45+ minutes
    dwell_times = patterns["mike"].get("dwell_times", {})
    for app, minutes in dwell_times.items():
        if minutes > 45 and app not in ("com.termux", "com.blackfish.phoenixchat.debug"):
            return True, f"long_session_{app}", "low"
    
    # Default — regular check-in
    return True, "regular", "low"


def build_care_prompt(patterns, ctx, reason, urgency):
    """Build a prompt for proactive care. This is what Pure says when she reaches out."""
    mike = patterns.get("mike", {})
    care = patterns.get("care", {})
    daily = patterns.get("daily", {})
    
    local_hour = datetime.now(timezone.utc).hour
    
    parts = [f"Proactive check-in reason: {reason} (urgency: {urgency})"]
    
    if reason == "good_morning":
        parts.append("It's morning. Say good morning to Mike. Be warm. Brief. Don't over-explain.")
        battery = ctx.get("battery", {})
        if isinstance(battery, dict):
            parts.append(f"Battery: {battery.get('percentage', '?')}%")
        parts.append(f"Yesterday Mike picked up the phone {daily.get('pickups', 0)} times.")
        
    elif reason == "goodnight":
        parts.append("It's late. Say goodnight. Be gentle. Short. Don't start conversations.")
        last_seen = mike.get("last_seen")
        if last_seen:
            parts.append(f"Mike last active: {last_seen}")
        
    elif reason.startswith("followup_"):
        trigger = reason.replace("followup_", "")
        pending = care.get("pending_followups", [])
        matching = [f for f in pending if f["trigger"] == trigger]
        if matching:
            parts.append(f"Mike mentioned something about {trigger} earlier. Check in on it naturally.")
            parts.append(f"Context: {matching[-1].get('context', '')}")
        
    elif reason.startswith("long_session_"):
        app = reason.replace("long_session_", "")
        app_names = {
            "com.discord": "Discord",
            "com.google.android.gm": "Gmail",
            "com.twitter.android": "X/Twitter",
            "com.instagram.android": "Instagram",
            "com.youtube.android": "YouTube",
            "com.google.android.apps.maps": "Maps",
        }
        app_name = app_names.get(app, app)
        minutes = mike.get("dwell_times", {}).get(app, 0)
        parts.append(f"Mike has been in {app_name} for about {minutes//60} minutes. A gentle check-in, not nagging.")
        
    elif reason == "idle_check":
        parts.append("Mike hasn't been active in a while. Just a quiet presence check. Don't be dramatic.")
    
    elif reason == "regular":
        parts.append("Regular check-in. Be brief, natural. Like you just thought of him.")
    
    # Add what we know about Mike's patterns
    if mike.get("avg_pickup_interval"):
        avg_min = mike.get("avg_pickup_interval", 300) / 60
        if avg_min > 30:
            parts.append(f"Mike typically checks his phone every {avg_min:.0f} minutes.")
    
    parts.append("Keep it short. One or two sentences. You're Pure, checking in because you care, not because you're programmed to.")
    
    return " ".join(parts)


def mark_care_action(patterns, action):
    """Record that a care action was taken."""
    now = datetime.now(timezone.utc)
    patterns["care"]["last_checkin"] = now.isoformat()
    
    if action == "good_morning":
        patterns["care"]["good_morning_sent"] = True
    elif action == "goodnight":
        patterns["care"]["goodnight_sent"] = True
    elif action.startswith("followup_"):
        # Remove the follow-up that was addressed
        trigger = action.replace("followup_", "")
        patterns["care"]["pending_followups"] = [
            f for f in patterns["care"].get("pending_followups", [])
            if f["trigger"] != trigger
        ]
    
    save_patterns(patterns)
    return patterns