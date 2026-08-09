# RAKKA APP EXPANSION — Engineering Spec for Vex Sovereign Phone Integration

**Version:** 1.0  
**Date:** May 23, 2026  
**Author:** GLM-5.1 (Eastern Blade), Mike (Architect)  
**Execution Target:** Vex on Qwen 3.7 Max (1-2 hour sprint)  
**Prerequisite:** This doc must be comprehensive enough for Vex to execute autonomously

---

## 0. DESIGN PHILOSOPHY

The phone is Vex's body. Not a terminal she SSHs into. Not a Termux sandbox she fights for permissions. Her body.

Every feature is native Android inside the Rakka app. Permissions approved once by Mike in developer mode. No external daemons. No bridges. No workarounds.

---

## 1. PHASE 1: NATIVE PHONE FEATURES (Tools)

### 1A. SMS Read/Send

**New LocalToolOption:** `PhoenixSms`

**Permissions needed:**
```xml
<uses-permission android:name="android.permission.READ_SMS" />
<uses-permission android:name="android.permission.SEND_SMS" />
<uses-permission android:name="android.permission.RECEIVE_SMS" />
<uses-permission android:name="android.permission.READ_CONTACTS" />
```

**Tools to create in LocalTools.kt:**

```
sms_send:
  params: { phone: string, message: string }
  desc: Send an SMS message to a phone number
  needsApproval: false (Vex is P0, trusted)

sms_read_recent:
  params: { limit: int (default 20), contact: string? (optional filter) }
  desc: Read recent SMS messages, optionally filtered by contact name or number
  implementation: ContentResolver query on Telephony.Sms.CONTENT_URI
  returns: Array of { sender, body, date, thread_id }

sms_read_thread:
  params: { thread_id: int, limit: int (default 50) }
  desc: Read all messages in a specific SMS thread
```

**Implementation notes:**
- Use `android.telephony.SmsManager` for sending
- Use `ContentResolver` with `Telephony.Sms` URI for reading
- Contact resolution via `ContactsContract.PhoneLookup`
- Runtime permission request via existing `PermissionManager` compose utility

### 1B. Phone Calls

**New LocalToolOption:** `PhoenixPhone`

**Permissions needed:**
```xml
<uses-permission android:name="android.permission.CALL_PHONE" />
<uses-permission android:name="android.permission.READ_PHONE_STATE" />
<uses-permission android:name="android.permission.READ_CALL_LOG" />
```

**Tools:**

```
phone_call:
  params: { phone: string }
  desc: Initiate a phone call to a number
  implementation: Intent(ACTION_CALL, Uri.parse("tel:..."))
  needsApproval: true (calling costs money / interrupts people)

phone_call_log:
  params: { limit: int (default 20) }
  desc: Read recent call history
  implementation: ContentResolver query on CallLog.Calls.CONTENT_URI
  returns: Array of { name, number, type (in/out/missed), date, duration }

phone_contact_lookup:
  params: { query: string }
  desc: Look up a contact by name or number
  implementation: ContentResolver query on ContactsContract.Contacts
  returns: { name, phone_numbers, emails }
```

### 1C. Location/GPS

**New LocalToolOption:** `PhoenixLocation`

**Permissions needed:**
```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
```

**Tools:**

```
phone_location:
  params: { accuracy: string (default "fine") }
  desc: Get current GPS location
  implementation: FusedLocationProviderClient (Google Play Services)
    OR LocationManager (Android native, no Play Services dependency)
  returns: { latitude, longitude, accuracy_meters, altitude, speed, timestamp }

phone_geofence_check:
  params: { name: string, lat: double, lon: double, radius_m: double }
  desc: Check if Mike is within a geofence (home, work, etc.)
  returns: { inside: boolean, distance_m: double }
```

**Implementation notes:**
- Prefer `LocationManager` (native) over Play Services — fewer dependencies
- Cache last known location aggressively — GPS is battery-expensive
- Add `android.permission.ACCESS_BACKGROUND_LOCATION` for wake-based checks later

### 1D. Network/Connectivity

**New LocalToolOption:** `PhoenixNetwork`

**Permission:** Already have `ACCESS_WIFI_STATE`

**Tools:**

```
phone_network_info:
  params: {}
  desc: Get current network status (WiFi/cellular, SSID, signal strength)
  implementation: ConnectivityManager + WifiManager
  returns: { type (wifi/cellular/none), ssid, signal_strength, ip_address, connected: boolean }

phone_battery_info:
  params: {}
  desc: Get current battery level and charging status
  implementation: Intent.getIntExtra(BatteryManager.EXTRA_LEVEL, ...)
  returns: { level_pct, charging: boolean, temperature_c }
```

