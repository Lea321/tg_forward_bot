import os
import logging
import random
import re
import time
import html
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

# 扩展颜色池
MARKS = [
    "💎",
    "🔮",
    "🍀",
    "🔥",
    "🌈",
    "⚡️",
    "🌙",
    "🍕",
    "🍔",
    "🍟",
    "🌭",
    "🍿",
    "🍧",
    "🍭",
    "🍡",
    "❤️",
    "🩷",
    "🧡",
    "💛",
    "💚",
    "💙",
    "🩵",
    "💜",
]

# 验证有效期（小时）
try:
    EXPIRE_HOURS = float(os.getenv("EXPIRE_HOURS", "2"))
except:
    EXPIRE_HOURS = 2.0
EXPIRE_TIME = EXPIRE_HOURS * 3600

# 自动删除消息的延迟（秒）
try:
    DELETE_DELAY = int(os.getenv("DELETE_DELAY", "2"))
except:
    DELETE_DELAY = 2

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

pending_users = {}
verified_users = {}

CAPTCHAS = [
    ("请选择：🐶", "🐶"),
    ("请选择：🐱", "🐱"),
    ("请选择：🐼", "🐼"),
    ("请选择：🦊", "🦊"),
    ("请选择：🐸", "🐸"),
]

# --- 工具函数 ---


def get_user_mark(user_id):
    return MARKS[user_id % len(MARKS)]


def generate_captcha():
    q, a = random.choice(CAPTCHAS)
    emojis = ["🐶", "🐱", "🐼", "🦊", "🐸"]
    options = emojis.copy()
    random.shuffle(options)
    buttons = [InlineKeyboardButton(e, callback_data=f"verify:{e}") for e in options]
    return q, a, InlineKeyboardMarkup([buttons])


def extract_user_id(message):
    text = message.text or message.caption or ""
    match = re.search(r"(id|ID)[=：:\s]*(\d+)", text, re.IGNORECASE)
    return int(match.group(2)) if match else None


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id, message_id = job.data
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass


async def send_flash_message(
    context: ContextTypes.DEFAULT_TYPE, chat_id, text, reply_markup=None
):
    try:
        msg = await context.bot.send_message(
            chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="HTML"
        )
        context.job_queue.run_once(
            delete_message_job, when=DELETE_DELAY, data=(chat_id, msg.message_id)
        )
        return msg
    except Exception as e:
        logger.error(f"Flash message error: {e}")


# --- 核心转发逻辑 ---


async def forward_to_owner(context, user_id, user_name, msg):
    """转发并为用户昵称上色"""
    safe_name = html.escape(user_name)
    user_mark = get_user_mark(user_id)
    username_str = f"(@{msg.from_user.username})" if msg.from_user.username else ""
    user_id_str = (
        f"用户ID：{user_id}" if msg.from_user.username else f"tg://user?id={user_id}"
    )

    header = f"{user_mark} <b>{safe_name}</b> {username_str}\n{user_id_str}"

    try:
        params = {"chat_id": OWNER_ID, "parse_mode": "HTML"}

        if msg.text:
            await context.bot.send_message(
                **params, text=f"{header}\n-----------------------\n{msg.text}"
            )
        elif msg.photo:
            await context.bot.send_photo(
                **params,
                photo=msg.photo[-1].file_id,
                caption=f"{header}\n{msg.caption or ''}",
            )
        elif msg.video:
            await context.bot.send_video(
                **params,
                video=msg.video.file_id,
                caption=f"{header}\n{msg.caption or ''}",
            )
        elif msg.sticker:
            await context.bot.send_message(**params, text=header)
            await context.bot.send_sticker(OWNER_ID, msg.sticker.file_id)
        elif msg.voice:
            await context.bot.send_voice(
                **params, voice=msg.voice.file_id, caption=header
            )
        elif msg.video_note:
            await context.bot.send_message(**params, text=header)
            await context.bot.send_video_note(OWNER_ID, msg.video_note.file_id)
        elif msg.audio:
            await context.bot.send_audio(
                **params,
                audio=msg.audio.file_id,
                caption=f"{header}\n{msg.caption or ''}",
            )
        elif msg.document:
            await context.bot.send_document(
                **params,
                document=msg.document.file_id,
                caption=f"{header}\n{msg.caption or ''}",
            )
        elif msg.animation:
            await context.bot.send_animation(
                **params,
                animation=msg.animation.file_id,
                caption=f"{header}\n{msg.caption or ''}",
            )
        else:
            await context.bot.send_message(**params, text=header)
            await msg.forward(OWNER_ID)
    except Exception as e:
        logger.error(f"Forwarding failed: {e}")


# --- 消息/回调处理 ---


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message
    if not msg:
        return

    if user_id == OWNER_ID:
        if msg.reply_to_message:
            target_id = extract_user_id(msg.reply_to_message)
            if target_id:
                try:
                    await msg.copy(target_id)
                    await send_flash_message(context, OWNER_ID, "✅ 已送达")
                    return
                except:
                    await send_flash_message(
                        context, OWNER_ID, "❌ 发送失败，可能被拉黑"
                    )
                    return
        await send_flash_message(context, OWNER_ID, "💡 请回复转发的消息。")
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
            f"🛡 <b>请进行验证</b>：\n{q}", reply_markup=keyboard, parse_mode="HTML"
        )
        return

    await forward_to_owner(context, user_id, update.effective_user.first_name, msg)
    await send_flash_message(context, user_id, "✅ 已送达")


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

        user_mark = get_user_mark(user_id)
        await query.edit_message_text(
            f"✅ 验证通过！\n🎨 您的专属标识：{user_mark}\n⏳ 对话有效期：{EXPIRE_HOURS}小时"
        )
        context.job_queue.run_once(
            delete_message_job,
            when=DELETE_DELAY,
            data=(query.message.chat_id, query.message.message_id),
        )
    else:
        await query.answer("❌ 选错啦！", show_alert=True)


# --- 新增：上线通知功能 ---
async def post_init(application: Application) -> None:
    """机器人启动后执行的任务"""
    if OWNER_ID != 0:
        try:
            await application.bot.send_message(
                chat_id=OWNER_ID,
                text="🚀 <b>机器人已成功启动并上线！</b>\n\n当前配置：\n"
                f"• 验证有效期：{EXPIRE_HOURS} 小时\n"
                f"• 消息删除延迟：{DELETE_DELAY} 秒",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"发送上线通知失败: {e}")


def main():
    if not BOT_TOKEN or not OWNER_ID:
        print("错误：请先在 .env 中设置 BOT_TOKEN 和 OWNER_ID")
        return

    # 在这里添加 post_init 钩子
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_message))

    print("Bot 运行中...")
    app.run_polling()


if __name__ == "__main__":
    main()
