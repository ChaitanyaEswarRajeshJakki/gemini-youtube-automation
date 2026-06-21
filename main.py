import os
import google.generativeai as genai

# Fetch the key
api_key = os.environ.get("GEMINI_API_KEY")

# If the code reaches here, the key MUST be in the environment
if not api_key:
    raise ValueError("GEMINI_API_KEY is still not visible to the Python script.")

genai.configure(api_key=api_key)
print("Configuration successful.")
