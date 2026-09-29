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

def trim_video_clip(input_file: str, start_time: str, end_time: str, output_file: str):
    cmd = [
        'ffmpeg', '-y', '-ss', start_time, '-to', end_time, '-i', input_file,
        '-c:v', 'libx264', '-crf', '22', '-preset', 'fast',
        '-c:a', 'aac', '-b:a', '192k', output_file
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
        'format': 'bestvideo+bestaudio/best/best',
        'merge_output_format': 'mp4',
        'extractor_args': {
            'youtube': {'player_client': ['android', 'web']},
            'tiktok': {'app_version': ['16.6.4']}
        },
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    if is_audio:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        })

    target_query = f"ytsearch1:{query_str}" if is_search else query_str

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(target_query, download=True)
        if isinstance(info, dict) and 'entries' in info:
            entries = info['entries']
            if entries:
                info = entries[0]
            else:
                raise Exception("No entries found")

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
        broadcast_text = "<b>خبر جديد 😆✨</b>\n\nتم تحديث البوت وإصلاح مشكلة الـ bool وتحسين استقرار روابط تيك توك ويوتيوب ⚡"
    
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

    if user.id in user_trim_state:
        state_info = user_trim_state.pop(user.id)
        q_val = state_info["query"]
        is_srch = state_info["is_search"]
        
        numbers = re.findall(r'\d+', text)
        if len(numbers) >= 2:
            start_t, end_t = numbers[0], numbers[1]
            status_msg = await update.message.reply_text("✂️ <b>جاري قص المقطع...</b>", parse_mode="HTML")
            file_path, trimmed_path = None, "downloads/trimmed_output.mp4"
            try:
                file_path = download_media(q_val, is_audio=False, is_search=is_srch)
                trim_video_clip(file_path, start_t, end_t, trimmed_path)
                increment_downloads()
                increment_user_usage(user.id)

                completion_caption = (
                    f"✂️ <b>تم قص المقطع بنجاح (من {start_t} إلى {end_t})!</b>\n\n"
                    "شكراً لاستخدامك البوت ❤️\n"
                    "لأي مقترح تواصل مع المطور: @xlxm3"
                )
                with open(trimmed_path, 'rb') as f_trim:
                    await update.message.reply_video(video=f_trim, caption=completion_caption, parse_mode="HTML", supports_streaming=True)
                await status_msg.delete()
            except Exception as e:
                logging.error(f"Trim Error: {e}")
                await status_msg.edit_text("⚠️ عذراً، حدث خطأ أثناء قص الفيديو!\nتواصل مع المطور للاكتشاف والحل: @xlxm3")
            finally:
                if file_path and os.path.exists(file_path): os.remove(file_path)
                if os.path.exists(trimmed_path): os.remove(trimmed_path)
        else:
            await update.message.reply_text("⚠️ يرجى كتابة وقت البداية والنهاية بالأرقام (مثال: 10 إلى 45).")
        return

    if user_search_mode.get(user.id, False):
        user_search_mode[user.id] = False
        status_msg = await update.message.reply_text("⚡ <b>جاري البحث والتحميل...</b>", parse_mode="HTML")
        file_path = None
        try:
            file_path = download_media(text, is_audio=False, is_search=True)
            msg_id_key = str(update.message.message_id)
            message_links[msg_id_key] = {"query": text, "is_search": True, "file_path": file_path}
            
            keyboard = [
                [InlineKeyboardButton("🎧 تحويل إلى MP3", callback_data=f"audio_{msg_id_key}")],
                [InlineKeyboardButton("✂️ قص الفيديو", callback_data=f"trim_{msg_id_key}")],
                [InlineKeyboardButton("🌟 دقة 2K", callback_data=f"res_2K_{msg_id_key}"), InlineKeyboardButton("🚀 دقة 4K", callback_data=f"res_4K_{msg_id_key}")],
                [InlineKeyboardButton("💎 دقة 1400p", callback_data=f"res_1400_{msg_id_key}")],
                [InlineKeyboardButton("🎚️ التحكم بالصوت", callback_data=f"volmenu_{msg_id_key}")],
                [InlineKeyboardButton("🔍 ميزة البحث", callback_data=f"guide_{msg_id_key}")],
                [InlineKeyboardButton("⭐ ادعمني", callback_data=f"starsmenu_{msg_id_key}")]
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
            logging.error(f"Search Error: {e}")
            await status_msg.edit_text("⚠️ عذراً، فشل التحميل أو أن المحتوى غير مدعوم!\nتواصل مع المطور للاكتشاف والحل: @xlxm3")
        finally:
            if file_path and os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass
        return

    match = re.search(URL_PATTERN, text)
    if match:
        query_val = match.group(0)
        status_msg = await update.message.reply_text("⚡ <b>جاري التحميل ومعالجة الرابط...</b>", parse_mode="HTML")
        file_path = None
        try:
            file_path = download_media(query_val, is_audio=False, is_search=False)
            
            if not file_path or not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                await status_msg.edit_text("⚠️ عذراً، لم يتم العثور على فيديو صالح في هذا الرابط.\nتواصل مع المطور: @xlxm3")
                return

            msg_id_key = str(update.message.message_id)
            message_links[msg_id_key] = {"query": query_val, "is_search": False, "file_path": file_path}
            
            keyboard = [
                [InlineKeyboardButton("🎧 تحويل إلى MP3", callback_data=f"audio_{msg_id_key}")],
                [InlineKeyboardButton("✂️ قص الفيديو", callback_data=f"trim_{msg_id_key}")],
                [InlineKeyboardButton("🌟 دقة 2K", callback_data=f"res_2K_{msg_id_key}"), InlineKeyboardButton("🚀 دقة 4K", callback_data=f"res_4K_{msg_id_key}")],
                [InlineKeyboardButton("💎 دقة 1400p", callback_data=f"res_1400_{msg_id_key}")],
                [InlineKeyboardButton("🎚️ التحكم بالصوت", callback_data=f"volmenu_{msg_id_key}")],
                [InlineKeyboardButton("🔍 ميزة البحث", callback_data=f"guide_{msg_id_key}")],
                [InlineKeyboardButton("⭐ ادعمني", callback_data=f"starsmenu_{msg_id_key}")]
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
            await status_msg.edit_text("⚠️ عذراً، فشل التحميل أو الرابط محمي أو غير مدعوم حالياً!\nتواصل مع المطور للاكتشاف والحل: @xlxm3")
        finally:
            if file_path and os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass
        return

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

    await update.message.reply_text("⚠️ يرجى إرسال رابط مباشر أو تفعيل ميزة البحث.")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    user_id = query.from_user.id

    if data == "start_guide":
        await query.message.reply_text("أرسل رابط الفيديو المباشر الآن (يوتيوب، تيك توك، انستغرام) وسأقوم بتحميله فوراً 📥")
        return

    if data in ["cancel_search", "cancel_trim"]:
        if data == "cancel_search": user_search_mode[user_id] = False
        if data == "cancel_trim": user_trim_state.pop(user_id, None)
        await query.message.edit_text("❌ تم إغلاق الميزة بنجاح.")
        return

    if data.startswith("starsmenu_"):
        stars_keyboard = [
            [InlineKeyboardButton("⭐ 1 نجمة", callback_data="paystar_1")],
            [InlineKeyboardButton("⭐⭐ 10 نجمات", callback_data="paystar_10")],
            [InlineKeyboardButton("⭐⭐⭐ 50 نجمة", callback_data="paystar_50")]
        ]
        await query.message.reply_text("⭐ اختر عدد النجوم لدعم البوت:", reply_markup=InlineKeyboardMarkup(stars_keyboard))
        return

    if data.startswith("paystar_"):
        amount = int(data.split("_")[1])
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=f"دعم البوت بـ {amount} نجمة ⭐",
            description="شكراً لدعمك المستمر ❤️",
            payload=f"stars_{amount}",
            currency="XTR",
            prices=[LabeledPrice("نجوم", amount)]
        )
        return

    try:
        if data.startswith("guide_"):
            user_search_mode[user_id] = True
            await query.message.reply_text("🔍 <b>أرسل الآن اسم البحث المطلوب:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إغلاق", callback_data="cancel_search")]]))
            return

        if data.startswith("trim_"):
            msg_id = data.split("_", 1)[1]
            stored = message_links.get(msg_id, {"query": "", "is_search": False})
            user_trim_state[user_id] = {"query": stored["query"], "is_search": stored["is_search"]}
            await query.message.reply_text("✂️ أرسل وقت البداية والنهاية (مثال: <code>10 إلى 30</code>)", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إغلاق", callback_data="cancel_trim")]]))
            return

        if data.startswith("volmenu_"):
            msg_id = data.split("_", 1)[1]
            vol_keyboard = [
                [InlineKeyboardButton("🔉 تخفيض -25%", callback_data=f"vboost_0.75_{msg_id}"), InlineKeyboardButton("🔊 زيادة 125%", callback_data=f"vboost_1.25_{msg_id}")],
                [InlineKeyboardButton("🔉 تخفيض -50%", callback_data=f"vboost_0.50_{msg_id}"), InlineKeyboardButton("🔊 زيادة 150%", callback_data=f"vboost_1.50_{msg_id}")],
                [InlineKeyboardButton("🔉 تخفيض -75%", callback_data=f"vboost_0.25_{msg_id}"), InlineKeyboardButton("🔊 زيادة 175%", callback_data=f"vboost_1.75_{msg_id}")],
                [InlineKeyboardButton("🔇 كتم -100%", callback_data=f"vboost_0.00_{msg_id}"), InlineKeyboardButton("🔊 زيادة 200%", callback_data=f"vboost_2.00_{msg_id}")]
            ]
            await query.message.reply_text("🎚️ اختر مستوى الصوت:", reply_markup=InlineKeyboardMarkup(vol_keyboard))
            return

        if data.startswith("res_"):
            parts = data.split("_")
            res_type = parts[1]
            msg_id = parts[2]
            
            status_msg = await query.message.reply_text(f"⏳ جاري تعديل دقة الفيديو ({res_type})...")
            
            stored = message_links.get(msg_id, {})
            q_val = stored.get("query", "")
            is_srch = stored.get("is_search", False)
            
            local_file = download_media(q_val, is_audio=False, is_search=is_srch)
            up_path = upscale_video_resolution(local_file, res_type)
            
            if not os.path.exists(up_path) or os.path.getsize(up_path) == 0:
                await status_msg.edit_text("⚠️ عذراً، حدث خطأ أثناء معالجة دقة الفيديو أو أن الملف غير موجود.")
                return
            
            increment_downloads()
            increment_user_usage(user_id)
            
            caption = (
                f"✨ <b>تم ضبط دقة الفيديو بنجاح ({res_type})!</b>\n\n"
                "شكراً لاستخدامك البوت ❤️\n"
                "للدعم تواصل مع المطور: @xlxm3"
            )
            
            with open(up_path, 'rb') as f_video:
                await query.message.reply_video(video=f_video, caption=caption, parse_mode="HTML", supports_streaming=True)
                
            await status_msg.delete()
            if local_file and os.path.exists(local_file): os.remove(local_file)
            if up_path and os.path.exists(up_path): os.remove(up_path)
            return

        if data.startswith("vboost_"):
            parts = data.split("_")
            factor = float(parts[1])
            msg_id = parts[2]
            
            status_msg = await query.message.reply_text("🎚️ جاري تعديل مستوى الصوت...")
            
            stored = message_links.get(msg_id, {})
            q_val = stored.get("query", "")
            is_srch = stored.get("is_search", False)
            
            local_file = download_media(q_val, is_audio=False, is_search=is_srch)
            processed_path = "downloads/processed_audio.mp4"
            process_audio_volume(local_file, factor, processed_path)
            
            if not os.path.exists(processed_path) or os.path.getsize(processed_path) == 0:
                await status_msg.edit_text("⚠️ عذراً، حدث خطأ أثناء معالجة الصوت.")
                return
            
            increment_downloads()
            increment_user_usage(user_id)
            
            caption = "🎚️ تم تعديل الصوت بنجاح!\n\nشكراً لاستخدامك البوت ❤️\nللدعم تواصل مع المطور: @xlxm3"
            with open(processed_path, 'rb') as f_audio:
                await query.message.reply_video(video=f_audio, caption=caption, supports_streaming=True)
                
            await status_msg.delete()
            if local_file and os.path.exists(local_file): os.remove(local_file)
            if processed_path and os.path.exists(processed_path): os.remove(processed_path)
            return

        if data.startswith("audio_"):
            msg_id = data.split("_", 1)[1]
            status_msg = await query.message.reply_text("🎧 جاري استخراج ملف MP3...")
            stored = message_links.get(msg_id, {})
            q_val = stored.get("query", "")
            is_srch = stored.get("is_search", False)
            
            audio_path = download_media(q_val, is_audio=True, is_search=is_srch)
            
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                await status_msg.edit_text("⚠️ عذراً، فشل استخراج الملف الصوتي.")
                return
            
            increment_downloads()
            increment_user_usage(user_id)
            
            caption = "🎵 تم استخراج الصوت بنجاح!\n\nشكراً لاستخدامك البوت ❤️\nللدعم تواصل مع المطور: @xlxm3"
            with open(audio_path, 'rb') as f_mp3:
                await query.message.reply_audio(audio=f_mp3, caption=caption)
                
            await status_msg.delete()
            if audio_path and os.path.exists(audio_path): os.remove(audio_path)
            return

    except Exception as e:
        logging.error(f"Callback Error in data '{data}': {e}")
        await query.message.reply_text(
            "⚠️ **عذراً، حدث خطأ أثناء تنفيذ العملية.**\n\n"
            "يرجى المحاولة لاحقاً، وإذا تكررت المشكلة يرجى التواصل مع المطور للاكتشاف والحل:\n"
            "@xlxm3",
            parse_mode="HTML"
        )

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❤️ شكراً جزيلاً على دعمك بالنجوم!")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 تم تحديث البوت وحل مشكلة روابط تيك توك بالكامل...")
    app.run_polling(drop_pending_updates=True)
