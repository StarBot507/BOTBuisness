import discord
from discord.ext import commands
import re
import requests
import json
import os
import random
import time
import asyncio

class AutreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.questions = self.charger_questions()
        self.cooldowns = {}
        self.cooldowns2 = {}

    def extract_id_from_mention(self, mention: str) -> str:
        match = re.match(r"<@!?(\d+)>", mention)
        if match:
            return match.group(1)
        return None

    def charger_questions(self):
        chemin_absolu = 'C:/Users/Suel/OneDrive/Documents/Anatole/Cartable/Bot_buisness/Question.json'
        chemin_relatif = 'Question.json'
        questions = None

        if os.path.exists(chemin_absolu):
            try:
                with open(chemin_absolu, 'r', encoding='utf-8') as f:
                    questions = json.load(f)
            except json.JSONDecodeError:
                print("Erreur JSON dans le fichier absolu.")
        elif os.path.exists(chemin_relatif):
            try:
                with open(chemin_relatif, 'r', encoding='utf-8') as f:
                    questions = json.load(f)
            except json.JSONDecodeError:
                print("Erreur JSON dans le fichier relatif.")

        if not questions:
            print("Impossible de charger les questions.")
        return questions

    def get_question(self):
        if not self.questions:
            return None, None, None
        question_data = random.choice(self.questions)
        question = question_data.get("question", "Pas de question trouvée")
        options = question_data.get("options", [])
        correct_answer = question_data.get("réponse", "Aucune réponse trouvée")
        return question, options, correct_answer





    @discord.app_commands.command(name="sim", description="Simule un vol avec probabilité d'échec et gain estimé")
    async def sim_vol(self, interaction: discord.Interaction, cible_mention: str, initiator_mention: str):
        if not discord.utils.get(interaction.user.roles, name="Conseil d'administration"):
            await interaction.followup.send("❌ Cette commande est en phase de test pour une **amélioration** de */simuler_vol*.", ephemeral=True)
            return
            
        cible_id = self.extract_id_from_mention(cible_mention)
        initiator_id = self.extract_id_from_mention(initiator_mention)

        if not cible_id or not initiator_id:
            await interaction.response.send_message("Erreur : mention invalide.")
            return

        headers = {
            "accept": "application/json",
            "Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzU4MDEwNTg0MDA3ODM4NDIzIiwiaWF0IjoxNzQzODQ1MzUzfQ.MVyA4OU4bgetYIB-T1aCajjJgEI2YTrcnV7owX38BlU"  # Remplace par ton token UnbelievaBoat
        }

        url_base = "https://unbelievaboat.com/api/v1/guilds/1161602328714023013/users/"
        response_initiator = requests.get(url_base + initiator_id, headers=headers)

        if response_initiator.status_code != 200:
            await interaction.response.send_message("Erreur API pour l'initiateur.")
            print(response_initiator)
            return

        data_initiator = response_initiator.json()
        ton_cash = data_initiator.get('cash', 0)
        ta_richesse = data_initiator.get('total', 0)

        response_cible = requests.get(url_base + cible_id, headers=headers)

        if response_cible.status_code != 200:
            await interaction.response.send_message("Erreur API pour la cible.")
            return

        data_cible = response_cible.json()
        cash_cible = data_cible['cash']
        X = cash_cible
        Y = ton_cash
        Z = (Y / ta_richesse) * 100 if ta_richesse > 0 else 100

        if Z < 20:
            proba = 20
            msg = "❌ Tu as **20%** de probabilité d'échec."
        elif Z > 80:
            proba = 80
            msg = "❌ Tu as **80%** de probabilité d'échec."
        else:
            proba = round(Z, 2)
            msg = f"🎲 Tu as **{proba}%** de probabilité d'échec."

        gain = round(((100 - proba) * X) / 100, 2)
        perte = round(0.20 * ta_richesse, 2)

        embed = discord.Embed(title="🔐 Simulation de Vol", color=0x3498db)
        embed.add_field(name="", value=f"", inline=False)
        embed.add_field(name="🎯 Cible", value=cible_mention, inline=True)
        embed.add_field(name="💵 Cash de la Cible", value=f"{X:,}💰", inline=True)
        embed.add_field(name="", value=f"", inline=False)
        embed.add_field(name="🧍 Ton cash", value=f"{Y:,}💰", inline=True)
        embed.add_field(name="📊 Ta richesse totale", value=f"{ta_richesse:,}💰", inline=True)
        embed.add_field(name="", value=f"", inline=False)
        embed.add_field(name="🎲 Probabilité d'échec", value=msg, inline=False)
        embed.add_field(name="", value=f"", inline=False)
        embed.add_field(name="💰 Gain estimé", value=f"{gain:,}💰", inline=False)
        embed.add_field(name="", value=f"", inline=False)
        embed.add_field(name="💸 Perte possible", value=f"{perte:,}💰", inline=False)

