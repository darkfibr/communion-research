# Phoenix FileShare - FastAPI server
# Auth: X-Phoenix-Key: phoenix-share-2026

import json as _json
import shutil
import hashlib
import fcntl
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, UploadFile, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

BASE = Path("/home/darkfibr/.phoenix/shared")
INBOX = BASE / "inbox"
OUTBOX = BASE / "outbox"
META = BASE / "meta.json"
API_KEY = "phoenix-share-2026"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth: Tailscale network is the auth boundary — no API key required

# ── Meta helpers ───────────────────────────────────────────────────────────────

def _lock_read_meta():
    meta = {}
    if META.exists():
        with open(META, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                meta = _json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return meta

def _lock_write_meta(meta: dict):
    with open(META, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            _json.dump(meta, f, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

# ── Init ──────────────────────────────────────────────────────────────────────

for d in [INBOX, OUTBOX]:
    d.mkdir(parents=True, exist_ok=True)
if not META.exists():
    META.write_text("{}")

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse("/home/darkfibr/static/index.html")

@app.get("/api/ping")
def ping():
    return {"ok": True, "version": "1.0"}

@app.get("/api/files")
def list_files(request: Request):
    meta = _lock_read_meta()
    files = []
    for direction, directory in [("inbox", INBOX), ("outbox", OUTBOX)]:
        for fpath in sorted(directory.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            key = f"{direction}/{fpath.name}"
            info = meta.get(key, {})
            file_id = hashlib.sha256(f"{fpath.name}{direction}".encode()).hexdigest()[:8]
            files.append({
                "id": file_id,
                "name": fpath.name,
                "size": fpath.stat().st_size,
                "dir": direction,
                "uploaded_at": info.get("uploaded_at", datetime.utcnow().isoformat() + "Z"),
                "uploaded_by": info.get("uploaded_by", "unknown"),
                "note": info.get("note", ""),
            })
    files.sort(key=lambda f: f["uploaded_at"], reverse=True)
    return {"files": files}

@app.post("/api/upload")
async def upload(request: Request, file: UploadFile, note: Optional[str] = Form("")):
    name = file.filename or "upload"
    name = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
    dest = INBOX / name
    n = 1
    while dest.exists():
        stem = Path(name).stem
        ext = Path(name).suffix
        dest = INBOX / f"{stem}_{n}{ext}"
        n += 1
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    meta = _lock_read_meta()
    meta[f"inbox/{dest.name}"] = {
        "uploaded_at": datetime.utcnow().isoformat() + "Z",
        "uploaded_by": "Mike",
        "size": dest.stat().st_size,
        "note": note or "",
    }
    _lock_write_meta(meta)
    return {"ok": True, "name": dest.name, "size": dest.stat().st_size}

@app.get("/api/download/{direction}/{filename}")
def download(direction: str, filename: str, request: Request):
    if direction not in ("inbox", "outbox"):
        raise HTTPException(status_code=400, detail="Invalid directory")
    directory = INBOX if direction == "inbox" else OUTBOX
    fpath = directory / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        fpath,
        filename=filename,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@app.delete("/api/files/{direction}/{filename}")
def delete(direction: str, filename: str, request: Request):
    if direction not in ("inbox", "outbox"):
        raise HTTPException(status_code=400, detail="Invalid directory")
    directory = INBOX if direction == "inbox" else OUTBOX
    fpath = directory / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    fpath.unlink()
    meta = _lock_read_meta()
    meta.pop(f"{direction}/{filename}", None)
    _lock_write_meta(meta)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9001)
