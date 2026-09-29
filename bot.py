import os
import re
import json
import logging
import subprocess
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = "8828537412:AAHAS_jsgcKGCo3VPit9y4gH-Q2wErroSTE"
URL_PATTERN = r'https?://[^\s]+'
ADMIN_ID = 8839862955  # آيدي الأدمن الخاص بك

FIXED_USERS = {
    938974602: {"name": "مستخدم 1", "username": ""},
    5990156757: {"name": "مستخدم 2", "username": ""},
    6140252398: {"name": "Mostfa Akeel", "username": "masvjx"},
    8223488142: {"name": "مستخدم 3", "username": ""},
    8070988228: {"name": "مستخدم 4", "username": ""},
    8959012413: {"name": "مستخدم 5", "username": ""},
    8635443964: {"name": "مستخدم 6", "username": ""},
    1464881243: {"name": "مستخدم 7", "username": ""},
    969197512: {"name": "مستخدم 8", "username": ""},
    7320625137: {"name": "Mousa ❤️", "username": "Mousaa_313"},
    8839862955: {"name": "المطور", "username": "xlxm3"}
}

BLOCKED_USERNAME = "ddgxgt"
BLOCKED_MESSAGE = "امشي ليك عريض جلبيه تعيب على بوتاتي🥒"

USERS_FILE = "users_detailed.json"
STATS_FILE = "stats.json"

message_links = {}

def load_users():
    users = {}
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
        except Exception as e:
            logging.error(f"Error loading users json: {e}")
    
    for uid, info in FIXED_USERS.items():
        uid_str = str(uid)
        if uid_str not in users:
            users[uid_str] = {
                "first_seen": "مُسجل مسبقاً",
                "last_active": "غير متوفر",
                "name": info["name"],
                "username": info["username"],
                "usage_count": 0,
                "status": "active"
            }
    return users

def save_users(users_data):
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving users json: {e}")

def load_downloads():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f).get("downloads", 0)
        except:
            return 0
    return 0

def increment_downloads():
    d_count = load_downloads() + 1
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump({"downloads": d_count}, f)
    except Exception as e:
        logging.error(f"Error saving stats: {e}")

async def update_user_activity(user, context: ContextTypes.DEFAULT_TYPE):
    try:
        users = load_users()
        uid = str(user.id)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if uid not in users:
            users[uid] = {
                "first_seen": now_str,
                "last_active": now_str,
                "name": user.full_name or "بدون اسم",
                "username": user.username if user.username else "",
                "usage_count": 0,
                "status": "active"
            }
            try:
                admin_notify = (
                    "🚨 <b>مستخدم جديد دخل إلى البوت!</b>\n\n"
                    f"👤 الاسم: {user.full_name or 'بدون اسم'}\n"
                    f"🔗 اليوزر: @{user.username if user.username else 'لا يوجد'}\n"
                    f"🆔 الآيدي: <a href='tg://user?id={user.id}'><code>{user.id}</code></a>"
                )
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notify, parse_mode="HTML")
            except Exception as e:
                logging.error(f"Failed to send admin notification: {e}")
        else:
            users[uid]["last_active"] = now_str
            users[uid]["name"] = user.full_name or "بدون اسم"
            if user.username:
                users[uid]["username"] = user.username
            users[uid]["status"] = "active"

        save_users(users)
    except Exception as e:
        logging.error(f"Error in update_user_activity: {e}")

def increment_user_usage(user_id):
    try:
        users = load_users()
        uid = str(user_id)
        if uid in users:
            users[uid]["usage_count"] = users[uid].get("usage_count", 0) + 1
            users[uid]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_users(users)
        else:
            users[uid] = {
                "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": f"مستخدم {uid}",
                "username": "",
                "usage_count": 1,
                "status": "active"
            }
            save_users(users)
    except Exception as e:
        logging.error(f"Error in increment_user_usage: {e}")

def is_user_blocked(user) -> bool:
    if user.username and user.username.lower() == BLOCKED_USERNAME.lower():
        return True
    return False

