import os
import re
import logging
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from google import genai
from youtube_transcript_api import YouTubeTranscriptApi
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ai_client = genai.Client(api_key=GEMINI_API_KEY)


# Web Service အတွက် Dummy Server ဖွင့်ပေးခြင်း (Render Free ရစေရန်)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


def extract_video_id(url: str):
    pattern = r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None


def get_youtube_transcript(video_id: str):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["en", "my", "en-US", "en-GB"]
        )
        return " ".join([item["text"] for item in transcript_list])
    except Exception:
        try:
            transcript_list_obj = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list_obj.find_transcript(["en"])
            return " ".join([item["text"] for item in transcript.fetch()])
        except Exception:
            return None


def generate_burmese_recap(transcript_text: str):
    prompt = f"""
    အောက်ပါ YouTube transcript ကို အခြေခံပြီး မြန်မာဘာသာစကားဖြင့် သပ်ရပ်ရှင်းလင်းသော Recap/Summary တစ်ခု ဖန်တီးပေးပါ။

    ဖွဲ့စည်းပုံ-
    📌 **ဗီဒီယို၏ အဓိကရည်ရွယ်ချက် (Overview)**
    - အကျဉ်းချုပ် ရှင်းလင်းချက် (၂-၃ ကြောင်း)

    💡 **အရေးကြီးသော အချက်အလက်များ (Key Takeaways)**
    - အဓိကကျသော အကြောင်းအရာများကို Bullet points များဖြင့် ဖော်ပြရန်

    🎯 **အဆုံးသတ် သုံးသပ်ချက် (Conclusion)**
    - အဓိက သင်ခန်းစာ သို့မဟုတ် ကောက်ချက်

    Transcript:
    {transcript_text[:20000]}
    """
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
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
    video_id = extract_video_id(user_message)

    if not video_id:
        await update.message.reply_text("ကျေးဇူးပြု၍ မှန်ကန်သော YouTube Video Link တစ်ခု ပို့ပေးပါ။")
        return

    status_message = await update.message.reply_text("⏳ ဗီဒီယိုအချက်အလက်များကို ရယူနေပါသည်... ခေတ္တစောင့်ပေးပါ။")

    transcript_text = get_youtube_transcript(video_id)

    if not transcript_text:
        await status_message.edit_text(
            "⚠️ ဒီဗီဒီယိုအတွက် Subtitle/Transcript မတွေ့ရှိပါ သို့မဟုတ် ပိတ်ထားပါသည်။"
        )
        return

    await status_message.edit_text("✍️ Gemini AI ဖြင့် မြန်မာလို Recap ရေးသားနေပါသည်...")

    try:
        recap_result = generate_burmese_recap(transcript_text)
        await status_message.edit_text(recap_result)
    except Exception:
        await status_message.edit_text("⚠️ Recap ထုတ်ယူရာတွင် အမှားအယွင်း ဖြစ်ပေါ်ခဲ့ပါသည်။ နောက်တစ်ကြိမ် ထပ်ကြိုးစားပေးပါ။")


if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
        raise ValueError("TELEGRAM_BOT_TOKEN နှင့် GEMINI_API_KEY လိုအပ်ပါသည်။")

    # Background Dummy Web Server စတင်ခြင်း
    web_thread = Thread(target=run_dummy_server, daemon=True)
    web_thread.start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    app.run_polling()
    
