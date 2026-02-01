import discord
import os
import re
import subprocess
import asyncio
from datetime import datetime, timezone

# =====================
# ENV VARS
# =====================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID", "0"))
POST_CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID", "0"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID", "0"))

if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN não definido")

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
scan_running = False
cancel_scan = False

# =====================
# EVENTS
# =====================
@client.event
async def on_ready():
    print(f"✅ Bot conectado como {client.user}")

@client.event
async def on_message(message):
    global scan_running, cancel_scan

    if message.author.bot:
        return

    content = message.content.lower()

    # =====================
    # !scan
    # =====================
    if content.startswith("!scan"):
        if message.channel.id != SCAN_CHANNEL_ID:
            return

        if scan_running:
            await message.channel.send("⚠️ Scan já em execução")
            return

        scan_running = True
        cancel_scan = False

        args = message.content.split()
        start_date = datetime(1970, 1, 1, tzinfo=timezone.utc)

        if len(args) == 2 and args[1] != "post":
            start_date = datetime.strptime(args[1], "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )

        post_mode = "post" in args

        await message.channel.send("🔍 **Scan iniciado**")

        summary = {}
        total_seconds = 0
        total_files = 0

        async for msg in message.channel.history(after=start_date, oldest_first=True):
            if cancel_scan:
                break

            if msg.author.bot:
                continue

            if msg.reactions:
                continue

            urls = URL_REGEX.findall(msg.content)
            if not urls:
                continue

            for url in urls:
                if cancel_scan:
                    break

                ok = await process_download(
                    msg, url, post_mode, summary
                )

                if ok:
                    total_files += 1
                    seconds = get_video_duration(url)
                    total_seconds += seconds

        scan_running = False

        # resumo
        hours = total_seconds / 3600
        text = (
            f"📊 **Scan finalizado**\n"
            f"🎞️ Vídeos: {total_files}\n"
            f"⏱️ Horas totais: {hours:.2f}\n\n"
        )

        for user, count in summary.items():
            text += f"👤 <@{user}> → {count} arquivos\n"

        await message.channel.send(text)
        return

    # =====================
    # !cancelscan
    # =====================
    if content == "!cancelscan":
        cancel_scan = True
        await message.channel.send("⛔ Scan cancelado")
        return

# =====================
# !botlimpar
# =====================
if content == "!botlimpar":
    if not message.channel.permissions_for(message.guild.me).manage_messages:
        await message.channel.send("❌ Não tenho permissão de **Gerenciar Mensagens**")
        return

    removed = 0

    await message.channel.send("🧹 Limpando reações do bot...")

    async for msg in message.channel.history(limit=1000):
        if not msg.reactions:
            continue

        for reaction in msg.reactions:
            try:
                await reaction.remove(client.user)
                removed += 1
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass

    await message.channel.send(
        f"✅ Limpeza concluída — {removed} reações removidas"
    )


# =====================
# FUNCTIONS
# =====================
async def process_download(message, url, post_mode, summary):
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)
    post_channel = client.get_channel(POST_CHANNEL_ID)

    user_id = str(message.author.id)
    summary[user_id] = summary.get(user_id, 0) + 1

    safe_name = str(abs(hash(url)))
    folder = os.path.join(DOWNLOAD_BASE, user_id, safe_name)
    os.makedirs(folder, exist_ok=True)

    status = await download_channel.send(f"⏳ Baixando {url}")

    try:
        subprocess.run(
            ["yt-dlp", "-o", f"{folder}/%(title)s.%(ext)s", url],
            check=True
        )

        await message.add_reaction("✅")

        target = download_channel

        if post_mode and post_channel:
            thread = await post_channel.create_thread(
                name=message.author.name,
                type=discord.ChannelType.public_thread
            )
            target = thread

        for file in os.listdir(folder):
            await target.send(file=discord.File(os.path.join(folder, file)))
            os.remove(os.path.join(folder, file))

        await status.edit(content="✅ Concluído")
        return True

    except Exception:
        await message.add_reaction("❌")
        await status.edit(content="❌ Erro no download")
        return False

def get_video_duration(url):
    try:
        result = subprocess.run(
            ["yt-dlp", "--print", "duration", url],
            capture_output=True,
            text=True
        )
        return int(result.stdout.strip())
    except:
        return 0

# =====================
# START
# =====================
client.run(TOKEN)
