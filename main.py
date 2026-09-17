import os
import asyncio
import threading
import tempfile
import urllib.request
import wave
from http.server import HTTPServer, BaseHTTPRequestHandler
from gradio_client import Client, handle_file
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# API ပွင့်နေသော အခြား VoxCPM Space များကို အလှည့်ကျ အသုံးပြုမည်
HF_SPACES = ["openbmb/VoxCPM-Demo", "akhaliq/VoxCPM-0.5B"]
# Bot Token အသစ်
TOKEN = "8822125415:AAF9XHUbf3JTMa6jhNbtQOmdbOJEqlElxYU"

# Clone လုပ်ရန် အသံဖိုင်များကို ယာယီမှတ်သားမည့်နေရာ
user_clone_audio = {}

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), SimpleHandler).serve_forever()

def create_blank_audio():
    path = os.path.join(tempfile.gettempdir(), "blank.wav")
    if not os.path.exists(path):
        with wave.open(path, "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(16000)
            f.writeframes(b'\x00\x00' * 16000)
    return path

def extract_audio(data):
    if not data: return None
    if isinstance(data, dict):
        for k in ["path", "name", "url", "video", "file_path"]:
            if k in data and data[k]:
                res = extract_audio(data[k])
                if res: return res
        for v in data.values():
            if isinstance(v, (dict, list, str)):
                res = extract_audio(v)
                if res: return res
    elif isinstance(data, (list, tuple)):
        for i in data:
            res = extract_audio(i)
            if res: return res
    elif isinstance(data, str):
        if os.path.exists(data): return data
        if data.startswith("http"):
            path = tempfile.mktemp(suffix=".wav")
            urllib.request.urlretrieve(data, path)
            return path
        if any(data.lower().endswith(x) for x in [".wav", ".mp3", ".ogg", ".flac", ".m4a"]):
            return data
    return None

def get_audio_from_hf(text, ref_audio_path=None):
    if ref_audio_path and os.path.exists(ref_audio_path):
        hf_file = handle_file(ref_audio_path)
    else:
        blank_wav = create_blank_audio()
        hf_file = handle_file(blank_wav)
        
    prompt = f"(A warm, gentle young female voice, clear storytelling tone) ... {text}"
    
    last_error = ""
    for space in HF_SPACES:
        try:
            c = Client(space)
            
            for fn_idx, endp in enumerate(c.endpoints):
                params = getattr(endp, 'parameters', [])
                if not params: continue
                args = []
                for p in params:
                    t = str(getattr(p, 'type', '')).lower()
                    p_name = str(getattr(p, 'parameter_name', '')).lower()
                    
                    if 'file' in t or 'audio' in t: 
                        args.append(hf_file)
                    elif 'bool' in t: 
                        args.append(False)
                    elif 'int' in t: 
                        args.append(10)
                    elif 'float' in t: 
                        args.append(2.0)
                    else:
                        if 'text' in p_name and 'prompt' not in p_name and 'ref' not in p_name:
                            args.append(text)
                        else:
                            args.append(prompt)
                try:
                    res = c.predict(*args, fn_index=fn_idx)
                    audio = extract_audio(res)
                    if audio: return audio
                except:
                    continue
                    
            payloads = [
                (hf_file, prompt, text, 2.0, 10, 42),
                (hf_file, "", text, 2.0, 10, 42),
                (hf_file, text, 2.0, 10, 42)
            ]
            for fn_idx in range(4):
                for p in payloads:
                    try:
                        res = c.predict(*p, fn_index=fn_idx)
                        audio = extract_audio(res)
                        if audio: return audio
                    except Exception as e:
                        last_error = str(e)
                        continue
        except Exception as e:
            last_error = str(e)
            continue
            
    raise Exception(f"AI Model များမှ အသံဖိုင်ထုတ်ပေးခြင်း မရှိပါ။ (API ပြောင်းလဲသွားပါသည်)")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "မင်္ဂလာပါ အစ်ကို!\n\n"
        "💬 **ရိုးရိုးအသံထုတ်ရန်:**\nစာသားကို တိုက်ရိုက် ပို့ပါ။\n\n"
        "🎤 **အသံတု (Clone) လုပ်ရန်:**\nအသံဖိုင် (Voice Note) ကို အရင်ပို့ပါ၊ ပြီးမှ စာသားကို ပို့ပါ။"
    )
    await update.message.reply_text(msg)

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    audio_obj = update.message.voice or update.message.audio
    if not audio_obj: return
    
    status = await update.message.reply_text("📥 အသံဖိုင်ကို မှတ်သားနေပါသည်...")
    file = await context.bot.get_file(audio_obj.file_id)
    
    path = os.path.join(tempfile.gettempdir(), f"{audio_obj.file_id}.ogg")
    await file.download_to_drive(path)
    
    user_clone_audio[update.message.chat_id] = path
    await status.edit_text("✅ အသံဖိုင် မှတ်သားပြီးပါပြီ။ ဒီအသံနဲ့ ပြောစေချင်တဲ့ **စာသား** ကို ပို့ပေးပါ အစ်ကို။")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text: return
    
    chat_id = update.message.chat_id
    ref_audio = user_clone_audio.get(chat_id)
    
    status_msg = "🎙️ Clone အသံဖြင့် ထုတ်လုပ်နေပါသည်..." if ref_audio else "🎙️ ရိုးရိုးအသံ ထုတ်လုပ်နေပါသည်..."
    status = await update.message.reply_text(status_msg)
    
    try:
        loop = asyncio.get_running_loop()
        audio_path = await loop.run_in_executor(None, lambda: get_audio_from_hf(text, ref_audio))
        
        with open(audio_path, 'rb') as f:
            await update.message.reply_voice(voice=f, caption=text[:40])
        await status.delete()
        
        if chat_id in user_clone_audio:
            del user_clone_audio[chat_id]
            
    except Exception as e:
        await status.edit_text(f"Error တက်သွားပါသည်:\n{str(e)}")

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is running perfectly...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
