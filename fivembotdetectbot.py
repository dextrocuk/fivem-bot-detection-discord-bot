import requests
import discord
from discord.ext import commands
from discord import app_commands
import asyncio

DISCORD_TOKEN = ""
WEBHOOK_URL = ""

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)

def check_server(cfx_code):
    try:
        headers = {
            'User-Agent': 'MyDiscordBot/1.0'
        }
        response = requests.get(f"https://servers-frontend.fivem.net/api/servers/single/{cfx_code}", headers=headers)

        if response.status_code == 404:
            return "Hata: API'den sunucu bulunamadı. Lütfen CFX kodunu kontrol edin.", None, []

        response.raise_for_status()

        server_data = response.json().get("Data", {})
        if not server_data:
            return "Hata: API'den geçerli sunucu verisi alınamadı.", None, []

        server_name = server_data.get("hostname", "Bilinmiyor")
        total_players = server_data.get("clients", 0)
        bot_detected = server_data.get("botDetected", False)
        fake_players_count = server_data.get("fakePlayersCount", 0)
        build_version = server_data.get("vars", {}).get("sv_enforceGameBuild", "Bilinmiyor")
        license_key_token = server_data.get("vars", {}).get("sv_licenseKeyToken", "Bilinmiyor")
        resources_count = len(server_data.get("resources", []))
        banner_url = server_data.get("vars", {}).get("banner_connecting", "")

        bot_list = []
        players = server_data.get("players", [])
        for player in players:
            for identifier in player.get("identifiers", []):
                if identifier.startswith("steam:"):
                    steam_hex = identifier.split(":")[1]
                    persona_name, err = get_steam_profile(hex_to_steam64(steam_hex))
                    if err or persona_name == "":
                        bot_list.append(player)

        if bot_detected or bot_list:
            provider = "NotPlayers"
        else:
            provider = "NOT DETECTED"

        result = (
            f"Server Name: {server_name}\n"
            f"Bot Detected: {'TRUE' if bot_detected or bot_list else 'FALSE'}\n"
            f"Provider: {provider}\n"
            f"Total Players: {total_players}\n"
            f"Fake Players Count: {len(bot_list)}\n"
            f"Build Version: {build_version}\n"
            f"Server License Key Token: {license_key_token}\n"
            f"Resource Count: {resources_count}"
        )
        return result, banner_url, bot_list

    except requests.exceptions.HTTPError as http_err:
        return f"Hata: API'den geçerli yanıt alınamadı. ({http_err})", None, []
    except requests.exceptions.RequestException as req_err:
        return f"Hata: Sunucuya bağlanırken bir hata oluştu. ({req_err})", None, []
    except Exception as e:
        return f"Hata: Beklenmeyen bir sorun oluştu. ({e})", None, []

def hex_to_steam64(hex_id):
    try:
        return str(int(hex_id, 16))
    except ValueError:
        return None

def get_steam_profile(steam64_id):
    return "", False

async def send_fake_player_to_webhook(fake_player):
    embed = {
        "title": "Fake Player Detected",
        "color": 15158332,
        "fields": [
            {"name": "Player Name", "value": fake_player.get("name", "Not available"), "inline": False},
            {"name": "Discord ID", "value": fake_player.get("discord", "Not available"), "inline": False},
            {"name": "XBL ID", "value": fake_player.get("xbl", "Not available"), "inline": False},
            {"name": "Live ID", "value": fake_player.get("live", "Not available"), "inline": False},
            {"name": "License", "value": fake_player.get("license", "Not available"), "inline": False},
        ],
        "footer": {"text": "kendini hacker zanneden dextro"}
    }

    try:
        response = requests.post(WEBHOOK_URL, json={"embeds": [embed]})
        response.raise_for_status()
    except requests.exceptions.RequestException as req_err:
        print(f"Webhook gönderilemedi: {req_err}")

