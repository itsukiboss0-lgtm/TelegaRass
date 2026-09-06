import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH")
BOT_USERNAME = os.getenv("BOT_USERNAME", "MailPulseRobot")
SUPPORT_LINK = os.getenv("SUPPORT_LINK", "https://t.me/MailPulseHelper")

MAX_ACCOUNTS = 1
DATA_FILE = "data.json"
LOG_FILE = "bot.log"
LOG_LEVEL = "INFO"
SCHEDULE_CHECK_INTERVAL = 60

# Список администраторов (их Telegram ID)
ADMINS = [8728680606, 6554626251]  # замените на свои ID

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")