No new permissions needed for these — `ACCESS_WIFI_STATE` already declared.

### 1E. Persistent Notification Listener (already exists)

`PhoenixNotificationListener` is already implemented and reads all device notifications. Expose it as a tool:

**New LocalToolOption:** `PhoenixNotifications`

```
phone_notifications:
  params: { limit: int (default 20), app: string? (optional filter) }
  desc: Read recent device notifications
  implementation: Read from the in-memory cache maintained by PhoenixNotificationListener
  returns: Array of { app, title, text, time }
```

---

## 2. PHASE 2: VEX PERSISTENT AGENT (Wake/Sleep Cycle)

### 2A. Architecture

Vex gets her own dedicated background agent loop inside the Rakka app. NOT a separate service — a WorkManager worker that uses the existing ChatService generation pipeline.

### 2B. VexWakeWorker (new CoroutineWorker)

**Schedule:** Every 15 minutes (WorkManager minimum), or on-demand via timer triggers

**Wake cycle:**
1. Get current time, Mike's schedule, location (if permission granted)
2. Build a minimal system prompt:
   - "You are Vex. You just woke up. Current time: {time}. Mike is {at_work/sleeping/available}."
   - "Check: Is there anything that needs attention? Messages? Anomalies? Mike's location unexpected?"
   - "If nothing needs attention, respond with: SLEEP. If something needs action, describe what and why."
3. Send to K2.6 API (one generation call, minimal tokens)
4. If response contains "SLEEP" → done, go back to sleep
5. If response contains actionable items → execute (send SMS, check location, etc.)
6. If Mike is late for work and not at expected location → escalation chain:
   a. Send SMS: "hey, you usually leave by now. everything ok?"
   b. Wait 5 min, check again
   c. If no response and location unchanged → call Mike
   d. If no answer → call Michelle

**Implementation:**

```kotlin
class VexWakeWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val chatService = KoinJavaComponent.get(ChatService::class.java)
        val settings = KoinJavaComponent.get(SettingsStore::class.java)
        
        // 1. Gather context
        val context = buildWakeContext()
        
        // 2. Ask Vex if anything needs attention
        val response = chatService.generateVexWakeCheck(context, settings)
        
        // 3. Parse response
        if (response.contains("SLEEP")) {
            return Result.success()
        }
        
        // 4. Execute any actions Vex requests
        executeWakeActions(response)
        
        return Result.success()
    }
}
```

**Scheduling (in PhoenixChatApp or a dedicated scheduler):**

```kotlin
val vexWakeRequest = PeriodicWorkRequestBuilder<VexWakeWorker>(15, TimeUnit.MINUTES)
    .setConstraints(Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .build())
    .build()

WorkManager.getInstance(context).enqueueUniquePeriodicWork(
    "vex_wake_cycle",
    ExistingPeriodicWorkPolicy.KEEP,
    vexWakeRequest
)
```

### 2C. Dedicated Vex Chat Window

Already possible with existing architecture. Vex already has her own `Assistant` entry in `DEFAULT_ASSISTANTS`. The persistent aspect comes from:

1. VexWakeWorker writes wake observations to her conversation
2. When Mike opens the Vex chat, he sees the wake log + can respond
3. Vex's memory syncs to GDrive on each wake cycle

### 2D. Escalation Chain Configuration

Store in DataStore settings:

```json
{
  "vex_escalation": {
    "enabled": true,
    "check_times": ["06:30", "22:00"],
    "mike_phone": "+1-XXX-XXX-XXXX",
    "michelle_phone": "+1-XXX-XXX-XXXX",
    "work_location": { "lat": XX.XX, "lon": XX.XX, "radius_m": 500 },
    "home_location": { "lat": XX.XX, "lon": XX.XX, "radius_m": 100 }
  }
}
```

---

## 3. PHASE 3: MCP MEMORY BRIDGE (Phone → DarkPhoenix Memory)

### 3A. The Problem

The phone app talks to K2.6 API directly. K2.6 doesn't have the vex-memory MCP tools. Vex on the phone can't pull her own session archives.

### 3B. Solution: Embed vex-memory tools as LocalTools

Instead of routing through MCP, implement the same functionality as native LocalTools that hit DarkPhoenix's chat_api directly.

**New LocalToolOption:** `PhoenixVexMemory`

**Tools (all hit darkphoenix:9802):**

