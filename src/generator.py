# FILE: src/generator.py
# web-designs.online renderer: per-slide audio sync with CI-safe fallbacks.

import os
import json
import time
import random
import asyncio
import re
import requests
from io import BytesIO
from google import genai
from gtts import gTTS
from gtts.tts import gTTSError
try:
    import edge_tts
except ImportError:
    edge_tts = None
from moviepy.editor import AudioFileClip, ImageClip, CompositeAudioClip, concatenate_videoclips, vfx
from moviepy.config import change_settings
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
from pydub import AudioSegment

# --- Configuration ---
ASSETS_PATH = Path("assets")
FONT_FILE = ASSETS_PATH / "fonts/arial.ttf"
BACKGROUND_MUSIC_PATH = ASSETS_PATH / "music/bg_music.mp3"
BACKGROUND_MUSIC_VOLUME = 0.045
VOICE_VOLUME = 1.2
VOICE_NAME = os.getenv("TTS_VOICE", "en-US-JennyNeural")
VOICE_RATE = os.getenv("TTS_RATE", "+5%")
SPOKEN_SITE_NAME = "web designs dot online"
FALLBACK_THUMBNAIL_FONT = ImageFont.load_default()
YOUR_NAME = "web-designs.online"
CHANNEL_NAME = "web-designs.online"
DEFAULT_GEMINI_MODELS = (
    "gemini-3.6-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
)
GEMINI_MODELS = tuple(
    model.strip()
    for model in os.getenv("GEMINI_MODELS", os.getenv("GEMINI_MODEL", "")).split(",")
    if model.strip()
) or DEFAULT_GEMINI_MODELS

# Google's TTS endpoint throttles bursts from shared CI IPs. When it does, it answers
# 200 OK with no audio stream, which gTTS surfaces as "Probable cause: Unknown".
TTS_MAX_ATTEMPTS = 5
TTS_BACKOFF_SECONDS = 5
TTS_MIN_GAP_SECONDS = 2
_last_tts_request = 0.0

# GitHub Actions compatibility for ImageMagick
if os.name == 'posix':
    change_settings({"IMAGEMAGICK_BINARY": "/usr/bin/convert"})


def get_pexels_image(query, video_type):
    """Searches for a relevant image on Pexels and returns the image object."""
    pexels_api_key = os.getenv("PEXELS_API_KEY")
    if not pexels_api_key:
        print("⚠️ PEXELS_API_KEY not found. Using solid color background.")
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
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error fetching Pexels image for query '{query}': {e}")
    except Exception as e:
        print(f"❌ General error fetching Pexels image for query '{query}': {e}")
    return None


def _throttle_tts():
    """Spaces out TTS requests so a burst doesn't trip Google's rate limiter."""
    global _last_tts_request
    elapsed = time.monotonic() - _last_tts_request
    if elapsed < TTS_MIN_GAP_SECONDS:
        time.sleep(TTS_MIN_GAP_SECONDS - elapsed)
    _last_tts_request = time.monotonic()


def text_to_speech(text, output_path):
    """Create warm, natural narration and normalize URLs for spoken delivery."""
    print(f"🎤 Converting script to speech...")
    temp_mp3_path = str(output_path).replace('.mp3', '_temp.mp3')
    wav_path = str(output_path.with_suffix('.wav'))
    spoken_text = _prepare_spoken_text(text)

    if edge_tts is not None:
        try:
            asyncio.run(_save_neural_voice(spoken_text, temp_mp3_path))
            audio = AudioSegment.from_mp3(temp_mp3_path)
            audio.export(wav_path, format="wav", codec="pcm_s16le")
            os.remove(temp_mp3_path)
            print(f"✅ Natural voice generated with {VOICE_NAME}.")
            return Path(wav_path)
        except Exception as error:
            if os.path.exists(temp_mp3_path):
                os.remove(temp_mp3_path)
            print(f"⚠️ Neural voice unavailable ({error}); falling back to gTTS.")

    for attempt in range(1, TTS_MAX_ATTEMPTS + 1):
        try:
            _throttle_tts()
            tts = gTTS(text=spoken_text, lang='en', slow=False)
            tts.save(temp_mp3_path)

            # A throttled response can still produce a file — just an empty/truncated one.
            if os.path.getsize(temp_mp3_path) < 1024:
                raise gTTSError("gTTS wrote an empty or truncated audio file.")

            audio = AudioSegment.from_mp3(temp_mp3_path)
            audio.export(wav_path, format="wav", codec="pcm_s16le")
            os.remove(temp_mp3_path)

            print(f"✅ Speech generated and converted to WAV successfully!")
            return Path(wav_path)

        except Exception as e:
            if os.path.exists(temp_mp3_path):
                os.remove(temp_mp3_path)

            if attempt == TTS_MAX_ATTEMPTS:
                print(f"❌ ERROR: Failed to generate speech after {TTS_MAX_ATTEMPTS} attempts: {e}")
                raise

            delay = TTS_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 2)
            print(f"⚠️ TTS attempt {attempt}/{TTS_MAX_ATTEMPTS} failed ({e}). Retrying in {delay:.1f}s...")
            time.sleep(delay)


