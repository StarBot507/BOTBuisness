import sqlite3
import datetime
import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests
import re

GUILD_ID = 1161602328714023013  # Remplace par l'ID de ton serveur
UNBELIEVABOAT_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzU4MDEwNTg0MDA3ODM4NDIzIiwiaWF0IjoxNzQzODQ1MzUzfQ.MVyA4OU4bgetYIB-T1aCajjJgEI2YTrcnV7owX38BlU'
banque_id = '1352967560798277712'
BASE_URL = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users"
HEADERS = {
    "Authorization": UNBELIEVABOAT_API_KEY,
    "Content-Type": "application/json"
}

class Banque(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.init_db()
        self.appliquer_frais_auto.start()  # Lancer la tâche dès l'init
    def init_db(self):
        conn = sqlite3.connect('prets.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                montant_emprunte REAL NOT NULL,
                duree INTEGER NOT NULL,
                date_debut TEXT NOT NULL,
                date_fin TEXT NOT NULL,
                taux_interet REAL NOT NULL,
                montant_dus REAL NOT NULL,
                statut TEXT DEFAULT 'en_cours',
                date_remboursement TEXT,
                interets_calcules BOOLEAN DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()

    @app_commands.command(name="pret", description="Faire une demande de prêt")
    @app_commands.describe(montant="Montant souhaité", duree="Durée du prêt (1 à 30 jours)")
    async def pret(self, interaction: discord.Interaction, montant: int, duree: int):
        user_id = str(interaction.user.id)

        if montant <= 0 or not (1 <= duree <= 30):
            await interaction.response.send_message("❌ Montant ou durée invalide.", ephemeral=True)
            return

        conn = sqlite3.connect("prets.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM prets WHERE user_id = ? AND statut = 'en_cours'", (user_id,))
        if cursor.fetchone():
            await interaction.response.send_message("❌ Tu as déjà un prêt en cours.", ephemeral=True)
            conn.close()
            return

        # Détermination du taux
        if 1 <= duree <= 7:
            taux_interet = 0.03
        elif 8 <= duree <= 14:
            taux_interet = 0.05
        else:
            taux_interet = 0.07

        if montant < 5000:
            taux_majoration = 0.00
        elif 5000 <= montant <= 10000:
            taux_majoration = 0.01
        elif 10000 < montant <= 20000:
            taux_majoration = 0.02
        else:
            taux_majoration = 0.03

        taux_total = taux_interet + taux_majoration
        interets = int(montant * taux_total * duree / 30)
        montant_dus = montant + interets

        url = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}"
        headers = {
            "Authorization": UNBELIEVABOAT_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        r = requests.patch(url, headers=headers, json={"cash": montant, "bank": 0})

        if r.status_code != 200:
            await interaction.response.send_message("❌ Erreur avec UnbelievaBoat (voir console).", ephemeral=True)
            conn.close()
            return

        # Retirer le montant de la banque
        url_banque = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{banque_id}"
        requests.patch(url_banque, headers=headers, json={"cash": -montant, "bank": 0})

        date_debut = datetime.datetime.utcnow()
        date_fin = date_debut + datetime.timedelta(days=duree)

        cursor.execute("""
            INSERT INTO prets (
                user_id, montant_emprunte, duree, date_debut, date_fin,
                taux_interet, montant_dus, statut, interets_calcules
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'en_cours', 1)
        """, (
            user_id, montant, duree,
            date_debut.strftime('%Y-%m-%d %H:%M:%S'),
            date_fin.strftime('%Y-%m-%d %H:%M:%S'),
            taux_total, montant_dus
        ))

        conn.commit()
        conn.close()

        await interaction.response.send_message(
            f"✅ Prêt accepté : {montant}€ déposés en banque.\n"
            f"📆 Durée : {duree} jours\n"
            f"💰 Total à rembourser : {montant_dus}€ (taux : {taux_total * 100:.2f}%)",
            ephemeral=True
        )



    @app_commands.command(name="rembourser", description="Rembourser un prêt")
    @app_commands.describe(montant="Montant à rembourser")
    async def rembourser(self, interaction: discord.Interaction, montant: float):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        montant = int(montant)

        conn = sqlite3.connect("prets.db")
        cursor = conn.cursor()

        cursor.execute("SELECT montant_emprunte, montant_dus FROM prets WHERE user_id = ? AND statut = 'en_cours'", (user_id,))
        pret = cursor.fetchone()

        if pret is None:
            await interaction.followup.send("❌ Tu n'as aucun prêt en cours.", ephemeral=True)
            conn.close()
            return

        montant_emprunte, montant_dus = map(int, pret)

        if montant < 1 or montant > montant_dus:
            await interaction.followup.send("❌ Le montant entré est invalide (hors bornes).", ephemeral=True)
            conn.close()
            return

        headers = {
            "Authorization": UNBELIEVABOAT_API_KEY,
            "Accept": "application/json"
        }
        url_user = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{user_id}"
        r_user = requests.get(url_user, headers=headers)

        if r_user.status_code != 200:
            await interaction.followup.send("❌ Impossible de vérifier ton solde.", ephemeral=True)
            conn.close()
            return

        solde_cash = r_user.json().get("cash", 0)

        if solde_cash < montant:
            await interaction.followup.send("❌ Tu n'as pas assez d'argent pour rembourser ce montant.", ephemeral=True)
            conn.close()
            return

        patch_user = requests.patch(url_user, headers={
            "Authorization": UNBELIEVABOAT_API_KEY,
            "Content-Type": "application/json"
        }, json={"cash": -montant, "bank": 0})

        if patch_user.status_code != 200:
            await interaction.followup.send("❌ Erreur lors du retrait du montant.", ephemeral=True)
            conn.close()
            return

        url_banque = f"https://unbelievaboat.com/api/v1/guilds/{GUILD_ID}/users/{banque_id}"
        patch_banque = requests.patch(url_banque, headers={
            "Authorization": UNBELIEVABOAT_API_KEY,
            "Content-Type": "application/json"
        }, json={"cash": montant, "bank": 0})

        if patch_banque.status_code != 200:
            await interaction.followup.send("❌ Erreur lors du versement à la banque.", ephemeral=True)
            conn.close()
            return

        montant_restant = montant_dus - montant
        if montant_restant <= 0:
            cursor.execute("UPDATE prets SET statut = 'remboursé' WHERE user_id = ? AND statut = 'en_cours'", (user_id,))
        else:
            cursor.execute("UPDATE prets SET montant_dus = ? WHERE user_id = ? AND statut = 'en_cours'", (montant_restant, user_id))

        conn.commit()
        conn.close()

        await interaction.followup.send(
            f"✅ Tu as remboursé {montant}€. Montant restant : {montant_restant}€.",
            ephemeral=True
        )

    @app_commands.command(name="suiviprets", description="Voir tous les prêts en cours et remboursés")
    async def suiviprets(self, interaction: discord.Interaction):
        role_autorisé = "Directeur de Banque"
        if not any(role.name == role_autorisé for role in interaction.user.roles):
            await interaction.response.send_message("❌ Tu n'as pas l'autorisation pour cette commande.", ephemeral=True)
            return

        conn = sqlite3.connect("prets.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, montant_emprunte, montant_dus, statut FROM prets")
        prets = cursor.fetchall()
        conn.close()

        if not prets:
            await interaction.response.send_message("📭 Aucun prêt enregistré.", ephemeral=True)
            return

        prets_en_cours = [p for p in prets if p[3] == "en_cours"]
        prets_rembourses = [p for p in prets if p[3] == "remboursé"]

        embed = discord.Embed(title="📊 Suivi des prêts", color=discord.Color.blue())

        if prets_en_cours:
            en_cours_text = "\n".join(f"• <@{uid}> : 💸 {emprunt}€ | 💰 Reste : {dus}€" for uid, emprunt, dus, _ in prets_en_cours)
            embed.add_field(name="🟢 Prêts en cours", value=en_cours_text, inline=False)
        else:
            embed.add_field(name="🟢 Prêts en cours", value="Aucun prêt en cours.", inline=False)

        if prets_rembourses:
            remb_text = "\n".join(f"• <@{uid}> : 💸 {emprunt}€" for uid, emprunt, _, _ in prets_rembourses)
            embed.add_field(name="✅ Prêts remboursés", value=remb_text, inline=False)
        else:
            embed.add_field(name="✅ Prêts remboursés", value="Aucun prêt remboursé.", inline=False)

        embed.set_footer(text="Système bancaire UnbelievaBoat ⚙️")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="testamende", description="Test : envoie un faux message d'amende")
    @app_commands.describe(montant="Montant de l'amende (ex: 22707)")
    async def testamende(self, interaction: discord.Interaction, montant: int):
        montant_formate = "{:,}".format(montant)
        message_test = f"You were caught attempting to rob fuze34081, and have been fined {montant_formate}."
        await interaction.response.send_message(message_test, ephemeral=True)

    def calcul_frais(self, excedent):
        if excedent < 10000:
            return round(excedent * 0.01)
        elif excedent < 20000:
            return round(excedent * 0.02)
        else:
            return round(excedent * 0.03)

    def appliquer_frais(self):
        response = requests.get(BASE_URL, headers=HEADERS)
        if response.status_code != 200:
            print("❌ Erreur API :", response.text)
            return "Erreur de récupération."

        users = response.json()
        logs = []
        limite_banque = 75000

        for user in users:
            user_id = user["user_id"]
            bank = user["bank"]

            if bank > limite_banque:
                excedent = bank - limite_banque
                frais = self.calcul_frais(excedent)

                payload = {
                    "bank": -frais,
                    "reason": f"Frais du au montant de la banque superieur a 75 000"
                }

                r = requests.patch(f"{BASE_URL}/{user_id}", headers=HEADERS, json=payload)

                if r.status_code == 200:
                    nouveau_bank = bank - frais
                    logs.append(f"✅ {user_id} : {bank} → {nouveau_bank} (frais appliqués : -{frais})")
                else:
                    logs.append(f"❌ Erreur pour {user_id} : {r.status_code} | {r.text}")

        return "\n".join(logs) if logs else "Aucun frais appliqué."

    @app_commands.command(name="frais", description="Applique les frais sur les comptes avec excédent.")
    async def frais(self, interaction: discord.Interaction):
        print("🚀 Application des frais manuellement...")
        result = self.appliquer_frais()
        await interaction.response.send_message(f"**Résultat des frais appliqués :**\n{result}", ephemeral=True)

    @tasks.loop(hours=12)
    async def appliquer_frais_auto(self):
        print("⏳ Application des frais de banque automatique...")
        result = self.appliquer_frais()
        print(result)

    @appliquer_frais_auto.before_loop
    async def before_frais(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.author.bot:
            return

        match = re.search(r"fined ([\d,]+)", message.content)
        if match:
            montant_str = match.group(1)
            montant_net = int(montant_str.replace(",", ""))

            url = f"{BASE_URL}/{banque_id}"
            payload = {"cash": montant_net}
            response = requests.patch(url, headers=HEADERS, json=payload)

            if response.status_code == 200:
                print(f"💰 {montant_net}€ d’amende récupérés pour la banque.")
            else:
                print(f"❌ Erreur PATCH banque : {response.status_code} | {response.text}")




async def setup(bot: commands.Bot):
    await bot.add_cog(Banque(bot))
