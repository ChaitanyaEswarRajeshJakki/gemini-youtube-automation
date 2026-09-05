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
    return {"topic": topic["title"], "pillar": topic["pillar"], "audience": topic["audience"], "reason": topic["selection_reason"], "priority_score": topic["priority_score"], "seo_score": topic.get("seo_score", 0), "geo_score": topic.get("geo_score", 0), "aeo_score": topic.get("aeo_score", 0), "optimization_mix": config("channel.json").get("search_optimization_mix", {})}


def _metadata_value(metadata: dict, key: str, fallback: str) -> str:
    value = metadata.get(key, fallback)
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip() or fallback


def _format_tags(value: str) -> str:
    tags = [tag.strip().lstrip("#") for tag in value.replace("\n", ",").split(",") if tag.strip()]
    return ",".join(dict.fromkeys(tags))


def _build_long_description(topic, content, channel, cta) -> str:
    metadata = content.get("long_form_metadata", {})
    keywords = content.get("seo_keywords", [])
    questions = content.get("answer_questions", [])
    entities = content.get("geo_entities", [])
    answers = "\n".join(f"Q: {item.get('question', '')}\nA: {item.get('answer', '')}" for item in questions if isinstance(item, dict) and item.get("question") and item.get("answer"))
    return "\n\n".join(filter(None, [
        _metadata_value(metadata, "description", f"{topic['title']} explained for entrepreneurs and service businesses."),
        f"{channel['brand_promise']} Learn what to change, why it matters, and how to apply it today.",
        f"Free resource: {cta['lead_magnet']} at {cta.get('destination', 'https://web-designs.online')}",
        f"Search topics: {', '.join(keywords[:10])}" if keywords else "",
        f"Relevant context: {', '.join(entities[:6])}" if entities else "",
        answers,
        f"Subscribe to {channel['channel_name']} for practical website growth ideas.",
    ]))


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
    long_metadata = content.get("long_form_metadata", {})
    long_title = _metadata_value(long_metadata, "title", topic["title"])[:100]
    short_metadata = content.get("short_form_metadata", {})
    short_title = _metadata_value(short_metadata, "title", f"{content.get('short_form_highlight', topic['title'])} #Shorts")[:100]
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
    thumb = generate_visuals(OUTPUT_DIR, "long", thumbnail_title=long_title)
    topic["status"] = "ready"; persist_topic(topic)
    if stage == "render": return str(video_path)

    from src.uploader import upload_to_youtube
    description = _build_long_description(topic, content, channel, cta)
    long_tags = _format_tags(_metadata_value(long_metadata, "tags", content.get("hashtags", "webdesign,smallbusiness,conversionrateoptimization")))
    video_id = upload_to_youtube(video_path, long_title, description, long_tags, thumb)

    short_slide = {"title": short_title.replace(" #Shorts", ""), "content": content.get("short_form_highlight", payoff)}
    short_audio_path = text_to_speech(short_slide["content"], OUTPUT_DIR / f"short_audio_{unique_id}.mp3")
    short_slide_dir = OUTPUT_DIR / f"short_slides_{unique_id}"
    short_slide_path = generate_visuals(short_slide_dir, "short", slide_content=short_slide, slide_number=1, total_slides=1)
    short_video_path = OUTPUT_DIR / f"short_{unique_id}.mp4"
    create_video([short_slide_path], [short_audio_path], short_video_path, "short")
    short_thumb = generate_visuals(OUTPUT_DIR, "short", thumbnail_title=short_title.replace(" #Shorts", ""))
    short_description = _metadata_value(short_metadata, "description", f"{content.get('short_form_highlight', payoff)} Learn more at https://web-designs.online")
    short_tags = _format_tags(_metadata_value(short_metadata, "tags", content.get("hashtags", "webdesign,smallbusiness,Shorts")))
    short_video_id = upload_to_youtube(short_video_path, short_title, short_description, short_tags, short_thumb)
    topic["status"] = "published"; topic["youtube_id"] = video_id; topic["short_youtube_id"] = short_video_id; topic["published_at"] = now(); persist_topic(topic)
    append_history({"event": "published", "topic_id": topic["id"], "youtube_id": video_id, "short_youtube_id": short_video_id, "title": long_title})
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
