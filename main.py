import discord
import os
import re
import asyncio
import subprocess
import json
from datetime import datetime, timezone

# =====================
# ENV VARS (Railway)
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID", "0"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID", "0"))

if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN não definido")

if SCAN_CHANNEL_ID == 0:
    raise RuntimeError("❌ SCAN_CHANNEL_ID não definido")

if DOWNLOAD_CHANNEL_ID == 0:
    raise RuntimeError("❌ DOWNLOAD_CHANNEL_ID não definido")

# =====================
# DISCORD CONFIG
# =====================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# =====================
# GLOBALS
# =====================
URL_REGEX = re.compile(r'https?://\S+')
DOWNLOAD_BASE = "downloads"
scan_cancelled = False

# =====================
# UTILS
# =====================
def parse_date(arg):
    try:
        return datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

def get_video_duration(url):
    try:
        result = subprocess.check_output(
            ["yt-dlp", "--dump-json", "--skip-download", url],
            stderr=subprocess.DEVNULL
        )
        data = json.loads(result)
        return data.get("duration", 0)
    except:
        return 0

# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Bot conectado como {client.user}")

# =====================
# CORE SCAN FUNCTION
# =====================
async def run_scan(ctx_message, post_topics=False, date_filter=None):
    global scan_cancelled
    scan_cancelled = False

    channel = ctx_message.channel
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    stats = {}
    total_duration = 0

    await channel.send("🔍 **Iniciando varredura...**")

    async for msg in channel.history(limit=None, oldest_first=True, after=date_filter):
        if scan_cancelled:
            await channel.send("⛔ Scan cancelado")
            return

        if msg.author.bot:
            continue

        if msg.reactions:
            continue

        urls = URL_REGEX.findall(msg.content)
        if not urls:
            continue

        user_id = str(msg.author.id)
        stats.setdefault(user_id, {"count": 0, "duration": 0})

        for url in urls:
            safe_name = str(abs(hash(url)))
            date_folder = msg.created_at.strftime("%Y-%m-%d")
            download_folder = os.path.join(
                DOWNLOAD_BASE, user_id, date_folder, safe_name
            )
            os.makedirs(download_folder, exist_ok=True)

            duration = get_video_duration(url)
            total_duration += duration
            stats[user_id]["duration"] += duration

            try:
                subprocess.run(
                    ["yt-dlp", "-o", f"{download_folder}/%(title)s.%(ext)s", url],
                    check=True
                )

                await msg.add_reaction("✅")
                stats[user_id]["count"] += 1

                for file in os.listdir(download_folder):
                    path = os.path.join(download_folder, file)
                    if os.path.isfile(path):
                        await download_channel.send(
                            content=f"📦 <@{user_id}>",
                            file=discord.File(path)
                        )
                        os.remove(path)

            except Exception:
                await msg.add_reaction("❌")

    # =====================
    # FINAL SUMMARY
    # =====================
    summary = ["📊 **Resumo da Varredura**"]

    for uid, data in stats.items():
        h = data["duration"] // 3600
        m = (data["duration"] % 3600) // 60
        summary.append(
            f"👤 <@{uid}> — {data['count']} arquivos — ⏱ {h}h {m}m"
        )

    th = total_duration // 3600
    tm = (total_duration % 3600) // 60

    summary.append(f"\n⏱ **Total Geral:** {th}h {tm}m")

    await channel.send("\n".join(summary))

# =====================
# MESSAGE COMMANDS
# =====================
@client.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()

    # =====================
    # !scan
    # =====================
    if content.startswith("!scan"):
        if message.channel.id != SCAN_CHANNEL_ID:
            await message.channel.send("❌ Use este comando no canal autorizado")
            return

        parts = content.split()
        date_filter = parse_date(parts[1]) if len(parts) > 1 else None

        await run_scan(message, post_topics=False, date_filter=date_filter)

    # =====================
    # !scan post
    # =====================
    elif content.startswith("!scan post"):
        if message.channel.id != SCAN_CHANNEL_ID:
            return

        parts = content.split()
        date_filter = parse_date(parts[2]) if len(parts) > 2 else None

        await run_scan(message, post_topics=True, date_filter=date_filter)

    # =====================
    # !cancelscan
    # =====================
    elif content == "!cancelscan":
        global scan_cancelled
        scan_cancelled = True
        await message.channel.send("⛔ Cancelamento solicitado")

    # =====================
    # !botlimpar
    # =====================
    elif content == "!botlimpar":
        if not message.channel.permissions_for(message.guild.me).manage_messages:
            await message.channel.send("❌ Sem permissão para gerenciar mensagens")
            return

        removed = 0
        async for msg in message.channel.history(limit=1000):
            for reaction in msg.reactions:
                try:
                    await reaction.remove(client.user)
                    removed += 1
                except:
                    pass

        await message.channel.send(f"🧹 {removed} reações removidas")

# =====================
# START
# =====================
client.run(TOKEN)
