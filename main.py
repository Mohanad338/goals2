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
VIDEO_MAX_SECONDS = 600  # 10 دقائق - أي فيديو أطول من هذا يتجاهل ولا ينشر

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
    elif media_type == "video":
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
        with open(media_path, "rb") as f:
            r = requests.post(url, data={"chat_id": TARGET_CHANNEL, "caption": full_text}, files={"video": f}, timeout=120)
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id": TARGET_CHANNEL, "text": full_text}, timeout=30)

    print("TELEGRAM SEND STATUS:", r.status_code)
    print("TELEGRAM SEND RESPONSE:", r.text)

def get_video_duration(msg):
    try:
        if msg.file and msg.file.duration:
            return msg.file.duration
    except Exception:
        pass
    return None

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

        media_path = None
        media_type = None
        if msg.media:
            try:
                detected_type = None
                if isinstance(msg.media, MessageMediaPhoto):
                    detected_type = "photo"
                elif isinstance(msg.media, MessageMediaDocument) and msg.video:
                    duration = get_video_duration(msg)
                    if duration is not None and duration > VIDEO_MAX_SECONDS:
                        print(f"DEBUG: skipping long video ({duration}s) for msg {msg.id}")
                        detected_type = None
                    else:
                        detected_type = "video"

                if detected_type:
                    media_path = await asyncio.wait_for(
                        client.download_media(msg, file="temp_media"),
                        timeout=DOWNLOAD_TIMEOUT
                    )
                    media_type = detected_type
            except asyncio.TimeoutError:
                print("DEBUG: media download timed out, sending as text only")
                media_path = None
                media_type = None
            except Exception as e:
                print("DEBUG: media download failed:", e)
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
