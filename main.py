async def process_message(message):
    if message.author.bot:
        return

    urls = URL_REGEX.findall(message.content)
    if not urls:
        return

    user_id = str(message.author.id)
    date_folder = message.created_at.strftime("%Y-%m-%d")
    user_folder = os.path.join(DOWNLOAD_BASE, user_id, date_folder)
    os.makedirs(user_folder, exist_ok=True)

    for url in urls:
        try:
            print(f"⬇️ Baixando {url} | Usuário {user_id}")

            subprocess.run(
                [
                    "yt-dlp",
                    "-o",
                    f"{user_folder}/%(title)s.%(ext)s",
                    url
                ],
                check=True
            )

            # enviar todos os arquivos baixados
            for filename in os.listdir(user_folder):
                file_path = os.path.join(user_folder, filename)

                if os.path.isfile(file_path):
                    try:
                        await message.channel.send(
                            content=f"📥 Arquivo enviado por <@{user_id}>",
                            file=discord.File(file_path)
                        )
                        os.remove(file_path)
                        print(f"✅ Enviado e removido: {filename}")

                    except Exception as e:
                        print(f"❌ Erro ao enviar {filename}: {e}")

        except subprocess.CalledProcessError as e:
            print(f"❌ yt-dlp falhou para {url}: {e}")
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
