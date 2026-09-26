import os
import re
import json
import logging
import subprocess
import requests
import html
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, PreCheckoutQueryHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = "8828537412:AAHAS_jsgcKGCo3VPit9y4gH-Q2wErroSTE"
URL_PATTERN = r'https?://[^\s]+'
ADMIN_ID = 8839862955  # آيدي الأدمن الخاص بك

BLOCKED_USERNAME = "ddgxgt"
BLOCKED_MESSAGE = "امشي ليك عريض جلبيه تعيب على بوتاتي🥒"

USERS_FILE = "users_detailed.json"
STATS_FILE = "stats.json"

message_links = {}
user_trim_state = {}
user_search_mode = {}  # حالة وضع البحث الخاصة بكل مستخدم

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users_data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)

def load_downloads():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r') as f:
            return json.load(f).get("downloads", 0)
    return 0

def increment_downloads():
    d_count = load_downloads() + 1
    with open(STATS_FILE, 'w') as f:
        json.dump({"downloads": d_count}, f)

async def update_user_activity(user, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    uid = str(user.id)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    is_new = uid not in users
    if is_new:
        users[uid] = {
            "first_seen": now_str,
            "last_active": now_str,
            "name": user.full_name or "بدون اسم",
            "username": f"@{user.username}" if user.username else "بدون يوزر",
            "usage_count": 0,
            "status": "نشط"
        }
        try:
            admin_notify = (
                "🚨 <b>مستخدم جديد دخل إلى البوت!</b>\n\n"
                f"👤 الاسم: {html.escape(user.full_name or 'بدون اسم')}\n"
                f"🔗 اليوزر: @{user.username if user.username else 'لا يوجد'}\n"
                f"🆔 الآيدي: <code>{user.id}</code>\n"
                f"🕒 الوقت: {now_str}"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notify, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Failed to send admin notification: {e}")
    else:
        users[uid]["last_active"] = now_str
        users[uid]["name"] = user.full_name or "بدون اسم"
        users[uid]["username"] = f"@{user.username}" if user.username else "بدون يوزر"
        users[uid]["status"] = "نشط"

    save_users(users)
    return is_new

def increment_user_usage(user_id):
    users = load_users()
    uid = str(user_id)
    if uid in users:
        users[uid]["usage_count"] = users[uid].get("usage_count", 0) + 1
        users[uid]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_users(users)

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
        scale_filter = 'scale=-2:1440:force_original_aspect_ratio=decrease,pad=2560:1440:(ow-iw)/2:(oh-ih)/2'
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
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
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
            'format': 'best[ext=mp4]/best',
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
            for ext in ['.jpg', '.jpeg', '.png', '.webp', '.mp4', '.m4v', '.webm']:
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
        "🔥 <b>أهلاً بك يا فخم في عالم الجيل الجديد!</b> 🚀🇮🇶\n\n"
        "يا هلا بيك في التحفة التقنية الأحدث والأقوى لتنزيل الوسائط.\n\n"
        "✨ <b>المميزات المتوفرة:</b>\n"
        "⚡ تنزيل سريع للروابط وبدون إعلانات.\n"
        "🔍 البحث المباشر (يتطلب تفعيله حصرياً من الأزرار الشفافة).\n"
        "💎 جودات خارقة ومطورة (2K & 1400p).\n"
        "🎧 تحويل الفيديو إلى MP3 باحترافية.\n"
        "🎚️ التحكم الكامل بالصوت.\n"
        "✂️ ميزة القص الذكي للمقاطع.\n\n"
        "📥 أرسل لي رابطاً مباشراً للبدء! 🎯"
    )
    
    keyboard = [[InlineKeyboardButton("🚀 ابدأ بإرسال رابط الآن", callback_data="start_guide")]]
    await update.message.reply_text(start_msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    
    users = load_users()
    broadcast_text = "تم تحديث البوت وصار البحث يعمل حصرياً عبر الزر الشفاف مع زر إغلاق خاص! 🚀🇮🇶"
    
    success_count = 0
    fail_count = 0

    status_msg = await update.message.reply_text(f"🚀 جاري إرسال الإذاعة إلى {len(users)} مستخدم...")

    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=broadcast_text)
            success_count += 1
        except Exception as e:
            logging.error(f"فشل الإرسال إلى {uid}: {e}")
            fail_count += 1

    await status_msg.edit_text(
        f"✅ تمت الإذاعة بنجاح!\n- تم الإرسال إلى: {success_count}\n- فشل الإرسال لـ: {fail_count}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if is_user_blocked(user):
        await update.message.reply_text(BLOCKED_MESSAGE)
        return

    await update_user_activity(user, context)
    text = update.message.text.strip()

    # 1. فحص حالة القص
    if user.id in user_trim_state:
        state_info = user_trim_state.pop(user.id)
        q_val = state_info["query"]
        is_srch = state_info["is_search"]
        
        numbers = re.findall(r'\d+', text)
        if len(numbers) >= 2:
            start_t = numbers[0]
            end_t = numbers[1]

            status_msg = await update.message.reply_text("✂️ <b>جاري قص المقطع بدقة...</b>", parse_mode="HTML")
            file_path = None
            trimmed_path = "downloads/trimmed_output.mp4"
            try:
                file_path = download_media(q_val, is_audio=False, is_search=is_srch)
                trim_video_clip(file_path, start_t, end_t, trimmed_path)

                increment_downloads()
                increment_user_usage(user.id)

                await update.message.reply_video(
                    video=open(trimmed_path, 'rb'),
                    caption=f"✂️ <b>تم قص المقطع بنجاح (من {start_t} إلى {end_t})!</b>\n\n@xlxm3",
                    parse_mode="HTML",
                    supports_streaming=True
                )
                await status_msg.delete()
            except Exception as e:
                logging.error(f"Trim Error: {e}")
                await status_msg.edit_text("حدث خطأ أثناء عملية قص الفيديو!")
            finally:
                if file_path and os.path.exists(file_path): os.remove(file_path)
                if os.path.exists(trimmed_path): os.remove(trimmed_path)
        else:
            await update.message.reply_text("⚠️ يرجى كتابة وقت البداية والنهاية بالأرقام فقط (مثال: 10 إلى 45).")
        return

    # 2. فحص حالة البحث المفعّلة حصرياً من الزر الشفاف
    if user_search_mode.get(user.id, False):
        user_search_mode[user.id] = False  # إيقاف وضع البحث بعد التنفيذ لمرة واحدة
        
        try: await update.message.set_reaction(reaction=[ReactionTypeEmoji(emoji="🔥")])
        except Exception: pass

        status_msg = await update.message.reply_text(
            "⚡ <b>جاري البحث عن الطلب وتحميله بأقصى سرعة...</b>",
            parse_mode="HTML"
        )

        file_path = None
        try:
            file_path = download_media(text, is_audio=False, is_search=True)

            if not file_path or not os.path.exists(file_path):
                raise Exception("File not downloaded properly.")

            msg_id_key = str(update.message.message_id)
            message_links[msg_id_key] = {"query": text, "is_search": True}
            
            keyboard = [
                [InlineKeyboardButton("🎧 تحويل إلى ملف صوتي MP3", callback_data=f"audio_{msg_id_key}")],
                [InlineKeyboardButton("✂️ قص الفيديو (تحديد وقت محدد)", callback_data=f"trim_{msg_id_key}")],
                [InlineKeyboardButton("🌟 تفعيل جودة 2K الخارقة", callback_data=f"resmenu_{msg_id_key}")],
                [InlineKeyboardButton("🎚️ التحكم بمستوى الصوت (رفع/خفض)", callback_data=f"volmenu_{msg_id_key}")],
                [InlineKeyboardButton("🔍 ميزة البحث عن الفيديوهات", callback_data=f"guide_{msg_id_key}")],
                [InlineKeyboardButton("⭐ ادعمني", callback_data=f"starsmenu_{msg_id_key}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            increment_downloads()
            increment_user_usage(user.id)

            caption_text = "شكرا لاستخدامك الجيل الجديد للبوت ❤️\n\nإذا عندك مقترحات راسلني @xlxm3 حتى نطور البوت 🫶🏻🇮🇶"

            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.avif')):
                sent_msg = await update.message.reply_photo(photo=open(file_path, 'rb'), caption=caption_text, reply_markup=reply_markup)
            else:
                sent_msg = await update.message.reply_video(video=open(file_path, 'rb'), caption=caption_text, reply_markup=reply_markup, supports_streaming=True)
            
            try: await sent_msg.set_reaction(reaction=[ReactionTypeEmoji(emoji="❤️")])
            except Exception: pass

            await status_msg.delete()

        except Exception as e:
            logging.error(f"Search Error: {e}")
            await status_msg.edit_text("اعتذر عن الخطأ 🙏🏻 لم أتمكن من العثور على طلبك، تأكد من صحة العنوان.")
        
        finally:
            if file_path and os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass
        return

    # 3. معالجة الروابط العادية فقط إذا أرسل رابط
    match = re.search(URL_PATTERN, text)
    if match:
        query_val = match.group(0)
        is_search = False

        try: await update.message.set_reaction(reaction=[ReactionTypeEmoji(emoji="🔥")])
        except Exception: pass

        status_msg = await update.message.reply_text(
            "⚡ <b>جاري التحميل والإرسال بأقصى سرعة...</b>",
            parse_mode="HTML"
        )

        file_path = None
        try:
            file_path = download_media(query_val, is_audio=False, is_search=is_search)

            if not file_path or not os.path.exists(file_path):
                raise Exception("File not downloaded properly.")

            msg_id_key = str(update.message.message_id)
            message_links[msg_id_key] = {"query": query_val, "is_search": is_search}
            
            keyboard = [
                [InlineKeyboardButton("🎧 تحويل إلى ملف صوتي MP3", callback_data=f"audio_{msg_id_key}")],
                [InlineKeyboardButton("✂️ قص الفيديو (تحديد وقت محدد)", callback_data=f"trim_{msg_id_key}")],
                [InlineKeyboardButton("🌟 تفعيل جودة 2K الخارقة", callback_data=f"res_2K_{msg_id_key}")],
                [InlineKeyboardButton("🎚️ التحكم بمستوى الصوت (رفع/خفض)", callback_data=f"volmenu_{msg_id_key}")],
                [InlineKeyboardButton("🔍 ميزة البحث عن الفيديوهات", callback_data=f"guide_{msg_id_key}")],
                [InlineKeyboardButton("⭐ ادعمني", callback_data=f"starsmenu_{msg_id_key}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            increment_downloads()
            increment_user_usage(user.id)

            caption_text = "شكرا لاستخدامك الجيل الجديد للبوت ❤️\n\nإذا عندك مقترحات راسلني @xlxm3 حتى نطور البوت 🫶🏻🇮🇶"

            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.avif')):
                sent_msg = await update.message.reply_photo(photo=open(file_path, 'rb'), caption=caption_text, reply_markup=reply_markup)
            else:
                sent_msg = await update.message.reply_video(video=open(file_path, 'rb'), caption=caption_text, reply_markup=reply_markup, supports_streaming=True)
            
            try: await sent_msg.set_reaction(reaction=[ReactionTypeEmoji(emoji="❤️")])
            except Exception: pass

            await status_msg.delete()

        except Exception as e:
            logging.error(f"Download/Send Error: {e}")
            await status_msg.edit_text("اعتذر عن الخطأ 🙏🏻 لم أتمكن من العثور على طلبك، تأكد من صحة الرابط.")
        
        finally:
            if file_path and os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass
        return

    if text == "مستخدمين":
        if user.id != ADMIN_ID:
            return
        
        users = load_users()
        if not users:
            await update.message.reply_text("📂 لا يوجد أي مستخدمين مسجلين حتى الآن.")
            return

        total_users = len(users)
        report = f"📊 <b>قائمة المستخدمين الكلية ({total_users}):</b>\n\n"
        
        count = 0
        for uid, info in users.items():
            count += 1
            name = html.escape(info.get("name", "بدون اسم"))
            uname = info.get("username", "بدون يوزر")
            usage = info.get("usage_count", 0)
            last_active = info.get("last_active", "غير محدد")
            
            report += f"<b>{count}. {name}</b> ({uname})\n"
            report += f"🆔 الآيدي: <code>{uid}</code>\n"
            report += f"📥 التنزيلات: <b>{usage}</b>\n"
            report += f"⏱️ آخر نشاط: {last_active}\n"
            report += "-----------------------------------\n"
            
            if len(report) > 3500:
                await update.message.reply_text(report, parse_mode="HTML")
                report = ""

        if report:
            await update.message.reply_text(report, parse_mode="HTML")
        return

    await update.message.reply_text("⚠️ يرجى إرسال **رابط مباشر** أو تفعيل **ميزة البحث** من الأزرار الشفافة للبحث بالعنوان.")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    user_id = query.from_user.id

    if data == "start_guide":
        await query.message.reply_text("أرسل رابط الفيديو المباشر الآن وسأقوم بتحميله فوراً! ⚡")
        return

    if data == "cancel_search":
        user_search_mode[user_id] = False
        await query.message.edit_text("❌ **تم إغلاق ميزة البحث بنجاح.**")
        return

    if data.startswith("starsmenu_"):
        stars_keyboard = [
            [InlineKeyboardButton("⭐ 1 نجمة", callback_data="paystar_1")],
            [InlineKeyboardButton("⭐⭐ 10 نجمات", callback_data="paystar_10")],
            [InlineKeyboardButton("⭐⭐⭐ 50 نجمة", callback_data="paystar_50")],
            [InlineKeyboardButton("⭐⭐⭐⭐ 100 نجمة", callback_data="paystar_100")]
        ]
        await query.message.reply_text("⭐ <b>اختر عدد النجوم لدعم البوت:</b>", reply_markup=InlineKeyboardMarkup(stars_keyboard), parse_mode="HTML")
        return

    if data.startswith("paystar_"):
        amount = int(data.split("_")[1])
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=f"دعم البوت بـ {amount} نجمة ⭐",
            description="شكراً لدعمك المستمر لتطوير البوت ❤️",
            payload=f"stars_payload_{amount}_{query.from_user.id}",
            currency="XTR",
            prices=[LabeledPrice("نجوم تيليجرام", amount)]
        )
        return

    if "_" not in data:
        return

    parts = data.split("_", 1)
    action = parts[0]
    msg_id = parts[1]

    stored_info = message_links.get(msg_id, {"query": "", "is_search": False})
    q_val = stored_info["query"]
    is_srch = stored_info["is_search"]

    if action == "guide":
        user_search_mode[user_id] = True  # تفعيل وضع البحث لهذا المستخدم حصرياً
        guide_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إغلاق الميزة", callback_data="cancel_search")]
        ])
        guide_explanation = (
            "🔍 <b>تم تفعيل ميزة البحث بنجاح!</b>\n\n"
            "أرسل الآن اسم الأغنية أو العنوان الذي تريد البحث عنه بالدردشة.\n\n"
            "<i>إذا أردت إلغاء العملية، اضغط على زر الإغلاق أدناه.</i>"
        )
        await query.message.reply_text(guide_explanation, parse_mode="HTML", reply_markup=guide_markup)
        return

    if action == "trim":
        user_trim_state[user_id] = {"query": q_val, "is_search": is_srch}
        guide_text = (
            "✂️ <b>القص الذكي لتحديد الوقت:</b>\n\n"
            "أرسل لي الآن وقت <b>البداية والنهاية</b> بالثواني (مثال: <code>10 إلى 45</code>).\n"
        )
        await query.message.reply_text(guide_text, parse_mode="HTML")
        return

    if action == "volmenu":
        vol_keyboard = [
            [InlineKeyboardButton("🔊 زيادة 125%", callback_data=f"vboost_1.25_{msg_id}"), InlineKeyboardButton("🔉 تخفيض 75%", callback_data=f"vboost_0.75_{msg_id}")],
            [InlineKeyboardButton("🔊 زيادة 150%", callback_data=f"vboost_1.50_{msg_id}"), InlineKeyboardButton("🔉 تخفيض 50%", callback_data=f"vboost_0.50_{msg_id}")],
            [InlineKeyboardButton("🔊 زيادة 200%", callback_data=f"vboost_2.00_{msg_id}"), InlineKeyboardButton("🔇 كتم الصوت", callback_data=f"vboost_0.00_{msg_id}")]
        ]
        await query.message.reply_text("🎚️ <b>اختر مستوى الصوت المطلوبة:</b>", reply_markup=InlineKeyboardMarkup(vol_keyboard), parse_mode="HTML")
        return

    if action == "resmenu":
        res_keyboard = [
            [InlineKeyboardButton("🚀 تفعيل دقة 2K الخارقة", callback_data=f"upscale_2K_{msg_id}")],
            [InlineKeyboardButton("💎 تفعيل دقة 1400p الاحترافية", callback_data=f"upscale_1400_{msg_id}")]
        ]
        await query.message.reply_text("✨ <b>اختر الجودة الخارقة المطلوبة:</b>", reply_markup=InlineKeyboardMarkup(res_keyboard), parse_mode="HTML")
        return

    if action == "vboost":
        try:
            sub_parts = msg_id.split("_", 1)
            factor_str = sub_parts[0]
            orig_msg_id = sub_parts[1] if len(sub_parts) > 1 else msg_id
            
            factor = float(factor_str)
            status_msg = await query.message.reply_text("🎚️ جاري تعديل مستوى الصوت...")

            s_info = message_links.get(orig_msg_id, {"query": q_val, "is_search": is_srch})
            file_path = download_media(s_info["query"], is_audio=False, is_search=s_info["is_search"])
            processed_path = "downloads/processed_audio.mp4"
            process_audio_volume(file_path, factor, processed_path)

            increment_downloads()
            increment_user_usage(user_id)

            await query.message.reply_video(video=open(processed_path, 'rb'), caption="🎚️ تم تعديل صوت الفيديو بنجاح!\n\n@xlxm3", supports_streaming=True)
            await status_msg.delete()

            if file_path and os.path.exists(file_path): os.remove(file_path)
            if os.path.exists(processed_path): os.remove(processed_path)
        except Exception as e:
            logging.error(f"Volume Adjust Error: {e}")
            await query.message.reply_text("حدث خطأ أثناء تعديل الصوت!")
        return

    if action == "upscale" or action == "res":
        try:
            sub_parts = msg_id.split("_", 1)
            res_type = sub_parts[0]
            orig_msg_id = sub_parts[1] if len(sub_parts) > 1 else msg_id

            status_msg = await query.message.reply_text(f"⏳ جاري رفع دقة الفيديو إلى ({res_type})...")

            s_info = message_links.get(orig_msg_id, {"query": q_val, "is_search": is_srch})
            file_path = download_media(s_info["query"], is_audio=False, is_search=s_info["is_search"])
            file_path = upscale_video_resolution(file_path, res_type)

            increment_downloads()
            increment_user_usage(user_id)

            await query.message.reply_video(
                video=open(file_path, 'rb'),
                caption=f"✨ تم ترقية الفيديو بنجاح إلى الجودة الخارقة ({res_type})!\n\n@xlxm3",
                supports_streaming=True
            )
            await status_msg.delete()

            if file_path and os.path.exists(file_path): os.remove(file_path)
        except Exception as e:
            logging.error(f"Upscale Error: {e}")
            await status_msg.edit_text("حدث خطأ أثناء ترقية الجودة!")
        return

    if action == "audio":
        status_msg = await query.message.reply_text("🎧 جاري استخراج الصوت...")
        file_path = None
        try:
            file_path = download_media(q_val, is_audio=True, is_search=is_srch)
            increment_downloads()
            increment_user_usage(user_id)
            await query.message.reply_audio(audio=open(file_path, 'rb'), caption="🎵 تم استخراج الصوت بنجاح!\n\n@xlxm3")
            await status_msg.delete()
        except Exception as e:
            logging.error(f"Audio Action Error: {e}")
            await status_msg.edit_text("حدث خطأ أثناء تحويل الصوت!")
        finally:
            if file_path and os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❤️ شكراً جزيلاً على دعمك بالنجوم! الله يوفقك ويسعدك 🌟")

if __name__ == '__main__':
    if not os.path.exists('downloads'): 
        os.makedirs('downloads')
        
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 البوت يعمل الآن بالوضع الآمن والدقيق...")
    app.run_polling(drop_pending_updates=True)
