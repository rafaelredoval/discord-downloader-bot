import discord
import os
import re
import asyncio
import subprocess
from datetime import datetime, timedelta, timezone

# ======================
# DISCORD CONFIG
# ======================
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.reactions = True

client = discord.Client(intents=intents)

# ======================
# ENV (Railway / Host)
# ======================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))

URL_REGEX = re.compile(r"https?://\S+")

# ======================
# CONTROLE GLOBAL
# ======================
CANCEL_SCAN = False

# ======================
# DATETIME PARSER
# ======================
def parse_datetime(text):
    if not text:
        return None

    text = text.lower().strip()
    now = datetime.now(timezone.utc)

    if text == "hoje":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    if text == "ontem":
        return (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None

# ======================
# SAFE HISTORY
# ======================
async def safe_history(channel):
    async for msg in channel.history(limit=None, oldest_first=True):
        yield msg
        await asyncio.sleep(0.35)  # evita rate-limit

# ======================
# DOWNLOAD LINKS
# ======================
async def try_download(msg, download_channel):
    urls = URL_REGEX.findall(msg.content)
    if not urls:
        return False

    success = True

    for url in urls:
        try:
            result = subprocess.run(
                ["yt-dlp", "-f", "mp4", "-o", "temp.%(ext)s", url],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                raise Exception("yt-dlp erro")

            file_name = next(
                (f for f in os.listdir(".") if f.startswith("temp.")),
                None
            )

            if not file_name:
                raise Exception("arquivo não encontrado")

            await download_channel.send(
                content=f"📥 <@{msg.author.id}>\n{url}",
                file=discord.File(file_name)
            )

            os.remove(file_name)

        except Exception:
            success = False
            try:
                await msg.add_reaction("❌")
            except:
                pass

            await download_channel.send(f"🧐 Falha ao baixar:\n{url}")

    if success:
        try:
            await msg.add_reaction("✅")
        except:
            pass

    return success

# ======================
# SCAN / RESCAN
# ======================
async def run_scan(origin_msg, start_date=None):
    global CANCEL_SCAN
    CANCEL_SCAN = False

    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    total = ok = fail = 0

    async for msg in safe_history(scan_channel):
        if CANCEL_SCAN:
            await origin_msg.channel.send("🛑 Scan cancelado")
            return

        if msg.author.bot:
            continue

        if start_date and msg.created_at < start_date:
            continue

        total += 1
        result = await try_download(msg, download_channel)

        if result:
            ok += 1
        else:
            fail += 1

    await origin_msg.channel.send(
        f"✅ **Scan finalizado**\n"
        f"📨 {total} mensagens\n"
        f"✔️ {ok} sucesso\n"
        f"❌ {fail} falhas"
    )

# ======================
# DOWNVIDEOS (UPLOADS)
# ======================
async def run_downvideos(origin_msg, start_date=None):
    global CANCEL_SCAN
    CANCEL_SCAN = False

    source_channel = origin_msg.channel
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    count = 0

    async for msg in safe_history(source_channel):
        if CANCEL_SCAN:
            await origin_msg.channel.send("🛑 downvideos cancelado")
            return

        if msg.author.bot:
            continue

        if start_date and msg.created_at < start_date:
            continue

        videos = [
            a for a in msg.attachments
            if a.content_type and a.content_type.startswith("video")
        ]

        for video in videos:
            try:
                await download_channel.send(
                    content=f"📦 <@{msg.author.id}>",
                    file=await video.to_file()
                )
                count += 1
            except:
                pass

        if videos:
            try:
                await msg.add_reaction("✅")
            except:
                pass

    await origin_msg.channel.send(
        f"📥 **downvideos concluído** — {count} vídeos enviados"
    )

# ======================
# BOTLIMPAR
# ======================
async def run_botlimpar(channel, emoji):
    removed = 0

    async for msg in safe_history(channel):
        for reaction in msg.reactions:
            if reaction.me and str(reaction.emoji) == emoji:
                try:
                    await msg.clear_reaction(emoji)
                    removed += 1
                except:
                    pass

    await channel.send(f"🧹 {removed} reações `{emoji}` removidas")

# ======================
# EVENTS
# ======================
@client.event
async def on_ready():
    print(f"✅ Bot online como {client.user}")

@client.event
async def on_message(message):
    global CANCEL_SCAN

    if message.author.bot:
        return

    content = message.content.strip()

    if content.startswith("!cancelgeral"):
        CANCEL_SCAN = True
        await message.channel.send("🛑 Cancelamento geral ativado")
        return

    if content.startswith("!scan"):
        arg = content.replace("!scan", "").strip()
        start = parse_datetime(arg)

        if arg and not start:
            await message.channel.send(
                "❌ Use: `!scan hoje | ontem | DD/MM/YYYY | DD/MM/YYYY HH:MM`"
            )
            return

        await message.channel.send("🔍 Scan iniciado…")
        await run_scan(message, start)

    elif content.startswith("!rescan"):
        arg = content.replace("!rescan", "").strip()
        start = parse_datetime(arg)

        if not start:
            await message.channel.send(
                "❌ Use: `!rescan DD/MM/YYYY HH:MM`"
            )
            return

        await message.channel.send("♻️ Re-scan iniciado…")
        await run_scan(message, start)

    elif content.startswith("!downvideos"):
        arg = content.replace("!downvideos", "").strip()
        start = parse_datetime(arg)

        if arg and not start:
            await message.channel.send(
                "❌ Use: `!downvideos hoje | ontem | DD/MM/YYYY HH:MM`"
            )
            return

        await message.channel.send("📦 Coletando vídeos…")
        await run_downvideos(message, start)

    elif content.startswith("!botlimpar"):
        parts = content.split()
        emoji = parts[1] if len(parts) > 1 else "✅"
        await run_botlimpar(message.channel, emoji)

# ======================
# START
# ======================
client.run(TOKEN)
