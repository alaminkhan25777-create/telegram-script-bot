# Telegram Script Runner Bot

## Setup

1. @BotFather থেকে token নাও
2. তোমার Telegram User ID জানতে @userinfobot এ /start দাও

## Deploy on Render (Free)

1. এই folder টা GitHub এ push করো
2. render.com → New → Background Worker
3. GitHub repo connect করো
4. Environment Variables:
   - BOT_TOKEN = তোমার bot token
   - ADMIN_ID  = তোমার user ID (শুধু তুমি চালাতে পারবে)
5. Create Worker → Deploy

## Local Test

```bash
pip install -r requirements.txt
export BOT_TOKEN="your_token_here"
export ADMIN_ID="your_user_id"
python bot.py