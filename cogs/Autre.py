import discord
from discord.ext import commands
import re
import requests
import json
import os
import random

class AutreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.questions = self.charger_questions()

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
    async def simulateur_vol(self, interaction: discord.Interaction, cible_mention: str, initiator_mention: str):
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

        

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
