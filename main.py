import discord
import asyncio
import os
from discord.ext import commands
from datetime import datetime, timezone, time

# ================= VARIÁVEIS =================
TOKEN = os.getenv("DISCORD_TOKEN")
SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))
POST_CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID"))

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)
CANCEL_FLAG = False

# ================= UTILITÁRIOS =================
def parse_date(text):
    try:
        if text.lower() == "hoje":
            agora = datetime.now(timezone.utc)
            return datetime.combine(agora.date(), time.min).replace(tzinfo=timezone.utc)
        if "/" in text:
            return datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

async def anti_rate():
    await asyncio.sleep(1.4)

# ================= FUNÇÕES DE EXECUÇÃO =================

async def run_downvideos(ctx, start_date=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False

    scan_channel = bot.get_channel(SCAN_CHANNEL_ID)
    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)

    if not scan_channel or not download_channel:
        await ctx.send("❌ Erro: Canais não configurados corretamente.")
        return

    await ctx.send(f"📥 Movendo vídeos de <#{SCAN_CHANNEL_ID}> para <#{DOWNLOAD_CHANNEL_ID}>...")

    async for msg in scan_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG:
            await ctx.send("🛑 Operação interrompida.")
            return

        if start_date and msg.created_at < start_date:
            continue

        if not msg.attachments:
            continue

        for att in msg.attachments:
            extensoes_video = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
            if any(att.filename.lower().endswith(ext) for ext in extensoes_video):
                try:
                    arquivo = await att.to_file()
                    
                    # Envia para o canal de Download (Texto)
                    await download_channel.send(
                        content=f"🎬 Vídeo de: {msg.author.mention}", 
                        file=arquivo
                    )
                    
                    # REAÇÃO DE VERIFICADO: Adiciona o check na mensagem original do SCAN
                    await msg.add_reaction("✅")
                    
                except Exception as e:
                    print(f"Erro ao mover: {e}")
                    await msg.add_reaction("❌") # Reage com X se der erro no upload
                
                await anti_rate()

    await ctx.send("✅ Todos os vídeos foram processados e marcados!")

async def run_scan_post(ctx, start_date=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False
    
    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    post_channel = bot.get_channel(POST_CHANNEL_ID)

    await ctx.send("📦 Iniciando postagens no Fórum...")
    
    async for msg in download_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if start_date and msg.created_at < start_date: continue
        if not msg.attachments: continue

        if msg.mentions:
            thread_title = f"@{msg.mentions[0].display_name}"
        else:
            thread_title = f"Post de {msg.author.display_name}"

        header = f"🎬 Vídeo enviado por: **{msg.author.display_name}**"

        for att in msg.attachments:
            try:
                arquivo = await att.to_file()
                if isinstance(post_channel, discord.ForumChannel):
                    await post_channel.create_thread(name=thread_title, content=header, file=arquivo)
                else:
                    await post_channel.send(content=f"**{thread_title}**\n{header}", file=arquivo)
                
                await msg.add_reaction("✅")
            except:
                await msg.add_reaction("🧐")
            
            await anti_