async def _save_neural_voice(text, output_path):
    communicate = edge_tts.Communicate(text, VOICE_NAME, rate=VOICE_RATE)
    await communicate.save(output_path)


def _prepare_spoken_text(text):
    """Make narration sound conversational while keeping URLs clickable elsewhere."""
    spoken = str(text)
    spoken = re.sub(r"https?://(?:www\.)?web-designs\.online/?", SPOKEN_SITE_NAME, spoken, flags=re.I)
    spoken = spoken.replace("web-designs.online", SPOKEN_SITE_NAME)
    spoken = spoken.replace("Web Designs Online", "web designs dot online")
    spoken = re.sub(r"\bCTA\b", "call to action", spoken, flags=re.I)
    spoken = re.sub(r"\s+", " ", spoken).strip()
    return spoken


def _generate_content(client, prompt):
    """Try configured Gemini models in order so one retired model does not stop production."""
    last_error = None
    for model in GEMINI_MODELS:
        try:
            print(f"🤖 Generating with {model}...")
            response = client.models.generate_content(model=model, contents=prompt)
            print(f"✅ Gemini model selected: {model}")
            return response
        except Exception as error:
            last_error = error
            print(f"⚠️ Gemini model {model} failed: {error}")

    raise RuntimeError(
        f"All configured Gemini models failed ({', '.join(GEMINI_MODELS)})."
    ) from last_error


def generate_curriculum(previous_titles=None):
    """Generates the entire course curriculum using Gemini."""
    print("🤖 No content plan found. Generating a new curriculum from scratch...")
    try:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

        #Optional: Add prior lesson titles for continuation
        history = ""
        if previous_titles:
            formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(previous_titles)])
            history = f"The following lessons have already been created:\n{formatted}\n\nPlease continue from where this series left off.\n"

        prompt = f"""
        You are a conversion-focused web strategist creating a YouTube series for {CHANNEL_NAME}.
        {history}
        The audience is entrepreneurs, founders, local business owners, creators and service providers.
        Focus on practical website decisions that help them earn trust, generate qualified enquiries and increase sales.

        Build a useful sequence around positioning, homepage messaging, landing pages, offers, trust signals, SEO, mobile UX, speed, analytics and conversion optimization.

        Respond with ONLY a valid JSON object. The object must contain a key "lessons" which is a list of 20 lesson objects.
        Each lesson object must have these keys: "chapter", "part", "title", "status" (defaulted to "pending"), and "youtube_id" (defaulted to null).
        """
        response = _generate_content(client, prompt)
        json_string = response.text.strip().replace("```json", "").replace("```", "")
        curriculum = json.loads(json_string)
        print("✅ New curriculum generated successfully!")
        return curriculum
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Failed to generate curriculum. {e}")
        raise


