import sqlite3
from collections import Counter
import discord
from discord import app_commands, ui
from discord.ext import commands

class Election(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.create_db()

    # Création de la base de données et des tables
    def create_db(self):
        conn = sqlite3.connect('election.db')
        c = conn.cursor()

        c.execute('''
        CREATE TABLE IF NOT EXISTS candidats (
            user_id INTEGER PRIMARY KEY,
            parti TEXT NOT NULL,
            programme TEXT NOT NULL,
            slogan TEXT
        )
        ''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            user_id INTEGER PRIMARY KEY,
            parti TEXT NOT NULL
        )
        ''')

        conn.commit()
        conn.close()

    # Enregistrer une candidature
    def enregistrer_candidat(self, user_id, parti, programme, slogan):
        conn = sqlite3.connect('election.db')
        c = conn.cursor()
        c.execute('''
        INSERT INTO candidats (user_id, parti, programme, slogan) 
        VALUES (?, ?, ?, ?)
        ''', (user_id, parti, programme, slogan))
        conn.commit()
        conn.close()

    # Enregistrer un vote
    def enregistrer_vote(self, user_id, parti):
        conn = sqlite3.connect('election.db')
        c = conn.cursor()
        c.execute('''
        INSERT INTO votes (user_id, parti) 
        VALUES (?, ?)
        ''', (user_id, parti))
        conn.commit()
        conn.close()

    @app_commands.command(name="list_partis", description="Affiche la liste des partis enregistrés")
    async def list_partis(self, interaction: discord.Interaction):
        conn = sqlite3.connect('election.db')
        c = conn.cursor()
        c.execute("SELECT user_id, parti, programme, slogan FROM candidats")
        resultats = c.fetchall()
        conn.close()

        if not resultats:
            await interaction.response.send_message("❌ Aucun parti enregistré.", ephemeral=True)
            return

        embed = discord.Embed(title="📋 Liste des partis enregistrés", color=discord.Color.blurple())
        for user_id, parti, programme, slogan in resultats:
            user = await self.bot.fetch_user(user_id)
            embed.add_field(
                name=f"🏛️ {parti}",
                value=f"👤 Candidat : {user.mention}\n📜 Programme : {programme}\n📣 Slogan : {slogan}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="candidater", description="Devenir candidat à l'élection")
    @app_commands.describe(parti="Nom du parti", programme="Ton programme", slogan="Ton slogan (facultatif)")
    async def candidater(self, interaction: discord.Interaction, parti: str, programme: str, slogan: str = None):
        user_id = interaction.user.id
        conn = sqlite3.connect('election.db')
        c = conn.cursor()
        c.execute('SELECT * FROM candidats WHERE user_id = ?', (user_id,))
        if c.fetchone():
            await interaction.response.send_message("❌ Tu es déjà candidat.", ephemeral=True)
            return
        conn.close()

        self.enregistrer_candidat(user_id, parti, programme, slogan or "Aucun slogan.")

        embed = discord.Embed(title="📥 Candidature enregistrée !", color=discord.Color.green())
        embed.add_field(name="👤 Candidat", value=interaction.user.mention, inline=True)
        embed.add_field(name="🏛️ Parti", value=parti, inline=True)
        embed.add_field(name="📜 Programme", value=programme, inline=False)
        embed.add_field(name="📣 Slogan", value=slogan or "Aucun slogan.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        admin_user_id = 1149382861040926841
        admin_user = await interaction.client.fetch_user(admin_user_id)
        try:
            await admin_user.send(f"🔔 Un utilisateur a candidater : {interaction.user.mention} a candidater.")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Impossible d'envoyer un message privé à l'administrateur.", ephemeral=True)

    # Bouton de vote
    class VoteButton(ui.Button):
        def __init__(self, label, parent):
            super().__init__(label=label, style=discord.ButtonStyle.primary)
            self.parent = parent

        async def callback(self, interaction: discord.Interaction):
            conn = sqlite3.connect('election.db')
            c = conn.cursor()
            c.execute('SELECT * FROM votes WHERE user_id = ?', (interaction.user.id,))
            if c.fetchone():
                await interaction.response.send_message("⚠️ Tu as déjà voté !", ephemeral=True)
                return
            conn.close()

            self.parent.enregistrer_vote(interaction.user.id, self.label)
            await interaction.response.send_message("✅ Ton vote a bien été enregistré !", ephemeral=True)

            admin_user_id = 1149382861040926841
            admin_user = await interaction.client.fetch_user(admin_user_id)
            try:
                await admin_user.send(f"🔔 Un utilisateur a voté : {interaction.user.mention} a voté pour le parti {self.label}.")
            except discord.Forbidden:
                await interaction.response.send_message("❌ Impossible d'envoyer un message privé à l'administrateur.", ephemeral=True)

    class VoteView(ui.View):
        def __init__(self, parent, timeout: int):
            super().__init__(timeout=timeout)
            self.parent = parent
            self.message = None

        async def on_timeout(self):
            for item in self.children:
                item.disabled = True
            if self.message:
                await self.message.edit(content="⏱️ Le vote est terminé !", view=self)
            await self.annoncer_resultats()

        async def annoncer_resultats(self):
            conn = sqlite3.connect('election.db')
            c = conn.cursor()
            c.execute('SELECT * FROM votes')
            votes = c.fetchall()

            if not votes:
                await self.message.channel.send("❌ Aucun vote enregistré.")
                return

            compteur = Counter([vote[1] for vote in votes])
            vote_blanc_count = compteur.pop("Vote blanc", 0)
            deux_mieux = compteur.most_common(2)

            embed = discord.Embed(title="🏁 Résultats de l'élection 🏁", color=discord.Color.green())
            if deux_mieux:
                for i, (parti, count) in enumerate(deux_mieux, 1):
                    embed.add_field(name=f"{i}. Parti : {parti}", value=f"Nombre de votes : {count}", inline=False)
            else:
                embed.description = "❌ Aucun vote valide (hors vote blanc)."

            if vote_blanc_count > 0:
                embed.add_field(name="🗳️ Votes blancs", value=f"{vote_blanc_count} vote(s)", inline=False)

            await self.message.channel.send(embed=embed)

        def add_candidate_buttons(self):
            conn = sqlite3.connect('election.db')
            c = conn.cursor()
            c.execute('SELECT * FROM candidats')
            candidats = c.fetchall()

            for _, parti, _, _ in candidats:
                self.add_item(Election.VoteButton(parti, self.parent))
            self.add_item(Election.VoteButton("Vote blanc", self.parent))

    @app_commands.command(name="election", description="Lance une élection avec durée en secondes.")
    @app_commands.describe(duree="Durée du vote en secondes")
    async def start_election(self, interaction: discord.Interaction, duree: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Tu dois être administrateur pour lancer une élection.", ephemeral=True)
            return

        conn = sqlite3.connect('election.db')
        c = conn.cursor()
        c.execute('SELECT * FROM candidats')
        if not c.fetchall():
            await interaction.response.send_message("❌ Aucun candidat inscrit.", ephemeral=True)
            return

        c.execute('SELECT * FROM candidats')
        candidats = c.fetchall()
        embed_partis = discord.Embed(title="📊 **Les partis candidats**", color=discord.Color.blue())

        for _, parti, programme, slogan in candidats:
            embed_partis.add_field(name=f"🏛️ {parti}", value=f"📜 {programme}\n📣 {slogan}", inline=False)

        await interaction.channel.send(embed=embed_partis)

        view = self.VoteView(parent=self, timeout=duree)
        view.add_candidate_buttons()
        message = await interaction.channel.send("🗳️ **Élection ouverte !** Votez pour un parti :", view=view)
        view.message = message
        await interaction.response.send_message("✅ Élection lancée.", ephemeral=True)

    @app_commands.command(name="reset", description="Réinitialise les candidats et les votes")
    async def reset(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Tu dois être administrateur pour utiliser cette commande.", ephemeral=True)
            return

        conn = sqlite3.connect('election.db')
        c = conn.cursor()
        c.execute('DELETE FROM candidats')
        c.execute('DELETE FROM votes')
        conn.commit()
        conn.close()

        await interaction.response.send_message("♻️ Élection réinitialisée. Tous les candidats et votes ont été supprimés.", ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Election(bot))
