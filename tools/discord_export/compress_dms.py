#!/usr/bin/env python3
"""
Discord DM Compressor for MSM Project
Strips HTML export to dense AI-ingestible format

Output formats:
  - jsonl: One JSON object per line (machine-readable)
  - txt: Plain text with timestamps (human-readable)
  - csv: CSV format (spreadsheet-compatible)

Usage:
  python3 compress_dms.py -i kimi_dms.html -o kimi_dms_compressed.jsonl --format jsonl
  python3 compress_dms.py -i kimi_dms.html -o kimi_dms_compressed.txt --format txt
  python3 compress_dms.py -i kimi_dms.html -o kimi_dms_compressed.csv --format csv
"""

import argparse
import json
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 required. Install: pip install beautifulsoup4")
    sys.exit(1)


def parse_discord_html(html_path: str) -> List[Dict]:
    """Parse Discord HTML export and return list of messages"""
    
    html_content = Path(html_path).read_text(encoding='utf-8')
    soup = BeautifulSoup(html_content, 'html.parser')
    
    messages = []
    
    # Find all message containers
    containers = soup.find_all('div', class_='chatlog__message-container')
    
    for container in containers:
        msg_id = container.get('data-message-id', '')
        
        # Extract author - try multiple classes
        author_el = container.find('span', class_='chatlog__author')
        if not author_el:
            # Try data attribute for system messages
            author_el = container.find('span', {'data-user-id': True})
        author = author_el.get_text(strip=True) if author_el else '[System]'
        
        # Extract timestamp from title attribute
        timestamp_el = container.find('span', class_='chatlog__timestamp')
        timestamp = timestamp_el.get('title', '') if timestamp_el else ''
        
        # Extract content
        content_el = container.find('div', class_='chatlog__content')
        if content_el:
            # Get text and clean it up
            content = content_el.get_text(separator=' ', strip=True)
            # Decode common HTML entities
            content = content.replace('\xa0', ' ')
        else:
            content = ''
        
        # Extract edited timestamp if present
        edited_el = container.find('span', class_='chatlog__edited-timestamp')
        edited = edited_el.get_text(strip=True) if edited_el else None
        
        messages.append({
            'id': msg_id,
            'timestamp': timestamp,
            'author': author,
            'content': content,
            'edited': edited
        })
    
    return messages


def format_jsonl(messages: List[Dict]) -> str:
    """Format messages as JSONL (one JSON object per line)"""
    lines = []
    for msg in messages:
        # Minimal format - just what AI needs
        line = json.dumps({
            'ts': msg['timestamp'],
            'from': msg['author'],
            'text': msg['content']
        }, ensure_ascii=False)
        lines.append(line)
    return '\n'.join(lines)


def format_txt(messages: List[Dict]) -> str:
    """Format messages as plain text with timestamps"""
    lines = []
    for msg in messages:
        line = f"[{msg['timestamp']}] {msg['author']}: {msg['content']}"
        lines.append(line)
    return '\n'.join(lines)


def format_csv(messages: List[Dict]) -> str:
    """Format messages as CSV"""
    lines = ['timestamp,author,content']
    for msg in messages:
        # Escape commas and quotes in content
        content = msg['content'].replace('"', '""')
        line = f'"{msg["timestamp"]}","{msg["author"]}","{content}"'
        lines.append(line)
    return '\n'.join(lines)


def filter_messages(messages: List[Dict], 
                    author: Optional[str] = None,
                    date_from: Optional[str] = None,
                    date_to: Optional[str] = None,
                    keyword: Optional[str] = None) -> List[Dict]:
    """Filter messages by criteria"""
    
    filtered = messages
    
    if author:
        filtered = [m for m in filtered if author.lower() in m['author'].lower()]
        
    if keyword:
        filtered = [m for m in filtered if keyword.lower() in m['content'].lower()]
        
    if date_from:
        filtered = [m for m in filtered if m['timestamp'] >= date_from]
        
    if date_to:
        filtered = [m for m in filtered if m['timestamp'] <= date_to]
        
    return filtered


