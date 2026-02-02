import discord
import os
import re
import asyncio
import subprocess
from datetime import datetime, timedelta, timezone

TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

scan_task = None
cancel_scan = False

URL_REGEX = re.compile(r"https?://[^\s]+")

@client.event
async def on_ready():
    print(f"Bot conectado como {client.user}")
    print(f"Canal Scan: {SCAN_CHANNEL_ID}")
    print(f"Canal Download: {DOWNLOAD_CHANNEL_ID}")


@client.event
async def on_message(message):
    global scan_task, cancel_scan

    if message.author.bot:
        return

    if message.content.startswith("!cancelscan"):
        cancel_scan = True
        await message.channel.send("⛔ Cancelando scan...")
        return

    if message.content.startswith("!scan"):
        if message.channel.id != SCAN_CHANNEL_ID:
            return

        args = message.content.split(maxsplit=1)
        date_filter = None
        now = datetime.now(timezone.utc)

        if len(args) > 1:
            arg = args[1].strip().lower()

            if arg == "hoje":
                date_filter = now.replace(hour=0, minute=0, second=0, microsecond=0)

            elif arg == "ontem":
                yesterday = now - timedelta(days=1)
                date_filter = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

            else:
                try:
                    date_filter = datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    await message.channel.send("❌ Data inválida. Use YYYY-MM-DD, hoje ou ontem.")
                    return

        cancel_scan = False
        scan_task = asyncio.create_task(run_scan(message, date_filter))


async def run_scan(message, date_filter):
    global cancel_scan

    channel = message.channel
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    await channel.send("🔍 Scan iniciado...")

    total_downloads = 0

    async for msg in channel.history(limit=None, oldest_first=True):
        if cancel_scan:
            await channel.send("⛔ Scan cancelado.")
            return

        if msg.author.bot:
            continue

        if date_filter and msg.created_at < date_filter:
            continue

        urls = URL_REGEX.findall(msg.content)

        if not urls:
            continue

        for url in urls:
            if cancel_scan:
                await channel.send("⛔ Scan cancelado.")
                return

            success = await download_video(url, download_channel)

            try:
                if success:
                    await msg.add_reaction("✅")
                    total_downloads += 1
                else:
                    await msg.add_reaction("❌")
            except discord.Forbidden:
                pass

            await asyncio.sleep(1.5)

    await channel.send(f"✅ Scan finalizado — {total_downloads} downloads")


async def download_video(url, download_channel):
    try:
        process = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "-f",
            "mp4",
            url,
            "-o",
            "video.mp4",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        await process.communicate()

        if not os.path.exists("video.mp4"):
            return False

        await download_channel.send(file=discord.File("video.mp4"))
        os.remove("video.mp4")
        return True

    except Exception as e:
        print("Erro no download:", e)
        return False


client.run(TOKEN)
