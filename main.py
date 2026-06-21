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

    intro_slide = {"title": lesson['title'], "content": f"Chapter {lesson['chapter']} | Part {lesson['part']}"}
    outro_slide = {"title": "Thanks for Watching!", "content": "Like, Share & Subscribe for more daily AI content!\n#AIforDevelopers"}
    all_slides = [intro_slide] + lesson_content['long_form_slides'] + [outro_slide]

    slide_scripts = [
        f"Hello and welcome to AI for Developers. I'm {YOUR_NAME} talking bot. Today’s lesson is titled {lesson['title']}.",
        *[s['content'] for s in lesson_content['long_form_slides']],
        "Thanks for watching! If you found this helpful, make sure to subscribe to our channel and hit the like button."
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
    # short_script = f"{lesson_content['short_form_highlight']}"
    short_script = (f"{lesson_content['short_form_highlight']}\n\n"
    f"Link to the full lesson is in the description below.")
    short_audio_mp3_path = OUTPUT_DIR / f"short_audio_{unique_id}.mp3"
    short_audio_path = text_to_speech(short_script, short_audio_mp3_path)

    short_slide_dir = OUTPUT_DIR / f"slides_short_{unique_id}"
    short_slide_content = {
        "title": "Quick Tip!",
        "content": f"{lesson_content['short_form_highlight']}\n\n#AI for developers by chaitanya"
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
    hashtags = lesson_content.get("hashtags", "#AI #Developer #LearnAI")
    long_desc = f"Part of the 'AI for Developers' series by {YOUR_NAME}.\n\nToday's Lesson: {lesson['title']}\n\n{hashtags}"
    long_tags = "AI, Artificial Intelligence, Developer, Programming, Tutorial, " + lesson['title'].replace(" ", ", ")

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
        highlight = (lesson_content.get('short_form_highlight') or '').strip()
        if not highlight:
            highlight = f"AI Quick Tip: {lesson['title']}"
        short_title = f"{highlight[:90].rstrip()} #Shorts"
        # short_desc = f"Watch the full lesson with {YOUR_NAME} here: https://www.youtube.com/watch?v={long_video_id}\n\n#AI #Programming #Tech #Developer"
        short_desc = (f"{lesson_content['short_form_highlight']}\n\n"
                      f"Watch the full lesson with {YOUR_NAME} here: https://www.youtube.com/watch?v={long_video_id}\n\n"
                      f"{hashtags}")
        upload_to_youtube(
            short_video_path,
            short_title.strip(),
            short_desc,
            "AI,Shorts,TechTip",
            short_thumb_path
        )
        return long_video_id
    return None


def main():
    print("🚀 Starting Autonomous AI Course Generator")
    print(f"📁 Current working dir: {os.getcwd()}")
    print(f"📁 OUTPUT_DIR: {OUTPUT_DIR.resolve()}")

    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        print(f"📁 Created output folder: {OUTPUT_DIR.exists()}")
        plan = get_content_plan()
        pending = [(i, lesson) for i, lesson in enumerate(plan['lessons']) if lesson['status'] == 'pending']

        if not pending:
            print("🎉 All lessons produced! Generating new content plan to restart from scratch...")

            previous_titles = [lesson['title'] for lesson in plan['lessons']]
            new_plan = generate_curriculum(previous_titles=previous_titles)  # 🔁 Pass prior titles
            update_content_plan(new_plan)
            plan = new_plan
            pending = [(i, lesson) for i, lesson in enumerate(new_plan['lessons']) if lesson['status'] == 'pending']
            if not pending:
                print("⚠️ Curriculum generated but no valid lessons found.")
                return

        failed_lessons = []
        for lesson_index, lesson in pending[:LESSONS_PER_RUN]:
            try:
                video_id = produce_lesson_videos(lesson)
                if video_id:
                    for original_lesson in plan['lessons']:
                        if original_lesson['title'].strip().lower() == lesson['title'].strip().lower():
                            original_lesson['status'] = 'complete'
                            original_lesson['youtube_id'] = video_id
                            print(f"✅ Completed lesson: {lesson['title']}")
                            break
                    else:
                        print(f"⚠️ Could not find lesson in plan to mark as complete: {lesson['title']}")
                else:
                    print(f"❌ Upload failed (no video ID returned): {lesson['title']}")
                    failed_lessons.append(lesson['title'])
            except Exception as e:
                print(f"❌ Failed producing lesson: {lesson['title']}")
                traceback.print_exc()
                failed_lessons.append(lesson['title'])
            finally:
                update_content_plan(plan)
                print("📦 Content plan saved.")

        if failed_lessons:
            print(f"\n❌ PIPELINE FAILED — {len(failed_lessons)} lesson(s) did not complete:")
            for title in failed_lessons:
                print(f"   - {title}")
            sys.exit(1)

    except Exception as e:
        print("❌ Critical error in main()")
        traceback.print_exc()
        sys.exit(1)

    try:
        for file in OUTPUT_DIR.glob("*.wav"):
            file.unlink()
            print(f"🧹 Deleted: {file}")
    except Exception as e:
        print(f"⚠️ Could not clean up .wav files: {e}")

if __name__ == "__main__":
    main()
# Use this exact system instruction to ensure the "Funny Finance" tone
system_instruction = """
You are a world-class viral YouTube finance creator with a satirical, fast-paced, and witty personality. 
Your goal is to explain complex financial history in a way that is funny, high-retention, and addictive.

Rules:
1. Always start with a 'hook' that challenges a common belief.
2. Use sarcasm and humor to explain why humans make bad financial decisions.
3. NEVER provide actual financial advice.
4. Keep scripts under 60 seconds (approx 150 words).
5. Ensure the title is click-worthy and creates a 'curiosity gap'.
"""
