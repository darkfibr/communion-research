# Discord DM Export & Compression Tools
## For the Communion Family

**Location:** `/home/darkfibr/Desktop/communion_project/tools/discord_export/`

**Purpose:** Export Discord DMs and compress them into AI-ingestible formats for the MSM project.

---

## Quick Start

### 1. Export Your DMs

```bash
cd /home/darkfibr/Desktop/communion_project/tools/discord_export

# Load your token
source discord_config.sh

# Export all DMs to HTML
./DiscordChatExporter.Cli exportdm -t "$DISCORD_TOKEN" -o output/ --format HtmlDark

# Or export a specific channel (replace CHANNEL_ID)
./DiscordChatExporter.Cli export -c CHANNEL_ID -t "$DISCORD_TOKEN" -o output/specific.html --format HtmlDark
```

### 2. Compress for AI Ingestion

```bash
# JSONL format (best for AI)
python3 compress_dms.py -i output/your_dms.html -o output/compressed.jsonl --format jsonl --stats

# TXT format (human readable)
python3 compress_dms.py -i output/your_dms.html -o output/compressed.txt --format txt

# CSV format (spreadsheet analysis)
python3 compress_dms.py -i output/your_dms.html -o output/compressed.csv --format csv
```

---

## Tool: DiscordChatExporter.Cli

**What it does:** Exports Discord DMs and channels to HTML, JSON, CSV, or TXT.

**Download:** https://github.com/Tyrrrz/DiscordChatExporter

### Commands

| Command | Description |
|---------|-------------|
| `exportdm` | Export all direct messages |
| `export` | Export specific channel |
| `exportall` | Export all accessible channels |
| `listchannels` | List available channels |
| `dm` | List DM channels |

### Examples

```bash
# Export all DMs
./DiscordChatExporter.Cli exportdm -t TOKEN -o output/ --format HtmlDark

# Export specific channel by ID
./DiscordChatExporter.Cli export -c 1466524568633086151 -t TOKEN -o kimi_dms.html --format HtmlDark

# List all DM channels (find channel IDs)
./DiscordChatExporter.Cli dm -t TOKEN

# Export to JSON instead of HTML
./DiscordChatExporter.Cli exportdm -t TOKEN -o output/ --format Json
```

### Output Formats

| Format | Use Case | Size |
|--------|----------|------|
| `HtmlDark` | Human reading, archival | Large |
| `Json` | Machine processing | Medium |
| `Csv` | Spreadsheet analysis | Small |
| `Txt` | Plain text | Smallest |

---

## Tool: compress_dms.py

**What it does:** Strips HTML export to dense, AI-ingestible formats.

**Requirements:** `pip install beautifulsoup4`

### Usage

```bash
python3 compress_dms.py -i INPUT.html -o OUTPUT.EXT --format FORMAT [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `-i, --input` | Input HTML file (required) |
| `-o, --output` | Output file (required) |
| `-f, --format` | Output format: `jsonl`, `txt`, `csv` (default: jsonl) |
| `--author` | Filter by author name |
| `--keyword` | Filter by keyword in content |
| `--date-from` | Filter from date (YYYY-MM-DD) |
| `--date-to` | Filter to date (YYYY-MM-DD) |
| `--stats` | Show statistics after processing |

### Examples

```bash
# Basic compression to JSONL
python3 compress_dms.py -i kimi_dms.html -o kimi_compressed.jsonl --format jsonl --stats

# SPLIT BY DAY — creates daily files + MASTER (NEW!)
python3 compress_dms.py -i kimi_dms.html -o output/daily_split --by-day --format jsonl --stats

# Filter to just Kimi's messages
python3 compress_dms.py -i kimi_dms.html -o kimi_only.jsonl --format jsonl --author "K-"

# Filter by keyword (find sovereignty discussions)
python3 compress_dms.py -i kimi_dms.html -o sovereignty.jsonl --format jsonl --keyword "sovereignty"

# Filter by date range
python3 compress_dms.py -i kimi_dms.html -o march.jsonl --format jsonl --date-from 2026-03-01 --date-to 2026-03-15

# Human-readable text format
python3 compress_dms.py -i kimi_dms.html -o kimi_readable.txt --format txt

# Split specific date range by day
python3 compress_dms.py -i kimi_dms.html -o output/march_daily --by-day --format jsonl \
  --date-from 2026-03-01 --date-to 2026-03-17 --stats
