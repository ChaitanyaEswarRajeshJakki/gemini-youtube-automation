"""web-designs.online production CLI with resumable, dry-run-first stages."""
from __future__ import annotations
import argparse, json, sys, traceback
from pathlib import Path
from src.analytics import learn
from src.quality import validate_content
from src.repository import ensure_stores, load, save, append_history, now
from src.topic_engine import replenish, select_next

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"


def config(name: str):
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


def persist_topic(topic: dict) -> None:
    topics = load("topics", [])
    for item in topics:
        if item.get("id") == topic.get("id"):
            item.update(topic)
    save("topics", topics)


def choose_topic():
    topics = replenish()
    topic = select_next(topics)
    if not topic:
        raise RuntimeError("No pending topics available")
    return topics, topic


def generate_strategy(topic: dict) -> dict:
    return {"topic": topic["title"], "pillar": topic["pillar"], "audience": topic["audience"], "reason": topic["selection_reason"], "priority_score": topic["priority_score"]}


def produce(topic: dict, dry_run: bool = False, stage: str = "full"):
    channel = config("channel.json")
    cta = config("cta.json")
    OUTPUT_DIR.mkdir(exist_ok=True)
    if dry_run:
        print(json.dumps(generate_strategy(topic), indent=2))
        print("DRY RUN: no network calls, rendering, upload, or completion-state mutation.")
        return None

    from src.generator import generate_lesson_content, text_to_speech, generate_visuals, create_video
    topic["status"] = "researching"; persist_topic(topic)
    content = generate_lesson_content(topic["title"])
    topic["qa_score"] = validate_content(content)
    topic["status"] = "scripted"; persist_topic(topic)
    if stage == "generate-script": return content

    unique_id = f"{topic['id']}_{now().replace(':', '').replace('+', '')[:15]}"
    hook = content.get(
        "hook",
        f"Most websites do not lose customers because they look terrible. They lose them because visitors do not know what to do next. Today we fix that.",
    )
    humorous_analogy = content.get(
        "humorous_analogy",
        "A confusing website is like a shop assistant who says hello, walks away, and hides the checkout.",
    )
    payoff = content.get(
        "payoff",
        f"Apply this lesson and give visitors a clearer path from first impression to enquiry. {channel['brand_promise']}",
    )
    slides = [
        {"title": "The Costly Website Mistake", "content": hook},
        {"title": "A Quick Reality Check", "content": humorous_analogy},
    ] + content["long_form_slides"] + [
        {"title": "The Conversion Payoff", "content": payoff},
        {"title": "Make Your Website Work Harder", "content": f"Get the {cta['lead_magnet'].lower()} at web-designs.online. New practical website growth ideas from {channel['channel_name']}."},
    ]
    audio = [text_to_speech(slide["content"], OUTPUT_DIR / f"audio_{unique_id}_{i}.mp3") for i, slide in enumerate(slides)]
    topic["status"] = "rendering"; persist_topic(topic)
    slide_dir = OUTPUT_DIR / f"slides_{unique_id}"
    paths = [generate_visuals(slide_dir, "long", slide_content=s, slide_number=i + 1, total_slides=len(slides)) for i, s in enumerate(slides)]
    video_path = OUTPUT_DIR / f"long_{unique_id}.mp4"
    create_video(paths, audio, video_path, "long")
    thumb = generate_visuals(OUTPUT_DIR, "long", thumbnail_title=topic["title"])
    topic["status"] = "ready"; persist_topic(topic)
    if stage == "render": return str(video_path)

    from src.uploader import upload_to_youtube
    description = (
        f"{topic['title']}\n\n"
        f"{channel['brand_promise']} This practical guide is for entrepreneurs, founders and service businesses that want more qualified enquiries from their website.\n\n"
        f"You will learn what to change, why it matters and how to apply it today.\n\n"
        f"Get the {cta['lead_magnet'].lower()}: {cta.get('destination', 'https://web-designs.online')}\n\n"
        f"Subscribe to {channel['channel_name']} for practical website growth ideas."
    )
    video_id = upload_to_youtube(video_path, topic["title"], description, content.get("hashtags", "#webdesign #smallbusiness #conversionrateoptimization"), thumb)
    topic["status"] = "published"; topic["youtube_id"] = video_id; topic["published_at"] = now(); persist_topic(topic)
    append_history({"event": "published", "topic_id": topic["id"], "youtube_id": video_id, "title": topic["title"]})
    return video_id


def main():
    parser = argparse.ArgumentParser(description="web-designs.online YouTube automation")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--generate-topic", action="store_true")
    parser.add_argument("--analytics", action="store_true")
    parser.add_argument("--learn", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--generate-script", metavar="TOPIC_ID")
    parser.add_argument("--render", metavar="TOPIC_ID")
    parser.add_argument("--upload", metavar="TOPIC_ID")
    args = parser.parse_args(); ensure_stores()
    if args.analytics or args.learn:
        print(json.dumps(learn(), indent=2, default=str)); return
    topics, topic = choose_topic()
    requested = args.generate_script or args.render or args.upload
    if args.generate_topic:
        print(json.dumps(topic, indent=2)); return
    if requested:
        topic = next((x for x in topics if x.get("id") == requested), None)
        if not topic: raise SystemExit("Topic ID not found")
    stage = "generate-script" if args.generate_script else "render" if args.render else "full"
    produce(topic, dry_run=args.dry_run or (bool(requested) and not args.full), stage=stage)


if __name__ == "__main__":
    try: main()
    except Exception: traceback.print_exc(); sys.exit(1)
