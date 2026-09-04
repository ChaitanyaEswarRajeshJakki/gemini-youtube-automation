"""Web Designs Online production CLI."""
from __future__ import annotations
import argparse, json, os, sys, traceback
from pathlib import Path
from src.analytics import learn
from src.quality import validate_content
from src.repository import ensure_stores, load, save, append_history, now
from src.topic_engine import replenish, select_next
from src.uploader import upload_to_youtube

OUTPUT_DIR=Path("output")

def config(name): return json.loads((Path("config") / name).read_text(encoding="utf-8"))
def choose_topic():
    topics=replenish(); topic=select_next(topics)
    if not topic: raise RuntimeError("No pending topics available")
    return topics, topic

def generate_strategy(topic):
    return {"topic":topic["title"],"pillar":topic["pillar"],"audience":topic["audience"],"reason":topic["selection_reason"],"priority_score":topic["priority_score"]}

def produce(topic, dry_run=False):
    channel=config("channel.json"); OUTPUT_DIR.mkdir(exist_ok=True)
    if not dry_run:
        from src.generator import generate_lesson_content, text_to_speech, generate_visuals, create_video
        from src.uploader import upload_to_youtube
    if dry_run:
        print(json.dumps(generate_strategy(topic),indent=2)); print("DRY RUN: no rendering, upload, or completion state mutation."); return None
    topic["status"]="researching"; save("topics",load("topics",[]))
    content=generate_lesson_content(topic["title"]); qa=validate_content(content); topic["qa_score"]=qa; topic["status"]="scripted"
    unique_id=f"{topic['id']}_{now().replace(':','').replace('+','')[:15]}"
    slides=[{"title":topic["title"],"content":"A practical guide for Web Designs Online."}]+content["long_form_slides"]
    audio=[]
    for i, slide in enumerate(slides): audio.append(text_to_speech(slide["content"],OUTPUT_DIR/f"audio_{unique_id}_{i}.mp3"))
    topic["status"]="rendering"; save("topics",load("topics",[]))
    slide_dir=OUTPUT_DIR/f"slides_{unique_id}"; paths=[generate_visuals(slide_dir,"long",s,i+1,len(slides)) for i,s in enumerate(slides)]
    video_path=OUTPUT_DIR/f"long_{unique_id}.mp4"; create_video(paths,audio,video_path,"long")
    thumb=generate_visuals(OUTPUT_DIR,"long",thumbnail_title=topic["title"])
    topic["status"]="ready"; save("topics",load("topics",[]))
    video_id=upload_to_youtube(video_path,topic["title"],f"{topic['title']}\n\n{channel['lead_magnet']}",content.get("hashtags","#WebDesign"),thumb)
    if not video_id: raise RuntimeError("Upload did not return a video ID")
    topic["status"]="published"; topic["youtube_id"]=video_id; topic["published_at"]=now()
    topics=load("topics",[])
    for item in topics:
        if item.get("id")==topic["id"]: item.update(topic)
    save("topics",topics); append_history({"event":"published","topic_id":topic["id"],"youtube_id":video_id,"title":topic["title"]})
    return video_id

def main():
    parser=argparse.ArgumentParser(description="Web Designs Online YouTube automation")
    parser.add_argument("--dry-run",action="store_true"); parser.add_argument("--generate-topic",action="store_true"); parser.add_argument("--analytics",action="store_true"); parser.add_argument("--learn",action="store_true"); parser.add_argument("--full",action="store_true")
    parser.add_argument("--generate-script",metavar="TOPIC_ID"); parser.add_argument("--render",metavar="TOPIC_ID"); parser.add_argument("--upload",metavar="TOPIC_ID")
    args=parser.parse_args(); ensure_stores()
    if args.analytics or args.learn: print(json.dumps(learn(),indent=2,default=str)); return
    topics,topic=choose_topic()
    if args.generate_topic: print(json.dumps(topic,indent=2)); return
    if args.generate_script or args.render or args.upload:
        topic=next((x for x in topics if x.get("id")==next(v for v in (args.generate_script,args.render,args.upload) if v)),None)
        if not topic: raise SystemExit("Topic ID not found")
    produce(topic,args.dry_run or not args.full and bool(args.generate_script or args.render))

if __name__ == "__main__":
    try: main()
    except Exception: traceback.print_exc(); sys.exit(1)