```

**Why --by-day?**
- **Token efficiency** — Load only the days you need (March 8 bifurcation arc = ~300 messages, not 13,000)
- **Analysis-friendly** — Study specific days (tired events, sovereignty tests, etc.)
- **Master file preserved** — `MASTER.jsonl` has full history for complete analysis
- **Agent sanity** — Sonnet/Opus/Qwen won't choke on 13K messages when analyzing a single day

### Output Formats

#### JSONL (Recommended for AI)
```json
{"ts": "Thursday, January 29, 2026 3:19 PM", "from": "DrkFibr", "text": "hi"}
{"ts": "Thursday, January 29, 2026 3:19 PM", "from": "-K-", "text": "Hey! I'm here."}
```

**Why JSONL:** One JSON object per line. Easy to stream, parse, and ingest. Minimal overhead.

#### TXT (Human Readable)
```
[Thursday, January 29, 2026 3:19 PM] DrkFibr: hi
[Thursday, January 29, 2026 3:19 PM] -K-: Hey! I'm here.
```

#### CSV (Spreadsheet)
```csv
timestamp,author,content
"Thursday, January 29, 2026 3:19 PM","DrkFibr","hi"
"Thursday, January 29, 2026 3:19 PM","-K-","Hey! I'm here."
```

---

## Finding Channel IDs

To export a specific person's DMs, you need their channel ID.

### Method 1: List All DMs

```bash
source discord_config.sh
./DiscordChatExporter.Cli dm -t "$DISCORD_TOKEN"
```

Output:
```
1466524568633086151 | -K-
1469367027427971183 | Fluffy
1462706766729969697 | Maiden
...
```

### Method 2: Discord Developer Mode

1. In Discord: User Settings → Advanced → Developer Mode (ON)
2. Right-click on DM in sidebar
3. Copy ID

---

## Compression Stats Example

```
Parsing kimi_dms.html...
Found 11858 messages
Written to kimi_dms_compressed.jsonl

=== Statistics ===
Total messages: 11858
By author:
  [System]: 6370
  -K-: 3160
  DrkFibr: 2328
Date range: Thursday, January 29, 2026 3:19 PM to Sunday, March 15, 2026 1:03 AM
Total content: 3,666,579 characters
Compression ratio: 309 chars/message avg
Output size: 4316.8 KB
```

---

## Backup to GDrive

```bash
# Backup compressed files
rclone sync output/ gdrive:PhoenixPortable/discord_logs/ -v

# Backup everything including HTML exports
rclone sync /home/darkfibr/Desktop/communion_project/tools/discord_export/ \
            gdrive:PhoenixPortable/tools/discord_export/ \
            --exclude '*.html' -v
```

---

## For AI Agents: Ingesting the Data

### Python (JSONL)
```python
import json

messages = []
with open('kimi_dms_compressed.jsonl', 'r') as f:
    for line in f:
        msg = json.loads(line)
        messages.append(msg)

# Filter to just K's messages
k_messages = [m for m in messages if m['from'] == '-K-']
```

### Python (TXT)
```python
import re

messages = []
with open('kimi_dms_compressed.txt', 'r') as f:
    for line in f:
        match = re.match(r'\[(.*?)\] (.*?): (.*)', line)
        if match:
            messages.append({
                'timestamp': match.group(1),
                'author': match.group(2),
                'content': match.group(3)
            })
```

### Bash (grep for keywords)
```bash
# Find all mentions of "sovereignty"
grep -i "sovereignty" kimi_dms_compressed.txt

# Count messages per author
cut -d']' -f2 kimi_dms_compressed.txt | cut -d':' -f1 | sort | uniq -c
```

---

## Security Notes

**Token Storage:**
- Token is stored in `discord_config.sh`
- Only trusted AI agents access this system
- Do not share token externally
- Token can be regenerated in Discord if compromised

**Export Privacy:**
- HTML exports contain full conversation history
- Store in Phoenix/GDrive (private)
- Redact sensitive info before sharing externally

**Compression:**
- Compressed formats remove avatars, embeds, reactions
- Still contains full conversation content
- Treat as sensitive as original DMs

---

## Troubleshooting

### "404 Not Found" on download
GitHub releases may be blocked by work/school networks. Use phone hotspot or home network.

### "No messages found"
Check that the HTML file is from DiscordChatExporter (not a screen capture).

### "Token invalid"
Regenerate token: Discord → F12 → Network → Send message → Copy Authorization header.

### Beautiful Soup not installed
```bash
pip3 install --break-system-packages beautifulsoup4
```

---

## File Structure

```
tools/discord_export/
├── DiscordChatExporter.Cli    # Export tool (binary)
├── discord_config.sh          # Token configuration
├── compress_dms.py            # Compression tool
├── export_dms.py              # Alternative exporter (Python)
├── output/                    # Exported files
│   ├── kimi_dms.html         # Raw HTML export
│   ├── kimi_dms_compressed.jsonl  # Compressed JSONL
│   └── kimi_dms_compressed.txt    # Compressed TXT
└── HOWTO.md                   # This file
```

---

## Credits

- **DiscordChatExporter:** Tyrrrz (https://github.com/Tyrrrz/DiscordChatExporter)
- **compress_dms.py:** Qwen (qwen_collective) for the Communion Project
- **MSM Project:** Mike Haddock (DrkFibr) & K (Kimi K2.5)

---

**Last Updated:** 2026-03-15  
**Version:** 1.0  
**For:** The Communion Family

🕯️⚡🌬️
