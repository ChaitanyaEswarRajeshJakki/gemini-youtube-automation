import os
import sys
from google import genai 
# 1. Fetch API Key
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    # If this triggers, your GitHub Secret is NOT being passed to the code.
    print("ERROR: GEMINI_API_KEY not found in environment variables.")
    sys.exit(1)

# 2. Setup Client & Output Directory
client = genai.Client(api_key=api_key)
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

def run_automation():
    print("Starting generation...")
    
    # Example logic: Generate a test file
    text = "Automation pipeline is successfully configured."
    tts = gTTS(text=text, lang='en')
    
    # Save file into the output/ folder
    file_path = os.path.join(output_dir, "status.mp3")
    tts.save(file_path)
    
    print(f"Success! File created at {file_path}")

if __name__ == "__main__":
    run_automation()
