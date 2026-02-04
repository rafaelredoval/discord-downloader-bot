import discord
import asyncio
import os
from discord.ext import commands
from datetime import datetime, timezone

# ================= VARIÁVEIS =================

TOKEN = os.getenv("DISCORD_TOKEN")

SCAN_CHANNEL_ID = int(os.getenv("SCAN_CHANNEL_ID"))
DOWNLOAD_CHANNEL_ID = int(os.getenv("DOWNLOAD_CHANNEL_ID"))
POST_CHANNEL_ID = int(os.getenv("POST_CHANNEL_ID"))
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", 0))

# ================= BOT =================

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True # Importante para resolver nomes de usuários

bot = commands.Bot(command_prefix="!", intents=intents)

CANCEL_FLAG = False

# ================= UTIL =================

def parse_date(text):
    try:
        if "/" in text:
            return datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except:
        return None

async def anti_rate():
    await asyncio.sleep(1.4)

# ================= SCAN POST =================

async def run_scan_post(ctx, start_date=None):
    global CANCEL_FLAG
    CANCEL_FLAG = False

    download_channel = bot.get_channel(DOWNLOAD_CHANNEL_ID)
    post_channel = bot.get_channel(POST_CHANNEL_ID)

    if not download_channel or not post_channel:
        await ctx.send("❌ Erro: Canais não encontrados.")
        return

    await ctx.send("📦 Coletando mídias e convertendo menções em nomes...")

    async for msg in download_channel.history(limit=None, oldest_first=True):
        if CANCEL_FLAG:
            await ctx.send("🛑 Scan post cancelado")
            return

        if start_date and msg.created_at < start_date:
            continue

        if not msg.attachments:
            continue

        # --- LÓGICA PARA O TÍTULO SEM NÚMEROS ---
        # Verificamos se há usuários mencionados na mensagem
        if msg.mentions:
            # Pega o nome de exibição do primeiro usuário mencionado
            thread_title = f"@{msg.mentions[0].display_name}"
        elif msg.content and len(msg.content.strip()) > 0:
            # Se não for menção mas tiver texto, limpa possíveis IDs de canais/cargos
            # Pega a primeira linha e remove caracteres de menção bruta <@...>
            clean_text = discord.utils.remove_markdown(msg.content.split('\n')[0])
            thread_title = clean_text[:95] if clean_text else f"Post de {msg.author.display_name}"
        else:
            # Caso padrão: nome de quem postou
            thread_title = f"Post de {msg.author.display_name}"

        header = f"🎬 Vídeo enviado por: **{msg.author.display_name}**"

        for att in msg.attachments:
            try:
                file = await att.to_file()
                
                if isinstance(post_channel, discord.ForumChannel):
                    await post_channel.create_thread(name=thread_title, content=header, file=file)
                else:
                    await post_channel.send(content=f"**{thread_title}**\n{header}", file=file)
                
                await msg.add_reaction("✅")
            except Exception as e:
                error_content = f"**{thread_title}**\n{header}\n🔗 Link: {att.url}"
                
                if isinstance(post_channel, discord.ForumChannel):
                    await post_channel.create_thread(name=f"Link: {thread_title}", content=error_content)
                else:
                    await post_channel.send(content=error_content)
                
                await msg.add_reaction("🧐")
                print(f"Erro no anexo: {e}")

            await anti_rate()

    await ctx.send("✅ Scan post finalizado")

# ================= COMANDOS =================

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

    await ctx.send("ℹ️ Use `!scan post` ou `!scan post DD/MM/AAAA HH:MM`")

@bot.command()
async def cancelgeral(ctx):
    global CANCEL_FLAG
    CANCEL_FLAG = True
    await ctx.send("🛑 Cancelamento geral ativado")

# ================= READY =================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

if __name__ == "__main__":
    bot.run(TOKEN)
