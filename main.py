import discord
import asyncio
import os
import re
import yt_dlp
from io import BytesIO
from discord.ext import commands
from datetime import datetime, timezone, time

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

# Configuração do Extrair de Vídeos (yt-dlp)
YDL_OPTS = {
    'format': 'best[ext=mp4]/best', # Prioriza MP4 para o player do Discord
    'quiet': True,
    'no_warnings': True,
    'max_filesize': 25 * 1024 * 1024, # Limite de 25MB para não dar erro no Discord
}

def parse_date(text):
    if not text: return None
    try:
        text = text.lower().strip()
        if text == "hoje":
            agora = datetime.now(timezone.utc)
            return datetime.combine(agora.date(), time.min).replace(tzinfo=timezone.utc)
        if "/" in text:
            try: return datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
            except: return datetime.strptime(text, "%d/%m/%Y").replace(tzinfo=timezone.utc)
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except: return None

# ================= COMANDO LINKS DOWNLOAD (VERSÃO CORRIGIDA) =================

@bot.command()
async def linksdownload(ctx, *, arg=None):
    """Extrai o vídeo real do link e envia com player para o Discord"""
    global CANCEL_FLAG
    CANCEL_FLAG = False
    date = parse_date(arg)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    
    await ctx.send(f"🎬 Extraindo vídeos reais de <#{DOWNLOAD_CHANNEL_ID}>... Isso pode demorar.")
    
    async for msg in down_ch.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if date and msg.created_at < date: continue
        
        links = re.findall(URL_PATTERN, msg.content)
        if not links: continue

        mention_target = msg.mentions[0].mention if msg.mentions else msg.author.mention

        for url in links:
            try:
                # Usando yt-dlp para pegar o link DIRETO do vídeo
                with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                    info = ydl.extract_info(url, download=False)
                    video_url = info.get('url')
                    
                    # Agora baixamos o arquivo real usando o link extraído
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(video_url, timeout=30) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                
                                if len(data) > 25 * 1024 * 1024:
                                    await msg.add_reaction("❌") # Muito grande
                                    continue
                                
                                filename = f"video_{msg.id}.mp4"
                                d_file = discord.File(BytesIO(data), filename=filename)
                                
                                await down_ch.send(
                                    content=f"🎬 **Vídeo extraído para:** {mention_target}",
                                    file=d_file
                                )
                                await msg.add_reaction("💾")
                            else:
                                await msg.add_reaction("❌")
            except Exception as e:
                print(f"Erro no yt-dlp: {e}")
                await msg.add_reaction("❌")
            
            await asyncio.sleep(2) # Pausa maior para evitar ban de IP

    await ctx.send("✅ Finalizado.")

# --- Comandos Complementares (Mantidos) ---

@bot.command()
async def cancelgeral(ctx):
    global CANCEL_FLAG
    CANCEL_FLAG = True
    await ctx.send("🛑 Cancelado.")

@bot.command()
async def limpar(ctx, emoji_alvo=None, *, arg=None):
    if not ctx.author.guild_permissions.manage_messages: return
    date = parse_date(arg)
    count = 0
    async for msg in ctx.channel.history(limit=100):
        if date and msg.created_at < date: continue
        if not emoji_alvo: break
        if emoji_alvo.lower() == "tudo":
            await msg.clear_reactions()
            count += 1
        else:
            for r in msg.reactions:
                if str(r.emoji) == emoji_alvo:
                    await msg.clear_reaction(r.emoji)
                    count += 1
    await ctx.send(f"✅ Reações limpas: {count}")

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")

bot.run(TOKEN)
