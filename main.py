import json
import os
from pathlib import Path
from src.generator import (
    generate_curriculum, 
    generate_lesson_content, 
    create_video, 
    text_to_speech, 
    generate_visuals
)

# File path definition
CONTENT_PLAN_FILE = Path("content_plan.json")
OUTPUT_DIR = Path("output")

def get_content_plan():
    """Loads the plan safely or triggers regeneration if corrupted."""
    if not CONTENT_PLAN_FILE.exists():
        print("📝 No plan found. Generating new curriculum...")
        return generate_curriculum()
    
    try:
        with open(CONTENT_PLAN_FILE, 'r') as f:
            plan = json.load(f)
        
        if not isinstance(plan, dict) or "lessons" not in plan:
            print("❌ Plan is corrupted (wrong format). Regenerating...")
            return generate_curriculum()
            
        print("✅ Successfully loaded existing content plan.")
        return plan
    except Exception as e:
        print(f"⚠️ Error loading plan: {e}. Regenerating...")
        return generate_curriculum()

def main():
    print("🚀 Starting Autonomous Viral Content Generator")
    
    # 1. Ensure Output Directory Exists
    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
    
    # 2. Get the plan
    plan = get_content_plan()
    
    # Save the plan if it was just generated
    if not CONTENT_PLAN_FILE.exists():
        with open(CONTENT_PLAN_FILE, 'w') as f:
            json.dump(plan, f, indent=4)
            
    # 3. Iterate through lessons
    lessons = plan.get("lessons", [])
    
    for i, lesson in enumerate(lessons):
        # Skip if already done
        if lesson.get("status") == "done":
            continue
            
        print(f"\n🎬 Processing Lesson {i+1}: {lesson['title']}...")
        
        try:
            # 4. Generate content structure
            content = generate_lesson_content(lesson['title'])
            slides = content.get("long_form_slides", [])
            
            slide_paths = []
            audio_paths = []
            
            # 5. Create assets (Visuals & Audio)
            for slide_num, slide_data in enumerate(slides):
                # Generate visual
                visual_path = generate_visuals(OUTPUT_DIR, "long", slide_content=slide_data, slide_number=slide_num)
                slide_paths.append(visual_path)
                
                # Generate audio (Assumes your LLM returns a 'text' key in the slide object)
                audio_path = text_to_speech(slide_data.get("text", "No content provided"), OUTPUT_DIR / f"audio_{i}_{slide_num}.mp3")
                audio_paths.append(audio_path)
            
            # 6. Create Video
            video_output_path = OUTPUT_DIR / f"long_video_{i:02d}.mp4"
            create_video(slide_paths, audio_paths, video_output_path, "long")
            
            # 7. Update status to 'done'
            lesson["status"] = "done"
            
            # Save progress after every lesson
            with open(CONTENT_PLAN_FILE, 'w') as f:
                json.dump(plan, f, indent=4)
                
            print(f"✅ Finished Lesson {i+1}: {lesson['title']}")
            
        except Exception as e:
            print(f"❌ Failed to process lesson {i+1}: {e}")
            continue # Move to next lesson if one fails

    print("\n🎉 All processing complete.")

if __name__ == "__main__":
    main()