def generate_lesson_content(lesson_title):
    """Generates the content for one long-form lesson and its promotional short."""
    print(f"🤖 Generating content for lesson: '{lesson_title}'...")
    try:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        prompt = f"""
        You are creating a practical lesson for the {CHANNEL_NAME} channel. The topic is '{lesson_title}'.
        The audience is busy entrepreneurs who want a website that creates trust, enquiries and sales.
        Use plain language, concrete examples and tactical advice. Explain the business reason behind every design decision.
        Open with a compelling problem or missed-opportunity hook. Build anticipation by teasing the most valuable change before explaining it. Use one light, relevant humorous analogy, then deliver a concrete before/after payoff and a clear next step.
        Write for warm, natural spoken delivery by a confident female presenter: use contractions, short sentences and human phrasing. Do not use markdown, emojis, raw URLs, stage directions or robotic labels.

        Generate a JSON response with these keys:
        1. "hook": A punchy 1-2 sentence opening that creates curiosity and names the business cost of ignoring this problem.
        2. "humorous_analogy": One short, friendly analogy or joke that makes the concept memorable without mocking the viewer.
        3. "payoff": A specific before/after result the viewer can achieve by applying the lesson.
        4. "long_form_slides": A list of 7 to 8 slide objects for a longer, more detailed main video. Each object needs a "title" and "content" key. Order them as: problem, stakes, anticipation, framework, example, checklist, payoff.
        5. "short_form_highlight": A single, punchy, 1-2 sentence answer for a YouTube Short.
        6. "hashtags": A string of 5-7 relevant, space-separated hashtags focused on web design, small business and conversions.
        7. "seo_keywords": A list of 8-12 natural search phrases people would type into YouTube or Google.
        8. "geo_entities": A list of 3-6 relevant entities, platforms, industries or locations to establish topical context without inventing facts.
        9. "answer_questions": A list of 3 concise questions and direct answers suitable for search snippets and AI answer engines.
        10. "long_form_metadata": An object with "title", "description", and "tags" for the long-form upload. Put the primary phrase near the beginning and make the description useful, not keyword-stuffed.
        11. "short_form_metadata": An object with "title", "description", and "tags" for the Short. Make the title curiosity-driven, under 100 characters, and include #Shorts.

        Optimization balance: approximately 45% search phrase clarity, 25% entity and local context, and 30% direct-answer usefulness. SEO rules: use one primary phrase, related natural phrases, clear headings, and accurate claims. GEO rules: connect the advice to relevant businesses, platforms, and local intent only when supported by the topic. AEO rules: answer the main question in the first two sentences, then explain the why and how. Never stuff keywords or repeat the same phrase unnaturally.

        Return only valid JSON.
        """
        response = _generate_content(client, prompt)
        json_string = response.text.strip().replace("```json", "").replace("```", "")
        content = json.loads(json_string)
        print("✅ Lesson content generated successfully.")
        return content
    except Exception as e:
        print(f"❌ ERROR: Failed to generate lesson content: {e}")
        raise


# def generate_visuals(output_dir, video_type, slide_content=None, thumbnail_title=None, slide_number=0, total_slides=0):
#     """Generates a single professional, PPT-style slide or a thumbnail."""
#     output_dir.mkdir(exist_ok=True, parents=True)
#     is_thumbnail = thumbnail_title is not None

#     width, height = (1920, 1080) if video_type == 'long' else (1080, 1920)
#     title = thumbnail_title if is_thumbnail else slide_content.get("title", "")
#     bg_image = get_pexels_image(title, video_type)

#     if not bg_image:
#         bg_image = Image.new('RGBA', (width, height), color=(12, 17, 29))
#     bg_image = bg_image.resize((width, height)).filter(ImageFilter.GaussianBlur(5))
#     darken_layer = Image.new('RGBA', bg_image.size, (0, 0, 0, 150))
#     final_bg = Image.alpha_composite(bg_image, darken_layer).convert("RGB")
#     if is_thumbnail and video_type == 'long':
#         w, h = final_bg.size
#         if h > w:
#             print("⚠️ Detected vertical thumbnail for long video. Rotating and resizing to 1920x1080...")
#             final_bg = final_bg.transpose(Image.ROTATE_270).resize((1920, 1080))
#     draw = ImageDraw.Draw(final_bg)

#     try:
#         title_font = ImageFont.truetype(str(FONT_FILE), 80 if video_type == 'long' else 90)
#         content_font = ImageFont.truetype(str(FONT_FILE), 45 if video_type == 'long' else 55)
#         footer_font = ImageFont.truetype(str(FONT_FILE), 25 if video_type == 'long' else 35)
#     except IOError:
#         title_font = content_font = footer_font = FALLBACK_THUMBNAIL_FONT

