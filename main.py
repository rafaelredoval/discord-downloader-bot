import discord
import os
import re
import asyncio
from datetime import datetime, timezone, timedelta
import subprocess

# ======================
# ENV
# ======================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID", 0))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID", 0))
START_DATE_ENV = os.getenv("START_DATE")

if not TOKEN or not SCAN_CHANNEL_ID or not DOWNLOAD_CHANNEL_ID:
    raise RuntimeError("❌ Variáveis obrigatórias não definidas")

START_DATE = (
    datetime.strptime(START_DATE_ENV, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if START_DATE_ENV else
    datetime(1970, 1, 1, tzinfo=timezone.utc)
)

# ======================
# DISCORD
# ======================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ======================
# CONFIG
# ======================
URL_REGEX = re.compile(r'https?://\S+')
DOWNLOAD_BASE = "downloads"
MAX_SIZE = 8 * 1024 * 1024  # 8MB
LONG_FILE = "long_videos.txt"

downloaded_urls = set()
active_scan = False

# ======================
# UTILS
# ======================
def save_long_video(url):
    with open(LONG_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")

async def has_reaction(msg, emoji):
    for r in msg.reactions:
        if str(r.emoji) == emoji:
            async for u in r.users():
                if u == client.user:
                    return True
    return False

# ======================
# DOWNLOAD LINKS
# ======================
async def try_download(msg, download_channel):
    urls = URL_REGEX.findall(msg.content)
    if not urls:
        return

    for url in urls:
        if url in downloaded_urls:
            continue

        user_id = str(msg.author.id)
        date_folder = msg.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        safe = str(abs(hash(url)))

        folder = os.path.join(DOWNLOAD_BASE, user_id, date_folder, safe)
        os.makedirs(folder, exist_ok=True)

        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "-o", f"{folder}/%(title)s.%(ext)s",
            url
        )
        await proc.communicate()

        if proc.returncode != 0:
            await download_channel.send(f"🧐 **Erro ao baixar**\n{url}")
            await msg.add_reaction("🧐")
            continue

        sent = False
        too_large = False

        for file in os.listdir(folder):
            path = os.path.join(folder, file)
            if not os.path.isfile(path):
                continue

            size = os.path.getsize(path)

            if size > MAX_SIZE:
                too_large = True
                save_long_video(url)
                await download_channel.send(
                    f"💾 **Vídeo grande / longo**\n"
                    f"🔗 {url}\n"
                    f"👤 <@{user_id}>"
                )
                os.remove(path)
                continue

            await download_channel.send(
                content=f"📦 <@{user_id}>",
                file=discord.File(path)
            )
            os.remove(path)
            sent = True

        if sent:
            downloaded_urls.add(url)
            await msg.add_reaction("✅")
        elif too_large:
            await msg.add_reaction("💾")

# ======================
# DOWVIDEOS (ANEXOS)
# ======================
async def run_dowvideos(trigger_msg):
    channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    await trigger_msg.reply("🎥 Procurando vídeos anexados...")

    count = 0

    async for msg in channel.history(after=START_DATE, oldest_first=True, limit=None):
        if not msg.attachments:
            continue

        if await has_reaction(msg, "✅"):
            continue

        for att in msg.attachments:
            if not att.content_type or not att.content_type.startswith("video"):
                continue

            if att.size > MAX_SIZE:
                await msg.add_reaction("🧐")
                continue

            file_path = f"/tmp/{att.filename}"
            await att.save(file_path)

            await download_channel.send(
                content=f"📹 Vídeo de <@{msg.author.id}>",
                file=discord.File(file_path)
            )

            os.remove(file_path)
            await msg.add_reaction("✅")
            count += 1

        await asyncio.sleep(0.6)

    await trigger_msg.reply(f"✅ `{count}` vídeo(s) enviados")

# ======================
# CLEAN
# ======================
async def clean_reactions(channel):
    async for msg in channel.history(limit=500):
        for reaction in msg.reactions:
            async for user in reaction.users():
                if user == client.user:
                    await reaction.remove(user)

# ======================
# EVENTS
# ======================
@client.event
async def on_ready():
    print(f"✅ Conectado como {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!scan") and message.channel.id == SCAN_CHANNEL_ID:
        arg = message.content.replace("!scan", "").strip().lower()

        if arg == "hoje":
            start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        elif arg == "ontem":
            start = datetime.now(timezone.utc) - timedelta(days=1)
        elif arg:
            start = datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            start = START_DATE

        await run_scan(message, start)

    if message.content == "!dowvideos" and message.channel.id == SCAN_CHANNEL_ID:
        await run_dowvideos(message)

    if message.content == "!botlimpar" and message.channel.id == SCAN_CHANNEL_ID:
        await clean_reactions(message.channel)
        await message.reply("🧹 Reações do bot removidas")

# ======================
# START
# ======================
client.run(TOKEN)
