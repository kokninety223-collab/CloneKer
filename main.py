import os
import asyncio
import threading
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import edge_tts

# အစ်ကို့ရဲ့ Token အသစ်
TOKEN = "8822125415:AAF9XHUbf3JTMa6jhNbtQOmdbOJEqlElxYU"

# User များ ရွေးချယ်ထားသော အသံများကို မှတ်သားရန်
user_voices = {}
MALE_VOICE = "my-MM-ThihaNeural"
FEMALE_VOICE = "my-MM-NilarNeural"

# Render မအိပ်သွားစေရန် Dummy Server
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "မင်္ဂလာပါ! သဘာဝကျသော AI အသံဖြင့် ဖတ်ပြပေးပါမည်။ စာသားကို တိုက်ရိုက် ပို့ပေးပါ။\n\n"
        "🎛 **အသံပြောင်းလဲရန် အောက်ပါတို့ကို နှိပ်ပါ:**\n"
        "/male - 👨 ယောကျ်ားလေးအသံ (Thiha)\n"
        "/female - 👩 မိန်းကလေးအသံ (Nilar)"
    )
    await update.message.reply_text(msg)

async def set_male(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_voices[update.message.chat_id] = MALE_VOICE
    await update.message.reply_text("✅ ယောကျ်ားလေးအသံ (Thiha) သို့ ပြောင်းလဲလိုက်ပါပြီ။ စာသား ပို့ကြည့်ပါ။")

async def set_female(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_voices[update.message.chat_id] = FEMALE_VOICE
    await update.message.reply_text("✅ မိန်းကလေးအသံ (Nilar) သို့ ပြောင်းလဲလိုက်ပါပြီ။ စာသား ပို့ကြည့်ပါ။")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text: return
        
    chat_id = update.message.chat_id
    # Default အနေဖြင့် ယောကျ်ားလေးအသံကို အရင်သုံးမည်
    voice = user_voices.get(chat_id, MALE_VOICE) 
    
    status = await update.message.reply_text("🎙️ Microsoft AI ဖြင့် အသံထုတ်လုပ်နေပါသည်...")
    
    try:
        audio_path = os.path.join(tempfile.gettempdir(), f"{chat_id}_voice.mp3")
        
        # edge-tts ဖြင့် အသံထုတ်လုပ်ခြင်း
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(audio_path)
        
        with open(audio_path, 'rb') as f:
            await update.message.reply_voice(voice=f, caption=text[:40])
            
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Error တက်သွားပါသည်:\n{str(e)}")

async def start_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Commands များ
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("male", set_male))
    app.add_handler(CommandHandler("female", set_female))
    
    # Text များ လက်ခံရန်
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Edge-TTS Bot is running perfectly...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()
    
