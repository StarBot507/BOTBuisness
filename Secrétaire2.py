import discord
from discord.ext import commands
import logging
import os
import time
import asyncio
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()




# Token du bot
token = os.getenv('BOT_TOKEN')

# Classe personnalisée pour le bot Discord
class MonBot(commands.Bot):
    """Classe personnalisée pour le bot Discord."""
    async def setup_hook(self):
        extensions = [
            'Autre', 'Election', 'Travailler'
        ]

        for extension in extensions:
            try:
                await self.load_extension(f'cogs.{extension}')
                print(f"Extension {extension} chargée avec succès.")
                # Introduire une pause entre chaque chargement pour différer
                await asyncio.sleep(1)  # Délai de 3 secondes
            except Exception as e:
                print(f"Erreur en chargeant {extension}: {e}")

intents = discord.Intents.all()
bot = MonBot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    """Action exécutée une fois le bot prêt."""
    print(f"Connecté en tant que {bot.user}")

    # Synchronisation des commandes différée avec gestion des erreurs
    try:
        await bot.tree.sync()
        print("Les commandes ont été synchronisées avec succès.")
    except discord.errors.HTTPException as e:
        print(f"Erreur lors de la synchronisation : {e}")

    # Afficher les commandes disponibles
    for command in bot.tree.get_commands():
        print(f'- {command.name}')
        
@discord.app_commands.command(name="sync_module", description="Force la synchronisation des commandes d'un module spécifique.")
async def sync_module(interaction: discord.Interaction, module: str):
    """
    Synchronise toutes les commandes d'un module spécifique.
    :param interaction: L'interaction Discord.
    :param module: Nom du module à synchroniser.
    """
    try:
        # Chargement du module (Cog) spécifié
        await bot.load_extension(f'cogs.{module}')
        await bot.tree.sync()  # Force la synchronisation globale
        await interaction.response.send_message(f"🔄 Le module **{module}** a été synchronisé avec succès !", ephemeral=True)

    except commands.ExtensionAlreadyLoaded:
        await interaction.response.send_message(f"⚠️ Le module **{module}** est déjà chargé.", ephemeral=True)

    except commands.ExtensionNotFound:
        await interaction.response.send_message(f"❌ Le module **{module}** n'a pas été trouvé. Vérifiez le nom !", ephemeral=True)

    except discord.errors.HTTPException as e:
        await interaction.response.send_message(f"❌ Erreur lors de la synchronisation : {e}.", ephemeral=True)



keep_alive()
# Ajout à l'arbre de commandes
bot.tree.add_command(sync_module)


# Lancer le bot
bot.run(token)
