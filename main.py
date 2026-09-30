import os
import random
import requests
import asyncio
import edge_tts
from moviepy import (
    ImageClip, AudioFileClip, TextClip, CompositeVideoClip, 
    CompositeAudioClip, concatenate_videoclips
)

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

VOICE = "tr-TR-AhmetNeural"
SEARCH_KEYWORDS = ["ancient ruins", "fire burning", "dark smoke", "bronze statue", "spooky dark background"]

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

async def generate_speech(text, output_audio):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_audio)

def fetch_pexels_image(query, index):
    """Pexels API üzerinden orijinal yüksek çözünürlüklü HD dikey fotoğraf indirir."""
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
    # Maksimum kalite için original veya large2x görsel çekilir
    img_url = selected_photo["src"].get("original", selected_photo["src"]["large2x"])

    img_data = requests.get(img_url).content
    temp_path = f"temp_img_{index}.jpg"
    with open(temp_path, "wb") as f:
        f.write(img_data)
    return temp_path

def send_telegram_video(video_path, caption=""):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID eksik, gönderim atlanıyor.")
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

    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [full_text]
        
    paragraphs.append("Beğenip Paylaşmayı Unutmayın ❤️")

    print("🎙️ Seslendirme üretiliyor (Edge-TTS)...")
    speech_audio_path = "speech.mp3"
    asyncio.run(generate_speech(full_text, speech_audio_path))

    speech_clip = AudioFileClip(speech_audio_path)
    total_duration = speech_clip.duration + 1.5

    segment_duration = total_duration / len(paragraphs)

    image_clips = []
    text_clips = []

    current_time = 0.0

    print("📸 Maksimum çözünürlüklü HD görseller indiriliyor...")
    for idx, text_segment in enumerate(paragraphs):
        query = SEARCH_KEYWORDS[idx % len(SEARCH_KEYWORDS)]
        img_path = fetch_pexels_image(query, idx)
        
        # 1. Arka Plan Görsel Klip
        img_clip = ImageClip(img_path)
        if hasattr(img_clip, 'resized'):
            img_clip = img_clip.resized(new_size=(1080, 1920))
        else:
            img_clip = img_clip.resize(newsize=(1080, 1920))

        if hasattr(img_clip, 'with_duration'):
            img_clip = img_clip.with_duration(segment_duration)
        else:
            img_clip = img_clip.set_duration(segment_duration)
            
        image_clips.append(img_clip)

        # 2. Yazı Klip - Altın Sarısı (#FFD700) ve Yarı Saydam Siyah Kart
        text_kwargs = {
            "text": text_segment,
            "font_size": 50 if idx == 0 else 44,
            "color": '#FFD700',
            "method": 'caption',
            "size": (920, None),
            "bg_color": (0, 0, 0, 180)
        }
        if font_path:
            text_kwargs["font"] = font_path

        txt_clip = TextClip(**text_kwargs)

        if hasattr(txt_clip, 'with_position'):
            txt_clip = (txt_clip.with_position(('center', 'center'))
                        .with_start(current_time)
                        .with_duration(segment_duration))
        else:
            txt_clip = (txt_clip.set_position(('center', 'center'))
                        .set_start(current_time)
                        .set_duration(segment_duration))

        text_clips.append(txt_clip)
        current_time += segment_duration

    final_bg = concatenate_videoclips(image_clips)

    # Müzik Birleştirme
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
    print("🚀 Video HD kalitede (kayıpsız/yüksek bitrate) render ediliyor...")
    
    # HD Çıktı Ayarları: Yüksek Bitrate (12M) ve Düşük CRF (15) ile neredeyse kayıpsız render
    final_video.write_videofile(
        output_filename,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        bitrate="12000k",
        preset="slow",
        ffmpeg_params=["-crf", "15"]
    )
    print("✅ HD Render tamamlandı!")

    # Temizlik
    for idx in range(len(paragraphs)):
        temp_file = f"temp_img_{idx}.jpg"
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
    if os.path.exists(speech_audio_path):
        os.remove(speech_audio_path)

    send_telegram_video(
        video_path=output_filename,
        caption="🎬 **Yeni Karanlık Tarih Videosu Hazır (HD)!**\n\nBeğenip Paylaşmayı Unutmayın ❤️"
    )

if __name__ == "__main__":
    create_video()
