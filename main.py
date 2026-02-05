import discord
import asyncio
import os
import re
import aiohttp
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

# ================= COMANDOS DE MOVIMENTAÇÃO =================

@bot.command()
async def downvideos(ctx, *, arg=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False
    date = parse_date(arg)
    scan_ch = bot.get_channel(SCAN_CHANNEL_ID)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    await ctx.send(f"📥 Movendo vídeos de <#{SCAN_CHANNEL_ID}>...")
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
    await ctx.send("✅ !downvideos concluído.")

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
    await ctx.send("✅ !link concluído.")

@bot.command()
async def linksdownload(ctx, *, arg=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False
    date = parse_date(arg)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    await ctx.send(f"💾 Baixando vídeos (Player ON) em <#{DOWNLOAD_CHANNEL_ID}>...")
    async with aiohttp.ClientSession() as session:
        async for msg in down_ch.history(limit=None, oldest_first=True):
            if CANCEL_FLAG: break
            if date and msg.created_at < date: continue
            links = re.findall(URL_PATTERN, msg.content)
            mention_target = msg.mentions[0].mention if msg.mentions else msg.author.mention
            for url in links:
                try:
                    async with session.get(url, timeout=20) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 25 * 1024 * 1024:
                                await msg.add_reaction("❌")
                                continue
                            # Força .mp4 para o player do Discord funcionar
                            d_file = discord.File(BytesIO(data), filename="video_player.mp4")
                            await down_ch.send(content=f"🎬 **Player pronto:** {mention_target}", file=d_file)
                            await msg.add_reaction("💾")
                        else: await msg.add_reaction("❌")
                except: await msg.add_reaction("❌")
                await anti_rate()
    await ctx.send("✅ !linksdownload concluído.")

# ================= COMANDOS DE FÓRUM E LIMPEZA =================

@bot.command()
async def scan(ctx, *, arg=None):
    if not arg or "link" not in arg.lower():
        await ctx.send("ℹ️ Use `!scan link hoje`")
        return
    global CANCEL_FLAG
    CANCEL_FLAG = False
    data_str = arg.lower().replace("link", "").strip()
    date = parse_date(data_str)
    down_ch = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    forum_ch = bot.get_channel(POST_CHANNEL_ID)
    async for msg in down_ch.history(limit=None, oldest_first=True):
        if CANCEL_FLAG: break
        if date and msg.created_at < date: continue
        if not msg.attachments: continue
        title = f"@{msg.mentions[0].display_name}" if msg.mentions else f"Post de {msg.author.display_name}"
        for att in msg.attachments:
            try:
                file = await att.to_file()
                if isinstance(forum_ch, discord.ForumChannel):
                    await forum_ch.create_thread(name=title, content=f"🎬 De: {msg.author.display_name}", file=file)
                else:
                    await forum_ch.send(content=f"**{title}**", file=file)
                await msg.add_reaction("✅")
            except: await msg.add_reaction("🧐")
            await anti_rate()
    await ctx.send("✅ !scan concluído.")

@bot.command()
async def limpar(ctx, emoji_alvo=None, *, arg=None):
    if not ctx.author.guild_permissions.manage_messages: return
    date = parse_date(arg)
    count = 0
    async for msg in ctx.channel.history(limit=100):
        if date and msg.created_at < date: continue
        if emoji_alvo.lower() == "tudo":
            await msg.clear_reactions()
            count += 1
        else:
            for r in msg.reactions:
                if str(r.emoji) == emoji_alvo:
                    await msg.clear_reaction(r.emoji)
                    count += 1
    await ctx.send(f"✅ Limpeza de reações concluída ({count}).")

@bot.command()
async def limparforum(ctx, *, arg=None):
    if not ctx.author.guild_permissions.manage_threads: return
    date = parse_date(arg)
    forum_ch = bot.get_channel(POST_CHANNEL_ID)
    if not date: return
    threads = forum_ch.threads + [t async for t in forum_ch.archived_threads()]
    for t in threads:
        if t.created_at < date:
            try: await t.delete()
            except: pass
            await asyncio.sleep(0.5)
    await ctx.send("✅ Fórum limpo.")

# ================= O COMANDO DE CANCELAMENTO =================

@bot.command()
async def cancelgeral(ctx):
    """Para qualquer operação de varredura (downvideos, link, scan, etc)"""
    global CANCEL_FLAG
    CANCEL_FLAG = True
    await ctx.send("🛑 **CANCELAMENTO SOLICITADO.** O bot vai parar assim que terminar o arquivo atual.")

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")

bot.run(TOKEN)
