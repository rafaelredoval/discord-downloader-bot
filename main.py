import discord
import asyncio
import os
from discord.ext import commands
from datetime import datetime, timedelta, timezone

# ================== VARIÁVEIS ==================

TOKEN = os.getenv("DISCORD_TOKEN")

SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))
POST_CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID"))
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", 0))

# ================== BOT ==================

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

CANCEL_FLAG = False

# ================== UTIL ==================

def parse_date(arg):
    try:
        if "/" in arg:
            return datetime.strptime(arg, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        return datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

async def pause():
    await asyncio.sleep(1.3)

# ================== SCAN POST ==================

async def run_scan_post(ctx, start_date=None):
    global CANCEL_FLAG

    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    post_channel = bot.get_channel(POST_CHANNEL_ID)

    await ctx.send("📦 Coletando vídeos do canal de download…")

    async for msg in download_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG:
            await ctx.send("❌ Scan post cancelado")
            return

        if start_date and msg.created_at < start_date:
            continue

        if not msg.attachments:
            continue

        for att in msg.attachments:
            try:
                file = await att.to_file()
                await post_channel.send(file=file)
                await msg.add_reaction("✅")
            except:
                await post_channel.send(att.url)
                await msg.add_reaction("🧐")

            await pause()

    await ctx.send("✅ Scan post finalizado")

# ================== COMANDOS ==================

@bot.command()
async def scan(ctx, *, arg=None):
    if ctx.channel.id != SCAN_CHANNEL_ID:
        return

    if arg and arg.startswith("post"):
        date = None
        parts = arg.split(" ", 1)
        if len(parts) == 2:
            date = parse_date(parts[1])
        await run_scan_post(ctx, date)
        return

    await ctx.send("ℹ️ Use `!scan post` para postar vídeos do canal de download.")

@bot.command()
async def cancelgeral(ctx):
    global CANCEL_FLAG
    CANCEL_FLAG = True
    await ctx.send("🛑 Cancelamento geral ativado")

# ================== READY ==================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

bot.run(TOKEN)