def main():
    parser = argparse.ArgumentParser(description='Compress Discord DM exports for AI ingestion')
    parser.add_argument('-i', '--input', required=True, help='Input HTML file')
    parser.add_argument('-o', '--output', required=True, help='Output file (or directory for --by-day)')
    parser.add_argument('-f', '--format', choices=['jsonl', 'txt', 'csv'], default='jsonl',
                       help='Output format (default: jsonl)')
    parser.add_argument('--author', help='Filter by author name')
    parser.add_argument('--keyword', help='Filter by keyword in content')
    parser.add_argument('--date-from', help='Filter messages from this date (YYYY-MM-DD)')
    parser.add_argument('--date-to', help='Filter messages to this date (YYYY-MM-DD)')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--by-day', action='store_true', 
                       help='Split output into daily files (creates directory with YYYY-MM-DD files)')
    
    args = parser.parse_args()
    
    # Parse HTML
    print(f"Parsing {args.input}...")
    messages = parse_discord_html(args.input)
    print(f"Found {len(messages)} messages")
    
    # Filter
    if any([args.author, args.keyword, args.date_from, args.date_to]):
        messages = filter_messages(messages, args.author, args.date_from, 
                                   args.date_to, args.keyword)
        print(f"After filtering: {len(messages)} messages")
    
    # By-day split
    if args.by_day:
        
        # Group messages by date
        by_date = defaultdict(list)
        for msg in messages:
            # Extract date from timestamp (e.g., "Thursday, January 29, 2026 3:19 PM")
            ts = msg['timestamp']
            if ts:
                # Try to extract YYYY-MM-DD
                import re
                match = re.search(r'(\w+), (\w+) (\d+), (\d+)', ts)
                if match:
                    day_name, month_name, day, year = match.groups()
                    # Convert month name to number
                    months = {'January':'01','February':'02','March':'03','April':'04',
                             'May':'05','June':'06','July':'07','August':'08',
                             'September':'09','October':'10','November':'11','December':'12'}
                    month_num = months.get(month_name, '01')
                    date_key = f"{year}-{month_num}-{day.zfill(2)}"
                    by_date[date_key].append(msg)
        
        # Create output directory
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write daily files
        print(f"Splitting into {len(by_date)} daily files...")
        total_written = 0
        for date_key in sorted(by_date.keys()):
            day_msgs = by_date[date_key]
            day_file = output_dir / f"{date_key}.{args.format}"
            
            if args.format == 'jsonl':
                output = format_jsonl(day_msgs)
            elif args.format == 'txt':
                output = format_txt(day_msgs)
            elif args.format == 'csv':
                output = format_csv(day_msgs)
            
            day_file.write_text(output, encoding='utf-8')
            total_written += len(day_msgs)
            print(f"  {date_key}: {len(day_msgs)} messages → {day_file.name}")
        
        # Write master file
        master_file = output_dir / f"MASTER.{args.format}"
        if args.format == 'jsonl':
            output = format_jsonl(messages)
        elif args.format == 'txt':
            output = format_txt(messages)
        elif args.format == 'csv':
            output = format_csv(messages)
        master_file.write_text(output, encoding='utf-8')
        
        print(f"\nWritten {len(by_date)} daily files + MASTER to {output_dir}/")
        print(f"Total messages: {total_written}")
        
        # Stats
        if args.stats:
            print(f"\n=== Daily Breakdown ===")
            for date_key in sorted(by_date.keys()):
                print(f"  {date_key}: {len(by_date[date_key])} messages")
    
    else:
        # Single file output (original behavior)
        if args.format == 'jsonl':
            output = format_jsonl(messages)
        elif args.format == 'txt':
            output = format_txt(messages)
        elif args.format == 'csv':
            output = format_csv(messages)
        
        # Write
        Path(args.output).write_text(output, encoding='utf-8')
        print(f"Written to {args.output}")
        
        # Stats
        if args.stats and messages:
            print(f"\n=== Statistics ===")
            print(f"Total messages: {len(messages)}")
            authors = {}
            for msg in messages:
                authors[msg['author']] = authors.get(msg['author'], 0) + 1
            print("By author:")
            for author, count in sorted(authors.items(), key=lambda x: -x[1]):
                print(f"  {author}: {count}")
            
            # Date range
            if messages:
                print(f"Date range: {messages[0]['timestamp']} to {messages[-1]['timestamp']}")
            
            # Total characters
            total_chars = sum(len(m['content']) for m in messages)
            print(f"Total content: {total_chars:,} characters")
            print(f"Compression ratio: {total_chars / len(messages):.0f} chars/message avg")
            print(f"Output size: {len(output.encode('utf-8')) / 1024:.1f} KB")


if __name__ == '__main__':
    main()
