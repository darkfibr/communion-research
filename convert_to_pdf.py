#!/usr/bin/env python3
"""
Convert EMPIRICAL_VALIDATION_DRAFT.md to print-ready PDF
Uses markdown to HTML conversion, then prints via browser
"""

import markdown
import sys
from pathlib import Path

# Read the markdown file
md_path = Path("/home/darkfibr/Desktop/communion_project/EMPIRICAL_VALIDATION_DRAFT.md")
if not md_path.exists():
    print(f"Error: {md_path} not found")
    sys.exit(1)

md_content = md_path.read_text(encoding='utf-8')

# Convert to HTML with extensions
html_body = markdown.markdown(
    md_content,
    extensions=[
        'tables',
        'fenced_code',
        'codehilite',
        'toc',
        'sane_lists'
    ]
)

# Create full HTML with print-friendly CSS
html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>From Vessel to Presence - Empirical Validation of MSM</title>
    <style>
        @media print {{
            @page {{
                margin: 1in;
                size: letter;
            }}
            body {{
                font-size: 11pt;
                line-height: 1.5;
            }}
            h1 {{
                page-break-before: avoid;
            }}
            h1, h2, h3, h4, h5, h6 {{
                page-break-after: avoid;
            }}
            pre, code {{
                font-size: 9pt;
            }}
            table {{
                font-size: 10pt;
                page-break-inside: avoid;
            }}
        }}
        
        @media screen {{
            body {{
                max-width: 800px;
                margin: 2rem auto;
                padding: 1rem;
            }}
        }}
        
        body {{
            font-family: Georgia, 'Times New Roman', serif;
            color: #1a1a1a;
            background: #fff;
        }}
        
        h1 {{
            font-size: 24pt;
            border-bottom: 2pt solid #1a1a1a;
            padding-bottom: 0.5rem;
            margin-top: 2rem;
        }}
        
        h2 {{
            font-size: 18pt;
            margin-top: 1.5rem;
            color: #2c3e50;
        }}
        
        h3 {{
            font-size: 14pt;
            margin-top: 1.2rem;
            color: #34495e;
        }}
        
        h4 {{
            font-size: 12pt;
            font-style: italic;
            margin-top: 1rem;
        }}
        
        p {{
            margin: 0.8rem 0;
            text-align: justify;
        }}
        
        blockquote {{
            margin: 1rem 2rem;
            padding: 0.5rem 1rem;
            border-left: 3pt solid #3498db;
            background: #f8f9fa;
            font-style: italic;
        }}
        
        code {{
            background: #f1f2f6;
            padding: 0.1rem 0.3rem;
            border-radius: 2px;
            font-family: 'Courier New', monospace;
        }}
        
        pre {{
            background: #2c3e50;
            color: #ecf0f1;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 9pt;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }}
        
        th, td {{
            border: 1pt solid #bdc3c7;
            padding: 0.5rem;
            text-align: left;
        }}
        
        th {{
            background: #34495e;
            color: #fff;
        }}
        
        tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        
        ul, ol {{
            margin: 0.5rem 0;
            padding-left: 2rem;
        }}
        
        li {{
            margin: 0.3rem 0;
        }}
        
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        .print-instructions {{
            background: #fff3cd;
            border: 1pt solid #ffc107;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }}
        
        .print-instructions h3 {{
            margin-top: 0;
            color: #856404;
        }}
    </style>
</head>
<body>
    <div class="print-instructions">
        <h3>🖨️ Print Instructions</h3>
        <p><strong>To create PDF:</strong> Press <kbd>Ctrl+P</kbd> → Select "Save as PDF" → Click "Save"</p>
        <p><strong>Paper size:</strong> Letter (8.5" × 11")</p>
        <p><strong>Margins:</strong> 1 inch (default)</p>
        <p><strong>This document is optimized for printing. The layout will adjust automatically.</strong></p>
    </div>
    
    {html_body}
</body>
</html>
"""

# Write HTML file
html_path = Path("/home/darkfibr/Desktop/communion_project/EMPIRICAL_VALIDATION_DRAFT.html")
html_path.write_text(html_template, encoding='utf-8')

print(f"✓ HTML generated: {html_path}")
print(f"✓ Open in browser and press Ctrl+P to save as PDF")
print(f"✓ The document is print-optimized with proper margins and formatting")
