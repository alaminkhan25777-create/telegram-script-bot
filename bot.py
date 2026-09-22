import os
import sys
import subprocess
import tempfile
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID  = int(os.environ.get("ADMIN_ID", "0"))
MAX_TIME  = 15

def is_admin(update):
    if ADMIN_ID == 0:
        return True
    return update.effective_user.id == ADMIN_ID

def run_code(code):
    with tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(code)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=MAX_TIME
        )
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()
        return stdout, stderr, False
    except subprocess.TimeoutExpired:
        return "", "", True
    except Exception as e:
        return "", str(e), False
    finally:
        os.unlink(path)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Script Runner Bot\n\n"
        ".py file পাঠাও — run করে output দেব।\n"
        "/run code — inline code চালাও।\n"
        "/ping — bot status।"
    )

async def ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Bot চলছে!")

async def run_inline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ permission নেই।")
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /run print('hello')")
        return
    code = " ".join(ctx.args)
    msg  = await update.message.reply_text("⏳ Running...")
    stdout, stderr, timeout = run_code(code)
    if timeout:
        await msg.edit_text("❌ Timeout!")
    elif stdout:
        await msg.edit_text(f"✅ Output:\n```\n{stdout[:3000]}\n```",
                            parse_mode="Markdown")
    elif stderr:
        await msg.edit_text(f"⚠️ Error:\n```\n{stderr[:1000]}\n```",
                            parse_mode="Markdown")
    else:
        await msg.edit_text("✅ Done — কোনো output নেই।")

async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ permission নেই।")
        return
    doc = update.message.document
    if not doc.file_name.endswith(".py"):
        await update.message.reply_text("❌ শুধু .py file পাঠাও।")
        return
    msg = await update.message.reply_text(f"⏳ {doc.file_name} চালাচ্ছি...")
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
        stdout, stderr, timeout = run_code(code)
        if timeout:
            reply = "❌ Timeout!"
        elif stdout:
            reply = f"✅ Output:\n```\n{stdout[:3000]}\n```"
        elif stderr:
            reply = f"⚠️ Error:\n```\n{stderr[:1000]}\n```"
        else:
            reply = "✅ Done — কোনো output নেই।"
    finally:
        os.unlink(tmp_path)
    await msg.edit_text(reply, parse_mode="Markdown")

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN নেই!")
        sys.exit(1)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping",  ping))
    app.add_handler(CommandHandler("run",   run_inline))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    print("✅ Bot চালু হচ্ছে...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