async def send_fake_players(bot_list):
    for bot in bot_list:
        fake_player = {
            "name": bot.get("name", "Unknown"),
            "discord": "",
            "xbl": "",
            "live": "",
            "license": ""
        }

        for identifier in bot.get("identifiers", []):
            if identifier.startswith("discord:"):
                fake_player["discord"] = identifier.split(":")[1]
            elif identifier.startswith("xbl:"):
                fake_player["xbl"] = identifier.split(":")[1]
            elif identifier.startswith("live:"):
                fake_player["live"] = identifier.split(":")[1]
            elif identifier.startswith("license:"):
                fake_player["license"] = identifier.split(":")[1]

        await send_fake_player_to_webhook(fake_player)
        await asyncio.sleep(1.5)

@bot.event
async def on_ready():
    print(f"Bot {bot.user} olarak giriş yaptı.")
    try:
        guild = discord.utils.get(bot.guilds, id=1313181392217313340)
        if guild:
            print(f"Bot, belirtilen sunucuda aktif: {guild.name}")
        else:
            print("Bot, belirtilen sunucuda değil.")
            await bot.close()
            return

        synced = await bot.tree.sync()
        print(f"Slash komutları senkronize edildi: {len(synced)} komut.")
    except Exception as e:
        print(f"Komut senkronizasyon hatası: {e}")

async def role_check(interaction: discord.Interaction) -> bool:
    required_role_id = 1313185198267043880
    user_roles = [role.id for role in interaction.user.roles]
    if required_role_id not in user_roles:
        await interaction.response.send_message(
            "Bu komutu kullanmak için gerekli izne sahip değilsiniz.", ephemeral=True
        )
        return False
    return True

@bot.tree.command(name="check", description="Bir FiveM sunucusunda bot var mı kontrol edin.")
@app_commands.describe(cfx_code="Kontrol edilecek FiveM sunucusunun CFX kodu.")
@app_commands.choices(webhook_gönderilsinmi=[
    app_commands.Choice(name="Evet", value="evet"),
    app_commands.Choice(name="Hayır", value="hayir")
])
async def check(interaction: discord.Interaction, cfx_code: str, webhook_gönderilsinmi: app_commands.Choice[str]):
    if interaction.guild_id != 1313181392217313340:
        await interaction.response.send_message(
            "bu bot bu sunucuda kullanılamaz.", ephemeral=True
        )
        return

    if not await role_check(interaction):
        return

    await interaction.response.defer()

    result, banner_url, bot_list = check_server(cfx_code)

    embed = discord.Embed(title="Server Status Report", color=discord.Color.dark_red())
    for line in result.split("\n"):
        if ": " in line:
            key, value = line.split(": ", 1)
            embed.add_field(name=key.strip(), value=value.strip(), inline=False)

    if banner_url and banner_url.startswith("http"):
        embed.set_image(url=banner_url)

    await interaction.followup.send(embed=embed)

    if webhook_gönderilsinmi.value == "evet":
        await send_fake_players(bot_list)

@bot.tree.command(name="checkapi", description="Sunucunun API durumu ve bilgilerini kontrol eder.")
@app_commands.describe(cfx_code="Kontrol edilecek FiveM sunucusunun CFX kodu.")
async def check_api(interaction: discord.Interaction, cfx_code: str):
    if interaction.guild_id != 1313181392217313340:
        await interaction.response.send_message(
            "Bu bot bu sunucuda kullanılamaz.", ephemeral=True
        )
        return

    if not await role_check(interaction):
        return

    await interaction.response.defer()

    result, banner_url, _ = check_server(cfx_code)

    embed = discord.Embed(title="API CHECK", color=discord.Color.green())
    for line in result.split("\n"):
        if ": " in line:
            key, value = line.split(": ", 1)
            if key.strip() == "Server Name":
                embed.add_field(name="Server Name", value=value.strip(), inline=False)
            elif key.strip() == "Provider":
                embed.add_field(name="API", value=value.strip(), inline=False)
            elif key.strip() == "Server License Key Token":
                embed.add_field(name="License Key", value=value.strip(), inline=False)

    if banner_url and banner_url.startswith("http"):
        embed.set_image(url=banner_url)

    await interaction.followup.send(embed=embed)

if __name__ == "__main__":
    if not DISCORD_TOKEN or not WEBHOOK_URL:
        print("Lütfen DISCORD_TOKEN ve WEBHOOK_URL ayarlarını yapın.")
        exit(1)

    bot.run(DISCORD_TOKEN)