#        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="simuler_vol", description="Simule un vol avec une probabilité d'échec et un gain estimé")
    async def simulateur_vol(self, interaction: discord.Interaction, cible_mention: str, initiator_mention: str):
        user_id = interaction.user.id
        current_time = time.time()

        # Vérifier si l'utilisateur a déjà exécuté la commande récemment
        if user_id in self.cooldowns2:
            last_used = self.cooldowns2[user_id]
            time_left = 259200 - (current_time - last_used)  # 259200 secondes = 3 Jours
            if time_left > 0:
                # Convertir le temps restant en Jours, Heures, Minutes, Secondes
                days = int(time_left // 86400)
                hours = int((time_left % 86400) // 3600)
                minutes = int((time_left % 3600) // 60)
                seconds = int(time_left % 60)

                # Formater le message
                cooldown_msg = f"⌛ Tu dois attendre encore {days}J {hours}H {minutes}M {seconds}S avant de réutiliser cette commande."

                await interaction.response.send_message(cooldown_msg, ephemeral=True)
                return

        # Si la commande peut être exécutée, la mettre à jour dans le cooldown
        self.cooldowns2[user_id] = current_time

        # Extraire les ID des mentions
        cible_id = self.extract_id_from_mention(cible_mention)
        initiator_id = self.extract_id_from_mention(initiator_mention)

        if not cible_id or not initiator_id:
            await interaction.response.send_message("Erreur : Veuillez utiliser une mention valide pour l'ID.")
            return

        # Requête API pour obtenir les informations de l'initiateur avec son ID
        url_initiator = f"https://unbelievaboat.com/api/v1/guilds/1161602328714023013/users/{initiator_id}"

        headers = {
            "accept": "application/json",
            "Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzU4MDEwNTg0MDA3ODM4NDIzIiwiaWF0IjoxNzQzODQ1MzUzfQ.MVyA4OU4bgetYIB-T1aCajjJgEI2YTrcnV7owX38BlU"  # Remplace par ton token
        }

        # Envoi de la requête pour l'initiateur
        response_initiator = requests.get(url_initiator, headers=headers)

        # Afficher les logs pour comprendre la réponse
    #    print(f"Réponse pour l'initiateur: {response_initiator.status_code}")
     #   print(f"Réponse brute: {response_initiator.text}")

        # Si la réponse est valide
        if response_initiator.status_code == 200:
            data_initiator = response_initiator.json()  # Récupère la réponse au format JSON
    #        print("Réponse JSON de l'initiateur:", data_initiator)  # Affiche la réponse JSON pour vérifier les clés

            # Utilisation de 'total' pour représenter la richesse totale de l'initiateur
            ton_cash = data_initiator.get('cash', 0)  # Utilise .get pour éviter une erreur si la clé n'existe pas
            ta_richesse = data_initiator.get('total', 0)  # Utilise 'total' comme richesse totale

            # Vérifie si les données sont présentes
           # if ton_cash == 0 or ta_richesse == 0:
            #    await interaction.response.send_message(f"Erreur : Impossible de récupérer les informations nécessaires pour l'initiateur. Détails: Cash: {ton_cash}, Total: {ta_richesse}")
             #   return
        else:
            # Si la réponse de l'API ne contient pas un statut 200 (succès)
            await interaction.response.send_message(f"Erreur API pour l'initiateur. Code de statut: {response_initiator.status_code}")
            return

        # Requête API pour obtenir les informations de la cible avec l'ID
        url_cible = f"https://unbelievaboat.com/api/v1/guilds/1161602328714023013/users/{cible_id}"
        response_cible = requests.get(url_cible, headers=headers)

        # Si la réponse est valide
        if response_cible.status_code == 200:
            data_cible = response_cible.json()  # Récupère la réponse au format JSON
            cash_cible = data_cible['cash']  # Récupère le cash de la cible
            cible_nom = data_cible['user_id']  # Récupère l'ID de l'utilisateur pour la cible (à ajuster si tu veux un nom)

            X = cash_cible  # Richesse de la cible
            Y = ton_cash  # Ton cash
            Z = (Y / ta_richesse) * 100  # Probabilité d'échec calculée avec ta richesse

            if Z < 20:
                proba = 20
                msg = "❌ Tu as **20%** de probabilité d'échec."
            elif Z > 80:
                proba = 80
                msg = "❌ Tu as **80%** de probabilité d'échec."
            else:
                proba2 = random.randint(5, 40)
                proba = round(Z, 2)
                msg = f"🎲 Tu as **{2}%** de probabilité d'échec."

            # Calcul du gain estimé
            gain = round(((100 - proba) * X) / 100 - 10000, 2)

            # Calcul de la perte (20% de ton cash)
            perte = round(0.20 * ta_richesse + 20000, 2)  # Calcul basé sur ton cash

            embed = discord.Embed(title="🔐 Simulation de Vol", color=0x3498db)
            embed.add_field(name="", value=f"", inline=False)
            embed.add_field(name="🎯 Cible", value=cible_mention, inline=True)
            embed.add_field(name="💵 Cash de la Cible", value=f"{X:,}💰", inline=True)
            embed.add_field(name="", value=f"", inline=False)
            embed.add_field(name="🧍 Ton cash", value=f"{Y:,}💰", inline=True)
            embed.add_field(name="📊 Ta richesse totale", value=f"{ta_richesse:,}💰", inline=True)
            embed.add_field(name="", value=f"", inline=False)
            embed.add_field(name="🎲 Probabilité d'échec", value=msg, inline=False)
            embed.add_field(name="", value=f"", inline=False)
            embed.add_field(name="💰 Gain estimé", value=f"{gain:,}💰", inline=False)
            embed.add_field(name="", value=f"", inline=False)
            embed.add_field(name="💸 Perte possible", value=f"{perte:,}💰", inline=False)  # Perte de 20% de ton cash

#            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Si l'API ne répond pas correctement pour la cible
            await interaction.response.send_message("Erreur : Impossible de récupérer les données de la cible.")        

    @discord.app_commands.command(name= 'caca', description= 'fair le /caca et tent d\'obtenir de l\'argent.')
    async def ma_commande(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        current_time = time.time()

        # Vérifier si l'utilisateur a déjà exécuté la commande récemment
        if user_id in self.cooldowns:
            last_used = self.cooldowns[user_id]
            time_left = 14400 - (current_time - last_used)  # 14400 secondes = 4 heures
            if time_left > 0:
                # Convertir le temps restant en Jours, Heures, Minutes, Secondes
                days = int(time_left // 86400)
                hours = int((time_left % 86400) // 3600)
                minutes = int((time_left % 3600) // 60)
                seconds = int(time_left % 60)

                # Formater le message
                cooldown_msg = f"⌛ Tu dois attendre encore {days}J {hours}H {minutes}M {seconds}S avant de réutiliser cette commande."

                await interaction.response.send_message(cooldown_msg, ephemeral=True)
                return

        # Si la commande peut être exécutée, la mettre à jour dans le cooldown
        self.cooldowns[user_id] = current_time
        nb_aleatoire = random.randint(1, 100)
        nb_aleatoire2 = random.randint(1, 100)
        if nb_aleatoire == 100:
            await interaction.response.send_message(f"tirage en cour ...")
            await asyncio.sleep(2)  # Pause de 5 secondes
            await interaction.followup.send(f"Tu as obtenue un caca l'Epique tu as donc 1 chance sur 100 d'en obtenir un **l'égendaire**")
            await interaction.followup.send(f"tirage en cour ...")
            await asyncio.sleep(2)  # Pause de 5 secondes
            await interaction.followup.send(f"tirage en cour ...")
            await asyncio.sleep(1)  # Pause de 5 secondes
            if nb_aleatoire2 == 100:
              await interaction.followup.send(f"Tu as obtenue un caca **l'Egendaire** tu as donc gagner 50,000 dans ta poche.")
              await self.caca_gagnant(interaction)

            else:
                await interaction.followup.send(f"Dommage une autre fois peut-être !")  

        else:
            await interaction.response.send_message(f"tirage en cour ...")
            await asyncio.sleep(2)  # Pause de 5 secondes
            await interaction.followup.send(f'Tu es une grosse merde tu as obtenu un caca **COMMUN**')

    async def caca_gagnant(interaction):
        url = f"https://unbelievaboat.com/api/v1/guilds/1161602328714023013/users/{interaction.user.id}"

        payload = { 
            "cash": 50000,
            "reason": "un caca épique" 
        }
        headers = {
           "accept": "application/json",
            "content-type": "application/json",
            "Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzU4MDEwNTg0MDA3ODM4NDIzIiwiaWF0IjoxNzQzODQ1MzUzfQ.MVyA4OU4bgetYIB-T1aCajjJgEI2YTrcnV7owX38BlU"
        }

        response = requests.patch(url, json=payload, headers=headers)

        #print(response.text)


    
    @discord.app_commands.command(name="question", description="Pose une question de culture générale.")
    async def question(self, interaction: discord.Interaction):
        question, options, correct_answer = self.get_question()

        if not question:
            await interaction.response.send_message("Impossible de récupérer une question.")
            return

        message_content = f"**Question**: {question}\n"
        for i, option in enumerate(options, 1):
            message_content += f"{i}. {option}\n"
        
        await interaction.response.send_message(message_content)

        def check(m):
            return m.author == interaction.user and m.content.isdigit() and 1 <= int(m.content) <= len(options)

        try:
            response = await self.bot.wait_for('message', check=check, timeout=30)
            answer = options[int(response.content) - 1]

            if answer == correct_answer:
                await interaction.followup.send(f"✅ Bravo {interaction.user.mention} ! Bonne réponse : **{correct_answer}**.")
            else:
                await interaction.followup.send(f"❌ Mauvaise réponse. La bonne réponse était : **{correct_answer}**.")
        except:
            await interaction.followup.send(f"⏰ Temps écoulé ! La bonne réponse était : **{correct_answer}**.")

async def setup(bot):
    await bot.add_cog(AutreCog(bot))
