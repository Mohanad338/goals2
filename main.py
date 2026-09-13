import os
import json
import time
import asyncio
import requests
from telethon import TelegramClient, events
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
FIRST_RUN_BACKFILL = 5
MAX_RUNTIME_SECONDS = 5 * 3600 + 40 * 60  # 5 ساعات و40 دقيقة

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)


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
        r = requests.post(url, data={"chat_id": TARGET_CHANNEL, "text": full_text, "disable_web_page_preview": True}, timeout=30)

    print("TELEGRAM SEND STATUS:", r.status_code)
    print("TELEGRAM SEND RESPONSE:", r.text)
    r.raise_for_status()


async def handle_message(msg):
    last_id = load_last_id()
    if msg.id <= last_id:
        return

    text = msg.message or ""
    full_text = f"{text}\n\n{CHANNEL_LINK}" if text else CHANNEL_LINK

    is_video = bool(msg.media and isinstance(msg.media, MessageMediaDocument) and msg.video)
    is_photo = bool(msg.media and isinstance(msg.media, MessageMediaPhoto))

    try:
        if is_video:
            sent = await client.forward_messages(TARGET_CHANNEL, msg, drop_author=True)
            sent_msg = sent[0] if isinstance(sent, list) else sent
            await client.edit_message(TARGET_CHANNEL, sent_msg, full_text)
            print("DEBUG: forwarded video for msg", msg.id)

        elif is_photo:
            media_path = None
            try:
                media_path = await asyncio.wait_for(
                    client.download_media(msg, file="temp_media"),
                    timeout=DOWNLOAD_TIMEOUT
                )
            except Exception as e:
                print("DEBUG: photo download failed:", e)

            if media_path:
                send_to_telegram(text, media_path, "photo")
                if os.path.exists(media_path):
                    os.remove(media_path)
            elif text.strip():
                send_to_telegram(text)
            else:
                print("DEBUG: skipping empty message", msg.id)

        elif text.strip():
            send_to_telegram(text)

        else:
            print("DEBUG: skipping empty message", msg.id)

    except Exception as e:
        print("DEBUG: failed to process msg", msg.id, ":", e)
        return  # لا نحدث last_id لو فشل، عشان يحاول مرة ثانية لاحقاً

    save_last_id(msg.id)


@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def live_handler(event):
    await handle_message(event.message)


async def catch_up():
    last_id = load_last_id()
    if last_id == 0:
        print("DEBUG: first run, backfilling last", FIRST_RUN_BACKFILL, "posts only")
        latest = await client.get_messages(SOURCE_CHANNEL, limit=1)
        if latest:
            last_id = max(latest[0].id - FIRST_RUN_BACKFILL, 0)
            save_last_id(last_id)

    messages = await client.get_messages(SOURCE_CHANNEL, min_id=last_id, limit=50)
    for msg in reversed(messages):
        await handle_message(msg)


async def main():
    await client.start()
    await catch_up()
    print("DEBUG: listening live for new messages...")
    start = time.time()
    while time.time() - start < MAX_RUNTIME_SECONDS:
        await asyncio.sleep(30)
    await client.disconnect()


asyncio.run(main())
