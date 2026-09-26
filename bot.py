import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# إعداد السجل لتتبع الأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# أمر البدء
async def start(command_update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = command_update.effective_user.first_name
    await command_update.message.reply_text(
        f"أهلاً بك يا {user_name} في بوت تحميل الوسائط والسيديات! 🚀\n\n"
        "أرسل لي رابط فيديو أو مقطع من (يوتيوب، تيك توك، انستغرام، وغيرها) وسأقوم بتحميله لك بجودة 720p فوراً."
    )

# دالة التعامل مع الروابط وتحميلها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not url.startswith("http"):
        await update.message.reply_text("يرجى إرسال رابط صالح يبدأ بـ http أو https.")
        return

    status_message = await update.message.reply_text("⏳ جاري معالجة الرابط وتحميل الفيديو... لطفاَ انتظر قليلاً.")
    
    output_filename = "downloaded_video.mp4"
    
    # إعدادات yt-dlp لتحسين الأداء وتقليل استهلاك المعالج (افتراضي 720p)
    ydl_opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'outtmpl': output_filename,
        'noplaylist': True,
        'quiet': True,
    }

    try:
        # تحميل الفيديو
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if os.path.exists(output_filename):
            await status_message.edit_text("📤 جاري إرسال الفيديو إليك...")
            with open(output_filename, 'rb') as video_file:
                await update.message.reply_video(video=video_file)
            
            # حذف الملف بعد الإرسال لتوفير مساحة السيرفر
            os.remove(output_filename)
            await status_message.delete()
        else:
            await status_message.edit_text("❌ عذراً، لم يتم العثور على الفيديو أو حدث خطأ أثناء التحميل.")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_message.edit_text(f"❌ حدث خطأ أثناء تحميل الفيديو: {str(e)}")
        if os.path.exists(output_filename):
            os.remove(output_filename)

def main():
    # استبدل هذا التوكن بتوكن بوتك الحقيقي أو ضعه كمتبي بيئي
    TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
