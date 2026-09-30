import os
import random
import requests
import asyncio
import edge_tts
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, 
    CompositeAudioClip, afx
)

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
VOICE = "tr-TR-AhmetNeural"  # Doğal duran erkek yapay zeka sesi

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
        # Arama sonucu bulunamazsa varsayılan koyu tema araması
        url = "https://api.pexels.com/videos/search?query=dark%20atmosphere&orientation=portrait&per_page=15"
        videos = requests.get(url, headers=headers).json().get("videos", [])

    selected_video = random.choice(videos)
    video_files = selected_video.get("video_files", [])
    
    # 1080x1920 veya en yakın dikey kaliteyi bul
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

def create_video():
    # 1. Metni Oku
    with open("metinler.txt", "r", encoding="utf-8") as f:
        full_text = f.read().strip()

    print("🎙️ Seslendirme oluşturuluyor (Edge-TTS)...")
    speech_audio_path = "speech.mp3"
    asyncio.run(generate_speech(full_text, speech_audio_path))

    speech_clip = AudioFileClip(speech_audio_path)
    video_duration = speech_clip.duration + 1.0  # Sona 1sn pay

    # 2. Arka Plan Videolarını Pexels'ten Çek
    print("🎬 Arka plan videosu çekiliyor...")
    queries = ["ancient ruins", "fire burning", "dark smoke", "bronze statue"]
    selected_query = random.choice(queries)
    bg_video_path = fetch_pexels_video(selected_query)

    bg_clip = VideoFileClip(bg_video_path)
    if bg_clip.duration < video_duration:
        # Yeterince uzun değilse döngüye al
        loop_count = int(video_duration // bg_clip.duration) + 1
        bg_clip = bg_clip.loop(n=loop_count)
    
    bg_clip = bg_clip.subclip(0, video_duration).resize(newsize=(1080, 1920))

    # 3. Altyazı / Metin Kartı Ekleme
    # Alt alta düzgün gözükmesi için metni sardırma
    wrapped_text = "\n".join([full_text[i:i+30] for i in range(0, len(full_text), 30)])
    
    txt_clip = TextClip(
        full_text,
        fontsize=42,
        color='white',
        font='Arial-Bold',
        method='caption',
        size=(900, None),
        bg_color='rgba(0,0,0,0.65)'
    ).set_position(('center', 'center')).set_duration(video_duration)

    # 4. Sesleri Birleştirme (Konuşma + Gerilim Müziği)
    bg_music_path = os.path.join("assets", "suspense.mp3")
    if os.path.exists(bg_music_path):
        bg_music = AudioFileClip(bg_music_path)
        if bg_music.duration < video_duration:
            bg_music = bg_music.loop(duration=video_duration)
        bg_music = bg_music.subclip(0, video_duration).volumex(0.15) # Müzik sesini kıs
        final_audio = CompositeAudioClip([speech_clip.volumex(1.2), bg_music])
    else:
        final_audio = speech_clip

    # 5. Sahne Birleştirme ve Render
    final_video = CompositeVideoClip([bg_clip, txt_clip]).set_audio(final_audio)

    print("🚀 Video render ediliyor...")
    final_video.write_videofile(
        "dark_history_output.mp4",
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast"
    )
    print("✅ İşlem tamamlandı: dark_history_output.mp4")

if __name__ == "__main__":
    create_video()
