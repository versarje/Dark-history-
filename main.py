import os
import random
import requests
import asyncio
import edge_tts
from moviepy.editor import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, 
    CompositeAudioClip, concatenate_videoclips
)

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

VOICE = "tr-TR-AhmetNeural"

# Metindeki anahtar kelimelere göre dinamik Pexels araması için havuz
SEARCH_KEYWORDS = ["ancient ruins", "fire burning", "dark smoke", "bronze statue", "spooky dark background"]

async def generate_speech(text, output_audio):
    """Metni doğal yapay zeka sesiyle seslendirir."""
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_audio)

def fetch_pexels_video(query, index):
    """Belirtilen sorguya göre dikey Pexels videosu indirir."""
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
    temp_path = f"temp_bg_{index}.mp4"
    with open(temp_path, "wb") as f:
        f.write(video_data)
    return temp_path

def send_telegram_video(video_path, caption=""):
    """Render edilen videoyu Telegram üzerinden gönderir."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID eksik, Telegram gönderimi atlanıyor.")
        return

    print("📤 Video Telegram'a yükleniyor...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    
    try:
        with open(video_path, "rb") as video_file:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
            files = {"video": video_file}
            response = requests.post(url, data=payload, files=files)
            
        if response.status_code == 200:
            print("✅ Video Telegram'a başarıyla gönderildi!")
        else:
            print(f"❌ Telegram Gönderim Hatası: {response.text}")
    except Exception as e:
        print(f"❌ Telegram bağlantı hatası: {e}")

def create_video():
    # 1. Metni Oku
    with open("metinler.txt", "r", encoding="utf-8") as f:
        full_text = f.read().strip()

    # Metni paragraflara/cümlelere böl
    sentences = [s.strip() for s in full_text.split("\n\n") if s.strip()]
    
    # 2. Seslendirme Oluştur
    print("🎙️ Seslendirme üretiliyor (Edge-TTS)...")
    speech_audio_path = "speech.mp3"
    asyncio.run(generate_speech(full_text, speech_audio_path))

    speech_clip = AudioFileClip(speech_audio_path)
    total_duration = speech_clip.duration + 1.0

    # 3. Kelime / Cümle Sayısına Göre Dinamik Çoklu Video Çekimi
    print(f"🎬 Metinde {len(sentences)} bölüm bulundu. Dinamik arka plan videoları indiriliyor...")
    
    segment_duration = total_duration / len(sentences) # Her cümle/bölüm için düşen süre
    video_clips = []

    for idx, sentence in enumerate(sentences):
        # Her bölüm için havuzdan farklı bir arama kelimesi seç
        query = SEARCH_KEYWORDS[idx % len(SEARCH_KEYWORDS)]
        print(f"  └─ [{idx+1}/{len(sentences)}] '{query}' kelimesi için video indiriliyor...")
        
        bg_video_path = fetch_pexels_video(query, idx)
        clip = VideoFileClip(bg_video_path)
        
        # Klip hedeflenen parçadan kısaysa döngüye al
        if clip.duration < segment_duration:
            loop_count = int(segment_duration // clip.duration) + 1
            clip = clip.loop(n=loop_count)
            
        # Tam bölüm süresi kadar kes ve boyutlandır
        clip = clip.subclip(0, segment_duration).resize(newsize=(1080, 1920))
        video_clips.append(clip)

    # Videoları peş peşe birleştir
    final_bg_clip = concatenate_videoclips(video_clips)

    # 4. Altyazı Kartı Ekleme
    txt_clip = TextClip(
        full_text,
        fontsize=42,
        color='white',
        font='Arial-Bold',
        method='caption',
        size=(900, None),
        bg_color='rgba(0,0,0,0.65)'
    ).set_position(('center', 'center')).set_duration(total_duration)

    # 5. Sesleri Birleştirme
    bg_music_path = os.path.join("assets", "suspense.mp3")
    if os.path.exists(bg_music_path):
        bg_music = AudioFileClip(bg_music_path)
        if bg_music.duration < total_duration:
            bg_music = bg_music.loop(duration=total_duration)
        bg_music = bg_music.subclip(0, total_duration).volumex(0.15)
        final_audio = CompositeAudioClip([speech_clip.volumex(1.2), bg_music])
    else:
        final_audio = speech_clip

    # 6. Final Video Render
    output_filename = "dark_history_output.mp4"
    final_video = CompositeVideoClip([final_bg_clip, txt_clip]).set_audio(final_audio)

    print("🚀 Video render ediliyor...")
    final_video.write_videofile(
        output_filename,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast"
    )
    print("✅ Render tamamlandı!")

    # 7. Geçici Video Dosyalarını Temizle
    for idx in range(len(sentences)):
        temp_file = f"temp_bg_{idx}.mp4"
        if os.path.exists(temp_file):
            os.remove(temp_file)

    # 8. Telegram'a Gönder
    send_telegram_video(
        video_path=output_filename,
        caption="🎬 **Yeni Karanlık Tarih Videosu Hazır!**\n\nBeğenip Paylaşmayı Unutmayın ❤️"
    )

if __name__ == "__main__":
    create_video()
