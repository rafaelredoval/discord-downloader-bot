import discord
import os
import re
import subprocess
import json
from datetime import datetime, timezone

# =====================
# ENV VARS
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
# DOWNLOAD CONFIG
# =====================
URL_REGEX = re.compile(r'https?://\S+')
DOWNLOAD_BASE = "downloads"

# =====================
# UTILS
# =====================
def format_seconds(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if h > 0:
        return f"{h:02d}h {m:02d}m {s:02d}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"

# =====================
# PROCESS MESSAGE
# =====================
async def process_message(message, create_thread=False):
    if message.author.bot:
        return 0, 0, None

    if message.reactions:
        return 0, 0, None

    urls = URL_REGEX.findall(message.content)
    if not urls:
        return 0, 0, None

    base_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)
    if not base_channel:
        return 0, 0, None

    target_channel = base_channel

    if create_thread:
        thread_name = f"{message.author.display_name}"
        target_channel = await base_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.public_thread
        )

    user_id = str(message.author.id)
    date_folder = message.created_at.strftime("%Y-%m-%d")

    total_seconds = 0
    total_videos = 0

    for url in urls:
        safe_name = str(abs(hash(url)))
        folder = os.path.join(DOWNLOAD_BASE, user_id, date_folder, safe_name)
        os.makedirs(folder, exist_ok=True)

        status = await target_channel.send(
            f"⏳ **Baixando**\n🔗 {url}\n👤 <@{user_id}>"
        )

        try:
            subprocess.run(
                [
                    "yt-dlp",
                    "--print-json",
                    "-o",
                    f"{folder}/%(title)s.%(ext)s",
                    url
                ],
                check=True,
                capture_output=True,
                text=True
            )

            await status.edit(content="📤 **Enviando arquivo(s)…**")

            for file in os.listdir(folder):
                path = os.path.join(folder, file)
                if os.path.isfile(path):
                    await target_channel.send(
                        content=f"📦 Enviado por <@{user_id}>",
                        file=discord.File(path)
                    )
                    os.remove(path)
                    total_videos += 1

            await status.edit(content="✅ **Concluído**")
            await message.add_reaction("✅")

            # tenta ler duração
            try:
                info_path = os.path.join(folder, "info.json")
                if os.path.exists(info_path):
                    with open(info_path) as f:
                        info = json.load(f)
                        total_seconds += int(info.get("duration", 0))
            except:
                pass

        except Exception as e:
            await status.edit(content="❌ **Erro no download**")
            await message.add_reaction("❌")
            print(e)

    return total_seconds, total_videos, target_channel

# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Conectado como {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != SCAN_CHANNEL_ID:
        return

    if message.content.lower() not in ["!scan", "!scan post"]:
        return

    create_thread = message.content.lower() == "!scan post"

    await message.channel.send("🔍 Iniciando varredura…")

    summary = {}

    async for msg in message.channel.history(limit=None, oldest_first=True):
        seconds, videos, _ = await process_message(msg, create_thread)

        if videos > 0:
            uid = msg.author.id
            if uid not in summary:
                summary[uid] = {
                    "name": msg.author.display_name,
                    "videos": 0,
                    "seconds": 0
                }

            summary[uid]["videos"] += videos
            summary[uid]["seconds"] += seconds

    if not summary:
        await message.channel.send("⚠️ Nenhum conteúdo novo encontrado.")
        return

    report = "📊 **RESUMO DA VARREDURA**\n\n"
    for data in summary.values():
        report += (
            f"👤 **{data['name']}**\n"
            f"🎬 Vídeos: {data['videos']}\n"
            f"⏱️ Duração total: {format_seconds(data['seconds'])}\n\n"
        )

    await message.channel.send(report)

# =====================
# START
# =====================
client.run(TOKEN)