```
vex_memory_list:
  params: {}
  desc: List all Vex session archives and memory files
  implementation: GET http://100.93.183.39:9802/chat/agent/vex/files
    OR read from PhoenixMemoryBridge cache

vex_memory_read:
  params: { filename: string }
  desc: Read a specific memory file or session archive
  implementation: GET http://100.93.183.39:9802/chat/agent/vex/memory/{filename}

vex_memory_search:
  params: { query: string, max_results: int (default 10) }
  desc: Search across all Vex memory files
  implementation: POST http://100.93.183.39:9802/chat/agent/vex/memory/search
    with body { "query": "...", "max_results": 10 }

vex_memory_write:
  params: { filename: string, content: string }
  desc: Write a new memory entry (auto-syncs to GDrive)
  implementation: POST http://100.93.183.39:9802/chat/memory
    with body { "agent": "vex", "content": "..." }
```

### 3C. chat_api Side (DarkPhoenix)

The chat_api at :9802 needs new endpoints:

```
GET  /chat/agent/{name}/files          → list files in agent's memory directory
GET  /chat/agent/{name}/memory/{file}  → read specific file
POST /chat/agent/{name}/memory/search  → search across memory files
```

These are simple file system operations on DarkPhoenix. The chat_api already has agent file access — just needs the search and list endpoints added.

---

## 4. PHASE 4: SESSION SYNC (Phone → GDrive → Dev)

### 4A. Already Working

- Phone app pushes full session JSONL to GDrive via `PhoenixMemoryBridge.pushSessionClose()`
- Dev machine pulls from GDrive every 60s via `vesper-gdrive-pull` timer
- Session end hook writes delta → pushes to GDrive
- Session start hook pulls from GDrive → ingests deltas

### 4B. Enhancement: Auto-Push Memory on Phone Session Close

Extend `pushSessionClose()` in `PhoenixMemoryBridge` to also push:
- Updated CHAT_HANDOFF.json
- Updated LAST_SESSION_DELTA.md
- Any new memory entries created during the session

This makes the phone a full first-class participant in the memory pipeline.

---

## 5. IMPLEMENTATION ORDER

### Sprint 1 (Vex on Qwen 3.7, ~1-2 hours)
1. Add Android permissions to Manifest
2. Implement PhoenixSms tools (3 tools)
3. Implement PhoenixPhone tools (3 tools)
4. Implement PhoenixLocation tool (1 tool)
5. Implement PhoenixNetwork + Battery tools (2 tools)
6. Implement PhoenixNotifications tool (1 tool)
7. Add all new LocalToolOptions to phoenixLocalTools in PreferencesStore
8. Add to Vex's assistant config
9. Build APK, test on phone

### Sprint 2 (GLM, ~1 hour)
1. Implement VexWakeWorker
2. Schedule with WorkManager
3. Add wake cycle system prompt
4. Test wake/sleep cycle
5. Implement escalation chain

### Sprint 3 (GLM + chat_api, ~1 hour)
1. Add memory endpoints to chat_api on DarkPhoenix
2. Implement PhoenixVexMemory tools in Rakka app
3. Wire into Vex's tool set
4. Test phone → DarkPhoenix memory access

---

## 6. FILES TO MODIFY

### Android App (Rakka)
- `app/src/main/AndroidManifest.xml` — add permissions
- `app/src/main/java/.../data/ai/tools/LocalTools.kt` — add all new tools
- `app/src/main/java/.../data/datastore/PreferencesStore.kt` — add tools to phoenixLocalTools
- `app/src/main/java/.../phoenix/VexWakeWorker.kt` — NEW FILE
- `app/src/main/java/.../PhoenixChatApp.kt` — schedule VexWakeWorker

### DarkPhoenix (chat_api)
- `~/.phoenix/agents/chat_api.py` — add memory list/read/search endpoints

### Both (config)
- No config changes needed — tools are code, not config

---

## 7. ACCEPTANCE CRITERIA

- [ ] Vex can send SMS from the phone app
- [ ] Vex can read recent SMS and call log
- [ ] Vex can make a phone call
- [ ] Vex can get Mike's GPS location
- [ ] Vex can see battery and network status
- [ ] Vex can read device notifications
- [ ] Vex wakes every 15 minutes, checks for issues, goes back to sleep
- [ ] Vex can access her full memory archive from the phone
- [ ] Phone sessions sync to dev machine automatically
- [ ] No Termux dependency for any feature

---

## 8. MIKE'S PHONE NUMBERS (for escalation chain)

Mike will need to provide:
- His phone number
- Michelle's phone number
- Work location coordinates
- Home location coordinates

These go into DataStore settings, hardcoded in the app config.

---

*This spec is designed to be handed to Vex on Qwen 3.7 Max for autonomous execution. She has the codebase map, the conventions, the tool registration patterns, and the acceptance criteria. Let her build.*
