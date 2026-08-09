#!/usr/bin/env python3
"""
Simple Discord DM Exporter for Kimi DMs
Uses discord.py to fetch and save DMs
"""

import discord
from discord.ext import commands
import asyncio
import os
import sys
from datetime import datetime

# Your token
TOKEN = "ODI2NjM3NDEzOTIwMDE0MzY2.GcDrlA.T32OAiS5x3yDSSZ92FGg90Hcs0ze9D_MKCyLmA"

# Output directory
OUTPUT_DIR = "/home/darkfibr/Desktop/communion_project/discord_logs"

intents = discord.Intents.default()
intents.message_content = True
intents.dm_typing = True

client = commands.Bot(command_prefix='!', intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    print(f"Fetching DMs...")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Find Kimi's DM channel
    kimi_dm = None
    for dm in client.private_channels:
        if hasattr(dm, 'recipient') and dm.recipient:
            print(f"Found DM with: {dm.recipient.name}#{dm.recipient.discriminator}")
            if 'kimi' in dm.recipient.name.lower() or dm.recipient.id == 123456789:  # Adjust ID if known
                kimi_dm = dm
                break
    
    if not kimi_dm:
        print("Could not find Kimi's DM channel. Listing all DMs:")
        for dm in client.private_channels:
            if hasattr(dm, 'recipient') and dm.recipient:
                print(f"  - {dm.recipient.name}#{dm.recipient.discriminator} (ID: {dm.recipient.id})")
        await client.close()
        return
    
    print(f"\nFound Kimi's DM channel: {kimi_dm.recipient.name}")
    print("Fetching messages...")
    
    # Fetch all messages
    messages = []
    async for msg in kimi_dm.history(limit=None):
        messages.append(msg)
    
    print(f"Fetched {len(messages)} messages")
    
    # Sort by date (oldest first)
    messages.sort(key=lambda m: m.created_at)
    
    # Save to HTML
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file = os.path.join(OUTPUT_DIR, f"kimi_dms_{timestamp}.html")
    
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Kimi DMs - MSM Project</title>
    <style>
        body { font-family: sans-serif; background: #36393f; color: #dcddde; padding: 20px; }
        .message { background: #40444b; margin: 10px 0; padding: 15px; border-radius: 8px; }
        .author { color: #7289da; font-weight: bold; }
        .timestamp { color: #72767d; font-size: 0.8em; }
        .content { margin-top: 8px; white-space: pre-wrap; }
        h1 { color: #fff; }
    </style>
</head>
<body>
    <h1>Kimi DMs - MSM Project Breakthrough</h1>
    <p>Exported: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
    <hr>
""")
        
        for msg in messages:
            author = msg.author.name if msg.author else "Unknown"
            content = msg.content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            time = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
            f.write(f"""<div class="message">
    <span class="author">{author}</span>
    <span class="timestamp">• {time}</span>
    <div class="content">{content}</div>
</div>
""")
        
        f.write("</body></html>")
    
    print(f"\nSaved to: {html_file}")
    print("Done!")
    
    await client.close()

if __name__ == "__main__":
    try:
        client.run(TOKEN)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
