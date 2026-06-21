import os
import google.generativeai as genai
from gtts import gTTS

# 1. Critical Check: API Key
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY not found in environment variables.")
    raise ValueError("You must set the GEMINI_API_KEY secret in GitHub.")

# 2. Configure
genai.configure(api_key=api_key)
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

def main():
    print("Pipeline active...")
    
    # Simple test to confirm functionality
    text = "If you hear this, the automation pipeline is working."
    tts = gTTS(text=text, lang='en')
    
    # Save into output/ directory so GitHub can upload it
    file_path = os.path.join(output_dir, "test_audio.mp3")
    tts.save(file_path)
    
    print(f"Success! File created at {file_path}")

if __name__ == "__main__":
    main()
