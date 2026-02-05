import discord
import asyncio
import os
import re
import aiohttp
from io import BytesIO
from discord.ext import commands
from datetime import datetime, timezone, time

# Tenta carregar o .env apenas se o arquivo existir (evita erro no Railway)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ================= CONFIGURAÇÃO =================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID") or 0)
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID") or 0)
POST_CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID") or 0)

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)
CANCEL_FLAG = False
URL_PATTERN = r'(https?://[^\s]+)'

# --- Utilitários ---
def parse_date(text):
    if not text: return None
    try:
        text = text.lower().strip()
        if text == "hoje":
            agora = datetime.now(timezone.utc)
            return datetime.combine(agora.date(), time.min).replace(tzinfo=timezone.utc)
        if "/" in text:
            try:
                return datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
            except:
                return datetime.strptime(text, "%d/%m/%Y").replace(tzinfo=timezone.utc)
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

async def anti_rate():
    await asyncio.sleep(1.4)

# --- Comandos ---
@bot.command()
async def downvideos(ctx, *, arg=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False
    date = parse_date(arg)
    scan_ch = bot.get_channel(SCAN_CHANNEL_ID)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    await ctx.send(f"📥 Coletando vídeos em <#{SCAN_CHANNEL_ID}>...")
    async for msg in scan_ch.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if date and msg.created_at < date: continue
        if not msg.attachments: continue
        for att in msg.attachments:
            if any(att.filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']):
                try:
                    file = await att.to_file()
                    await down_ch.send(content=f"🎬 Vídeo de: {msg.author.mention}", file=file)
                    await msg.add_reaction("✅")
                except: await msg.add_reaction("❌")
                await anti_rate()
    await ctx.send("✅ Finalizado.")

@bot.command()
async def link(ctx, *, arg=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False
    date = parse_date(arg)
    scan_ch = bot.get_channel(SCAN_CHANNEL_ID)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    await ctx.send("🔗 Capturando links...")
    async for msg in scan_ch.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if date and msg.created_at < date: continue
        links = re.findall(URL_PATTERN, msg.content)
        if links:
            try:
                await down_ch.send(content=f"🔗 **Link de:** {msg.author.mention}\n" + "\n".join(links))
                await msg.add_reaction("✅")
            except: await msg.add_reaction("❌")
            await anti_rate()
    await ctx.send("✅ Finalizado.")

@bot.command()
async def linksdownload(ctx, *, arg=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False
    date = parse_date(arg)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    await ctx.send(f"💾 Baixando links em <#{DOWNLOAD_CHANNEL_ID}>...")
    async with aiohttp.ClientSession() as session:
        async for msg in down_ch.history(limit=None, oldest_first=True):
            if CANCEL_FLAG: break
            if date and msg.created_at < date: continue
            links = re.findall(URL_PATTERN, msg.content)
            for url in links:
                try:
                    async with session.get(url, timeout=15) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 25 * 1024 * 1024:
                                await msg.add_reaction("❌")
                                continue
                            filename = url.split("/")[-1].split("?")[0] or "video.mp4"
                            d_file = discord.File(BytesIO(data), filename=filename)
                            await down_ch.send(content=f"💾 De: {msg.author.mention}", file=d_file)
                            await msg.add_reaction("💾")
                        else: await msg.add_reaction("❌")
                except: await msg.add_reaction("❌")
                await anti_rate()
    await ctx.send("✅ Finalizado.")

@bot.command()
async def limparforum(ctx, *, arg=None):
    if not ctx.author.guild_permissions.manage_threads: return
    date = parse_date(arg)
    forum_ch = bot.get_channel(POST_CHANNEL_ID)
    if not date: return
    await ctx.send(f"⚠️ Limpando tópicos anteriores a {date}...")
    threads = forum_ch.threads + [t async for t in forum_ch.archived_threads()]
    for t in threads:
        if t.created_at < date:
            try: 
                await t.delete()
                await asyncio.sleep(0.6)
            except: pass
    await ctx.send("✅ Limpeza concluída.")

@bot.command()
async def cancelgeral(ctx):
    global CANCEL_FLAG
    CANCEL_FLAG = True
    await ctx.send("🛑 Cancelado.")

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")

bot.run(TOKEN)
