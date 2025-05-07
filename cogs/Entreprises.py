import discord
from discord import app_commands
from discord.ext import commands
from discord import Embed
import sqlite3
import math
import requests
import aiohttp
from discord.ui import Button, View

# IDs des rôles
ROLE_ENTREPRENEUR = 1356316417435238469
ROLE_INVESTISSEUR = 1356317023172563137

# Connexion SQLite
conn = sqlite3.connect('entreprises.db')
c = conn.cursor()

# Tables
c.execute('''
CREATE TABLE IF NOT EXISTS entreprises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT UNIQUE,
    createur_id INTEGER,
    actions_totales INTEGER,
    actions_marche INTEGER,
    prix_action INTEGER
)
''')
c.execute('''
CREATE TABLE IF NOT EXISTS actions (
    utilisateur_id INTEGER,
    entreprise_id INTEGER,
    nombre_actions INTEGER,
    PRIMARY KEY (utilisateur_id, entreprise_id)
)
''')
conn.commit()

# Intégration de l'API UnbelievaBoat
UB_API_URL = "https://unbelievaboat.com/api"  # Exemple de base, tu devras ajouter la clé API à chaque requête
UB_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzU4MDEwNTg0MDA3ODM4NDIzIiwiaWF0IjoxNzQzODQ1MzUzfQ.MVyA4OU4bgetYIB-T1aCajjJgEI2YTrcnV7owX38BlU'# Remplace avec ta clé API
GUILD_ID = 1161602328714023013  # Remplace par l'ID de ton serveur
banque_id = '1352967560798277712'

