import os
import sys
import google.generativeai as genai
from gtts import gTTS

# 1. Fetch API Key
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY not found in environment variables.")
    sys.exit(1)

# 2. Configure Client
genai.configure(api_key=api_key)

# 3. Setup Output Directory
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

def run_automation():
    print("Starting generation...")
    
    # Example logic using gTTS
    text = "Automation pipeline is successfully configured."
    tts = gTTS(text=text, lang='en')
    
    # Save file into the output/ folder
    file_path = os.path.join(output_dir, "status.mp3")
    tts.save(file_path)
    
    print(f"Success! File created at {file_path}")

if __name__ == "__main__":
    run_automation()
