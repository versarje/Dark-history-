import os
import re
import random
import requests
import asyncio
import edge_tts
import textwrap
import urllib.parse
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip, 
    CompositeAudioClip, concatenate_videoclips
)

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

VOICE = "tr-TR-AhmetNeural"

def get_system_font():
    """Linux / GitHub Actions ortamında sorunsuz çalışan font yolunu döndürür."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
    ]
    for path in font_paths:
        if os.path.exists(path):
            return path
    return None

def clean_text_for_tts(text):
    """TTS okuması yaparken emoji ve sembolleri temizler."""
    cleaned = re.sub(r'[^\w\s,?!.çğıöşüÇĞİÖŞÜ]', '', text)
    return cleaned.strip()

def create_subtitle_image(text, max_width=860, font_path=None, font_size=46):
    """Metni şeffaf siyah kart üstünde dikey format için PIL görseline çevirir."""
    if font_path and os.path.exists(font_path):
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    avg_char_w = font.getlength("a") if hasattr(font, 'getlength') else 20
    max_chars_per_line = max(10, int(max_width / avg_char_w))
    wrapped_lines = textwrap.wrap(text, width=max_chars_per_line, break_long_words=False, break_on_hyphens=False)
    
    if not wrapped_lines:
        wrapped_lines = [text]

    line_widths = []
    line_heights = []
    
    for line in wrapped_lines:
        if hasattr(font, 'getbbox'):
            bbox = font.getbbox(line)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        else:
            w, h = 400, 50
        line_widths.append(w)
        line_heights.append(h + 14)

    total_w = max(line_widths) if line_widths else max_width
    total_h = sum(line_heights)

    pad_x, pad_y = 35, 25
    card_w = total_w + (pad_x * 2)
    card_h = total_h + (pad_y * 2)

    img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 190))
    draw = ImageDraw.Draw(img)

    curr_y = pad_y
    for i, line in enumerate(wrapped_lines):
        line_w = line_widths[i]
        line_x = (card_w - line_w) / 2
        draw.text((line_x, curr_y), line, font=font, fill=(255, 215, 0, 255))
        curr_y += line_heights[i]

    temp_path = f"temp_subtitle_{random.randint(1000,9999)}.png"
    img.save(temp_path)
    return temp_path

async def generate_speech(text, output_audio):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_audio)

def process_and_resize_image(img_path, target_w=1080, target_h=1920):
    """Görseli MoviePy resize kullanmadan doğrudan PIL ile 1080x1920 boyutlandırır (ANTIALIAS Hatasını Engeller)."""
    try:
        with Image.open(img_path) as img:
            img = img.convert("RGB")
            # Resampling filtresini yeni Pillow sürümleri ile uyumlu hale getiriyoruz
            resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
            img_resized = img.resize((target_w, target_h), resample_filter)
            img_resized.save(img_path)
    except Exception as e:
        print(f"  ⚠️ Görsel yeniden boyutlandırma hatası: {e}")

def generate_ai_image(sentence_text, index):
    """Pollinations.ai kullanarak cümleye uygun dikey yapay zeka görseli üretir."""
    temp_path = f"temp_img_{index}.jpg"
    
    cleaned_text = re.sub(r'[^\w\s]', '', sentence_text).strip()
    words = cleaned_text.split()
    base_keywords = " ".join(words[:4]) if words else "dark history"
    
    prompt = f"dark historical scene, cinematic lighting, realistic, {base_keywords}"
    encoded_prompt = urllib.parse.quote(prompt)
    
    ai_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true&seed={random.randint(1, 99999)}"

    try:
        res = requests.get(ai_url, timeout=10)
        if res.status_code == 200 and len(res.content) > 1000:
            with open(temp_path, "wb") as f:
                f.write(res.content)
            process_and_resize_image(temp_path)
            print(f"  🎨 [Cümle {index+1}] AI Görseli Üretildi!")
            return temp_path
    except Exception as e:
        print(f"  ⚠️ AI görseli zaman aşımına uğradı ({e}), Pexels/Yedek moda geçiliyor.")

    # Pexels Yedek
    if PEXELS_API_KEY:
        try:
            headers = {"Authorization": PEXELS_API_KEY}
            pexels_url = "https://api.pexels.com/v1/search?query=dark%20history&orientation=portrait&per_page=10"
            pexels_res = requests.get(pexels_url, headers=headers, timeout=5).json()
            photos = pexels_res.get("photos", [])
            if photos:
                selected_photo = random.choice(photos[:min(3, len(photos))])
                img_url = selected_photo["src"].get("original", selected_photo["src"]["large2x"])
                img_data = requests.get(img_url, timeout=5).content
                with open(temp_path, "wb") as f:
                    f.write(img_data)
                process_and_resize_image(temp_path)
                return temp_path
        except Exception:
            pass

    # Siyah Tuval Yedek
    Image.new('RGB', (1080, 1920), color=(15, 15, 15)).save(temp_path)
    return temp_path

def split_text_into_sentences(text):
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    return sentences

def send_telegram_video(video_path, caption=""):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram token eksik, gönderim atlanıyor.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    try:
        with open(video_path, "rb") as video_file:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
            files = {"video": video_file}
            requests.post(url, data=payload, files=files, timeout=60)
            print("✅ Video Telegram'a iletildi!")
    except Exception as e:
        print(f"❌ Telegram hatası: {e}")

def create_video():
    font_path = get_system_font()

    if not os.path.exists("metinler.txt"):
        raise FileNotFoundError("'metinler.txt' bulunamadı!")

    with open("metinler.txt", "r", encoding="utf-8") as f:
        full_text = f.read().strip()

    sentences = split_text_into_sentences(full_text)
    if not sentences:
        sentences = [full_text]
        
    call_to_action = "Beğenip Paylaşmayı Unutmayın ❤️"
    sentences.append(call_to_action)

    tts_sentences = [clean_text_for_tts(s) for s in sentences]
    tts_full_text = " ".join(tts_sentences)

    print("🎙️ Seslendirme üretiliyor (Edge-TTS)...")
    speech_audio_path = "speech.mp3"
    asyncio.run(generate_speech(tts_full_text, speech_audio_path))

    speech_clip = AudioFileClip(speech_audio_path)
    total_duration = speech_clip.duration + 0.8
    total_words = sum(len(s.split()) for s in sentences)
    
    image_clips = []
    text_clips = []
    temp_subtitle_files = []
    current_time = 0.0

    print("🤖 Yapay zeka ile cümleye özel görseller üretiliyor...")
    for idx, sentence in enumerate(sentences):
        word_count = len(sentence.split())
        sentence_duration = max(2.0, (word_count / total_words) * total_duration)

        # Yapay zeka görsel üretimi
        img_path = generate_ai_image(sentence, idx)
        
        # MoviePy'ın .resize() metodu yerine doğrudan PIL ile işlenmiş görseli ekliyoruz
        img_clip = ImageClip(img_path).set_duration(sentence_duration)
        image_clips.append(img_clip)

        f_size = 48 if idx == 0 else 40
        sub_img_path = create_subtitle_image(sentence, max_width=820, font_path=font_path, font_size=f_size)
        temp_subtitle_files.append(sub_img_path)

        y_pos = 380 if idx == 0 else 'center'
        txt_clip = (ImageClip(sub_img_path)
                    .set_position(('center', y_pos))
                    .set_start(current_time)
                    .set_duration(sentence_duration))

        text_clips.append(txt_clip)
        current_time += sentence_duration

    final_bg = concatenate_videoclips(image_clips)

    bg_music_path = os.path.join("assets", "suspense.mp3")
    if os.path.exists(bg_music_path):
        bg_music = AudioFileClip(bg_music_path)
        if bg_music.duration < total_duration:
            loop_count = int(total_duration // bg_music.duration) + 1
            bg_music = concatenate_videoclips([bg_music] * loop_count)

        bg_music = bg_music.subclip(0, total_duration).volumex(0.12)
        speech_clip = speech_clip.volumex(1.2)
        final_audio = CompositeAudioClip([speech_clip, bg_music])
    else:
        final_audio = speech_clip

    final_video = CompositeVideoClip([final_bg] + text_clips).set_audio(final_audio)

    output_filename = "dark_history_output.mp4"
    print("🚀 Video render ediliyor...")
    
    final_video.write_videofile(
        output_filename,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=2
    )

    # Temizlik
    for idx in range(len(sentences)):
        f_path = f"temp_img_{idx}.jpg"
        if os.path.exists(f_path):
            os.remove(f_path)
                
    for sub_file in temp_subtitle_files:
        if os.path.exists(sub_file):
            os.remove(sub_file)

    if os.path.exists(speech_audio_path):
        os.remove(speech_audio_path)

    send_telegram_video(
        video_path=output_filename,
        caption="🎬 **Yapay Zeka (AI) Tarafından Görselleri Üretilmiş HD Video!**"
    )

if __name__ == "__main__":
    create_video()