def get_balance(user_id):
    headers = {
        "Authorization": UB_API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.get(f"{UB_API_URL}/v1/guilds/{GUILD_ID}/users/{user_id}", headers=headers)
    if response.status_code == 200:
        return response.json()["total"]
    else:
        print('no code == 200')
        print(response.status_code)
        return None

def adjust_balance(user_id, guild_id, amount):
    url_user = f"{UB_API_URL}/v1/guilds/{GUILD_ID}/users/{user_id}"

    # PATCH utilisateur : retrait du cash
    patch_user = requests.patch(url_user, headers={
        "Authorization": UB_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }, json={"cash": -amount, "bank": 0, "reason": "Achat d'actions ou création d'entreprise (si montant = 100.000)"})



class Entreprises(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Commande: /creer_entreprise
    @app_commands.command(name="creer_entreprise", description="Crée une entreprise avec un nom et des actions.")
    @app_commands.describe(nom="Nom de l'entreprise", nombre_actions="Nombre total d'actions", prix_action="Prix de chaque action")
    async def creer_entreprise(self, interaction: discord.Interaction, nom: str, nombre_actions: int, prix_action: int):
        if not any(role.id == ROLE_ENTREPRENEUR for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Tu n'as pas le rôle pour créer une entreprise.", ephemeral=True)

        if nombre_actions < 100:
            await interaction.response.send_message("Le nombre d'action doit être supèrieur où égale à 100")
            return
        # Vérification du solde utilisateur pour la création d'entreprise (100000 nécessaires)
        balance = get_balance(interaction.user.id)
        if balance is None or balance < 100000:
            return await interaction.response.send_message("❌ Tu n'as pas assez d'argent pour créer une entreprise.", ephemeral=True)

        c.execute("SELECT * FROM entreprises WHERE createur_id = ?", (interaction.user.id,))
        if c.fetchone():
            return await interaction.response.send_message("❌ Tu as déjà une entreprise.", ephemeral=True)

        actions_createur = math.floor(nombre_actions * 0.34)
        actions_marche = nombre_actions - actions_createur

        try:
            c.execute("INSERT INTO entreprises (nom, createur_id, actions_totales, actions_marche, prix_action) VALUES (?, ?, ?, ?, ?) ",
                      (nom, interaction.user.id, nombre_actions, actions_marche, prix_action))
            entreprise_id = c.lastrowid

            c.execute("INSERT INTO actions (utilisateur_id, entreprise_id, nombre_actions) VALUES (?, ?, ?)",
                      (interaction.user.id, entreprise_id, actions_createur))
            conn.commit()

            # Déduire 100000 du solde pour la création de l'entreprise

            adjust_balance(guild_id=GUILD_ID, user_id=interaction.user.id, amount=100000)

        except sqlite3.IntegrityError:
            return await interaction.response.send_message("❌ Ce nom d’entreprise est déjà pris.", ephemeral=True)

        await interaction.response.send_message(
            f"✅ Ton entreprise **{nom}** a été créée avec **{nombre_actions} actions**.\n"
            f"Tu en possèdes **{actions_createur}**, et **{actions_marche}** sont sur le marché.\n"
            f"Le prix de chaque action est de **{prix_action}**."
        )

    # Commande: /investir
    @app_commands.command(name="investir", description="Investis dans une entreprise en achetant des actions.")
    @app_commands.describe(nom_entreprise="Nom de l'entreprise", quantite="Quantité d'actions à acheter")
    async def investir(self, interaction: discord.Interaction, nom_entreprise: str, quantite: int):
        if not any(role.id == ROLE_INVESTISSEUR for role in interaction.user.roles):
            return await interaction.response.send_message("❌ Tu n'as pas le rôle pour investir.", ephemeral=True)

        c.execute("SELECT id, actions_marche, prix_action FROM entreprises WHERE nom = ?", (nom_entreprise,))
        row = c.fetchone()
        if not row:
            return await interaction.response.send_message("❌ Cette entreprise n'existe pas.", ephemeral=True)

        entreprise_id, actions_disponibles, prix_action = row
        if quantite > actions_disponibles:
            return await interaction.response.send_message(
                f"❌ Il ne reste que **{actions_disponibles}** actions à acheter.", ephemeral=True)

        # Vérification du solde avant achat
        total_price = prix_action * quantite
        balance = get_balance(interaction.user.id)
        if balance is None or balance < total_price:
            return await interaction.response.send_message(f"❌ Tu n'as pas assez d'argent pour acheter **{quantite}** actions.", ephemeral=True)

        # Acheter les actions
        c.execute("UPDATE entreprises SET actions_marche = actions_marche - ? WHERE id = ?", (quantite, entreprise_id))
        c.execute("""
        INSERT INTO actions (utilisateur_id, entreprise_id, nombre_actions)
        VALUES (?, ?, ?)
        ON CONFLICT(utilisateur_id, entreprise_id)
        DO UPDATE SET nombre_actions = nombre_actions + ?
        """, (interaction.user.id, entreprise_id, quantite, quantite))
        
        # Déduire le montant de l'achat du solde utilisateur
        adjust_balance(guild_id=GUILD_ID, user_id=interaction.user.id, amount = total_price)
        conn.commit()

        await interaction.response.send_message(
            f"✅ Tu as acheté **{quantite} actions** de **{nom_entreprise}** au prix de **{prix_action}** chacun."
        )

    # Commande: /entreprises
    @app_commands.command(name="entreprises", description="Liste toutes les entreprises existantes.")
    async def entreprises(self, interaction: discord.Interaction):
        c.execute("SELECT nom, actions_totales, actions_marche, prix_action FROM entreprises")
        entreprises = c.fetchall()

        if not entreprises:
            return await interaction.response.send_message("📉 Aucune entreprise enregistrée.")

        embed = discord.Embed(title="📈 Liste des entreprises", color=discord.Color.green())
        for nom, total, marche, prix in entreprises:
            embed.add_field(
                name=nom,
                value=f"Total : **{total}** | Sur le marché : **{marche}** | Prix par action : **{prix}**",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    # Commande: /mon_portefeuille
    @app_commands.command(name="mon_portefeuille", description="Affiche les actions que tu possèdes.")
    async def mon_portefeuille(self, interaction: discord.Interaction):
        c.execute("""
        SELECT entreprises.nom, actions.nombre_actions, entreprises.prix_action
        FROM actions
        JOIN entreprises ON actions.entreprise_id = entreprises.id
        WHERE actions.utilisateur_id = ?
        """, (interaction.user.id,))
        resultats = c.fetchall()

        if not resultats:
            return await interaction.response.send_message("🪙 Tu ne possèdes aucune action.")

        embed = discord.Embed(title="📦 Ton portefeuille", color=discord.Color.gold())
        total = 0
        for nom, nb, prix in resultats:
            embed.add_field(name=nom, value=f"{nb} actions | Prix par action : {prix}", inline=False)
            total += nb * prix

        embed.set_footer(text=f"Total : {total} \u20AC")
        await interaction.response.send_message(embed=embed)

#Commande : /gestion_entreprise
    @app_commands.command(name="gestion_entreprise", description="Gère ton entreprise (changer le nom, voir les actionnaires, supprimer).")
    async def gestion_entreprise(self, interaction: discord.Interaction):
        c.execute("SELECT id, nom FROM entreprises WHERE createur_id = ?", (interaction.user.id,))
        entreprise = c.fetchone()
        if not entreprise:
            return await interaction.response.send_message("❌ Tu n'as pas d'entreprise à gérer.", ephemeral=True)

        entreprise_id, nom_actuel = entreprise

        # Actionnaires
        c.execute("""
        SELECT utilisateur_id, nombre_actions FROM actions WHERE entreprise_id = ?
        """, (entreprise_id,))
        actionnaires = c.fetchall()

        embed = discord.Embed(title=f"Gestion de l'entreprise : {nom_actuel}", color=discord.Color.blue())
        embed.add_field(name="Actionnaires", value="\n".join(
            [f"<@{uid}> : {nb} actions" for uid, nb in actionnaires]
        ) or "Aucun", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)





#Commande : /renommer_entreprise
    @app_commands.command(name="renommer_entreprise", description="Renomme ton entreprise.")
    @app_commands.describe(nouveau_nom="Nouveau nom de ton entreprise")
    async def renommer_entreprise(self, interaction: discord.Interaction, nouveau_nom: str):
        c.execute("SELECT id FROM entreprises WHERE createur_id = ?", (interaction.user.id,))
        entreprise = c.fetchone()
        if not entreprise:
            return await interaction.response.send_message("❌ Tu n'as pas d'entreprise à renommer.", ephemeral=True)

        try:
            c.execute("UPDATE entreprises SET nom = ? WHERE id = ?", (nouveau_nom, entreprise[0]))
            conn.commit()
        except sqlite3.IntegrityError:
            return await interaction.response.send_message("❌ Ce nom est déjà pris par une autre entreprise.", ephemeral=True)

        await interaction.response.send_message(f"✅ Ton entreprise a été renommée en {nouveau_nom}.", ephemeral=True)

    class SupprimerEntrepriseView(View):
        def __init__(self, entreprise_id: int, prix_action: int, author: discord.User):
            super().__init__(timeout=60)
            self.entreprise_id = entreprise_id
            self.prix_action = prix_action
            self.author = author

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            return interaction.user.id == self.author.id

        @discord.ui.button(label="✅ Confirmer", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: Button):
            # 1) Remboursement
            c.execute("SELECT utilisateur_id, nombre_actions FROM actions WHERE entreprise_id = ?", (self.entreprise_id,))
            actionnaires = c.fetchall()
            async with aiohttp.ClientSession() as session:
                for user_id, qty in actionnaires:
                    montant = qty * self.prix_action
                    await session.patch(
                        f"{UB_API_URL}/{user_id}",
                        headers={"Authorization": UB_API_KEY, "Content-Type": "application/json"},
                        json={"cash": montant}
                    )
            # 2) Suppression en base
            c.execute("DELETE FROM actions WHERE entreprise_id = ?", (self.entreprise_id,))
            c.execute("DELETE FROM entreprises WHERE id = ?", (self.entreprise_id,))
            conn.commit()

            await interaction.response.edit_message(
                content="✅ Ton entreprise a été supprimée et tous les actionnaires ont été remboursés.",
                embed=None, view=None
            )

        @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: Button):
            await interaction.response.edit_message(
                content="❌ Suppression annulée.",
                embed=None, view=None
            )

    @app_commands.command(
        name="supprimer_entreprise",
        description="Supprime ton entreprise (confirme et rembourse les actionnaires)."
    )
    async def supprimer_entreprise(self, interaction: discord.Interaction):
        c.execute("SELECT id, nom, prix_action FROM entreprises WHERE createur_id = ?", (interaction.user.id,))
        row = c.fetchone()
        if not row:
            return await interaction.response.send_message(
                "❌ Tu n'as pas d'entreprise à supprimer.", ephemeral=True
            )

        entreprise_id, nom, prix_action = row

        view = self.SupprimerEntrepriseView(
            entreprise_id=entreprise_id,
            prix_action=prix_action,
            author=interaction.user
        )
        embed = Embed(
            title="⚠️ Supprimer ton entreprise",
            description=(
                f"Tu t'apprêtes à supprimer **{nom}**.\n"
                f"Tous les actionnaires seront remboursés **{prix_action}$** par action.\n\n"
                "Clique sur ✅ **Confirmer** pour valider, ou ❌ **Annuler** pour revenir en arrière."
            ),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    

async def setup(bot):
    await bot.add_cog(Entreprises(bot))
