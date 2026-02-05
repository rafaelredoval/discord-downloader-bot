import discord
import asyncio
import os
import re
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

# ================= COMANDOS DE MOVIMENTAÇÃO =================

@bot.command()
async def downvideos(ctx, *, arg=None):
    """Varre SCAN, baixa vídeos e move para DOWNLOAD (reage com ✅)"""
    if ctx.channel.id != SCAN_CHANNEL_ID: return
    global CANCEL_FLAG
    CANCEL_FLAG = False
    
    date = parse_date(arg)
    scan_ch = bot.get_channel(SCAN_CHANNEL_ID)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)

    await ctx.send(f"📥 Movendo vídeos para <#{DOWNLOAD_CHANNEL_ID}>...")
    
    async for msg in scan_ch.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if date and msg.created_at < date: continue
        if not msg.attachments: continue

        for att in msg.attachments:
            if any(att.filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv']):
                try:
                    file = await att.to_file()
                    await down_ch.send(content=f"🎬 Vídeo de: {msg.author.mention}", file=file)
                    await msg.add_reaction("✅")
                except:
                    await msg.add_reaction("❌")
                await anti_rate()
    await ctx.send("✅ !downvideos finalizado.")

@bot.command()
async def link(ctx, *, arg=None):
    """Varre SCAN, captura links e move para DOWNLOAD (reage com ✅)"""
    if ctx.channel.id != SCAN_CHANNEL_ID: return
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
                content = f"🔗 **Link de:** {msg.author.mention}\n" + "\n".join(links)
                await down_ch.send(content=content)
                await msg.add_reaction("✅")
            except:
                await msg.add_reaction("❌")
            await anti_rate()
    await ctx.send("✅ !link finalizado.")

# ================= COMANDOS DE FÓRUM =================

@bot.command()
async def scan(ctx, *, arg=None):
    """Varre DOWNLOAD e posta no FÓRUM (reage com ✅ no download)"""
    if ctx.channel.id != SCAN_CHANNEL_ID: return
    if not arg or not arg.startswith("link"):
        await ctx.send("ℹ️ Use `!scan link hoje` ou `!scan link data`")
        return

    global CANCEL_FLAG
    CANCEL_FLAG = False
    
    data_str = arg.replace("link", "").strip()
    date = parse_date(data_str)
    
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    forum_ch = bot.get_channel(POST_CHANNEL_ID)

    await ctx.send("🚀 Postando no Fórum e validando com ✅...")
    async for msg in down_ch.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if date and msg.created_at < date: continue
        if not msg.attachments: continue

        title = f"@{msg.mentions[0].display_name}" if msg.mentions else f"Post de {msg.author.display_name}"
        header = f"🎬 Enviado por: **{msg.author.display_name}**"

        for att in msg.attachments:
            try:
                file = await att.to_file()
                if isinstance(forum_ch, discord.ForumChannel):
                    await forum_ch.create_thread(name=title, content=header, file=file)
                else:
                    await forum_ch.send(content=f"**{title}**\n{header}", file=file)
                await msg.add_reaction("✅")
            except:
                await msg.add_reaction("🧐")
            await anti_rate()
    await ctx.send("✅ !scan link finalizado.")

# ================= COMANDOS DE LIMPEZA =================

@bot.command()
async def limparforum(ctx, *, arg=None):
    """Deleta tópicos do fórum criados ANTES da data/hora informada"""
    if not ctx.author.guild_permissions.manage_threads:
        await ctx.send("❌ Você precisa da permissão 'Gerenciar Tópicos'.")
        return

    date = parse_date(arg)
    forum_ch = bot.get_channel(POST_CHANNEL_ID)
    if not date or not isinstance(forum_ch, discord.ForumChannel):
        await ctx.send("❌ Data inválida ou canal não é um Fórum.")
        return

    await ctx.send(f"⚠️ Limpando tópicos anteriores a {date}...")
    
    count = 0
    # Pega tópicos ativos e arquivados
    threads = forum_ch.threads + [t async for t in forum_ch.archived_threads()]
    
    for t in threads:
        if t.created_at < date:
            try:
                await t.delete()
                count += 1
                await asyncio.sleep(0.5)
            except: pass
            
    await ctx.send(f"✅ Sucesso! {count} tópicos removidos.")

@bot.command()
async def cancelgeral(ctx):
    global CANCEL_FLAG
    CANCEL_FLAG = True
    await ctx.send("🛑 Cancelamento ativado.")

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")

bot.run(TOKEN)