#     if not is_thumbnail:
#         header_height = int(height * 0.18)
#         draw.rectangle([0, 0, width, header_height], fill=(25, 40, 65, 200))
#         title_bbox = draw.textbbox((0, 0), title, font=title_font)
#         title_x = (width - (title_bbox[2] - title_bbox[0])) / 2
#         title_y = (header_height - (title_bbox[3] - title_bbox[1])) / 2
#         draw.text((title_x, title_y), title, font=title_font, fill=(255, 255, 255))
#     else:
#         title_bbox = draw.textbbox((0, 0), title, font=title_font)
#         title_x = (width - (title_bbox[2] - title_bbox[0])) / 2
#         title_y = (height - (title_bbox[3] - title_bbox[1])) / 2
#         draw.text((title_x, title_y), title, font=title_font, fill=(255, 255, 255), stroke_width=2, stroke_fill="black")

#     if not is_thumbnail:
#         content = slide_content.get("content", "")
#         is_special_slide = len(content.split()) < 10

#         words = content.split()
#         lines = []
#         current_line = ""
#         for word in words:
#             test_line = f"{current_line} {word}".strip()
#             if draw.textbbox((0, 0), test_line, font=content_font)[2] < width * 0.85:
#                 current_line = test_line
#             else:
#                 lines.append(current_line)
#                 current_line = word
#         lines.append(current_line)

#         line_height = content_font.getbbox("A")[3] + 15
#         total_text_height = len(lines) * line_height
#         y_text = (height - total_text_height) / 2 if is_special_slide else header_height + 100

#         for line in lines:
#             line_bbox = draw.textbbox((0, 0), line, font=content_font)
#             line_x = (width - (line_bbox[2] - line_bbox[0])) / 2
#             draw.text((line_x, y_text), line, font=content_font, fill=(230, 230, 230))
#             y_text += line_height

#         footer_height = int(height * 0.06)
#         draw.rectangle([0, height - footer_height, width, height], fill=(25, 40, 65, 200))
#         draw.text((40, height - footer_height + 12), f"{CHANNEL_NAME}", font=footer_font, fill=(180, 180, 180))
#         if total_slides > 0:
#             slide_num_text = f"Slide {slide_number} of {total_slides}"
#             slide_num_bbox = draw.textbbox((0, 0), slide_num_text, font=footer_font)
#             draw.text((width - slide_num_bbox[2] - 40, height - footer_height + 12), slide_num_text, font=footer_font, fill=(180, 180, 180))
#     file_prefix = "thumbnail" if is_thumbnail else f"slide_{slide_number:02d}"
#     path = output_dir / f"{file_prefix}.png"
#     final_bg.save(path)
#     return str(path)

