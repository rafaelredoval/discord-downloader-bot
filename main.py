import discord
import asyncio
import os
import re
import aiohttp
from io import BytesIO
from discord.ext import commands
from datetime import datetime, timezone, time

# Tenta carregar o .env apenas localmente
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

# --- Comandos de Movimentação ---

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
    await ctx.send("✅ !downvideos finalizado.")

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
    await ctx.send("✅ !link finalizado.")

# --- Comando LINKS DOWNLOAD (Agora com menção do usuário original) ---

@bot.command()
async def linksdownload(ctx, *, arg=None):
    """Baixa o vídeo do link e envia mencionando o usuário da mensagem original"""
    global CANCEL_FLAG
    CANCEL_FLAG = False
    date = parse_date(arg)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    
    await ctx.send(f"💾 Baixando vídeos dos links em <#{DOWNLOAD_CHANNEL_ID}>...")
    
    async with aiohttp.ClientSession() as session:
        async for msg in down_ch.history(limit=None, oldest_first=True):
            if CANCEL_FLAG: break
            if date and msg.created_at < date: continue
            
            links = re.findall(URL_PATTERN, msg.content)
            if not links: continue

            # Identifica quem deve ser mencionado (quem foi marcado na mensagem ou o autor)
            mention_target = msg.mentions[0].mention if msg.mentions else msg.author.mention

            for url in links:
                try:
                    async with session.get(url, timeout=20) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            
                            # Verificação de tamanho (25MB limite Discord)
                            if len(data) > 25 * 1024 * 1024:
                                await msg.add_reaction("❌") # Muito grande
                                continue
                            
                            # Tenta extrair um nome de arquivo
                            filename = url.split("/")[-1].split("?")[0] or "video_extraido.mp4"
                            if "." not in filename: filename += ".mp4"

                            file_data = BytesIO(data)
                            d_file = discord.File(file_data, filename=filename)
                            
                            await down_ch.send(
                                content=f"💾 **Vídeo completo baixado para:** {mention_target}",
                                file=d_file
                            )
                            await msg.add_reaction("💾")
                        else:
                            await msg.add_reaction("❌")
                except:
                    await msg.add_reaction("❌")
                await anti_rate()
                
    await ctx.send("✅ !linksdownload finalizado.")

# --- Comandos de Fórum e Limpeza ---

@bot.command()
async def scan(ctx, *, arg=None):
    if not arg or "link" not in arg.lower():
        await ctx.send("ℹ️ Use `!scan link hoje` ou data")
        return
    global CANCEL_FLAG
    CANCEL_FLAG = False
    data_str = arg.lower().replace("link", "").strip()
    date = parse_date(data_str)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    forum_ch = bot.get_channel(POST_CHANNEL_ID)

    await ctx.send("🚀 Postando no Fórum...")
    async for msg in down_ch.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if date and msg.created_at < date: continue
        if not msg.attachments: continue
        title = f"@{msg.mentions[0].display_name}" if msg.mentions else f"Post de {msg.author.display_name}"
        for att in msg.attachments:
            try:
                file = await att.to_file()
                content = f"🎬 Enviado por: **{msg.author.display_name}**"
                if isinstance(forum_ch, discord.ForumChannel):
                    await forum_ch.create_thread(name=title, content=content, file=file)
                else:
                    await forum_ch.send(content=f"**{title}**\n{content}", file=file)
                await msg.add_reaction("✅")
            except: await msg.add_reaction("🧐")
            await anti_rate()
    await ctx.send("✅ !scan concluído.")

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
    await ctx.send("🛑 Cancelamento ativado.")

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")

bot.run(TOKEN)
