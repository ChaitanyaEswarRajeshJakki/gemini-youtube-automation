import os
import google.generativeai as genai
from gtts import gTTS

# 1. Setup Environment
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")
genai.configure(api_key=api_key)

# 2. Ensure Output Directory Exists
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

def generate_content():
    print("Generating content...")
    
    # --- YOUR LOGIC HERE ---
    # Example: Generating a dummy file to test the pipeline
    text = "Your automation is working!"
    tts = gTTS(text=text, lang='en')
    
    # Save the file INSIDE the output/ directory
    file_path = os.path.join(output_dir, "output_video.mp3")
    tts.save(file_path)
    # -----------------------
    
    print(f"File saved successfully to: {file_path}")

if __name__ == "__main__":
    generate_content()