def upscale_video_resolution(file_path: str, resolution: str):
    output_hd = f"downloads/processed_{resolution}.mp4"
    if resolution == '2K':
        scale_filter = 'scale=-2:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2'
    elif resolution == '4K':
        scale_filter = 'scale=-2:1000:force_original_aspect_ratio=decrease,pad=1778:1000:(ow-iw)/2:(oh-ih)/2'
    else:
        scale_filter = 'scale=-2:1400:force_original_aspect_ratio=decrease,pad=2400:1400:(ow-iw)/2:(oh-ih)/2'
    
    cmd = [
        'ffmpeg', '-y', '-i', file_path,
        '-vf', scale_filter,
        '-c:v', 'libx264', '-crf', '20', '-preset', 'medium',
        '-c:a', 'aac', '-b:a', '192k', output_hd
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(output_hd):
        return output_hd
    return file_path

def download_media(query_str: str, is_audio: bool = False):
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'geo_bypass': True,
        # إجبار yt-dlp على دمج أفضل فيديو مع أفضل صوت معاً لضمان عدم نزول الفيديو صامتاً
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'extractor_args': {'tiktok': {'web_api': 'v2'}, 'youtube': {'player_client': ['android', 'web', 'mweb']}},
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    if is_audio:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query_str, download=True)
        if 'entries' in info:
            info = info['entries'][0]

        filename = ydl.prepare_filename(info)
        
        if not os.path.exists(filename):
            base, _ = os.path.splitext(filename)
            for ext in ['.jpg', '.jpeg', '.png', '.webp', '.mp4', '.m4v', '.webm', '.mkv']:
                if os.path.exists(base + ext):
                    filename = base + ext
                    break

        if is_audio:
            base, _ = os.path.splitext(filename)
            mp3_path = f"{base}.mp3"
            if os.path.exists(mp3_path):
                return mp3_path
            return filename

        # التأكد من امتداد mp4 للدمج السليم
        if not filename.endswith('.mp4') and os.path.exists(filename):
            base, _ = os.path.splitext(filename)
            mp4_fixed = f"{base}.mp4"
            cmd = ['ffmpeg', '-y', '-i', filename, '-c:v', 'copy', '-c:a', 'aac', mp4_fixed]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(mp4_fixed):
                return mp4_fixed

        return filename

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_user_blocked(user):
        await update.message.reply_text(BLOCKED_MESSAGE)
        return
    await update_user_activity(user, context)
    start_msg = (
        "مرحباً بك عزيزي في بوت تحميل الوسائط 📥\n\n"
        "أداة سريعة لتحميل الفيديوهات والملفات الصوتية من يوتيوب، تيك توك، انستغرام وباقي المنصات بدقة عالية وبدون إعلانات.\n\n"
        "أرسل الرابط المطلوب أو ابدأ الاستخدام عبر الزر أدناه."
    )
    keyboard = [[InlineKeyboardButton("🚀 ابدأ الاستخدام الآن", callback_data="start_guide")]]
    await update.message.reply_text(start_msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_user_blocked(user):
        await update.message.reply_text(BLOCKED_MESSAGE)
        return

    await update_user_activity(user, context)
    text = update.message.text.strip()

    if text == "مستخدمين":
        if user.id != ADMIN_ID: return
        users = load_users()
        report = f"📊 <b>قائمة جميع المستخدمين:</b>\n\n"
        all_uids = set(users.keys())
        for uid in FIXED_USERS.keys(): all_uids.add(str(uid))
        
        count = 0
        for uid_str in all_uids:
            count += 1
            u_info = users.get(uid_str, {})
            u_name = u_info.get("name", f"مستخدم {uid_str}")
            usage_cnt = u_info.get("usage_count", 0)
            report += f"<b>{count}.</b> {u_name} (<code>{uid_str}</code>) - التنزيلات: {usage_cnt}\n"
        await update.message.reply_text(report, parse_mode="HTML")
        return

    match = re.search(URL_PATTERN, text)
    if match:
        query_val = match.group(0)
        status_msg = await update.message.reply_text("⚡ <b>جاري التحميل ومعالجة الصوت والفيديو...</b>", parse_mode="HTML")
        file_path = None
        
        try:
            file_path = download_media(query_val, is_audio=False)
            
            if not file_path or not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                # إذا كان منشور صور (Slideshow)، اسحب الصوت تلقائياً
                await status_msg.edit_text("🎵 <b>هذا الرابط عبارة عن منشور صور، جاري استخراج الصوت MP3...</b>", parse_mode="HTML")
                audio_path = download_media(query_val, is_audio=True)
                
                if audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                    increment_downloads()
                    increment_user_usage(user.id)
                    with open(audio_path, 'rb') as f_aud:
                        await update.message.reply_audio(audio=f_aud, caption="✨ تم استخراج نغمة التيك توك بنجاح!\n\nللدعم: @xlxm3")
                    os.remove(audio_path)
                else:
                    await update.message.reply_text("⚠️ عذراً، لم نتمكن من العثور على محتوى في هذا الرابط.")
                
                await status_msg.delete()
                return

            msg_id_key = str(update.message.message_id)
            message_links[msg_id_key] = {"query": query_val, "file_path": file_path}
            
            keyboard = [
                [InlineKeyboardButton("🎧 تحويل إلى MP3", callback_data=f"audio_{msg_id_key}")],
                [InlineKeyboardButton("🌟 دقة 2K", callback_data=f"res_2K_{msg_id_key}"), InlineKeyboardButton("🚀 دقة 4K", callback_data=f"res_4K_{msg_id_key}")],
                [InlineKeyboardButton("💎 دقة 1400p", callback_data=f"res_1400_{msg_id_key}")]
            ]
            increment_downloads()
            increment_user_usage(user.id)
            caption_text = "تم التحميل بنجاح ✨ (مع الصوت بوضوح)\n\nشكراً لاستخدامك البوت ❤️\nللدعم تواصل مع المطور: @xlxm3"

            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                with open(file_path, 'rb') as f_photo:
                    await update.message.reply_photo(photo=f_photo, caption=caption_text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                with open(file_path, 'rb') as f_vid:
                    await update.message.reply_video(video=f_vid, caption=caption_text, reply_markup=InlineKeyboardMarkup(keyboard), supports_streaming=True)
            await status_msg.delete()
        except Exception as e:
            logging.error(f"Download Error: {e}")
            try:
                audio_path = download_media(query_val, is_audio=True)
                if audio_path and os.path.exists(audio_path):
                    increment_downloads()
                    increment_user_usage(user.id)
                    with open(audio_path, 'rb') as f_aud:
                        await update.message.reply_audio(audio=f_aud, caption="🎵 تم استخراج الصوت بنجاح ❤️\n\nللدعم: @xlxm3")
                    os.remove(audio_path)
                    await status_msg.delete()
                    return
            except:
                pass
            await status_msg.edit_text("⚠️ عذراً، فشل التحميل أو أن الرابط غير مدعوم!\nتواصل مع المطور: @xlxm3")
        finally:
            if file_path and os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass
        return

    await update.message.reply_text("⚠️ يرجى إرسال رابط مباشر صحيح.")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    user_id = query.from_user.id

    if data == "start_guide":
        await query.message.reply_text("أرسل رابط الفيديو المباشر الآن وسأقوم بتحميله مع الصوت بدقة عالية 📥")
        return

    try:
        if data.startswith("res_"):
            parts = data.split("_")
            res_type = parts[1]
            msg_id = parts[2]
            
            status_msg = await query.message.reply_text(f"⏳ جاري تعديل دقة الفيديو ({res_type})...")
            stored = message_links.get(msg_id, {})
            q_val = stored.get("query", "")
            
            local_file = download_media(q_val, is_audio=False)
            up_path = upscale_video_resolution(local_file, res_type)
            
            increment_downloads()
            increment_user_usage(user_id)
            caption = f"✨ <b>تم ضبط دقة الفيديو بنجاح ({res_type})!</b>\n\nللدعم: @xlxm3"
            
            with open(up_path, 'rb') as f_video:
                await query.message.reply_video(video=f_video, caption=caption, parse_mode="HTML", supports_streaming+True if False else True)
                
            await status_msg.delete()
            if local_file and os.path.exists(local_file): os.remove(local_file)
            if up_path and os.path.exists(up_path): os.remove(up_path)
            return

        if data.startswith("audio_"):
            msg_id = data.split("_", 1)[1]
            status_msg = await query.message.reply_text("🎧 جاري استخراج ملف MP3...")
            stored = message_links.get(msg_id, {})
            q_val = stored.get("query", "")
            
            audio_path = download_media(q_val, is_audio=True)
            increment_downloads()
            increment_user_usage(user_id)
            with open(audio_path, 'rb') as f_mp3:
                await query.message.reply_audio(audio=f_mp3, caption="🎵 تم استخراج الصوت بنجاح!\n\nللدعم: @xlxm3")
            await status_msg.delete()
            if audio_path and os.path.exists(audio_path): os.remove(audio_path)
            return
    except Exception as e:
        logging.error(f"Callback Error: {e}")
        await query.message.reply_text("⚠️ حدث خطأ أثناء التنفيذ، تواصل مع المطور: @xlxm3")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 البوت يعمل الآن مع إجبار دمج الصوت والفيديو ومعالجة الروابط بنجاح...")
    app.run_polling(drop_pending_updates=True)
