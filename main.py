import discord
import os
import re
import asyncio
import subprocess
from datetime import datetime, timedelta, timezone

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.reactions = True

client = discord.Client(intents=intents)

# =========================
# ENV
# =========================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))

URL_REGEX = re.compile(r"https?://\S+")

# =========================
# UTILS
# =========================
def parse_br_datetime(text):
    """
    Aceita:
    - DD/MM/YYYY HH:MM
    - hoje
    - ontem
    """
    text = text.lower().strip()

    now = datetime.now(timezone.utc)

    if text == "hoje":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    if text == "ontem":
        return (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    try:
        dt = datetime.strptime(text, "%d/%m/%Y %H:%M")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def safe_history(channel):
    async for msg in channel.history(limit=None, oldest_first=True):
        yield msg
        await asyncio.sleep(0.25)  # evita rate limit


# =========================
# DOWNLOAD
# =========================
async def try_download(msg, download_channel):
    urls = URL_REGEX.findall(msg.content)
    if not urls:
        return False

    success = True

    for url in urls:
        try:
            result = subprocess.run(
                ["yt-dlp", "-f", "mp4", "-o", "video.%(ext)s", url],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                raise Exception("yt-dlp erro")

            file_name = None
            for f in os.listdir("."):
                if f.startswith("video."):
                    file_name = f
                    break

            if not file_name:
                raise Exception("arquivo não encontrado")

            await download_channel.send(
                content=f"📥 Enviado por <@{msg.author.id}>\n{url}",
                file=discord.File(file_name)
            )

            os.remove(file_name)

        except Exception:
            await download_channel.send(
                content=f"🧐 **Falha no download**\n{url}"
            )
            try:
                await msg.add_reaction("❌")
            except:
                pass
            success = False

    if success:
        try:
            await msg.add_reaction("✅")
        except:
            pass

    return success


# =========================
# SCAN
# =========================
async def run_scan(message, start_date=None):
    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    total = 0
    ok = 0
    fail = 0

    async for msg in safe_history(scan_channel):
        if start_date and msg.created_at < start_date:
            continue

        if msg.author.bot:
            continue

        total += 1
        result = await try_download(msg, download_channel)

        if result:
            ok += 1
        else:
            fail += 1

    await message.channel.send(
        f"✅ **Scan finalizado**\n"
        f"📨 Mensagens: {total}\n"
        f"✔️ Sucesso: {ok}\n"
        f"❌ Falhas: {fail}"
    )


# =========================
# DOWNVIDEOS
# =========================
async def run_downvideos(message, start_date=None):
    channel = message.channel
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    count = 0

    async for msg in safe_history(channel):
        if start_date and msg.created_at < start_date:
            continue

        if msg.author.bot:
            continue

        videos = [
            att for att in msg.attachments
            if att.content_type and att.content_type.startswith("video")
        ]

        if not videos:
            continue

        for video in videos:
            try:
                await download_channel.send(
                    content=f"📦 Vídeo de <@{msg.author.id}>",
                    file=await video.to_file()
                )
                count += 1
            except:
                pass

        try:
            await msg.add_reaction("✅")
        except:
            pass

    await message.channel.send(
        f"📥 **downvideos concluído** — {count} vídeos enviados"
    )


# =========================
# BOTLIMPAR
# =========================
async def run_botlimpar(message, emoji="✅"):
    channel = message.channel
    removed = 0

    async for msg in safe_history(channel):
        for reaction in msg.reactions:
            if reaction.me and str(reaction.emoji) == emoji:
                try:
                    await msg.clear_reaction(reaction.emoji)
                    removed += 1
                except:
                    pass

    await message.channel.send(
        f"🧹 Reações `{emoji}` removidas: {removed}"
    )


# =========================
# EVENTS
# =========================
@client.event
async def on_ready():
    print(f"✅ Conectado como {client.user}")


@client.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()

    # !scan
    if content.startswith("!scan"):
        arg = content.replace("!scan", "").strip()
        start = parse_br_datetime(arg) if arg else None

        if arg and not start:
            await message.channel.send(
                "❌ Use: `!scan hoje` | `!scan ontem` | `!scan DD/MM/YYYY HH:MM`"
            )
            return

        await message.channel.send("🔍 Iniciando scan...")
        await run_scan(message, start)

    # !rescan
    elif content.startswith("!rescan"):
        arg = content.replace("!rescan", "").strip()
        start = parse_br_datetime(arg)

        if not start:
            await message.channel.send(
                "❌ Use: `!rescan DD/MM/YYYY HH:MM`"
            )
            return

        await message.channel.send("♻️ Re-scan iniciado...")
        await run_scan(message, start)

    # !downvideos
    elif content.startswith("!downvideos"):
        arg = content.replace("!downvideos", "").strip()
        start = parse_br_datetime(arg) if arg else None

        if arg and not start:
            await message.channel.send(
                "❌ Use: `!downvideos DD/MM/YYYY HH:MM`"
            )
            return

        await message.channel.send("📦 Buscando vídeos...")
        await run_downvideos(message, start)

    # !botlimpar
    elif content.startswith("!botlimpar"):
        parts = content.split()
        emoji = parts[1] if len(parts) > 1 else "✅"
        await run_botlimpar(message, emoji)


# =========================
# START
# =========================
client.run(TOKEN)
