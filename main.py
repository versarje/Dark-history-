import os
import random
import requests
import asyncio
import edge_tts
from moviepy import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, 
    CompositeAudioClip, concatenate_videoclips
)

# Ortam Değişkenleri
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

VOICE = "tr-TR-AhmetNeural"
SEARCH_KEYWORDS = ["ancient ruins", "fire burning", "dark smoke", "bronze statue", "spooky dark background"]

def get_system_font():
    """Linux ortamında Pillow ve MoviePy için %100 uyumlu font yolunu tespit eder."""
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
    """Metni gTTS yerine edge-tts ile yüksek kalitede seslendirir."""
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_audio)

def fetch_pexels_video(query, index):
    """Pexels API üzerinden dikey (1080x1920) HD video indirir."""
    if not PEXELS_API_KEY:
        raise ValueError("PEXELS_API_KEY bulunamadı! GitHub Secrets kontrol edilmeli.")
        
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&orientation=portrait&per_page=15"
    res = requests.get(url, headers=headers).json()
    videos = res.get("videos", [])
    
    # Arama sonucu boşsa varsayılan karanlık tema videosu çeker
    if not videos:
        url = "https://api.pexels.com/videos/search?query=dark%20atmosphere&orientation=portrait&per_page=15"
        videos = requests.get(url, headers=headers).json().get("videos", [])

    selected_video = random.choice(videos)
    video_files = selected_video.get("video_files", [])
    
    # En az 1080p yüksekliğinde video linkini seç
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
    """Render tamamlanan videoyu Telegram Bot API ile kanala/kullanıcıya iletir."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID eksik. Telegram gönderimi atlanıyor.")
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
    font_path = get_system_font()

    # 1. Metin Okuma
    if not os.path.exists("metinler.txt"):
        raise FileNotFoundError("'metinler.txt' dosyası ana dizinde bulunamadı!")

    with open("metinler.txt", "r", encoding="utf-8") as f:
        full_text = f.read().strip()

    sentences = [s.strip() for s in full_text.split("\n\n") if s.strip()]
    if not sentences:
        sentences = [full_text]
    
    # 2. Ses Dosyası Oluşturma
    print("🎙️ Seslendirme üretiliyor (Edge-TTS)...")
    speech_audio_path = "speech.mp3"
    asyncio.run(generate_speech(full_text, speech_audio_path))

    speech_clip = AudioFileClip(speech_audio_path)
    total_duration = speech_clip.duration + 1.0

    # 3. Arka Plan Videolarını İndirme ve İşleme
    print(f"🎬 Metinde {len(sentences)} bölüm bulundu. Dinamik arka plan videoları işleniyor...")
    segment_duration = total_duration / len(sentences)
    video_clips = []

    for idx, sentence in enumerate(sentences):
        query = SEARCH_KEYWORDS[idx % len(SEARCH_KEYWORDS)]
        print(f"  └─ [{idx+1}/{len(sentences)}] '{query}' kelimesi için video çekiliyor...")
        
        bg_video_path = fetch_pexels_video(query, idx)
        clip = VideoFileClip(bg_video_path)
        
        # Süre yetersizse videoyu döngüye al
        if clip.duration < segment_duration:
            loop_count = int(segment_duration // clip.duration) + 1
            clip = concatenate_videoclips([clip] * loop_count)
            
        # MoviePy 2.0+ ve eski sürümler ile çift uyumlu boyutlandırma
        if hasattr(clip, 'resized'):
            clip = clip.resized(new_size=(1080, 1920))
        else:
            clip = clip.resize(newsize=(1080, 1920))

        if hasattr(clip, 'subclipped'):
            clip = clip.subclipped(0, segment_duration)
        else:
            clip = clip.subclip(0, segment_duration)
            
        video_clips.append(clip)

    final_bg_clip = concatenate_videoclips(video_clips)

    # 4. Altyazı / Metin Kartı (TextClip) Yapılandırması
    # RGBA tuple formatı Pillow hatasını önler (0, 0, 0, 165 = %65 Saydam Siyah)
    text_kwargs = {
        "text": full_text,
        "font_size": 42,
        "color": 'white',
        "method": 'caption',
        "size": (900, None),
        "bg_color": (0, 0, 0, 165)
    }
    
    if font_path:
        text_kwargs["font"] = font_path

    txt_clip = TextClip(**text_kwargs)

    if hasattr(txt_clip, 'with_position'):
        txt_clip = txt_clip.with_position(('center', 'center')).with_duration(total_duration)
    else:
        txt_clip = txt_clip.set_position(('center', 'center')).set_duration(total_duration)

    # 5. Arka Plan Müzik Birleştirme
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

    # 6. Render Alma
    output_filename = "dark_history_output.mp4"
    final_video_clip = CompositeVideoClip([final_bg_clip, txt_clip])
    
    if hasattr(final_video_clip, 'with_audio'):
        final_video = final_video_clip.with_audio(final_audio)
    else:
        final_video = final_video_clip.set_audio(final_audio)

    print("🚀 Video render ediliyor...")
    final_video.write_videofile(
        output_filename,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast"
    )
    print("✅ Render tamamlandı!")

    # Geçici arka plan video dosyalarını temizle
    for idx in range(len(sentences)):
        temp_file = f"temp_bg_{idx}.mp4"
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
    if os.path.exists(speech_audio_path):
        os.remove(speech_audio_path)

    # 7. Telegram Botu İle Videoyu Gönderme
    send_telegram_video(
        video_path=output_filename,
        caption="🎬 **Yeni Karanlık Tarih Videosu Hazır!**\n\nBeğenip Paylaşmayı Unutmayın ❤️"
    )

if __name__ == "__main__":
    create_video()
