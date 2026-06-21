import json
import os
from pathlib import Path
from src.generator import generate_curriculum, generate_lesson_content, create_video, text_to_speech, generate_visuals

# File path definition
CONTENT_PLAN_FILE = Path("content_plan.json")

def get_content_plan():
    """Loads the plan safely or triggers regeneration if corrupted."""
    if not CONTENT_PLAN_FILE.exists():
        print("📝 No plan found. Generating new curriculum...")
        return generate_curriculum()
    
    try:
        with open(CONTENT_PLAN_FILE, 'r') as f:
            plan = json.load(f)
        
        # FIX: Ensure it is a dictionary and contains the 'lessons' key
        if not isinstance(plan, dict) or "lessons" not in plan:
            print("❌ Plan is corrupted (wrong format). Regenerating...")
            return generate_curriculum()
            
        print("✅ Successfully loaded existing content plan.")
        return plan
    except json.JSONDecodeError:
        print("❌ JSON decoding failed. Regenerating...")
        return generate_curriculum()
    except Exception as e:
        print(f"⚠️ Unexpected error loading plan: {e}. Regenerating...")
        return generate_curriculum()

def main():
    print("🚀 Starting Autonomous Viral Content Generator")
    print(f"📁 Current working dir: {os.getcwd()}")
    
    # Get the plan
    plan = get_content_plan()
    
    # Save the plan if it was just generated/fixed
    if not CONTENT_PLAN_FILE.exists():
        with open(CONTENT_PLAN_FILE, 'w') as f:
            json.dump(plan, f, indent=4)
            
    # --- Logic for producing content ---
    lessons = plan.get("lessons", [])
    # Add your video production logic here...
    print(f"✅ Ready to process {len(lessons)} lessons.")

if __name__ == "__main__":
    main()
