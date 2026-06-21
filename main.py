import json
import os
import google.genai as genai
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
def generate_description(video_title):
    """Generates a high-CTR YouTube description with your automated link."""
    # Using the same client logic as your generator
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    
    prompt = f"""
    Write a punchy, high-CTR YouTube video description for a video titled: '{video_title}'.
    - Tone: Cynical, smart, business-focused (The 'Business Myth-Buster' persona).
    - Style: 2-3 sentences max. High energy. 
    - End with the CTA provided below.
    - DO NOT use generic AI hashtags.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=prompt
    )
    
    description_text = response.text
    
    # The "Golden" footer
    footer = f"""
    ---
    🚀 Grab the 'Founder’s Decision Matrix' (100% Free): 
    {GUMROAD_URL}
    
    Join the Myth-Buster newsletter for daily business teardowns that actually work.
    """
    
    return f"{description_text}\n{footer}"

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
            
            # 5. Generate and Save Description
            desc = generate_description(lesson['title'])
            with open(OUTPUT_DIR / f"description_{i:02d}.txt", "w") as f:
                f.write(desc)
            
            slide_paths = []
            audio_paths = []
            
            # 6. Create assets (Visuals & Audio)
            for slide_num, slide_data in enumerate(slides):
                visual_path = generate_visuals(OUTPUT_DIR, "long", slide_content=slide_data, slide_number=slide_num)
                slide_paths.append(visual_path)
                
                audio_path = text_to_speech(slide_data.get("text", "No content provided"), OUTPUT_DIR / f"audio_{i}_{slide_num}.mp3")
                audio_paths.append(audio_path)
            
            # 7. Create Video
            video_output_path = OUTPUT_DIR / f"long_video_{i:02d}.mp4"
            create_video(slide_paths, audio_paths, video_output_path, "long")
            
            # 8. Update status to 'done'
            lesson["status"] = "done"
            
            # Save progress after every lesson
            with open(CONTENT_PLAN_FILE, 'w') as f:
                json.dump(plan, f, indent=4)
                
            print(f"✅ Finished Lesson {i+1}: {lesson['title']} (Description saved!)")
            
        except Exception as e:
            print(f"❌ Failed to process lesson {i+1}: {e}")
            continue 

    print("\n🎉 All processing complete.")

if __name__ == "__main__":
    main()
