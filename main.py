import os
import re
import asyncio
from datetime import datetime, timedelta, timezone

import discord

TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.reactions = True

client = discord.Client(intents=intents)

scan_task = None
cancel_scan = False

URL_REGEX = re.compile(r"(https?://[^\s]+)")


# =========================
# UTILIDADES
# =========================

def parse_date_filter(args: list[str]):
    """
    Aceita:
    - hoje
    - ontem
    - YYYY-MM-DD
    - YYYY-MM-DD HH:MM
    """
    now = datetime.now(timezone.utc)

    if not args:
        return None

    arg = args[0].lower()

    if arg == "hoje":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    if arg == "ontem":
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        if len(args) >= 2:
            dt = datetime.fromisoformat(f"{args[0]} {args[1]}")
        else:
            dt = datetime.fromisoformat(args[0])

        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def collect_existing_links(channel: discord.TextChannel):
    links = set()
    async for msg in channel.history(limit=None):
        for match in URL_REGEX.findall(msg.content):
            links.add(match)
    return links


# =========================
# SCAN
# =========================

async def run_scan(trigger_message: discord.Message, date_filter: datetime | None):
    global cancel_scan

    scan_channel = client.get_channel(SCAN_CHANNEL_ID)
    download_channel = client.get_channel(DOWNLOAD_CHANNEL_ID)

    if not scan_channel or not download_channel:
        await trigger_message.channel.send("❌ Canal inválido.")
        return

    await trigger_message.channel.send(
        "🔍 Scan iniciado — ignorando links duplicados"
    )

    existing_links = await collect_existing_links(download_channel)
    new_links = []
    count = 0

    async for msg in scan_channel.history(limit=None, oldest_first=True):
        if cancel_scan:
            await trigger_message.channel.send("⛔ Scan cancelado.")
            return

        msg_date = msg.created_at.astimezone(timezone.utc)

        if date_filter and msg_date < date_filter:
            continue

        for link in URL_REGEX.findall(msg.content):
            if link not in existing_links:
                existing_links.add(link)
                new_links.append(link)

        # evita estouro de payload
        if len(new_links) >= 20:
            await download_channel.send("\n".join(new_links))
            count += len(new_links)
            new_links.clear()
            await asyncio.sleep(1)

    if new_links:
        await download_channel.send("\n".join(new_links))
        count += len(new_links)

    await trigger_message.channel.send(f"✅ Scan finalizado — {count} links enviados")


# =========================
# EVENTOS
# =========================

@client.event
async def on_ready():
    print(f"✅ Bot conectado como {client.user}")


@client.event
async def on_message(message: discord.Message):
    global scan_task, cancel_scan

    if message.author.bot:
        return

    content = message.content.strip().lower()

    # !scan
    if content.startswith("!scan"):
        if scan_task and not scan_task.done():
            await message.channel.send("⚠️ Já existe um scan em andamento.")
            return

        parts = message.content.split()
        date_filter = parse_date_filter(parts[1:])

        if parts[1:] and not date_filter:
            await message.channel.send(
                "❌ Data inválida.\nUse:\n"
                "`!scan hoje`\n"
                "`!scan ontem`\n"
                "`!scan YYYY-MM-DD`\n"
                "`!scan YYYY-MM-DD HH:MM`"
            )
            return

        cancel_scan = False
        scan_task = asyncio.create_task(run_scan(message, date_filter))

    # !cancelscan
    if content in ("!cancelscan", "!cancel scan"):
        cancel_scan = True
        await message.channel.send("⛔ Cancelando scan...")


# =========================
# START
# =========================

client.run(TOKEN)
