import os
import google.generativeai as genai

# 1. Setup API Key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")

genai.configure(api_key=api_key)

# 2. Setup Output Directory
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

def run_pipeline():
    print("Starting generation...")
    # --- YOUR CORE LOGIC HERE ---
    # Example: Create a dummy file to verify the artifact upload
    with open(os.path.join(output_dir, "test_video.txt"), "w") as f:
        f.write("Pipeline Success!")
    print("Files saved to output/")

if __name__ == "__main__":
    run_pipeline()
