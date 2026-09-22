# bot.py — Python 3.10+
# python-telegram-bot==20.7

import os
import sys
import subprocess
import tempfile
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ── logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── config ────────────────────────────────────────────────────────────────────
BOT_TOKEN  = os.environ.get("BOT_TOKEN", "")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "0"))   # তোমার Telegram user ID
MAX_TIME   = 15    # seconds
MAX_OUTPUT = 3500  # chars

# ── helpers ───────────────────────────────────────────────────────────────────
def is_admin(update: Update) -> bool:
    if ADMIN_ID == 0:
        return True   # admin set না থাকলে সবাই চালাতে পারবে
    return update.effective_user.id == ADMIN_ID

def run_code(code: str, filename: str = "script.py") -> dict:
    """Execute python code, return dict with stdout/stderr/time."""
    with tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(code)
        path = f.name

    start = datetime.now()
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=MAX_TIME,
        )
        elapsed = (datetime.now() - start).total_seconds()
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "elapsed": elapsed,
            "timeout": False,
            "error": None,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "elapsed": MAX_TIME,
                "timeout": True, "error": None}
    except Exception as e:
        return {"stdout": "", "stderr": "", "elapsed": 0,
                "timeout": False, "error": str(e)}
    finally:
        os.unlink(path)

def format_output(res: dict, filename: str = "script") -> str:
    """Format run result into telegram message."""
    if res["timeout"]:
        return f"❌ *Timeout!*\n{MAX_TIME} সেকেন্ডের বেশি লেগেছে — বন্ধ করা হয়েছে।"
    if res["error"]:
        return f"❌ *System Error:*\n```\n{res['error']}\n```"

    parts = []
    if res["stdout"]:
        out = res["stdout"][:MAX_OUTPUT]
        parts.append(f"✅ *Output:*\n```\n{out}\n```")
    if res["stderr"]:
        err = res["stderr"][:1000]
        parts.append(f"⚠️ *Stderr:*\n```\n{err}\n```")
    if not res["stdout"] and not res["stderr"]:
        parts.append("✅ *Ran successfully* — কোনো output নেই।")

    parts.append(f"⏱ `{res['elapsed']:.2f}s`")
    return "\n".join(parts)

# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    text = (
        f"👋 হ্যালো *{name}*!\n\n"
        "🤖 *Script Runner Bot*\n\n"
        "আমি যা করতে পারি:\n"
        "• `.py` file পাঠাও → run করে output দেব\n"
        "• /run `code` → inline code চালাও\n"
        "• /help → সব commands\n"
        "• /ping → bot জীবিত আছে কিনা দেখো"
    )
    keyboard = [
        [InlineKeyboardButton("📋 Help", callback_data="help"),
         InlineKeyboardButton("🏓 Ping", callback_data="ping")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=reply_markup
    )

# ── /help ─────────────────────────────────────────────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *Commands:*\n\n"
        "/start — শুরু\n"
        "/run `<code>` — inline code চালাও\n"
        "/ping — bot status\n"
        "/help — এই message\n\n"
        "📁 *File:*\n"
        "যেকোনো `.py` file পাঠাও — আমি চালিয়ে output দেব।\n\n"
        f"⏱ Max runtime: `{MAX_TIME}s`\n"
        f"📤 Max output: `{MAX_OUTPUT} chars`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ── /ping ─────────────────────────────────────────────────────────────────────
async def ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! Bot চলছে।")

# ── /run inline ───────────────────────────────────────────────────────────────
async def run_inline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ তোমার permission নেই।")
        return
    if not ctx.args:
        await update.message.reply_text(
            "Usage: `/run print('hello')`", parse_mode="Markdown"
        )
        return

    code = " ".join(ctx.args)
    msg  = await update.message.reply_text("⏳ Running...")
    res  = run_code(code)
    out  = format_output(res)
    await msg.edit_text(out, parse_mode="Markdown")
    logger.info(f"Inline run by {update.effective_user.id} | {code[:50]}")

# ── file upload handler ───────────────────────────────────────────────────────
async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ তোমার permission নেই।")
        return

    doc = update.message.document
    if not doc.file_name.endswith(".py"):
        await update.message.reply_text(
            "❌ শুধু `.py` file পাঠাও।", parse_mode="Markdown"
        )
        return

    msg = await update.message.reply_text(
        f"⏳ `{doc.file_name}` চালাচ্ছি...", parse_mode="Markdown"
    )

    # download file
    with tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="wb"
    ) as tmp:
        tg_file = await ctx.bot.get_file(doc.file_id)
        content = await tg_file.download_as_bytearray()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()
        res = run_code(code, doc.file_name)
        out = format_output(res, doc.file_name)
    finally:
        os.unlink(tmp_path)

    await msg.edit_text(out, parse_mode="Markdown")
    logger.info(
        f"File run: {doc.file_name} | user: {update.effective_user.id}"
    )

# ── callback buttons ──────────────────────────────────────────────────────────
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "help":
        await query.message.reply_text(
            "📋 *Help:*\n`.py` file পাঠাও অথবা /run দিয়ে code লেখো।",
            parse_mode="Markdown"
        )
    elif query.data == "ping":
        await query.message.reply_text("🏓 Bot চলছে!")

# ── error handler ─────────────────────────────────────────────────────────────
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {ctx.error}", exc_info=ctx.error)

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN environment variable set করো!")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_cmd))
    app.add_handler(CommandHandler("ping",  ping))
    app.add_handler(CommandHandler("run",   run_inline))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    print("✅ Bot চালু হচ্ছে...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()