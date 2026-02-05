import discord
import asyncio
import os
import re
import aiohttp
from io import BytesIO
from discord.ext import commands
from datetime import datetime, timezone, time

# Tenta carregar o .env localmente
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

# ================= COMANDOS =================

@bot.command()
async def linksdownload(ctx, *, arg=None):
    """Baixa o vídeo, força o player do Discord e menciona o alvo"""
    global CANCEL_FLAG
    CANCEL_FLAG = False
    date = parse_date(arg)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    
    await ctx.send(f"💾 Baixando vídeos e gerando player em <#{DOWNLOAD_CHANNEL_ID}>...")
    
    async with aiohttp.ClientSession() as session:
        async for msg in down_ch.history(limit=None, oldest_first=True):
            if CANCEL_FLAG: break
            if date and msg.created_at < date: continue
            
            links = re.findall(URL_PATTERN, msg.content)
            if not links: continue

            # Define quem mencionar
            mention_target = msg.mentions[0].mention if msg.mentions else msg.author.mention

            for url in links:
                try:
                    async with session.get(url, timeout=20) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            
                            # Limite de 25MB (padrão Railway/Discord Free)
                            if len(data) > 25 * 1024 * 1024:
                                await msg.add_reaction("❌")
                                continue
                            
                            # FORÇAR EXTENSÃO .MP4 PARA GERAR PLAYER
                            # Remove parâmetros de URL e garante o .mp4 no final
                            filename = "video_player.mp4" 

                            file_data = BytesIO(data)
                            d_file = discord.File(file_data, filename=filename)
                            
                            await down_ch.send(
                                content=f"🎬 **Vídeo pronto para reprodução:** {mention_target}",
                                file=d_file
                            )
                            await msg.add_reaction("💾")
                        else:
                            await msg.add_reaction("❌")
                except:
                    await msg.add_reaction("❌")
                await anti_rate()
    await ctx.send("✅ Finalizado.")

@bot.command()
async def limpar(ctx, emoji_alvo=None, *, arg=None):
    """Remove reações específicas das mensagens"""
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("❌ Sem permissão para gerenciar mensagens.")
        return

    date = parse_date(arg)
    if not emoji_alvo:
        await ctx.send("ℹ️ Ex: `!limpar 💾 hoje` ou `!limpar tudo hoje`")
        return

    await ctx.send(f"🧹 Limpando reações {emoji_alvo}...")
    count = 0
    async for msg in ctx.channel.history(limit=100):
        if date and msg.created_at < date: continue
        
        if emoji_alvo.lower() == "tudo":
            await msg.clear_reactions()
            count += 1
        else:
            for reaction in msg.reactions:
                if str(reaction.emoji) == emoji_alvo:
                    await msg.clear_reaction(reaction.emoji)
                    count += 1
        await asyncio.sleep(0.4)
    await ctx.send(f"✅ Removido de {count} mensagens.")

# (Manter os comandos !downvideos, !link, !scan e !limparforum das versões anteriores)

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")

bot.run(TOKEN)
