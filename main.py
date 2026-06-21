import os
import google.generativeai as genai
from gtts import gTTS

# Setup
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

def main():
    print("Script started.")
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("ERROR: API Key missing!")
        return

    # Simple test
    genai.configure(api_key=api_key)
    
    # Create test file to prove success
    with open(os.path.join(output_dir, "success.txt"), "w") as f:
        f.write("Pipeline ran successfully!")
    print("File created in output folder.")

if __name__ == "__main__":
    main()
