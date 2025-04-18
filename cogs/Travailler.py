import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction
import sqlite3
import time
import random
import requests
import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
import time

class Travailler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.DATABASE = "Metier.db"
        self.required_role = "Investisseur"
        


        self.metiers = {
            "developer": {
                "description": "Développeur, tu codes des applis.",
                "temps_par_tache": 1800,
                "gain": 250
            },
            "designer": {
                "description": "Designer, tu crées des visuels.",
                "temps_par_tache": 2700,
                "gain": 400
            },
            "Chercheur": {
                "description": "Chercheur, tu résous des énigmes scientifiques complexes.",
                "temps_par_tache": 3600,
                "gain": 500
            },
            "Investisseur": {
                "description": "Investisseur, tu prends des risques pour gagner plus.",
                "temps_par_tache": 1800,
                "gain": "variable"
            }
        }

        self.create_table()

    def get_db(self):
        return sqlite3.connect(self.DATABASE)

    def create_table(self):
        with self.get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS utilisateurs (
                    user_id TEXT PRIMARY KEY,
                    metier TEXT,
                    argent INTEGER,
                    dernier_travail REAL
                )
            """)
            conn.commit()

    def save_user(self, user_id, metier, argent, dernier_travail):
        with self.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO utilisateurs (user_id, metier, argent, dernier_travail)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                metier=excluded.metier,
                argent=excluded.argent,
                dernier_travail=excluded.dernier_travail
            """, (user_id, metier, argent, dernier_travail))
            conn.commit()

    def get_user_data(self, user_id):
        with self.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metier, argent, dernier_travail FROM utilisateurs WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return {"metier": row[0], "argent": row[1], "dernier_travail": row[2]} if row else None

    class MetierSelect(ui.Select):
        def __init__(self, parent, user_roles):
            self.parent = parent
            options = [
                discord.SelectOption(label=metier.capitalize(), description=parent.metiers[metier]["description"], value=metier)
                for metier in parent.metiers
                if metier != "Investisseur" or parent.required_role in [r.name for r in user_roles]
            ]
            super().__init__(placeholder="Choisis ton métier", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: Interaction):
            metier = self.values[0]
            user_id = str(interaction.user.id)

            if metier not in self.parent.metiers:
                await interaction.response.send_message(f"❌ Le métier `{metier}` n'existe pas.", ephemeral=True)
                return

            self.parent.save_user(user_id, metier, 0, time.time())

            embed = discord.Embed(
                title=f"Tu es maintenant **{metier.capitalize()}** !",
                description=self.parent.metiers[metier]["description"],
                color=discord.Color.green()
            )
            embed.add_field(name="Temps entre chaque tâche", value=f"{self.parent.metiers[metier]['temps_par_tache']} secondes")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="choisir_metier", description="Choisis un métier parmi les options disponibles")
    async def choisir_metier(self, interaction: Interaction):
        user_roles = interaction.user.roles

        metiers_visibles = {
            nom: info for nom, info in self.metiers.items()
            if nom != "Investisseur" or self.required_role in [r.name for r in user_roles]
        }

        embed = discord.Embed(
            title="Choisis ton métier",
            description="Sélectionne un métier ci-dessous pour démarrer.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Métiers disponibles",
            value="\n".join([f"**{m.capitalize()}** - {i['description']}" for m, i in metiers_visibles.items()]),
            inline=False
        )

        view = ui.View()
        view.add_item(self.MetierSelect(self, user_roles))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    async def attribuer_recompense(self, interaction, metier):
        try:
            if metier not in self.metiers:
                await interaction.followup.send("❌ Métier inconnu.", ephemeral=True)
                return

            gain = random.randint(100, 600) if self.metiers[metier]["gain"] == "variable" else self.metiers[metier]["gain"]

            url = f"https://unbelievaboat.com/api/v1/guilds/{interaction.guild.id}/users/{interaction.user.id}"
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzU4MDEwNTg0MDA3ODM4NDIzIiwiaWF0IjoxNzQzODQ1MzUzfQ.MVyA4OU4bgetYIB-T1aCajjJgEI2YTrcnV7owX38BlU"
            }
            payload = {
                "cash": gain,
                "reason": f"Travail en tant que {metier.capitalize()}"
            }

            response = requests.patch(url, json=payload, headers=headers)

            if response.status_code == 200:
                await interaction.followup.send(f"💰 Tu as gagné **{gain}$** comme **{metier}** !", ephemeral=True)
            else:
                await interaction.followup.send("❌ Erreur lors de l’attribution de la récompense.", ephemeral=True)
                print(f"[ERREUR API] {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[ERREUR] {e}")
            await interaction.followup.send("❌ Une erreur est survenue.", ephemeral=True)

    async def gestion_perte(self, interaction, perte):
        try:
            await interaction.followup.send(f"📉 Tu as perdu **{perte} pièces** !", ephemeral=True)

            url = f"https://unbelievaboat.com/api/v1/guilds/{interaction.guild.id}/users/{interaction.user.id}"
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzU4MDEwNTg0MDA3ODM4NDIzIiwiaWF0IjoxNzQzODQ1MzUzfQ.MVyA4OU4bgetYIB-T1aCajjJgEI2YTrcnV7owX38BlU"
            }
            payload = {
                "cash": -perte,
                "reason": "Perte d'argent suite à un investissement."
            }

            requests.patch(url, json=payload, headers=headers)
        except Exception as e:
            print(f"[ERREUR PERTE] {e}")
            await interaction.followup.send("❌ Erreur lors du traitement de la perte.", ephemeral=True)









    # Commande de travail
    @app_commands.command(name="travailler", description="Effectuer une tâche liée à ton métier.")
    async def travailler(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        user_data = self.get_user_data(user_id)

        if not user_data or not user_data["metier"]:
            await interaction.response.send_message("❌ Tu n'as pas encore choisi de métier.", ephemeral=True)
            return

        metier = user_data["metier"]
        argent = user_data["argent"]
        dernier_travail = user_data["dernier_travail"]
        maintenant = time.time()

        # === MINI-JEU DU DÉVELOPPEUR ===
        if metier == "developer":
            temps_attente = self.metiers[metier]["temps_par_tache"]

            if dernier_travail and isinstance(dernier_travail, (float, int)):
                delta = maintenant - dernier_travail
                if delta < temps_attente:
                    temps_restant = int(temps_attente - delta)
                    await interaction.response.send_message(
                        f"⏳ Tu dois attendre encore {temps_restant} secondes avant de retravailler.",
                        ephemeral=True
                    )
                    return

            nombre_secret = random.randint(1, 100)
            essais_max = 7

            await interaction.response.send_message(f"💻 Devine un nombre entre 1 et 100 ! Tu as {essais_max} tentatives.", ephemeral=False)

            def check(m):
                return m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit()

            async def victoire():
                await self.attribuer_recompense(interaction, "developer")
                self.save_user(user_id, metier, argent, time.time())

            reussi = False
            for _ in range(essais_max):
                try:
                    msg = await self.bot.wait_for("message", timeout=30.0, check=check)
                    guess = int(msg.content)

                    if guess == nombre_secret:
                        await interaction.followup.send("🎉 Bravo, tu as trouvé le bon nombre !", ephemeral=False)
                        reussi = True
                        await victoire()
                        break
                    elif guess < nombre_secret:
                        await interaction.followup.send("🔼 C'est plus grand.", ephemeral=True)
                    else:
                        await interaction.followup.send("🔽 C'est plus petit.", ephemeral=True)
                except asyncio.TimeoutError:
                    await interaction.followup.send("⏱️ Temps écoulé !", ephemeral=True)
                    break

            if reussi:
                argent += self.metiers[metier]["gain"]
                self.save_user(user_id, metier, argent, time.time()) 
            else:
                await interaction.followup.send("❌ Tu n'as pas réussi cette tâche.", ephemeral=True)

            self.save_user

        # === MINI-JEU DU DESIGNER ===
        elif metier == "designer":
            temps_attente = self.metiers[metier]["temps_par_tache"]

            if dernier_travail and isinstance(dernier_travail, (float, int)):
                delta = maintenant - dernier_travail
                if delta < temps_attente:
                    temps_restant = int(temps_attente - delta)
                    await interaction.response.send_message(
                        f"⏳ Tu dois attendre encore {temps_restant} secondes avant de retravailler.",
                        ephemeral=True
                    )
                    return

            async def victoire():
                await self.attribuer_recompense(interaction, "designer")
                self.save_user(user_id, metier, argent, time.time())

            game_view = self.MemoryGame(interaction, on_win=victoire)
            await interaction.response.send_message(
                "🎨 Jeu de mémoire ! Retourne les cartes et trouve les paires.",
                view=game_view
            )

        # === MINI-JEU DU CHERCHEUR ===
        elif metier == "Chercheur":
            temps_attente = self.metiers[metier]["temps_par_tache"]

            if dernier_travail and isinstance(dernier_travail, (float, int)):
                delta = maintenant - dernier_travail
                if delta < temps_attente:
                    temps_restant = int(temps_attente - delta)
                    await interaction.response.send_message(
                        f"⏳ Tu dois attendre encore {temps_restant} secondes avant de retravailler.",
                        ephemeral=True
                    )
                    return

            async def gagner():
                nonlocal argent
                argent += self.metiers[metier]["gain"]
                self.save_user(user_id, metier, argent, time.time())
                await self.attribuer_recompense(interaction, "Chercheur")
                await interaction.followup.send(f"💸 Tu gagnes {self.metiers[metier]['gain']} pièces !", ephemeral=True)

            embed = discord.Embed(
                title="🔬 Mission du Chercheur",
                description="Résous les 5 énigmes scientifiques pour terminer ta mission.",
                color=discord.Color.blue()
            )

            view = self.ScientistGame(self, interaction, metier)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

        # === MINI-JEU DE L'INVESTISSEUR ===
        if metier == "Investisseur":
            temps_attente = self.metiers[metier]["temps_par_tache"]

            if dernier_travail and isinstance(dernier_travail, (float, int)):
                delta = maintenant - dernier_travail
                if delta < temps_attente:
                    temps_restant = int(temps_attente - delta)
                    await interaction.response.send_message(
                        f"⏳ Tu dois attendre encore {temps_restant} secondes avant de retravailler.",
                        ephemeral=True
                    )
                    return

            async def gagner(gain):
                nonlocal argent
                argent += gain
                self.save_user(user_id, metier, argent, time.time())

            embed = discord.Embed(
                title="📊 Opportunité d'investissement",
                description="Fais un choix stratégique parmi les investissements disponibles.",
                color=discord.Color.gold()
            )

            view = self.InvestorGame(self, interaction, gagner)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)





    class MemoryGame(View):
        def __init__(self, interaction: discord.Interaction, on_win=None):
            super().__init__(timeout=60)
            self.interaction = interaction
            self.cards = self.create_cards()
            self.flipped = []
            self.matched = []
            self.buttons = []
            self.on_win = on_win  # Fonction à appeler à la victoire

            for i in range(len(self.cards)):
                button = Button(label="❓", style=discord.ButtonStyle.primary, custom_id=f"card_{i}")
                button.callback = self.make_callback(i)
                self.add_item(button)
                self.buttons.append(button)

        def create_cards(self):
            values = ["A", "B", "C", "D", "E"] * 2  # 5 paires
            random.shuffle(values)
            return values

        def make_callback(self, index):
            async def callback(interaction: discord.Interaction):
                if len(self.flipped) >= 2 or index in self.matched or index in self.flipped:
                    await interaction.response.defer()
                    return

                self.flipped.append(index)
                self.buttons[index].label = self.cards[index]
                await interaction.response.edit_message(view=self)

                if len(self.flipped) == 2:
                    await asyncio.sleep(1)
                    i1, i2 = self.flipped
                    if self.cards[i1] == self.cards[i2]:
                        self.buttons[i1].style = discord.ButtonStyle.success
                        self.buttons[i2].style = discord.ButtonStyle.success
                        self.buttons[i1].disabled = True
                        self.buttons[i2].disabled = True
                        self.matched.extend([i1, i2])
                    else:
                        self.buttons[i1].label = "❓"
                        self.buttons[i2].label = "❓"
                    self.flipped.clear()
                    await interaction.edit_original_response(view=self)

                    if len(self.matched) == len(self.cards):
                        await interaction.followup.send("🎉 Toutes les paires ont été trouvées !", ephemeral=False)
                        if self.on_win:
                            await self.on_win()

            return callback



    class ScientistGame(View):
        def __init__(self, cog, interaction: discord.Interaction, metier: str):
            super().__init__(timeout=120)
            self.interaction = interaction
            self.metier = metier
            self.correct_answers = 0
            self.answered = [False] * 5
            self.answers = {}
            self.cog = cog


            

            # Banque de questions
            math_questions = [
                ("Quel est le discriminant de l'équation x² - 4x + 3 ?", "4"),
                ("Combien de solutions réelles pour l'équation x² + 2x + 5 ?", "0"),
                ("Résous : 3(x - 2) = 2x + 4", "10"),
                ("Si f(x) = 2x + 3, que vaut f(4) ?", "11"),
                ("Quelle est la dérivée de f(x) = x² ?", "2x"),
                ("Simplifie : (3x² + 2x - 1) - (x² - x + 4)", "2x²+3x-5")
            ]

            chimie_questions = [
                ("Quel est le symbole chimique du sodium ?", "Na"),
                ("Combien de protons possède un atome de carbone ?", "6"),
                ("Quelle est la formule de l’eau ?", "H2O"),
                ("Quel est le pH d’une solution neutre ?", "7"),
                ("Quel gaz est libéré lors de la respiration cellulaire ?", "CO2")
            ]

            # Sélection aléatoire de 5 questions (60% maths, 40% chimie)
            total_questions = 5
            math_count = round(total_questions * 0.6)
            chimie_count = total_questions - math_count

            selected_math = random.sample(math_questions, math_count)
            selected_chem = random.sample(chimie_questions, chimie_count)

            self.questions = selected_math + selected_chem
            random.shuffle(self.questions)

            # Création des boutons
            for i in range(total_questions):
                label = f"Énigme {i+1}"
                button = Button(label=label, style=discord.ButtonStyle.secondary, custom_id=f"puzzle_{i}")
                button.callback = self.make_callback(i)
                self.add_item(button)
                self.answers[i] = self.questions[i][1].lower()

        def make_callback(self, idx):
            async def callback(interaction: discord.Interaction):
                if interaction.user.id != self.interaction.user.id:
                    await interaction.response.send_message("❌ Ce n'est pas à vous de répondre !", ephemeral=True)
                    return

                if self.answered[idx]:
                    return

                question, _ = self.questions[idx]
                await interaction.response.send_message(f"🔍 **{question}**\nRéponds avec ta réponse :", ephemeral=True)

                def check(m):
                    return m.author == interaction.user and m.channel == interaction.channel

                try:
                    msg = await interaction.client.wait_for("message", timeout=30.0, check=check)
                    user_answer = msg.content.strip().lower()

                    if user_answer == self.answers[idx]:
                        self.children[idx].style = discord.ButtonStyle.success
                        self.answered[idx] = True
                        self.correct_answers += 1
                        self.children[idx].disabled = True

                        await interaction.message.edit(view=self)
                        await interaction.followup.send("✅ Bonne réponse !", ephemeral=True)

                        if self.correct_answers == 5:
                            await interaction.followup.send(
                                "🎉 Tu as réussi toutes les énigmes ! Tu gagnes ta récompense !", ephemeral=True
                            )
                            await self.cog.attribuer_recompense(interaction, self.metier)

                    else:
                        await interaction.followup.send("❌ Mauvaise réponse. Essaie une autre énigme.", ephemeral=True)

                except asyncio.TimeoutError:
                    await interaction.followup.send("⏱️ Temps écoulé pour cette énigme.", ephemeral=True)

            return callback




    class InvestorGame(View):
        def __init__(self, cog, interaction: discord.Interaction, gagner_callback):
            super().__init__(timeout=60)
            self.interaction = interaction
            self.gagner_callback = gagner_callback
            self.cog = cog

            # Générer les investissements
            self.investissements = self.generer_investissements()

            # Créer les boutons
            for idx, (nom, gain) in enumerate(self.investissements):
                bouton = Button(
                    label=nom,
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"invest_{idx}"
                )
                bouton.callback = self.make_callback(gain)
                self.add_item(bouton)

        def generer_investissements(self):
            options = [
                ("Crypto-monnaie", random.randint(-100, 150)),
                ("Immobilier", random.randint(30, 70)),
                ("Start-up", random.randint(-50, 100)),
                ("Actions en bourse", random.randint(-80, 120)),
                ("Or et métaux précieux", random.randint(20, 60)),
                ("NFTs", random.randint(-100, 80)),
                ("Technologie verte", random.randint(-20, 90)),
                ("Pharmaceutique", random.randint(10, 60)),
            ]
            return random.sample(options, 5)

        def make_callback(self, gain):
            async def callback(interaction: discord.Interaction):
                # Désactiver tous les boutons
                for item in self.children:
                    item.disabled = True
                await interaction.response.edit_message(view=self)

                # Appeler la fonction passée (callback) pour gain
                await self.gagner_callback(gain)

                if gain < 0:
                    await self.cog.gestion_perte(interaction, -gain)
                else:
                    await self.cog.attribuer_recompense_personnalisee(interaction, "Investisseur", gain)

            return callback

    # Fonction utilitaire à l'extérieur de la classe
    async def attribuer_recompense_personnalisee(self, interaction, metier, gain=None):
        if metier == "Investisseur" and gain is not None:
            self.metiers["Investisseur"]["gain"] = gain
        await self.attribuer_recompense(interaction, metier)







# === SETUP DU COG ===
async def setup(bot):
    await bot.add_cog(Travailler(bot))
