import os
import json
import asyncio
import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = os.environ["TG_SESSION"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TARGET_CHANNEL = os.environ["TARGET_CHANNEL"]
SOURCE_CHANNEL = "nar0015"
CHANNEL_LINK = "https://t.me/FabriAr3"

STATE_FILE = "last_id.json"
DOWNLOAD_TIMEOUT = 90
FIRST_RUN_COUNT = 5

def load_last_id():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f).get("last_id", 0)
    return 0

def save_last_id(msg_id):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_id": msg_id}, f)
    print("DEBUG: saved last_id =", msg_id)

def send_to_telegram(text, media_path=None, media_type=None):
    full_text = f"{text}\n\n{CHANNEL_LINK}" if text else CHANNEL_LINK

    if media_type == "photo":
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        with open(media_path, "rb") as f:
            r = requests.post(url, data={"chat_id": TARGET_CHANNEL, "caption": full_text}, files={"photo": f}, timeout=60)
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TARGET_CHANNEL, "text": full_text}, timeout=30)

    print("TELEGRAM SEND STATUS:", r.status_code)
    print("TELEGRAM SEND RESPONSE:", r.text)

async def main():
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await client.start()

    last_id = load_last_id()
    is_first_run = (last_id == 0)
    new_last_id = last_id

    if is_first_run:
        print("DEBUG: first run detected, fetching last", FIRST_RUN_COUNT, "posts only")
        messages = await client.get_messages(SOURCE_CHANNEL, limit=FIRST_RUN_COUNT)
        messages = list(reversed(messages))
    else:
        messages = await client.get_messages(SOURCE_CHANNEL, min_id=last_id, limit=10)
        messages = list(reversed(messages))

    print("DEBUG messages found:", len(messages))

    for msg in messages:
        text = msg.message or ""
        full_text = f"{text}\n\n{CHANNEL_LINK}" if text else CHANNEL_LINK

        is_video = bool(msg.media and isinstance(msg.media, MessageMediaDocument) and msg.video)
        is_photo = bool(msg.media and isinstance(msg.media, MessageMediaPhoto))

        # الفيديو: تحويل (forward) مباشرة بدون تحميل، مع إخفاء اسم المرسل، ثم تعديل الوصف
        if is_video:
            try:
                sent = await client.forward_messages(TARGET_CHANNEL, msg, drop_author=True)
                sent_msg = sent[0] if isinstance(sent, list) else sent
                await client.edit_message(TARGET_CHANNEL, sent_msg, full_text)
                print("DEBUG: forwarded video for msg", msg.id)
            except Exception as e:
                print("DEBUG: forward/edit failed for msg", msg.id, ":", e)
            if msg.id > new_last_id:
                new_last_id = msg.id
            continue

        # الصورة: تحميل وإرسال عن طريق البوت
        media_path = None
        media_type = None
        if is_photo:
            try:
                media_path = await asyncio.wait_for(
                    client.download_media(msg, file="temp_media"),
                    timeout=DOWNLOAD_TIMEOUT
                )
                media_type = "photo"
            except asyncio.TimeoutError:
                print("DEBUG: photo download timed out, sending as text only")
                media_path = None
                media_type = None
            except Exception as e:
                print("DEBUG: photo download failed:", e)
                media_path = None
                media_type = None

        if not text.strip() and not media_path:
            if msg.id > new_last_id:
                new_last_id = msg.id
            continue

        send_to_telegram(text, media_path, media_type)

        if media_path and os.path.exists(media_path):
            os.remove(media_path)

        if msg.id > new_last_id:
            new_last_id = msg.id

    if new_last_id > last_id or is_first_run:
        save_last_id(new_last_id if new_last_id > 0 else last_id)

    await client.disconnect()

asyncio.run(main())
