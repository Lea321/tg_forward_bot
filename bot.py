import os
import logging
import random
import re
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

# --- 配置 ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

try:
    EXPIRE_HOURS = float(os.getenv("EXPIRE_HOURS", "2"))
except:
    EXPIRE_HOURS = 2.0
EXPIRE_TIME = EXPIRE_HOURS * 3600

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

pending_users = {}  # user_id: {"answer": str}
verified_users = {}  # user_id: timestamp

CAPTCHAS = [
    ("请选择：🐶", "🐶"),
    ("请选择：🐱", "🐱"),
    ("请选择：🐼", "🐼"),
    ("请选择：🦊", "🦊"),
    ("请选择：🐸", "🐸"),
]


def generate_captcha():
    q, a = random.choice(CAPTCHAS)
    emojis = ["🐶", "🐱", "🐼", "🦊", "🐸"]
    options = emojis.copy()
    random.shuffle(options)
    buttons = [InlineKeyboardButton(e, callback_data=f"verify:{e}") for e in options]
    return q, a, InlineKeyboardMarkup([buttons])


def extract_user_id(message):
    """从消息中提取 ID"""
    text = message.text or message.caption or ""
    match = re.search(r"ID[:：]\s*(\d+)", text)
    return int(match.group(1)) if match else None


# --- 核心转发逻辑 ---


async def forward_to_owner(context, user_id, user_name, msg):
    """转发给管理员（全媒体支持）"""
    username = f"(@{msg.from_user.username})" if msg.from_user.username else ""
    header = f"👤 <b>{user_name}</b> {username}\n用户ID: <code>{user_id}</code>"

    try:
        if msg.text:
            await context.bot.send_message(
                OWNER_ID,
                f"{header}\n-----------------------\n{msg.text}",
                parse_mode="HTML",
            )
        elif msg.photo:
            await context.bot.send_photo(
                OWNER_ID,
                msg.photo[-1].file_id,
                caption=f"{header}{msg.caption or ''}",
                parse_mode="HTML",
            )
        elif msg.video:
            await context.bot.send_video(
                OWNER_ID,
                msg.video.file_id,
                caption=f"{header}{msg.caption or ''}",
                parse_mode="HTML",
            )
        elif msg.sticker:
            await context.bot.send_message(OWNER_ID, header, parse_mode="HTML")
            await context.bot.send_sticker(OWNER_ID, msg.sticker.file_id)
        elif msg.voice:
            await context.bot.send_voice(
                OWNER_ID, msg.voice.file_id, caption=header, parse_mode="HTML"
            )
        elif msg.video_note:
            await context.bot.send_message(OWNER_ID, header, parse_mode="HTML")
            await context.bot.send_video_note(OWNER_ID, msg.video_note.file_id)
        elif msg.audio:
            await context.bot.send_audio(
                OWNER_ID,
                msg.audio.file_id,
                caption=f"{header}{msg.caption or ''}",
                parse_mode="HTML",
            )
        elif msg.document:
            await context.bot.send_document(
                OWNER_ID,
                msg.document.file_id,
                caption=f"{header}{msg.caption or ''}",
                parse_mode="HTML",
            )
        elif msg.animation:
            await context.bot.send_animation(
                OWNER_ID,
                msg.animation.file_id,
                caption=f"{header}{msg.caption or ''}",
                parse_mode="HTML",
            )
        else:
            await context.bot.send_message(OWNER_ID, header, parse_mode="HTML")
            await msg.forward(OWNER_ID)
    except Exception as e:
        logger.error(f"转发失败: {e}")


async def reply_to_user(context, target_id, msg):
    """回复给用户（全媒体支持）"""
    try:
        if msg.text:
            await context.bot.send_message(target_id, f"{msg.text}", parse_mode="HTML")
        elif msg.photo:
            await context.bot.send_photo(
                target_id, msg.photo[-1].file_id, caption=msg.caption or ""
            )
        elif msg.video:
            await context.bot.send_video(
                target_id, msg.video.file_id, caption=msg.caption or ""
            )
        elif msg.sticker:
            await context.bot.send_sticker(target_id, msg.sticker.file_id)
        elif msg.voice:
            await context.bot.send_voice(target_id, msg.voice.file_id)
        elif msg.video_note:
            await context.bot.send_video_note(target_id, msg.video_note.file_id)
        elif msg.audio:
            await context.bot.send_audio(
                target_id, msg.audio.file_id, caption=msg.caption or ""
            )
        elif msg.document:
            await context.bot.send_document(
                target_id, msg.document.file_id, caption=msg.caption or ""
            )
        elif msg.animation:
            await context.bot.send_animation(target_id, msg.animation.file_id)
        else:
            await msg.forward(target_id)
        return True
    except Exception as e:
        logger.error(f"回复失败: {e}")
        return False


# --- 事件处理 ---


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    if not msg:
        return

    if user_id == OWNER_ID:
        if msg.reply_to_message:
            target_id = extract_user_id(msg.reply_to_message)
            if target_id and await reply_to_user(context, target_id, msg):
                await msg.reply_text("✅ 已送达")
                return
        await msg.reply_text("💡 请回复转发消息进行回应。")
        return

    if (
        user_id in verified_users
        and (time.time() - verified_users[user_id]) > EXPIRE_TIME
    ):
        del verified_users[user_id]

    if user_id not in verified_users:
        q, answer, keyboard = generate_captcha()
        pending_users[user_id] = {"answer": answer}
        await msg.reply_text(
            f"🛡 <b>请进行安全验证</b>：\n{q}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return

    await forward_to_owner(context, user_id, update.effective_user.first_name, msg)
    await msg.reply_text("✅ 已送达")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if (
        user_id in pending_users
        and query.data == f"verify:{pending_users[user_id]['answer']}"
    ):
        verified_users[user_id] = time.time()
        del pending_users[user_id]
        await query.edit_message_text(f"✅ 验证通过，有效期 {EXPIRE_HOURS} 小时。")
    else:
        await query.answer("❌ 选错啦，请重试", show_alert=True)


async def post_init(application: Application):
    """启动成功后的通知逻辑"""
    if OWNER_ID != 0:
        try:
            await application.bot.send_message(
                OWNER_ID,
                f"🚀 <b>机器人启动成功！</b>\n当前验证有效期设置：{EXPIRE_HOURS} 小时。\n直接回复转发的消息即可回应用户。",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"启动通知发送失败: {e}")


def main():
    if not BOT_TOKEN or not OWNER_ID:
        print("错误: 缺失 BOT_TOKEN 或 OWNER_ID")
        return
    # 加入 post_init 以在启动时发消息
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", lambda u, c: handle_message(u, c)))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_message))
    print(f"Bot 运行中 (有效期: {EXPIRE_HOURS}h)...")
    app.run_polling()


if __name__ == "__main__":
    main()
