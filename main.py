import os
import re
import sys
import json
import datetime
import time
import traceback
from pathlib import Path
from src.generator import (
    generate_curriculum,
    generate_lesson_content,
    text_to_speech,
    generate_visuals,
    create_video,
    YOUR_NAME
)
from src.uploader import upload_to_youtube

CONTENT_PLAN_FILE = Path("content_plan.json")
OUTPUT_DIR = Path("output")
LESSONS_PER_RUN = 1

def get_content_plan():
    if not CONTENT_PLAN_FILE.exists():
        print("📄 content_plan.json not found. Generating new plan...")
        new_plan = generate_curriculum()
        with open(CONTENT_PLAN_FILE, 'w') as f:
            json.dump(new_plan, f, indent=2)
        print(f"✅ New curriculum saved to {CONTENT_PLAN_FILE}")
        return new_plan
    else:
        try:
            with open(CONTENT_PLAN_FILE, 'r') as f:
                plan = json.load(f)
            if not plan.get("lessons") or not isinstance(plan["lessons"], list):
                raise ValueError("⚠️ Invalid or empty lesson plan detected.")
            return plan
        except Exception as e:
            print(f"❌ ERROR loading existing plan: {e}. Regenerating...")
            new_plan = generate_curriculum()
            with open(CONTENT_PLAN_FILE, 'w') as f:
                json.dump(new_plan, f, indent=2)
            return new_plan


def update_content_plan(plan):
    with open(CONTENT_PLAN_FILE, 'w') as f:
        json.dump(plan, f, indent=2)


def produce_lesson_videos(lesson):
    print(f"\n▶️ Starting production for Lesson: '{lesson['title']}'")
    chapter_safe = re.sub(r'[^\w]', '_', str(lesson['chapter'])).strip('_')
    part_safe = re.sub(r'[^\w]', '_', str(lesson['part'])).strip('_')
    unique_id = f"{datetime.datetime.now().strftime('%Y%m%d')}_{chapter_safe}_{part_safe}"

    lesson_content = generate_lesson_content(lesson['title'])

    print("\n--- Producing Long-Form Video ---")

    intro_slide = {"title": lesson['title'], "content": f"The reality of {lesson['title']}..."}
    outro_slide = {"title": "The Wrap Up", "content": "That's the truth about it. If you want more, hit subscribe."}
    all_slides = [intro_slide] + lesson_content['long_form_slides'] + [outro_slide]

    # Humanized, conversational script segments
    slide_scripts = [
        f"You ever wonder why {lesson['title']} happened? It's not just business—it's pure, unadulterated human stupidity. Let's break it down.",
        *[s['content'] for s in lesson_content['long_form_slides']],
        "Look, money is weird. If you want more stories about people fumbling their finances, hit subscribe."
    ]

    slide_audio_paths = []
    for i, script in enumerate(slide_scripts):
        audio_path = OUTPUT_DIR / f"audio_slide_{i+1}_{unique_id}.mp3"
        wav_path = text_to_speech(script, audio_path)
        slide_audio_paths.append(wav_path)
    print(f"🎧 Total slide audios: {len(slide_audio_paths)}")

    slide_dir = OUTPUT_DIR / f"slides_long_{unique_id}"
    slide_paths = []
    for i, slide in enumerate(all_slides):
        path = generate_visuals(
            output_dir=slide_dir,
            video_type='long',
            slide_content=slide,
            slide_number=i + 1,
            total_slides=len(all_slides)
        )
        slide_paths.append(path)

    long_video_path = OUTPUT_DIR / f"long_video_{unique_id}.mp4"
    print(f"🎥 Creating long-form video at: {long_video_path}")
    create_video(slide_paths, slide_audio_paths, long_video_path, 'long')

    long_thumb_path = generate_visuals(
        output_dir=OUTPUT_DIR,
        video_type='long',
        thumbnail_title=lesson['title']
    )

    print("\n--- Producing Short Video ---")
    short_script = (f"{lesson_content['short_form_highlight']}\n\n"
    f"Link to the full story is in the description.")
    short_audio_mp3_path = OUTPUT_DIR / f"short_audio_{unique_id}.mp3"
    short_audio_path = text_to_speech(short_script, short_audio_mp3_path)

    short_slide_dir = OUTPUT_DIR / f"slides_short_{unique_id}"
    short_slide_content = {
        "title": "Quick Tip!",
        "content": f"{lesson_content['short_form_highlight']}"
    }
    short_slide_path = generate_visuals(
        output_dir=short_slide_dir,
        video_type='short',
        slide_content=short_slide_content,
        slide_number=1,
        total_slides=1
    )

    short_video_path = OUTPUT_DIR / f"short_video_{unique_id}.mp4"
    print(f"🎥 Creating short video at: {short_video_path}")
    create_video([short_slide_path], [short_audio_path], short_video_path, 'short')

    short_thumb_path = generate_visuals(
        output_dir=OUTPUT_DIR,
        video_type='short',
        thumbnail_title=f"Quick Tip: {lesson['title']}"
    )

    print("\n📤 Uploading to YouTube...")
    hashtags = lesson_content.get("hashtags", "#Finance #History #Money")
    long_desc = f"The real story behind {lesson['title']}.\n\n{hashtags}"
    long_tags = "Finance, History, Money, Viral, " + lesson['title'].replace(" ", ", ")

    long_video_id = upload_to_youtube(
        long_video_path,
        lesson['title'],
        long_desc,
        long_tags,
        long_thumb_path
    )

    if long_video_id:
        print("⏳ Waiting 30 seconds before uploading the short...")
        time.sleep(30)
        short_title = f"{lesson['title']} explained #Shorts"
        short_desc = (f"{lesson_content['short_form_highlight']}\n\n"
                      f"Watch the full story here: https://www.youtube.com/watch?v={long_video_id}\n\n"
                      f"{hashtags}")
        upload_to_youtube(
            short_video_path,
            short_title.strip(),
            short_desc,
            "Finance,Shorts,History",
            short_thumb_path
        )
        return long_video_id
    return None


def main():
    print("🚀 Starting Autonomous Viral Content Generator")
    print(f"📁 Current working dir: {os.getcwd()}")

    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        plan = get_content_plan()
        pending = [(i, lesson) for i, lesson in enumerate(plan['lessons']) if lesson['status'] == 'pending']

        if not pending:
            print("🎉 All lessons produced! Generating new content...")
            previous_titles = [lesson['title'] for lesson in plan['lessons']]
            new_plan = generate_curriculum(previous_titles=previous_titles)
            update_content_plan(new_plan)
            plan = new_plan
            pending = [(i, lesson) for i, lesson in enumerate(new_plan['lessons']) if lesson['status'] == 'pending']

        failed_lessons = []
        for lesson_index, lesson in pending[:LESSONS_PER_RUN]:
            try:
                video_id = produce_lesson_videos(lesson)
                if video_id:
                    for original_lesson in plan['lessons']:
                        if original_lesson['title'].strip().lower() == lesson['title'].strip().lower():
                            original_lesson['status'] = 'complete'
                            original_lesson['youtube_id'] = video_id
                            break
                    print(f"✅ Completed: {lesson['title']}")
                else:
                    failed_lessons.append(lesson['title'])
            except Exception as e:
                traceback.print_exc()
                failed_lessons.append(lesson['title'])
            finally:
                update_content_plan(plan)

        if failed_lessons:
            sys.exit(1)

    except Exception as e:
        traceback.print_exc()
        sys.exit(1)

    try:
        for file in OUTPUT_DIR.glob("*.wav"):
            file.unlink()
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")

if __name__ == "__main__":
    main()
