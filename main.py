import os
import random
import requests
import asyncio
import edge_tts
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, 
    CompositeAudioClip
)

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

VOICE = "tr-TR-AhmetNeural"

async def generate_speech(text, output_audio):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_audio)

def fetch_pexels_video(query):
    if not PEXELS_API_KEY:
        raise ValueError("PEXELS_API_KEY bulunamadı!")
        
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&orientation=portrait&per_page=15"
    res = requests.get(url, headers=headers).json()
    videos = res.get("videos", [])
    
    if not videos:
        url = "https://api.pexels.com/videos/search?query=dark%20atmosphere&orientation=portrait&per_page=15"
        videos = requests.get(url, headers=headers).json().get("videos", [])

    selected_video = random.choice(videos)
    video_files = selected_video.get("video_files", [])
    
    video_url = video_files[0]["link"]
    for vf in video_files:
        if vf.get("height", 0) >= 1920:
            video_url = vf["link"]
            break

    video_data = requests.get(video_url).content
    temp_path = "temp_bg.mp4"
    with open(temp_path, "wb") as f:
        f.write(video_data)
    return temp_path

def send_telegram_video(video_path, caption=""):
    """Üretilen videoyu Telegram üzerinden gönderir."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID bulunamadı, Telegram gönderimi atlanıyor.")
        return

    print("📤 Video Telegram'a gönderiliyor...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    
    with open(video_path, "rb") as video_file:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
        files = {"video": video_file}
        response = requests.post(url, data=payload, files=files)
        
    if response.status_code == 200:
        print("✅ Video Telegram'a başarıyla gönderildi!")
    else:
        print(f"❌ Telegram gönderim hatası: {response.text}")

def create_video():
    # 1. Metni Oku
    with open("metinler.txt", "r", encoding="utf-8") as f:
        full_text = f.read().strip()

    print("🎙️ Seslendirme oluşturuluyor (Edge-TTS)...")
    speech_audio_path = "speech.mp3"
    asyncio.run(generate_speech(full_text, speech_audio_path))

    speech_clip = AudioFileClip(speech_audio_path)
    video_duration = speech_clip.duration + 1.0

    # 2. Arka Plan Videolarını Pexels'ten Çek
    print("🎬 Arka plan videosu çekiliyor...")
    queries = ["ancient ruins", "fire burning", "dark smoke", "bronze statue"]
    selected_query = random.choice(queries)
    bg_video_path = fetch_pexels_video(selected_query)

    bg_clip = VideoFileClip(bg_video_path)
    if bg_clip.duration < video_duration:
        loop_count = int(video_duration // bg_clip.duration) + 1
        bg_clip = bg_clip.loop(n=loop_count)
    
    bg_clip = bg_clip.subclip(0, video_duration).resize(newsize=(1080, 1920))

    # 3. Altyazı / Metin Kartı Ekleme
    txt_clip = TextClip(
        full_text,
        fontsize=42,
        color='white',
        font='Arial-Bold',
        method='caption',
        size=(900, None),
        bg_color='rgba(0,0,0,0.65)'
    ).set_position(('center', 'center')).set_duration(video_duration)

    # 4. Sesleri Birleştirme
    bg_music_path = os.path.join("assets", "suspense.mp3")
    if os.path.exists(bg_music_path):
        bg_music = AudioFileClip(bg_music_path)
        if bg_music.duration < video_duration:
            bg_music = bg_music.loop(duration=video_duration)
        bg_music = bg_music.subclip(0, video_duration).volumex(0.15)
        final_audio = CompositeAudioClip([speech_clip.volumex(1.2), bg_music])
    else:
        final_audio = speech_clip

    # 5. Sahne Birleştirme ve Render
    output_filename = "dark_history_output.mp4"
    final_video = CompositeVideoClip([bg_clip, txt_clip]).set_audio(final_audio)

    print("🚀 Video render ediliyor...")
    final_video.write_videofile(
        output_filename,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast"
    )
    print("✅ Render tamamlandı!")

    # 6. Telegram Gönderimi
    send_telegram_video(
        video_path=output_filename, 
        caption="🎬 **Yeni Karanlık Tarih Videosu Hazır!**\n\nBeğenip Paylaşmayı Unutmayın ❤️"
    )

if __name__ == "__main__":
    create_video()
