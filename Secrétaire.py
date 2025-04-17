import discord
from discord import app_commands, Interaction, ui
from discord.ext import commands
import requests
import re
import asyncio
from collections import Counter
import sqlite3
import os
import random
from discord.ui import Button, View
import time 
import json
# Ton token Discord
TOKEN = os.getenv('BOT_TOKEN')

# === Mini serveur Flask juste pour Render ===
app = Flask('')

@app.route('/')
def home():
    return "Le bot est en ligne !"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

def keep_alive():
    t = Thread(target=run)
    t.start()


# Config du bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


tree = bot.tree
# Connexion à la base de données SQLite (création du fichier si nécessaire)
DATABASE = "data.db"

# Connexion à la base de données
def get_db():
    return sqlite3.connect(DATABASE)

# Fonction pour récupérer les données utilisateur
def get_user_data(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT metier, argent, dernier_travail FROM utilisateurs WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return {
                "metier": row[0],
                "argent": row[1],
                "dernier_travail": row[2]
            }
        return None

# Fonction pour sauvegarder les données utilisateur
def save_user(user_id, metier, argent, dernier_travail):
    with get_db() as conn:
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

# Création de la table dans la base de données
def create_table():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS utilisateurs (
                user_id TEXT PRIMARY KEY,
                metier TEXT,
                argent INTEGER,
                dernier_travail REAL
            )
        """)
        conn.commit()

create_table()

# Définition des métiers et des gains
metiers = {
    "developer": {
        "description": "Développeur, tu codes des applis.",
        "temps_par_tache": 1800,  # secondes d'attente entre chaque tâche
        "gain": 250
    },
    "designer": {
        "description": "Designer, tu crées des visuels.",
        "temps_par_tache": 2700, # de base c 150     # la c 45 min
        "gain": 400  # Récompense pour avoir terminé le jeu
    },
    "Chercheur": {
        "description": "Chercheur, tu résous des énigmes scientifiques complexes.",
        "temps_par_tache": 3600, # 1 heur
        "gain": 500
    },
    "Investisseur": {
        "description": "Investisseur, tu prends des risques pour gagner plus.",
        "temps_par_tache": 1800, # 30 min
        "gain": "variable"
    }
}









# Rôle nécessaire pour choisir le métier "Investisseur"
required_role = "Investisseur"  # Nom du rôle nécessaire

# === Embed des métiers avec Select ===
class MetierSelect(ui.Select):
    def __init__(self, user_roles):
        options = [
            discord.SelectOption(label=metier.capitalize(), description=metiers[metier]["description"], value=metier)
            for metier in metiers
        ]
        
        # Si l'utilisateur n'a pas le rôle "Investisseur", on retire ce métier de la liste
        if required_role not in [role.name for role in user_roles]:
            options = [option for option in options if option.value != "Investisseur"]

        super().__init__(placeholder="Choisis ton métier", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        selected_metier = self.values[0]  # Le métier sélectionné par l'utilisateur
        user_id = str(interaction.user.id)

        # Validation que le métier existe
        if selected_metier not in metiers:
            await interaction.response.send_message(f"❌ Le métier `{selected_metier}` n'existe pas.", ephemeral=True)
            return

        # Enregistrer le métier de l'utilisateur dans la base de données SQLite
        save_user(user_id, selected_metier, 0, time.time())

        # Envoi d'un message de confirmation avec un embed
        embed = discord.Embed(
            title=f"Tu es maintenant **{selected_metier.capitalize()}** !",
            description=metiers[selected_metier]["description"],
            color=discord.Color.green()
        )
        embed.add_field(name="Temps entre chaque tâche", value=f"{metiers[selected_metier]['temps_par_tache']} secondes")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Commande /choisir_metier
@bot.tree.command(name="choisir_metier", description="Choisis un métier parmi les options disponibles")
async def choisir_metier(interaction: Interaction):
    # Vérification des rôles de l'utilisateur
    user_roles = interaction.user.roles
    
    # Filtrage des métiers pour l'embed
    metiers_affichables = metiers.copy()

    # Si l'utilisateur n'a pas le rôle "Investisseur", on retire ce métier de la liste
    if required_role not in [role.name for role in user_roles]:
        metiers_affichables.pop("Investisseur", None)

    # Création de l'embed avec la liste des métiers filtrée
    embed = discord.Embed(
        title="Choisis ton métier",
        description="Sélectionne un métier ci-dessous pour démarrer.",
        color=discord.Color.blue()
    )
    embed.add_field(name="Métiers disponibles", value="\n".join([f"**{metier.capitalize()}** - {metiers_affichables[metier]['description']}" for metier in metiers_affichables]), inline=False)

    # Création du Select (menu déroulant) avec la liste filtrée des métiers
    select = MetierSelect(user_roles)

    # Création de la vue et ajout du Select
    view = ui.View()
    view.add_item(select)

    # Envoi du message avec l'embed et le Select
    await interaction.response.send_message(embed=embed, view=view, ephemeral=False)






import requests

async def attribuer_recompense(interaction, metier):
    try:
        # Vérifier que le métier existe
        if metier not in metiers:
            await interaction.followup.send("❌ Métier inconnu. Impossible d’attribuer la récompense.", ephemeral=True)
            return

        # Récupérer le gain du métier
        gain = metiers[metier]["gain"]

        # Gérer les cas particuliers
        if gain == "variable":
            gain = random.randint(100, 600)  # ou ta logique personnalisée

        # Construire l'URL pour l'API UnbelievaBoat
        url = f"https://unbelievaboat.com/api/v1/guilds/{interaction.guild.id}/users/{interaction.user.id}"

        payload = {
            "cash": gain,
            "reason": f"Récompense pour avoir travaillé comme {metier.capitalize()}"
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzU4MDEwNTg0MDA3ODM4NDIzIiwiaWF0IjoxNzQzODQ1MzUzfQ.MVyA4OU4bgetYIB-T1aCajjJgEI2YTrcnV7owX38BlU"
        }

        # Appel à l'API
        response = requests.patch(url, json=payload, headers=headers)

        if response.status_code == 200:
            await interaction.followup.send(f"💰 Tu as gagné **{gain}$** en tant que **{metier}** !", ephemeral=True)
        else:
            await interaction.followup.send("❌ Une erreur est survenue lors de l'attribution de ta récompense.", ephemeral=True)
            print(f"[ERREUR API] {response.status_code} - {response.text}")

    except Exception as e:
        print(f"[ERREUR] Impossible d'attribuer la récompense : {e}")
        await interaction.followup.send("❌ Une erreur est survenue.", ephemeral=True)


# Fonction appelée uniquement lorsqu'il y a une perte d'argent
async def gestion_perte(interaction, perte):
    try:
        # Annoncer la perte à l'utilisateur
        await interaction.followup.send(f"📉 Tu as perdu **{perte} pièces**. Sois plus prudent la prochaine fois !", ephemeral=True)

        # Construire l'URL pour l'API UnbelievaBoat pour mettre à jour le solde en négatif
        url = f"https://unbelievaboat.com/api/v1/guilds/{interaction.guild.id}/users/{interaction.user.id}"

        # Définir le payload pour retirer l'argent
        payload = {
            "cash": -perte,  # Retirer la somme (donc la mettre en négatif)
            "reason": f"Perte d'argent suite à un investissement dans le jeu."
        }

        # Définir les en-têtes nécessaires pour l'API
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiIxMzU4MDEwNTg0MDA3ODM4NDIzIiwiaWF0IjoxNzQzODQ1MzUzfQ.MVyA4OU4bgetYIB-T1aCajjJgEI2YTrcnV7owX38BlU"
        }

        # Appel à l'API UnbelievaBoat
        response = requests.patch(url, json=payload, headers=headers)

#        if response.status_code == 200:
 #           print(f"💸 {perte} pièces ont été retirées de l'utilisateur {interaction.user.name} sur UnbelievaBoat.")
  #      else:
   #         print(f"[ERREUR API] {response.status_code} - {response.text}")
    #        await interaction.followup.send("❌ Une erreur est survenue lors de la mise à jour de ton solde d'argent.", ephemeral=True)

    except Exception as e:
        print(f"[ERREUR] Impossible de gérer la perte : {e}")
        await interaction.followup.send("❌ Une erreur est survenue lors du traitement de la perte.", ephemeral=True)














# Commande de travail
@bot.tree.command(name="travailler", description="Effectuer une tâche liée à ton métier.")
async def travailler(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_data = get_user_data(user_id)

    if not user_data or not user_data["metier"]:
        await interaction.response.send_message("❌ Tu n'as pas encore choisi de métier.", ephemeral=True)
        return

    metier = user_data["metier"]
    argent = user_data["argent"]
    dernier_travail = user_data["dernier_travail"]
    maintenant = time.time()




    # === MINI-JEU DU DÉVELOPPEUR ===
    if metier == "developer":
        nombre_secret = random.randint(1, 100)
        essais_max = 7

        await interaction.response.send_message(f"💻 Devine un nombre entre 1 et 100 ! Tu as {essais_max} tentatives.", ephemeral=False)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit()

        async def victoire():
            await attribuer_recompense(interaction, "developer")
            save_user(user_id, metier, argent, time.time())

        reussi = False
        for _ in range(essais_max):
            try:
                msg = await bot.wait_for("message", timeout=30.0, check=check)
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
            argent += metiers[metier]["gain"]
            save_user(user_id, metier, argent, time.time())  # Sauvegarde avec le temps actuel
#            await interaction.followup.send(f"💸 Tu gagnes {metiers[metier]['gain']} pièces !", ephemeral=True)
        else:
            await interaction.followup.send("❌ Tu n'as pas réussi cette tâche.", ephemeral=True)


    elif metier == "designer":
        # Récupérer le temps d'attente spécifique au métier
        temps_attente = metiers[metier]["temps_par_tache"]

        # Vérification du cooldown pour le designer
        if dernier_travail and isinstance(dernier_travail, (float, int)):
            delta = maintenant - dernier_travail  # Calcul du temps écoulé depuis le dernier travail
            if delta < temps_attente:
                temps_restant = int(temps_attente - delta)  # Temps restant avant de pouvoir retravailler
                await interaction.response.send_message(
                    f"⏳ Tu dois attendre encore {temps_restant} secondes avant de retravailler.",
                    ephemeral=True
                )
                return  # Retour si le joueur ne peut pas retravailler encore

        # Si l'utilisateur peut jouer, démarrer le jeu
        async def victoire():
            await attribuer_recompense(interaction, "designer")  # Attribue la récompense
            save_user(user_id, metier, argent, time.time())  # Sauvegarde les infos de l'utilisateur

        game_view = MemoryGame(interaction, on_win=victoire)  # Lancer le mini-jeu
        await interaction.response.send_message(
            "🎨 Jeu de mémoire ! Retourne les cartes et trouve les paires.",
            view=game_view
        )







    # Jeu pour le métier Chercheur
    elif metier == "Chercheur":
        async def gagner():
            nonlocal argent
            argent += metiers[metier]["gain"]
            save_user(user_id, metier, argent, time.time())
            await interaction.followup.send(f"💸 Tu gagnes {metiers[metier]['gain']} pièces !", ephemeral=True)

        embed = discord.Embed(
            title="🔬 Mission du Chercheur",
            description="Résous les 5 énigmes scientifiques pour terminer ta mission.",
            color=discord.Color.blue()
        )

        # Ici, tu passes `interaction` et `metier` à la classe ScientistGame
        view = ScientistGame(interaction, metier)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)





    # 💼 Investisseur
    if metier == "Investisseur":
        async def gagner(gain):
            nonlocal argent
            argent += gain
            save_user(user_id, metier, argent, time.time())
#            if gain >= 0:
#                await interaction.followup.send(f"📈 Tu gagnes {gain} pièces !", ephemeral=True)
#            else:
#                await interaction.followup.send(f"📉 Tu perds {-gain} pièces...", ephemeral=True)
        
        embed = discord.Embed(
            title="📊 Opportunité d'investissement",
            description="Fais un choix stratégique parmi les investissements disponibles.",
            color=discord.Color.gold()
        )

        view = InvestorGame(interaction, gagner)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)




save_user



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

                # Vérifie si toutes les paires ont été trouvées
                if len(self.matched) == len(self.cards):
                    await interaction.followup.send(f"🎉 Toutes les paires ont été trouvées !", ephemeral=False)
                    
                    # Appeler la fonction on_win (récompense) si elle est définie
                    if self.on_win:
                        await self.on_win()

        return callback








class ScientistGame(View):
    def __init__(self, interaction: discord.Interaction, metier: str):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.metier = metier
        self.correct_answers = 0
        self.answered = [False] * 5
        self.answers = {}

        # Banque de questions niveau 3e
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

        # Sélection 60% maths, 40% chimie (pour 5 questions)
        total_questions = 5
        math_count = round(total_questions * 0.6)
        chimie_count = total_questions - math_count

        selected_math = random.sample(math_questions, math_count)
        selected_chem = random.sample(chimie_questions, chimie_count)

        self.questions = selected_math + selected_chem
        random.shuffle(self.questions)

        # Création des 5 boutons
        for i in range(total_questions):
            label = f"Énigme {i+1}"
            button = Button(label=label, style=discord.ButtonStyle.secondary, custom_id=f"puzzle_{i}")
            button.callback = self.make_callback(i)
            self.add_item(button)
            self.answers[i] = self.questions[i][1].lower()

    def make_callback(self, idx):
        async def callback(interaction: discord.Interaction):
            # Vérifier que la personne qui clique sur le bouton est l'utilisateur d'origine
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
                        await interaction.followup.send("🎉 Tu as réussi toutes les énigmes ! Tu gagnes ta récompense !", ephemeral=True)
                        await attribuer_recompense(interaction, self.metier)

                else:
                    await interaction.followup.send("❌ Mauvaise réponse. Essaie une autre énigme.", ephemeral=True)

            except asyncio.TimeoutError:
                await interaction.followup.send("⏱️ Temps écoulé pour cette énigme.", ephemeral=True)

        return callback







class InvestorGame(View):
    def __init__(self, interaction: discord.Interaction, gagner_callback):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.gagner_callback = gagner_callback

        # Générer les investissements
        self.investissements = self.generer_investissements()

        # Création des boutons pour chaque investissement
        for idx, (nom, gain) in enumerate(self.investissements):
            bouton = Button(
                label=nom,
                style=discord.ButtonStyle.secondary,
                custom_id=f"invest_{idx}"
            )
            bouton.callback = self.make_callback(gain)
            self.add_item(bouton)

    def generer_investissements(self):
        # Options d'investissements avec des gains et pertes aléatoires
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
            # Désactiver les boutons
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)

            # Appeler la fonction gagnant
            await self.gagner_callback(gain)

            # Gérer perte ou récompense
            if gain < 0:
                await gestion_perte(interaction, -gain)
            else:
                # ✅ Ici on utilise la fonction personnalisée avec le vrai gain
                await attribuer_recompense_personnalisee(interaction, "Investisseur", gain)
        return callback


# Wrapper pour gérer les gains personnalisés de l'investisseur
async def attribuer_recompense_personnalisee(interaction, metier, gain=None):
    if metier == "Investisseur" and gain is not None:
        # Injecte temporairement le gain dynamique dans le dictionnaire
        metiers["Investisseur"]["gain"] = gain
    await attribuer_recompense(interaction, metier)













def extract_id_from_mention(mention: str) -> str:
    """ Extrait l'ID d'une mention Discord """
    match = re.match(r"<@!?(\d+)>", mention)  # Utilise une regex pour extraire l'ID
    if match:
        return match.group(1)  # Retourne l'ID trouvé
    return None  # Si aucun ID n'est trouvé





@bot.tree.command(name="sim", description="Simule un vol avec une probabilité d'échec et un gain estimé")
async def simulateur_vol(interaction: discord.Interaction, cible_mention: str, initiator_mention: str):
    # Extraire les ID des mentions
    cible_id = extract_id_from_mention(cible_mention)
    initiator_id = extract_id_from_mention(initiator_mention)

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
    print(f"Réponse pour l'initiateur: {response_initiator.status_code}")
    print(f"Réponse brute: {response_initiator.text}")

    # Si la réponse est valide
    if response_initiator.status_code == 200:
        data_initiator = response_initiator.json()  # Récupère la réponse au format JSON
        print("Réponse JSON de l'initiateur:", data_initiator)  # Affiche la réponse JSON pour vérifier les clés

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
            proba = round(Z, 2)
            msg = f"🎲 Tu as **{proba}%** de probabilité d'échec."

        # Calcul du gain estimé
        gain = round(((100 - proba) * X) / 100, 2)

        # Calcul de la perte (20% de ton cash)
        perte = round(0.20 * ta_richesse, 2)  # Calcul basé sur ton cash

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

        await interaction.response.send_message(embed=embed)
    else:
        # Si l'API ne répond pas correctement pour la cible
        await interaction.response.send_message("Erreur : Impossible de récupérer les données de la cible.")


#     ELECTION



candidats = {}

@bot.tree.command(name="candidater", description="Devenir candidat à l'élection")
@app_commands.describe(parti="Nom du parti", programme="Ton programme", slogan="Ton slogan (facultatif)")
async def candidater(interaction: Interaction, parti: str, programme: str, slogan: str = None):
    user_id = interaction.user.id
    if user_id in candidats:
        await interaction.response.send_message("❌ Tu es déjà candidat.", ephemeral=True)
        return

    candidats[parti] = {
        "user": interaction.user,
        "programme": programme,
        "slogan": slogan or "Aucun slogan."
    }

    # Création d'un embed pour afficher les informations de la candidature
    embed = discord.Embed(title="📥 Candidature enregistrée !", color=discord.Color.green())
    embed.add_field(name="👤 Candidat", value=interaction.user.mention, inline=True)
    embed.add_field(name="🏛️ Parti", value=parti, inline=True)
    embed.add_field(name="📜 Programme", value=programme, inline=False)
    embed.add_field(name="📣 Slogan", value=slogan or "Aucun slogan.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)





# Stockage global
candidats = {}
votes = {}
user_id = 123456789012345678  # Remplace cette ID par l'ID de l'utilisateur auquel tu veux envoyer le message

class VoteButton(ui.Button):
    def __init__(self, label):
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: Interaction):
        # Vérification si l'utilisateur a déjà voté
        if interaction.user.id in votes:
            await interaction.response.send_message("⚠️ Tu as déjà voté !", ephemeral=True)
            return

        # Enregistrement du vote
        votes[interaction.user.id] = self.label
        print(interaction.user.mention, 'a voté pour', self.label)

        # Envoi du message de confirmation à l'utilisateur
        await interaction.response.send_message("✅ Ton vote a bien été enregistré !", ephemeral=True)

        # Envoi du message privé à l'administrateur ou à un utilisateur spécifique
        admin_user_id = 1149382861040926841  # Remplace ceci par l'ID Discord de l'administrateur ou de l'utilisateur
        admin_user = await interaction.client.fetch_user(admin_user_id)

        try:
            # Envoi d'un message privé à l'administrateur pour notifier du vote
            await admin_user.send(f"🔔 Un utilisateur a voté : {interaction.user.mention} a voté pour le parti {self.label}.")
        except discord.Forbidden:
            # Si l'administrateur ne peut pas recevoir de message privé
            await interaction.response.send_message("❌ Impossible d'envoyer un message privé à l'administrateur.", ephemeral=True)


        

class VoteView(ui.View):
    def __init__(self, timeout: int):
        super().__init__(timeout=timeout)
        self.message = None  # Initialiser un attribut pour le message

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(content="⏱️ Le vote est terminé !", view=self)

        # Annonce des gagnants
        await self.annoncer_resultats()

    async def annoncer_resultats(self):
        if not votes:
            await self.message.channel.send("❌ Aucun vote enregistré.")
            return

        compteur = Counter(votes.values())

        # ⛔ Supprimer "Vote blanc" du classement principal s’il existe
        vote_blanc_count = compteur.pop("Vote blanc", 0)

        deux_mieux = compteur.most_common(2)

        embed = discord.Embed(
            title="🏁 Résultats de l'élection 🏁",
            color=discord.Color.green()
        )

        if deux_mieux:
            for i, (parti, count) in enumerate(deux_mieux, 1):
                embed.add_field(
                    name=f"{i}. Parti : {parti}",
                    value=f"Nombre de votes : {count}",
                    inline=False
                )
        else:
            embed.description = "❌ Aucun vote valide (hors vote blanc)."

        # ✅ Afficher les votes blancs à part
        if vote_blanc_count > 0:
            embed.add_field(
                name="🗳️ Votes blancs",
                value=f"{vote_blanc_count} vote(s)",
                inline=False
            )

        if self.message:
            await self.message.channel.send(embed=embed)


    def add_candidate_buttons(self):
        for nom_parti in candidats:
            self.add_item(VoteButton(nom_parti))
        self.add_item(VoteButton("Vote blanc"))

# Dans la commande /election
@bot.tree.command(name="election", description="Lance une élection avec durée en secondes.")
@app_commands.describe(duree="Durée du vote en secondes")
async def start_election(interaction: Interaction, duree: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Tu dois être administrateur pour lancer une élection.", ephemeral=True)
        return

    if not candidats:
        await interaction.response.send_message("❌ Aucun candidat inscrit.", ephemeral=True)
        return

    # Création de l'embed pour la présentation des partis
    embed_partis = discord.Embed(title="📊 **Les partis candidats**", color=discord.Color.blue())

    for parti, info in candidats.items():
        embed_partis.add_field(
            name=f"🏛️ {parti}",
            value=f"👤 {info['user'].mention}\n📜 {info['programme']}\n📣 {info['slogan']}",
            inline=False
        )

    # Envoi du message des partis avec l'embed
    await interaction.channel.send(embed=embed_partis)

    # Création de la vue avec les boutons pour voter
    view = VoteView(timeout=duree)
    view.add_candidate_buttons()

    # Envoi du message pour voter
    message = await interaction.channel.send("🗳️ **Élection ouverte !** Votez pour un parti :", view=view)
    view.message = message
    await interaction.response.send_message("✅ Élection lancée.", ephemeral=True)


@bot.tree.command(name="reset", description="Réinitialise les candidats et les votes")
async def reset(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Tu dois être administrateur pour utiliser cette commande.", ephemeral=True)
        return

    candidats.clear()
    votes.clear()

    await interaction.response.send_message("♻️ Élection réinitialisée. Tous les candidats et votes ont été supprimés.", ephemeral=False)





















# Charger les questions depuis un fichier JSON
def load_questions():
    with open('Question.json', 'r', encoding='utf-8') as f:
        questions = json.load(f)

questions = load_questions()

# Fonction pour récupérer une question
def get_question():
    question_data = random.choice(questions)
    question = question_data["question"]
    correct_answer = question_data["correct_answer"]
    options = question_data["options"]
    random.shuffle(options)

    return question, options, correct_answer

# Définir la commande slash pour poser une question
@bot.tree.command(name="question", description="Pose une question de culture générale en français.")
async def question(interaction: discord.Interaction):
    question, options, correct_answer = get_question()

    message_content = f"**Question**: {question}\n"
    for i, option in enumerate(options, 1):
        message_content += f"{i}. {option}\n"
    
    await interaction.response.send_message(message_content)
    
    def check(m):
        return m.author == interaction.user and m.content.isdigit() and int(m.content) in range(1, 5)

    try:
        response = await bot.wait_for('message', check=check, timeout=30)
        answer = options[int(response.content) - 1]
        
        if answer == correct_answer:
            await interaction.followup.send(f"Bravo ! {interaction.user.mention}, Tu as trouvé la bonne réponse: {correct_answer}.")
        else:
            await interaction.followup.send(f"Dommage ! La bonne réponse était: {correct_answer}.")
    except:
        await interaction.followup.send(f"Temps écoulé ! La bonne réponse était: {correct_answer}.")























# Lancer le serveur Flask
keep_alive()

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Connecté en tant que {bot.user}")

# Lancer le bot
bot.run(TOKEN)




