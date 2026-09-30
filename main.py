import os
import re
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

def extract_keywords_for_sentence(sentence, index):
    """Metnin içeriğine göre en alakalı Pexels görsel sorgusunu belirler."""
    s = sentence.lower()
    
    if any(w in s for w in ["tarih", "cezalandırma", "korkunç", "yöntemi"]):
        return "ancient ruins dark history"
    elif any(w in s for w in ["antik yunan", "pirinç boğa", "icadı"]):
        return "ancient greece statue bronze"
    elif any(w in s for w in ["alet", "bronz", "heykel", "içi boş"]):
        return "bronze bull metal statue"
    elif any(w in s for w in ["ateş", "kilitleniyor", "yakılıyordu", "kurban"]):
        return "fire burning flames dark"
    elif any(w in s for w in ["metal", "ısındıkça", "pişiyordu"]):
        return "hot metal iron fire"
    elif any(w in s for w in ["ürpertici", "kısmı"]):
        return "dark mystery cinematic horror"
    elif any(w in s for w in ["ağzındaki", "boru", "çığlık", "böğürmesi", "öfkeli"]):
        return "roaring bull angry smoke"
    elif any(w in s for w in ["ironi", "biliyor musunuz"]):
        return "dramatic silhouette dark"
    elif any(w in s for w in ["icat eden", "canlı canlı", "ilk insan"]):
        return "ancient execution fire dark"
    elif "beğenip" in s or "paylaşmayı" in s:
        return "dark aesthetic cinematic background"
    
    # Eşleşme yoksa alternatif arama kelimeleri
    fallback_keywords = ["dark history", "ancient ruins", "spooky dark background", "fire flames"]
    return fallback_keywords[index % len(fallback_keywords)]

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
    """Belirtilen sorguya göre Pexels API üzerinden HD dikey fotoğraf indirir."""
    if not PEXELS_API_KEY:
        raise ValueError("PEXELS_API_KEY bulunamadı!")
        
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&orientation=portrait&per_page=15"
    res = requests.get(url, headers=headers).json()
    photos = res.get("photos", [])
    
    if not photos:
        # Sorgu sonuç vermezse varsayılan arama
        url = "https://api.pexels.com/v1/search?query=dark%20history&orientation=portrait&per_page=15"
        photos = requests.get(url, headers=headers).json().get("photos", [])

    selected_photo = random.choice(photos)
    img_url = selected_photo["src"].get("original", selected_photo["src"]["large2x"])

    img_data = requests.get(img_url).content
    temp_path = f"temp_img_{index}.jpg"
    with open(temp_path, "wb") as f:
        f.write(img_data)
    return temp_path

def split_text_into_sentences(text):
    """Metni noktalama işaretlerine göre cümle cümle ayırır."""
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    return sentences

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

    sentences = split_text_into_sentences(full_text)
    if not sentences:
        sentences = [full_text]
        
    sentences.append("Beğenip Paylaşmayı Unutmayın ❤️")

    print("🎙️ Seslendirme üretiliyor (Edge-TTS)...")
    speech_audio_path = "speech.mp3"
    asyncio.run(generate_speech(full_text, speech_audio_path))

    speech_clip = AudioFileClip(speech_audio_path)
    total_duration = speech_clip.duration + 1.5

    total_words = sum(len(s.split()) for s in sentences)
    
    image_clips = []
    text_clips = []
    current_time = 0.0

    print("📸 Metin içeriğine özel HD görseller seçiliyor ve altyazılar senkronize ediliyor...")
    for idx, sentence in enumerate(sentences):
        word_count = len(sentence.split())
        sentence_duration = max(2.0, (word_count / total_words) * total_duration)

        # 1. Metinden Arama Kelimelerini Tespit Et ve Görseli İndir
        query = extract_keywords_for_sentence(sentence, idx)
        print(f"  [Cümle {idx+1}] Sorgu: '{query}' -> Cümle: '{sentence[:30]}...'")
        img_path = fetch_pexels_image(query, idx)
        
        img_clip = ImageClip(img_path)
        if hasattr(img_clip, 'resized'):
            img_clip = img_clip.resized(new_size=(1080, 1920))
        else:
            img_clip = img_clip.resize(newsize=(1080, 1920))

        if hasattr(img_clip, 'with_duration'):
            img_clip = img_clip.with_duration(sentence_duration)
        else:
            img_clip = img_clip.set_duration(sentence_duration)
            
        image_clips.append(img_clip)

        # 2. Alt Yazı Kartı
        text_kwargs = {
            "text": sentence,
            "font_size": 52 if idx == 0 else 44,
            "color": '#FFD700',
            "method": 'caption',
            "size": (880, None),
            "bg_color": (0, 0, 0, 190)
        }
        if font_path:
            text_kwargs["font"] = font_path

        txt_clip = TextClip(**text_kwargs)

        if hasattr(txt_clip, 'with_position'):
            txt_clip = (txt_clip.with_position(('center', 0.65), relative=True)
                        .with_start(current_time)
                        .with_duration(sentence_duration))
        else:
            txt_clip = (txt_clip.set_position(('center', 0.65), relative=True)
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
        bitrate="12000k",
        preset="slow",
        ffmpeg_params=["-crf", "15"]
    )
    print("✅ HD Render tamamlandı!")

    # Temizlik
    for idx in range(len(sentences)):
        temp_file = f"temp_img_{idx}.jpg"
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
    if os.path.exists(speech_audio_path):
        os.remove(speech_audio_path)

    send_telegram_video(
        video_path=output_filename,
        caption="🎬 **İçeriğe Uygun Görselli HD Video Hazır!**\n\nBeğenip Paylaşmayı Unutmayın ❤️"
    )

if __name__ == "__main__":
    create_video()
