import os
import json
import requests
import re
from io import BytesIO
from google import genai
from gtts import gTTS
from moviepy.editor import AudioFileClip, ImageClip, CompositeAudioClip, concatenate_videoclips, vfx
from moviepy.config import change_settings
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
from pydub import AudioSegment

# --- Configuration ---
ASSETS_PATH = Path("assets")
FONT_FILE = ASSETS_PATH / "fonts/arial.ttf"
BACKGROUND_MUSIC_PATH = ASSETS_PATH / "music/bg_music.mp3"
FALLBACK_THUMBNAIL_FONT = ImageFont.load_default()
YOUR_NAME = "NeonSteel"

# --- The "Human" Persona ---
SYSTEM_PROMPT = """
You are a witty, street-smart financial commentator. 
- NEVER identify as an AI, bot, or automated system. 
- Write like a human talking to a friend at a bar.
- Use strong opinions: say 'I think', 'It's insane that', or 'Honestly'.
- Keep sentences short, punchy, and conversational.
- Never use 'educational' phrases like 'In this lesson' or 'Today we will learn'. 
- Just jump straight into the drama of the financial event.
"""

# GitHub Actions compatibility for ImageMagick
if os.name == 'posix':
    change_settings({"IMAGEMAGICK_BINARY": "/usr/bin/convert"})

def extract_json(response_text):
    """Robustly extracts JSON from LLM text output by finding the first { and last }."""
    # Find the first { and last }
    match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse found JSON: {e}")
            raise
    else:
        print(f"⚠️ Raw response did not contain valid JSON structure: {response_text[:100]}...")
        raise ValueError("LLM did not return valid JSON structure.")

def get_pexels_image(query, video_type):
    """Searches for a relevant image on Pexels."""
    pexels_api_key = os.getenv("PEXELS_API_KEY")
    if not pexels_api_key:
        return None

    orientation = 'landscape' if video_type == 'long' else 'portrait'
    try:
        headers = {"Authorization": pexels_api_key}
        params = {"query": f"abstract {query}", "per_page": 1, "orientation": orientation}
        response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get('photos'):
            image_url = data['photos'][0]['src']['large2x']
            image_response = requests.get(image_url, timeout=15)
            image_response.raise_for_status()
            return Image.open(BytesIO(image_response.content)).convert("RGBA")
    except Exception as e:
        print(f"⚠️ Pexels error: {e}")
    return None

def text_to_speech(text, output_path):
    """Converts text to speech using gTTS."""
    try:
        temp_mp3_path = str(output_path).replace('.mp3', '_temp.mp3')
        wav_path = str(output_path.with_suffix('.wav'))

        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(temp_mp3_path)

        audio = AudioSegment.from_mp3(temp_mp3_path)
        audio.export(wav_path, format="wav", codec="pcm_s16le")
        os.remove(temp_mp3_path)
        return Path(wav_path)
    except Exception as e:
        print(f"❌ Speech Error: {e}")
        raise

def generate_curriculum(previous_titles=None):
    """Generates the course curriculum using the persona."""
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    history = ""
    if previous_titles:
        formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(previous_titles)])
        history = f"Already covered:\n{formatted}\n\nContinue the series.\n"

    prompt = f"Generate a YouTube curriculum for 'AI for Developers by {YOUR_NAME}'. {history} Respond in JSON with a 'lessons' key (list of 20 objects: chapter, part, title, status)."
    
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=prompt,
        config={"system_instruction": SYSTEM_PROMPT}
    )
    return extract_json(response.text)

def generate_lesson_content(lesson_title):
    """Generates lesson content using the persona."""
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = f"Create a lesson for 'AI for Developers' about '{lesson_title}'. Generate JSON with: long_form_slides (7-8 objects), short_form_highlight (1-2 sentences), hashtags."
    
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=prompt,
        config={"system_instruction": SYSTEM_PROMPT}
    )
    return extract_json(response.text)

def generate_visuals(output_dir, video_type, slide_content=None, thumbnail_title=None, slide_number=0, total_slides=0):
    """Generates a professional slide or thumbnail."""
    output_dir.mkdir(exist_ok=True, parents=True)
    is_thumbnail = thumbnail_title is not None
    width, height = (1920, 1080) if video_type == 'long' else (1080, 1920)
    title = thumbnail_title if is_thumbnail else slide_content.get("title", "")
    
    bg_image = get_pexels_image(title, video_type)
    if not bg_image:
        bg_image = Image.new('RGBA', (width, height), color=(12, 17, 29))
    bg_image = bg_image.resize((width, height)).filter(ImageFilter.GaussianBlur(5))
    darken_layer = Image.new('RGBA', bg_image.size, (0, 0, 0, 150))
    final_bg = Image.alpha_composite(bg_image, darken_layer).convert("RGB")

    draw = ImageDraw.Draw(final_bg)
    title_font = ImageFont.truetype(str(FONT_FILE), 80 if video_type == 'long' else 90)
    
    if not is_thumbnail:
        header_height = int(height * 0.18)
        draw.rectangle([0, 0, width, header_height], fill=(25, 40, 65, 200))
        draw.text((width//2, header_height//2), title, font=title_font, fill=(255, 255, 255), anchor="mm")
    
    path = output_dir / (f"thumbnail.png" if is_thumbnail else f"slide_{slide_number:02d}.png")
    final_bg.save(path)
    return str(path)

def create_video(slide_paths, audio_paths, output_path, video_type):
    """Combines assets into the final video."""
    image_clips = []
    for img_path, audio_path in zip(slide_paths, audio_paths):
        audio_clip = AudioFileClip(str(audio_path))
        img_clip = ImageClip(img_path).set_duration(audio_clip.duration + 0.5).set_audio(audio_clip).fadein(0.5).fadeout(0.5)
        image_clips.append(img_clip)

    final_video = concatenate_videoclips(image_clips, method="compose")
    
    if BACKGROUND_MUSIC_PATH.exists():
        bg_music = AudioFileClip(str(BACKGROUND_MUSIC_PATH)).volumex(0.05).fx(vfx.loop, duration=final_video.duration)
        final_video = final_video.set_audio(CompositeAudioClip([final_video.audio.volumex(1.2), bg_music]))

    final_video.write_videofile(str(output_path), fps=24, codec="libx264", audio_codec="aac")
