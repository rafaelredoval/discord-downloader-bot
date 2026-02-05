import discord
import asyncio
import os
import re
import aiohttp
from io import BytesIO
from discord.ext import commands
from datetime import datetime, timezone, time

# ================= CONFIGURAÇÃO DE VARIÁVEIS =================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))
POST_CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID"))

# ================= INICIALIZAÇÃO DO BOT =================
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)
CANCEL_FLAG = False
URL_PATTERN = r'(https?://[^\s]+)'

# ================= UTILITÁRIOS =================
def parse_date(text):
    if not text: return None
    try:
        text = text.lower().strip()
        if text == "hoje":
            agora = datetime.now(timezone.utc)
            return datetime.combine(agora.date(), time.min).replace(tzinfo=timezone.utc)
        if "/" in text:
            # Tenta formato com hora, se falhar tenta só data
            try:
                return datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
            except:
                return datetime.strptime(text, "%d/%m/%Y").replace(tzinfo=timezone.utc)
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

async def anti_rate():
    await asyncio.sleep(1.4)

# ================= COMANDOS DE MOVIMENTAÇÃO (SCAN -> DOWNLOAD) =================

@bot.command()
async def downvideos(ctx, *, arg=None):
    """Move anexos de vídeo do SCAN para DOWNLOAD e reage com ✅"""
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
                except:
                    await msg.add_reaction("❌")
                await anti_rate()
    await ctx.send("✅ !downvideos concluído.")

@bot.command()
async def link(ctx, *, arg=None):
    """Captura links de texto no SCAN e envia para DOWNLOAD e reage com ✅"""
    global CANCEL_FLAG
    CANCEL_FLAG = False
    date = parse_date(arg)
    scan_ch = bot.get_channel(SCAN_CHANNEL_ID)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)

    await ctx.send(f"🔗 Capturando links em <#{SCAN_CHANNEL_ID}>...")
    async for msg in scan_ch.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if date and msg.created_at < date: continue
        
        links = re.findall(URL_PATTERN, msg.content)
        if links:
            try:
                content = f"🔗 **Link de:** {msg.author.mention}\n" + "\n".join(links)
                await down_ch.send(content=content)
                await msg.add_reaction("✅")
            except:
                await msg.add_reaction("❌")
            await anti_rate()
    await ctx.send("✅ !link concluído.")

# ================= COMANDO DOWNLOAD DE LINKS (DOWNLOAD CHANNEL) =================