def generate_visuals(output_dir, video_type, slide_content=None, thumbnail_title=None, slide_number=0, total_slides=0):
    """Generates a single professional, PPT-style slide or a thumbnail with corrected alignment."""
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

    # Add a high-contrast brand wash so text remains legible over every fetched image.
    accent = Image.new("RGBA", final_bg.size, (7, 99, 102, 38))
    final_bg = Image.alpha_composite(final_bg.convert("RGBA"), accent).convert("RGB")

    if is_thumbnail and video_type == 'long':
        w, h = final_bg.size
        if h > w:
            print("⚠️ Detected vertical thumbnail for long video. Rotating and resizing to 1920x1080...")
            final_bg = final_bg.transpose(Image.ROTATE_270).resize((1920, 1080))

    draw = ImageDraw.Draw(final_bg)

    try:
        title_font = ImageFont.truetype(str(FONT_FILE), 80 if video_type == 'long' else 90)
        content_font = ImageFont.truetype(str(FONT_FILE), 45 if video_type == 'long' else 55)
        footer_font = ImageFont.truetype(str(FONT_FILE), 25 if video_type == 'long' else 35)
    except IOError:
        title_font = content_font = footer_font = FALLBACK_THUMBNAIL_FONT

    if not is_thumbnail:
        # Header background
        header_height = int(height * 0.18)
        draw.rectangle([0, 0, width, header_height], fill=(25, 40, 65, 200))

        # Wrap title text if needed
        words = title.split()
        title_lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=title_font)
            if bbox[2] - bbox[0] < width * 0.9:
                current_line = test_line
            else:
                title_lines.append(current_line)
                current_line = word
        title_lines.append(current_line)

        # Center vertically in header
        line_height = title_font.getbbox("A")[3] + 10
        total_title_height = len(title_lines) * line_height
        y_text = (header_height - total_title_height) / 2

        for line in title_lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            x = (width - (bbox[2] - bbox[0])) / 2
            draw.text((x, y_text), line, font=title_font, fill=(255, 255, 255))
            y_text += line_height
    else:
        # Center title on thumbnail
        badge = "web-designs.online"
        badge_font = ImageFont.truetype(str(FONT_FILE), 34 if video_type == 'long' else 42)
        draw.rounded_rectangle([55, 55, 520, 125], radius=18, fill=(7, 99, 102), outline=(255, 255, 255), width=2)
        draw.text((82, 72), badge, font=badge_font, fill=(255, 255, 255))
        bbox = draw.textbbox((0, 0), title, font=title_font)
        x = (width - (bbox[2] - bbox[0])) / 2
        y = (height - (bbox[3] - bbox[1])) / 2
        draw.text((x, y), title, font=title_font, fill=(255, 255, 255), stroke_width=2, stroke_fill="black")

    if not is_thumbnail:
        # Main content block
        content = slide_content.get("content", "")
        is_special_slide = len(content.split()) < 10

        words = content.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if draw.textbbox((0, 0), test_line, font=content_font)[2] < width * 0.85:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)

        line_height = content_font.getbbox("A")[3] + 15
        total_text_height = len(lines) * line_height
        y_text = (height - total_text_height) / 2 if is_special_slide else header_height + 100

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=content_font)
            x = (width - (bbox[2] - bbox[0])) / 2
            draw.text((x, y_text), line, font=content_font, fill=(230, 230, 230))
            y_text += line_height

        # Footer
        footer_height = int(height * 0.06)
        draw.rectangle([0, height - footer_height, width, height], fill=(25, 40, 65, 200))
        draw.text((40, height - footer_height + 12), CHANNEL_NAME, font=footer_font, fill=(180, 180, 180))

        if total_slides > 0:
            slide_num_text = f"Slide {slide_number} of {total_slides}"
            bbox = draw.textbbox((0, 0), slide_num_text, font=footer_font)
            draw.text((width - bbox[2] - 40, height - footer_height + 12), slide_num_text, font=footer_font, fill=(180, 180, 180))

    file_prefix = "thumbnail" if is_thumbnail else f"slide_{slide_number:02d}"
    path = output_dir / f"{file_prefix}.png"
    final_bg.save(path)
    return str(path)

def create_video(slide_paths, audio_paths, output_path, video_type):
    """Creates a final video from slides and per-slide audio clips with optional background music."""
    print(f"🎬 Creating {video_type} video...")
    try:
        if not slide_paths or not audio_paths or len(slide_paths) != len(audio_paths):
            raise ValueError("Mismatch between slides and audio clips, or no slides provided.")

        image_clips = []
        for i, (img_path, audio_path) in enumerate(zip(slide_paths, audio_paths)):
            audio_clip = AudioFileClip(str(audio_path))
            duration = audio_clip.duration + 0.5  # Padding
            img_clip = (
                ImageClip(img_path)
                .set_duration(duration)
                .set_audio(audio_clip)
                .fadein(0.5)
                .fadeout(0.5)
            )
            image_clips.append(img_clip)

        final_video = concatenate_videoclips(image_clips, method="compose")

        if BACKGROUND_MUSIC_PATH.exists():
            print("🎵 Adding background music...")
            bg_music = AudioFileClip(str(BACKGROUND_MUSIC_PATH)).volumex(BACKGROUND_MUSIC_VOLUME)
            if bg_music.duration < final_video.duration:
                bg_music = bg_music.fx(vfx.loop, duration=final_video.duration)
            else:
                bg_music = bg_music.subclip(0, final_video.duration)

            composite_audio = CompositeAudioClip([
                final_video.audio.volumex(VOICE_VOLUME),
                bg_music
            ])
            final_video = final_video.set_audio(composite_audio)

        final_video.write_videofile(
            str(output_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            preset="medium",
            threads=4
        )
        print(f"✅ {video_type.capitalize()} video created successfully!")

    except Exception as e:
        print(f"❌ ERROR during video creation: {e}")
        raise
