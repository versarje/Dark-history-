import os
import re
import random
import requests
import asyncio
import edge_tts
import textwrap
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    ImageClip, AudioFileClip, CompositeVideoClip, 
    CompositeAudioClip, concatenate_videoclips
)

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

VOICE = "tr-TR-AhmetNeural"

def get_dark_history_query(index):
    """Sadece karanlık tarih ve gizem konseptli İngilizce arama terimleri döndürür."""
    queries = [
        "dark history",
        "ancient mystery",
        "dark history cinematic",
        "ancient ruins dark mystery",
        "dark moody historical background"
    ]
    return queries[index % len(queries)]

def get_system_font():
    """Linux ortamında sorunsuz çalışan font yolunu döndürür."""
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
    """Metni düzgün bir şekilde sararak şeffaf siyah kart üstünde PIL görseli oluşturur."""
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

def process_image_aspect_ratio(img_path, target_w=1080, target_h=1920):
    """Fotoğrafı esnetmeden, merkezden kırparak (crop) 1080x1920 yapar."""
    img = Image.open(img_path)
    w, h = img.size
    
    target_ratio = target_w / target_h
    img_ratio = w / h
    
    if img_ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
        
    img = img.resize((target_w, target_h), Image.LANCZOS)
    processed_path = f"processed_{os.path.basename(img_path)}"
    img.save(processed_path)
    return processed_path

async def generate_speech(text, output_audio):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_audio)

def fetch_pexels_image(query, index):
    """Sadece karanlık tarih ve gizem sorgularına göre Pexels API üzerinden görsel indirir."""
    if not PEXELS_API_KEY:
        raise ValueError("PEXELS_API_KEY bulunamadı!")
        
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&orientation=portrait&per_page=15"
    res = requests.get(url, headers=headers).json()
    photos = res.get("photos", [])
    
    if not photos:
        url = "https://api.pexels.com/v1/search?query=dark%20history&orientation=portrait&per_page=15"
        photos = requests.get(url, headers=headers).json().get("photos", [])

    selected_photo = random.choice(photos)
    img_url = selected_photo["src"].get("original", selected_photo["src"]["large2x"])

    img_data = requests.get(img_url).content
    temp_path = f"temp_img_{index}.jpg"
    with open(temp_path, "wb") as f:
        f.write(img_data)
        
    return process_image_aspect_ratio(temp_path)

def split_text_into_sentences(text):
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    return sentences

def send_telegram_video(video_path, caption=""):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️️ TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID eksik, gönderim atlanıyor.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    try:
        with open(video_path, "rb") as video_file:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
            files = {"video": video_file}
            requests.post(url, data=payload, files=files)
            print("✅ HD Video Telegram'a başarıyla iletildi!")
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

    print("🎙️️ Seslendirme üretiliyor (Edge-TTS)...")
    speech_audio_path = "speech.mp3"
    asyncio.run(generate_speech(tts_full_text, speech_audio_path))

    speech_clip = AudioFileClip(speech_audio_path)
    total_duration = speech_clip.duration + 1.0

    total_words = sum(len(s.split()) for s in sentences)
    
    image_clips = []
    text_clips = []
    temp_subtitle_files = []
    current_time = 0.0

    print("📸 Karanlık tarih ve gizem konseptli görseller çekiliyor...")
    for idx, sentence in enumerate(sentences):
        word_count = len(sentence.split())
        sentence_duration = max(2.2, (word_count / total_words) * total_duration)

        query = get_dark_history_query(idx)
        print(f"  [Cümle {idx+1}] Pexels Sorgusu: '{query}'")
        img_path = fetch_pexels_image(query, idx)
        
        img_clip = ImageClip(img_path)
        if hasattr(img_clip, 'with_duration'):
            img_clip = img_clip.with_duration(sentence_duration)
        else:
            img_clip = img_clip.set_duration(sentence_duration)
            
        image_clips.append(img_clip)

        # Alt Yazı Kartı
        f_size = 50 if idx == 0 else 42
        sub_img_path = create_subtitle_image(sentence, max_width=820, font_path=font_path, font_size=f_size)
        temp_subtitle_files.append(sub_img_path)

        txt_clip = ImageClip(sub_img_path)
        
        # Konumlandırma: Kanca Üstte (%20 Yükseklik), Diğer Altyazılar Ortada ('center')
        y_pos = 0.20 if idx == 0 else 'center'

        if hasattr(txt_clip, 'with_position'):
            txt_clip = (txt_clip.with_position(('center', y_pos), relative=True if idx == 0 else False)
                        .with_start(current_time)
                        .with_duration(sentence_duration))
        else:
            txt_clip = (txt_clip.set_position(('center', y_pos), relative=True if idx == 0 else False)
                        .set_start(current_time)
                        .set_duration(sentence_duration))

        text_clips.append(txt_clip)
        current_time += sentence_duration

    final_bg = concatenate_videoclips(image_clips)

    # Arka Plan Müzik Ayarı
    bg_music_path = os.path.join("assets", "suspense.mp3")
    if os.path.exists(bg_music_path):
        bg_music = AudioFileClip(bg_music_path)
        if bg_music.duration < total_duration:
            loop_count = int(total_duration // bg_music.duration) + 1
            bg_music = concatenate_videoclips([bg_music] * loop_count)

        if hasattr(bg_music, 'subclipped'):
            bg_music = bg_music.subclipped(0, total_duration)
        else:
            bg_music = bg_music.subclip(0, total_duration)

        if hasattr(bg_music, 'with_volume_scaling'):
            bg_music = bg_music.with_volume_scaling(0.15)
            speech_clip = speech_clip.with_volume_scaling(1.2)
        else:
            bg_music = bg_music.volumex(0.15)
            speech_clip = speech_clip.volumex(1.2)

        final_audio = CompositeAudioClip([speech_clip, bg_music])
    else:
        final_audio = speech_clip

    composite_elements = [final_bg] + text_clips
    final_video_clip = CompositeVideoClip(composite_elements)

    if hasattr(final_video_clip, 'with_audio'):
        final_video = final_video_clip.with_audio(final_audio)
    else:
        final_video = final_video_clip.set_audio(final_audio)

    output_filename = "dark_history_output.mp4"
    print("🚀 Video HD kalitede render ediliyor...")
    
    final_video.write_videofile(
        output_filename,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        preset="medium"
    )
    print("✅ HD Render tamamlandı!")

    # Temizlik
    for idx in range(len(sentences)):
        for f_path in [f"temp_img_{idx}.jpg", f"processed_temp_img_{idx}.jpg"]:
            if os.path.exists(f_path):
                os.remove(f_path)
                
    for sub_file in temp_subtitle_files:
        if os.path.exists(sub_file):
            os.remove(sub_file)

    if os.path.exists(speech_audio_path):
        os.remove(speech_audio_path)

    send_telegram_video(
        video_path=output_filename,
        caption="🎬 **Karanlık Tarih & Gizem Konseptli HD Video Hazır!**\n\nBeğenip Paylaşmayı Unutmayın ❤️"
    )

if __name__ == "__main__":
    create_video()
