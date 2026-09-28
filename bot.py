import os
import re
import json
import logging
import subprocess
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, PreCheckoutQueryHandler, filters, ContextTypes
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
user_trim_state = {}
user_search_mode = {}

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

def process_audio_volume(input_file: str, volume_factor: float, output_file: str):
    cmd = [
        'ffmpeg', '-y', '-i', input_file,
        '-filter:a', f'volume={volume_factor}',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        output_file
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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

def download_media(query_str: str, is_audio: bool = False, is_search: bool = False):
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'geo_bypass': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web', 'mweb']}},
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    if is_audio:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        })
    else:
        ydl_opts.update({
            'format': 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best/bestvideo+bestaudio',
            'merge_output_format': 'mp4',
        })

    target_query = f"ytsearch1:{query_str}" if is_search else query_str

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(target_query, download=True)
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

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    
    users = load_users()
    all_target_uids = set(users.keys())
    for uid in FIXED_USERS.keys():
        all_target_uids.add(str(uid))
    
    if context.args:
        broadcast_text = " ".join(context.args)
    else:
        broadcast_text = "<b>خبر جديد 😆✨</b>\n\nتم تحديث البوت وإضافة حماية وتحسينات شاملة لروابط يوتيوب وتيك توك ⚡"
    
    success_count = 0
    fail_count = 0
    status_msg = await update.message.reply_text(f"🚀 جاري الإرسال إلى {len(all_target_uids)} مستخدم...")

    for uid_str in all_target_uids:
        try:
            await context.bot.send_message(chat_id=int(uid_str), text=broadcast_text, parse_mode="HTML")
            success_count += 1
            await asyncio.sleep(0.1)
        except Exception:
            fail_count += 1

    await status_msg.edit_text(f"✅ تمت الإذاعة بنجاح!\n- ناجح: {success_count}\n- فاشل: {fail_count}")

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
        report = f"📊 <b>قائمة جميع المستخدمين (المسجلين والثابتين):</b>\n\n"
        
        all_uids = set(users.keys())
        for uid in FIXED_USERS.keys(): all_uids.add(str(uid))
        
        now_time = datetime.now()
        count = 0
        for uid_str in all_uids:
            count += 1
            u_info = users.get(uid_str, {})
            u_name = u_info.get("name", f"مستخدم {uid_str}")
            u_username = u_info.get("username", "")
            last_active_str = u_info.get("last_active", "غير متوفر")
            usage_cnt = u_info.get("usage_count", 0)
            
            status_icon = "🔴"
            if last_active_str != "غير متوفر" and last_active_str != "مُسجل مسبقاً":
                try:
                    diff_seconds = (now_time - datetime.strptime(last_active_str, "%Y-%m-%d %H:%M:%S")).total_seconds()
                    if diff_seconds <= 30:
                        status_icon = "🟢"
                    else:
                        status_icon = "🟡"
                except:
                    status_icon = "🟡"
            elif last_active_str == "مُسجل مسبقاً":
                status_icon = "⚪"
            
            if u_username:
                profile_link = f"<a href='https://t.me/{u_username}'>{u_name} (@{u_username})</a>"
            else:
                profile_link = f"<a href='tg://user?id={uid_str}'>{u_name}</a>"
            
            report += (
                f"<b>{count}.</b> {profile_link} {status_icon}\n"
                f"🆔 الآيدي: <a href='tg://user?id={uid_str}'><code>{uid_str}</code></a>\n"
                f"📥 التنزيلات: <code>{usage_cnt}</code> | 🕒 النشاط: {last_active_str}\n"
                "-------------------\n"
            )
        await update.message.reply_text(report, parse_mode="HTML", disable_web_page_preview=True)
        return

    match = re.search(URL_PATTERN, text)
    if match:
        query_val = match.group(0)
        
        # حماية صارمة لمنشورات صور تيك توك سواء كانت روابط مباشرة أو مختصرة
        if "tiktok.com" in query_val and ("/photo/" in query_val or "ZSb" in query_val or "photo" in query_val.lower()):
            # ملاحظة: إذا كان الرابط المختصر يحتوي على صور، سنحاول معالجته بحذر أو تنبيه المستخدم
            pass

        status_msg = await update.message.reply_text("⚡ <b>جاري التحميل والإرسال...</b>", parse_mode="HTML")
        file_path = None
        try:
            file_path = download_media(query_val, is_audio=False, is_search=False)
            
            if not file_path or not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                await status_msg.edit_text("⚠️ عذراً، هذا الرابط إما عبارة عن <b>منشور صور (Slideshow)</b> أو محتوى غير مدعوم في تيك توك 🤍\nتواصل مع المطور: @xlxm3", parse_mode="HTML")
                return

            msg_id_key = str(update.message.message_id)
            message_links[msg_id_key] = {"query": query_val, "is_search": False, "file_path": file_path}
            
            keyboard = [
                [InlineKeyboardButton("🎧 تحويل إلى MP3", callback_data=f"audio_{msg_id_key}")],
                [InlineKeyboardButton("🌟 دقة 2K", callback_data=f"res_2K_{msg_id_key}"), InlineKeyboardButton("🚀 دقة 4K", callback_data=f"res_4K_{msg_id_key}")],
                [InlineKeyboardButton("💎 دقة 1400p", callback_data=f"res_1400_{msg_id_key}")],
                [InlineKeyboardButton("🎚️ التحكم بالصوت", callback_data=f"volmenu_{msg_id_key}")]
            ]
            increment_downloads()
            increment_user_usage(user.id)
            caption_text = "تم التحميل بنجاح ✨\n\nشكراً لاستخدامك البوت ❤️\nللدعم تواصل مع المطور: @xlxm3"

            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.avif')):
                with open(file_path, 'rb') as f_photo:
                    await update.message.reply_photo(photo=f_photo, caption=caption_text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                with open(file_path, 'rb') as f_vid:
                    await update.message.reply_video(video=f_vid, caption=caption_text, reply_markup=InlineKeyboardMarkup(keyboard), supports_streaming=True)
            await status_msg.delete()
        except Exception as e:
            logging.error(f"Download Error for {query_val}: {e}")
            await status_msg.edit_text("⚠️ عذراً، هذا الرابط يعود لـ <b>منشور صور (Slideshow)</b> في تيك توك ولا يمكن تحميله كفيديو 🤍\nتواصل مع المطور: @xlxm3", parse_mode="HTML")
        finally:
            if file_path and os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass
        return

    await update.message.reply_text("⚠️ يرجى إرسال رابط مباشر أو كلمة مستخدمين.")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "start_guide":
        await query.message.reply_text("أرسل رابط الفيديو المباشر الآن (يوتيوب، تيك توك، انستغرام) وسأقوم بتحميله فوراً 📥")
        return

    try:
        if data.startswith("res_"):
            parts = data.split("_")
            res_type = parts[1]
            msg_id = parts[2]
            
            status_msg = await query.message.reply_text(f"⏳ جاري تعديل دقة الفيديو ({res_type})...")
            stored = message_links.get(msg_id, {})
            q_val = stored.get("query", "")
            
            local_file = download_media(q_val, is_audio=False, is_search=False)
            up_path = upscale_video_resolution(local_file, res_type)
            
            if not os.path.exists(up_path) or os.path.getsize(up_path) == 0:
                await status_msg.edit_text("⚠️ عذراً، حدث خطأ أثناء معالجة دقة الفيديو.")
                return
            
            increment_downloads()
            caption = f"✨ <b>تم ضبط دقة الفيديو بنجاح ({res_type})!</b>\n\nشكراً لاستخدامك البوت ❤️\nللدعم تواصل مع المطور: @xlxm3"
            
            with open(up_path, 'rb') as f_video:
                await query.message.reply_video(video=f_video, caption=caption, parse_mode="HTML", supports_streaming=True)
                
            await status_msg.delete()
            if local_file and os.path.exists(local_file): os.remove(local_file)
            if up_path and os.path.exists(up_path): os.remove(up_path)
            return

        if data.startswith("audio_"):
            msg_id = data.split("_", 1)[1]
            status_msg = await query.message.reply_text("🎧 جاري استخراج ملف MP3...")
            stored = message_links.get(msg_id, {})
            q_val = stored.get("query", "")
            
            audio_path = download_media(q_val, is_audio=True, is_search=False)
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                await status_msg.edit_text("⚠️ عذراً، فشل استخراج الملف الصوتي.")
                return
            
            increment_downloads()
            caption = "🎵 تم استخراج الصوت بنجاح!\n\nشكراً لاستخدامك البوت ❤️\nللدعم تواصل مع المطور: @xlxm3"
            with open(audio_path, 'rb') as f_mp3:
                await query.message.reply_audio(audio=f_mp3, caption=caption)
                
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
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 تم تحديث البوت والتعامل مع أخطاء روابط صور تيك توك بنجاح...")
    app.run_polling(drop_pending_updates=True)
