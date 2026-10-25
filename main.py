import os
import re
import asyncio
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# API Version v1 ကို တိုက်ရိုက် သတ်မှတ်ထားခြင်း
ai_client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={"api_version": "v1"}
)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")


def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


def extract_clean_youtube_url(text: str):
    pattern = r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})"
    match = re.search(pattern, text)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube.com/watch?v={video_id}"
    return None


def generate_burmese_recap(youtube_url: str):
    prompt = f"""
    အောက်ပါ YouTube ဗီဒီယိုလင့်ခ်၏ အကြောင်းအရာကို ရှာဖွေလေ့လာပြီး မြန်မာဘာသာစကားဖြင့် ပြည့်စုံသပ်ရပ်သော Recap (အနှစ်ချုပ်) တစ်ခု ဖန်တီးပေးပါ။

    YouTube Link: {youtube_url}

    ဖွဲ့စည်းပုံ-
    📌 **ဗီဒီယို၏ အဓိကရည်ရွယ်ချက် (Overview)**
    - ဗီဒီယိုအကြောင်း အကျဉ်းချုပ် ရှင်းလင်းချက် (၂-၃ ကြောင်း)

    💡 **အရေးကြီးသော အချက်အလက်များ (Key Takeaways / Plot Summary)**
    - အဓိက ဇာတ်လမ်း သို့မဟုတ် အရေးကြီးသော အချက်များကို အစီအစဉ်တကျ Bullet points များဖြင့် ဖော်ပြရန်

    🎯 **အဆုံးသတ် သုံးသပ်ချက် (Conclusion)**
    - အဆုံးသတ် ကောက်ချက် သို့မဟုတ် ရရှိသော သင်ခန်းစာ
    """
    
    response = ai_client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt
    )
    return response.text


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "မင်္ဂလာပါ! 👋\n\n"
        "ကျွန်တော်က YouTube ဗီဒီယိုတွေကို မြန်မာလို အနှစ်ချုပ် (Recap) လုပ်ပေးတဲ့ Bot ဖြစ်ပါတယ်။\n\n"
        "အနှစ်ချုပ်လိုသော YouTube Link ကို ပို့ပေးပါ။"
    )
    await update.message.reply_text(welcome_text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    clean_url = extract_clean_youtube_url(user_message)

    if not clean_url:
        await update.message.reply_text("ကျေးဇူးပြု၍ မှန်ကန်သော YouTube Video Link တစ်ခု ပို့ပေးပါ။")
        return

    status_message = await update.message.reply_text("⏳ ဗီဒီယိုကို လေ့လာပြီး မြန်မာလို Recap ရေးသားနေပါသည်... ခေတ္တစောင့်ပေးပါ။")

    try:
        recap_result = generate_burmese_recap(clean_url)
        await status_message.edit_text(recap_result)
    except Exception as e:
        logging.error(f"Error generating recap: {e}")
        await status_message.edit_text(f"⚠️ Recap ရေးသားရာတွင် အမှားဖြစ်ပေါ်ခဲ့သည်- {str(e)[:150]}")


async def main():
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
        raise ValueError("TELEGRAM_BOT_TOKEN နှင့် GEMINI_API_KEY လိုအပ်ပါသည်။")

    web_thread = Thread(target=run_dummy_server, daemon=True)
    web_thread.start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    async with app:
        await app.start()
        await app.updater.start_polling()
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
    
