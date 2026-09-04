"""Atomic JSON persistence for the channel pipeline."""
from __future__ import annotations
import json, os, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

FILES = {"topics":"topics.json", "videos":"videos.json", "analytics":"analytics.json", "experiments":"experiments.json", "history":"content_history.json"}

def now(): return datetime.now(timezone.utc).isoformat()

def load(name, default):
    path = DATA / FILES[name]
    if not path.exists(): return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return default

def save(name, value):
    path = DATA / FILES[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists(): shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    fd, tmp = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle: json.dump(value, handle, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def append_history(event):
    history = load("history", [])
    history.append({**event, "recorded_at": now()})
    save("history", history)

def migrate_content_plan():
    legacy = ROOT / "content_plan.json"
    topics = load("topics", [])
    if topics or not legacy.exists(): return topics
    try: lessons = json.loads(legacy.read_text(encoding="utf-8")).get("lessons", [])
    except (OSError, json.JSONDecodeError): return []
    topics = [{"id": f"legacy-{i+1}", "title": item.get("title", ""), "pillar": "Website design fundamentals", "cluster": "legacy", "format": "tutorial", "difficulty": "beginner", "status": item.get("status", "pending"), "youtube_id": item.get("youtube_id"), "created_at": now(), "related_topic_ids": []} for i, item in enumerate(lessons) if item.get("title")]
    save("topics", topics)
    return topics

def ensure_stores():
    for name, default in (("topics", []), ("videos", []), ("analytics", []), ("experiments", []), ("history", [])): save(name, default) if not (DATA / FILES[name]).exists() else None
    return migrate_content_plan()
