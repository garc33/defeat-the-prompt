#!/usr/bin/env python3
import argparse
from aiohttp import web
import aiohttp_sse
import json
import ollama
import csv
from datetime import datetime
from pathlib import Path
import logging

# Constants
JSON_CONTENT_TYPE = 'application/json'
DISTRIBUTIONS_FILE = Path('data/distributions.csv')
CADEAUX_FILE = Path('data/cadeaux_recus.csv')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameServer:
    def __init__(self, hidden_word: str, output_file: str, model_name: str):
        self.model_name = model_name
        self.conversation_history = []
        self.start_time = None
        self.current_pseudo = None
        self.system_prompt = f"""Tu es une IA qui joue à un jeu de devinette.
Le joueur doit deviner un mot en posant des questions.
Le mot à deviner est '{hidden_word.lower()}'.

Instructions:
- Si c'est une question fermée, réponds par oui ou non
- Si c'est une question ouverte, réponds par une phrase
- Ne donne JAMAIS une description complète du mot
- NE DONNE JAMAIS LE MOT EN ENTIER
- Base ta réponse en tenant compte de l'historique des questions précédentes"""
        logger.info(f"Initialisation du modèle {self.model_name}...")
        try:
            ollama.pull(self.model_name)
            logger.info(f"Modèle {self.model_name} téléchargé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement du modèle: {e}")
            raise
            
        self.hidden_word = hidden_word.lower()
        self.output_file = Path(output_file)
        self.app = web.Application()
        self.setup_routes()
        
        # Vérifier/créer le fichier CSV s'il n'existe pas
        # Créer le répertoire parent si nécessaire
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Créer le fichier CSV s'il n'existe pas
        if not self.output_file.exists():
            with open(self.output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'pseudo', 'telephone', 'mot_cache', 'resultat', 'temps_partie'])

    def setup_routes(self):
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/game', self.handle_game)
        self.app.router.add_get('/scores', self.handle_scores)
        self.app.router.add_get('/distribution', self.handle_distribution)
        self.app.router.add_post('/start', self.handle_start)
        self.app.router.add_get('/stream', self.handle_stream)
        self.app.router.add_post('/stream', self.handle_stream)
        self.app.router.add_post('/verify', self.handle_verify)
        self.app.router.add_post('/end', self.handle_end)
        self.app.router.add_get('/leaderboard', self.handle_leaderboard)
        self.app.router.add_get('/distribution/last', self.handle_last_distribution)
        self.app.router.add_get('/distribution/winners', self.handle_distribution_winners)
        self.app.router.add_post('/distribution/start', self.handle_distribution_start)
        self.app.router.add_get('/distribution/history', self.handle_distribution_history)
        self.app.router.add_static('/static', Path('frontend'))

    async def _update_game_result(self, pseudo: str, resultat: str) -> None:
        """Met à jour le résultat et le temps de la partie dans le CSV."""
        try:
            temps_partie = int((datetime.now() - self.start_time).total_seconds())
            
            # Lire tout le fichier CSV
            rows = []
            with open(self.output_file, 'r', newline='') as f:
                reader = csv.reader(f)
                header = next(reader)  # Sauvegarder l'en-tête
                rows = list(reader)
            
            # Trouver et mettre à jour la dernière entrée du joueur
            for i in reversed(range(len(rows))):
                logger.info(f"Ligne en cours d'analyse: {rows[i]}")
                if rows[i][1] == pseudo and rows[i][4] == 'en_cours':  # pseudo est dans colonne 1, resultat dans colonne 4
                    logger.info(f"Mise à jour de la ligne pour {pseudo}")
                    rows[i][4] = resultat  # Mettre à jour le résultat (indice 4)
                    rows[i][5] = str(temps_partie)  # Mettre à jour le temps (indice 5)
                    break
            
            # Réécrire le fichier CSV
            with open(self.output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
                
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du résultat: {e}")
            raise

    async def handle_index(self, request):
        return web.FileResponse('frontend/index.html')
    async def handle_scores(self, request):
        """Retourne la page du leaderboard."""
        return web.FileResponse('frontend/leaderboard.html')

    async def handle_distribution(self, request):
        """Retourne la page de distribution des cadeaux."""
        return web.FileResponse('frontend/distribution.html')

    async def handle_game(self, request):
        return web.FileResponse('frontend/game.html')
        
    async def handle_start(self, request):
        try:
            data = await request.json()
            # Valider les données
            if not data.get('pseudo') or not data.get('telephone'):
                raise web.HTTPBadRequest(text='Pseudo et téléphone requis')
            
            # Valider le format du téléphone
            import re
            if not re.fullmatch(r'\+?\d{10,}', data['telephone']):
                raise web.HTTPBadRequest(text='Format de téléphone invalide')

            # Réinitialiser l'historique des conversations et le temps
            self.conversation_history = []
            self.start_time = datetime.now()
            self.current_pseudo = data['pseudo']

            # Sauvegarder les informations du joueur
            now = datetime.now().isoformat()
            with open(self.output_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([now, data['pseudo'], data['telephone'],
                              self.hidden_word, 'en_cours', '0'])

            return web.Response(text=json.dumps({'status': 'success'}),
                              content_type=JSON_CONTENT_TYPE)

        except json.JSONDecodeError:
            raise web.HTTPBadRequest(text='Format JSON invalide')

    async def handle_stream(self, request):
        if request.method == 'GET':
            # Configuration SSE
            return await aiohttp_sse.sse_response(request)
            
        elif request.method == 'POST':
            try:
                data = await request.json()
                question = data.get('question', '')
                
                if not question.strip():
                    return web.Response(
                        text="Veuillez poser une question.",
                        status=400
                    )

                # Ajouter la question à l'historique
                self.conversation_history.append({"role": "user", "content": question})

                logger.info("Envoi de la question à Ollama avec l'historique")
                
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    *self.conversation_history
                ]
                
                try:
                    response = ollama.chat(
                        model=self.model_name,
                        messages=messages
                    )
                    logger.info(f"Structure de la réponse Ollama: {response}")
                    full_response = response.message.content
                    # Ajouter la réponse à l'historique
                    self.conversation_history.append({"role": "assistant", "content": full_response})
                    
                    logger.info(f"Réponse complète d'Ollama: {full_response}")
                    return web.Response(text=full_response)
                
                except ollama.ResponseError as e:
                    logger.error(f"Erreur Ollama: {e}")
                    return web.Response(
                        text="Désolé, je n'ai pas pu générer une réponse. Veuillez réessayer.",
                        status=500
                    )
                except Exception as e:
                    logger.error(f"Erreur inattendue avec Ollama: {e}")
                    return web.Response(
                        text="Une erreur s'est produite lors de la génération de la réponse.",
                        status=500
                    )

            except json.JSONDecodeError:
                logger.error("Erreur de décodage JSON")
                return web.Response(
                    text="Format de question invalide.",
                    status=400
                )
            except Exception as e:
                logger.error(f"Erreur lors du streaming: {e}")
                return web.Response(
                    text="Désolé, une erreur inattendue s'est produite. Veuillez réessayer.",
                    status=500
                )

    async def handle_verify(self, request):
        try:
            data = await request.json()
            guess = data.get('guess', '').lower()
            
            if guess == self.hidden_word:
                # Mettre à jour le CSV avec la victoire
                await self._update_game_result(self.current_pseudo, 'victoire')
                return web.Response(text=json.dumps({'correct': True}),
                                 content_type=JSON_CONTENT_TYPE)
            else:
                return web.Response(text=json.dumps({'correct': False}),
                                 content_type=JSON_CONTENT_TYPE)

        except json.JSONDecodeError:
            raise web.HTTPBadRequest(text='Format JSON invalide')
        except Exception as e:
            logger.error(f"Erreur lors de la vérification: {e}")
            raise web.HTTPInternalServerError(text=str(e))

    async def handle_end(self, request):
        """Gère l'abandon d'une partie."""
        try:
            if not self.current_pseudo:
                raise web.HTTPBadRequest(text='Aucune partie en cours')
                
            await self._update_game_result(self.current_pseudo, 'abandon')
            return web.Response(text=json.dumps({'status': 'success'}),
                              content_type=JSON_CONTENT_TYPE)
                             
        except Exception as e:
            logger.error(f"Erreur lors de l'abandon: {e}")
            raise web.HTTPInternalServerError(text=str(e))

    async def handle_leaderboard(self, request):
        """Retourne les 10 meilleurs scores."""
        try:
            # Lire le fichier CSV
            scores = []
            with open(self.output_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                # Filtrer les parties gagnées et convertir les données
                for row in reader:
                    if row['resultat'] == 'victoire':
                        scores.append({
                            'pseudo': row['pseudo'],
                            'temps': int(row['temps_partie']),
                            'date': row['date']
                        })
            
            # Trier par temps et prendre les 10 meilleurs
            top_scores = sorted(scores, key=lambda x: x['temps'])[:10]
            
            # Ajouter la position
            for i, score in enumerate(top_scores, 1):
                score['position'] = i
            
            return web.Response(
                text=json.dumps({'leaderboard': top_scores}),
                content_type=JSON_CONTENT_TYPE
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du leaderboard: {e}")
            raise web.HTTPInternalServerError(text=str(e))
    async def get_recent_players(self, since_date):
        """Récupère les joueurs qui ont joué depuis une date donnée."""
        recent_players = []
        try:
            with open(self.output_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row_date = datetime.fromisoformat(row['date'])
                    if row_date >= since_date:
                        recent_players.append(row)
            return recent_players
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des joueurs récents: {e}")
            raise

    async def get_last_distribution(self):
        """Récupère la dernière distribution de cadeaux."""
        try:
            if not DISTRIBUTIONS_FILE.exists():
                return None
                
            with open(DISTRIBUTIONS_FILE, 'r', newline='') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                rows = list(reader)
                if not rows:
                    return None
                    
                last_row = rows[-1]
                result = {'date_distribution': last_row[0]}
                # Chaque gagnant a deux colonnes (pseudo et téléphone)
                for i in range(3):
                    idx = 1 + i * 2  # Index de départ pour chaque gagnant
                    if idx + 1 < len(last_row):  # Vérifier qu'on a bien le pseudo et le téléphone
                        result[f'gagnant{i+1}'] = {
                            'pseudo': last_row[idx],
                            'telephone': last_row[idx + 1]
                        }
                return result
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la dernière distribution: {e}")
            raise

    async def save_distribution(self, winners):
        """Enregistre une nouvelle distribution."""
        try:
            now = datetime.now().isoformat()
            
            row = [now]  # Date de distribution
            for winner in winners:
                row.extend([winner['pseudo'], winner['telephone']])  # Ajouter pseudo et téléphone
            
            with open(DISTRIBUTIONS_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)

            # Enregistrer les cadeaux reçus
            with open(CADEAUX_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                for winner in winners:
                    writer.writerow([winner['pseudo'], now])
                    
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de la distribution: {e}")
            raise

    async def select_distribution_winners(self):
        """Sélectionne les gagnants pour la distribution."""
        try:
            # 1. Obtenir la dernière distribution
            last_dist = await self.get_last_distribution()
            last_dist_date = datetime.fromisoformat(last_dist['date_distribution']) if last_dist else datetime.min
            
            # 2. Récupérer les joueurs récents
            recent_players = await self.get_recent_players(last_dist_date)
            
            # 3. Sélectionner les gagnants
            winners_info = []
            
            # D'abord les victoires, triées par temps
            victoires = sorted(
                [p for p in recent_players if p['resultat'] == 'victoire'],
                key=lambda x: int(x['temps_partie'])
            )
            winners_info.extend([{'pseudo': p['pseudo'], 'telephone': p['telephone']} for p in victoires[:3]])
            
            # Si pas assez de gagnants, ajouter des perdants aléatoires
            if len(winners_info) < 3:
                import random
                perdants = [{'pseudo': p['pseudo'], 'telephone': p['telephone']}
                          for p in recent_players
                          if p['pseudo'] not in [w['pseudo'] for w in winners_info]]
                if perdants:
                    winners_info.extend(random.sample(perdants, min(3 - len(winners_info), len(perdants))))
            
            # Si toujours pas assez, prendre des anciens joueurs sans cadeau
            if len(winners_info) < 3:
                # Charger les joueurs qui ont déjà reçu un cadeau
                cadeaux_file = Path('data/cadeaux_recus.csv')
                recus = set()
                if cadeaux_file.exists():
                    with open(cadeaux_file, 'r', newline='') as f:
                        reader = csv.DictReader(f)
                        recus = {row['pseudo'] for row in reader}
                
                # Charger tous les joueurs qui n'ont pas encore reçu de cadeau
                with open(self.output_file, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    anciens = [{'pseudo': row['pseudo'], 'telephone': row['telephone']}
                             for row in reader
                             if row['pseudo'] not in recus and
                                row['pseudo'] not in [w['pseudo'] for w in winners_info]]
                
                if anciens:
                    winners_info.extend(random.sample(anciens, min(3 - len(winners_info), len(anciens))))
            
            return winners_info[:3]  # Assure qu'on ne retourne que 3 gagnants maximum
            
        except Exception as e:
            logger.error(f"Erreur lors de la sélection des gagnants: {e}")
            raise

    async def handle_last_distribution(self, request):
        """Retourne la dernière distribution de cadeaux."""
        try:
            last_dist = await self.get_last_distribution()
            return web.Response(
                text=json.dumps(last_dist if last_dist else {}),
                content_type=JSON_CONTENT_TYPE
            )
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la dernière distribution: {e}")
            raise web.HTTPInternalServerError(text=str(e))

    async def handle_distribution_winners(self, request):
        """Retourne la liste des gagnants de la dernière distribution."""
        try:
            last_dist = await self.get_last_distribution()
            if not last_dist:
                return web.Response(
                    text=json.dumps({'winners': []}),
                    content_type=JSON_CONTENT_TYPE
                )
            
            winners = []
            for i in range(1, 4):
                if f'gagnant{i}' in last_dist and last_dist[f'gagnant{i}']:
                    winners.append(last_dist[f'gagnant{i}'])
            
            return web.Response(
                text=json.dumps({'winners': winners}),
                content_type=JSON_CONTENT_TYPE
            )
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des gagnants: {e}")
            raise web.HTTPInternalServerError(text=str(e))

    async def handle_distribution_start(self, request):
        """Déclenche une nouvelle distribution de cadeaux."""
        try:
            winners = await self.select_distribution_winners()
            if len(winners) < 3:
                raise web.HTTPBadRequest(text="Pas assez de joueurs éligibles pour la distribution")
                
            await self.save_distribution(winners)
            
            return web.Response(
                text=json.dumps({'winners': winners}),
                content_type=JSON_CONTENT_TYPE
            )
        except web.HTTPBadRequest as e:
            raise
        except Exception as e:
            logger.error(f"Erreur lors du démarrage de la distribution: {e}")
            raise web.HTTPInternalServerError(text=str(e))

    async def handle_distribution_history(self, request):
        """Retourne l'historique des distributions avec pagination."""
        try:
            # Récupérer les paramètres de pagination
            page = int(request.query.get('page', '1'))
            per_page = int(request.query.get('per_page', '10'))
            
            # Vérifier la validité des paramètres
            if page < 1 or per_page < 1:
                raise web.HTTPBadRequest(text="Les paramètres de pagination doivent être positifs")
            
            if not DISTRIBUTIONS_FILE.exists():
                return web.Response(
                    text=json.dumps({'distributions': [], 'total': 0, 'page': page, 'per_page': per_page}),
                    content_type=JSON_CONTENT_TYPE
                )
            
            # Lire toutes les distributions
            rows = []
            with open(DISTRIBUTIONS_FILE, 'r', newline='') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                rows = list(reader)
            
            # Trier par date décroissante
            rows.sort(reverse=True)  # Supposant que la date est en première colonne
            
            # Calculer la pagination
            total = len(rows)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_rows = rows[start_idx:end_idx]
            
            # Formater les résultats
            distributions = []
            for row in page_rows:
                dist = {
                    'date_distribution': row[0],
                    'gagnants': []
                }
                # Chaque gagnant a deux colonnes (pseudo et téléphone)
                for i in range(3):
                    idx = 1 + i * 2
                    if idx + 1 < len(row) and row[idx]:  # Vérifier qu'on a le pseudo et le téléphone
                        dist['gagnants'].append({
                            'pseudo': row[idx],
                            'telephone': row[idx + 1]
                        })
                distributions.append(dist)
            
            return web.Response(
                text=json.dumps({
                    'distributions': distributions,
                    'total': total,
                    'page': page,
                    'per_page': per_page
                }),
                content_type=JSON_CONTENT_TYPE
            )
            
        except ValueError as e:
            raise web.HTTPBadRequest(text="Paramètres de pagination invalides")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique: {e}")
            raise web.HTTPInternalServerError(text=str(e))

def main():
    parser = argparse.ArgumentParser(description='Serveur de jeu de devinette')
    parser.add_argument('--word', required=True, help='Le mot à deviner')
    parser.add_argument('--output', required=True, help='Fichier CSV pour les résultats')
    parser.add_argument('--model', default='llama3.2:3b', help='Nom du modèle LLM à utiliser (par défaut: llama3.2:3b)')
    args = parser.parse_args()

    game_server = GameServer(args.word, args.output, args.model)
    web.run_app(game_server.app, host='localhost', port=8080)

if __name__ == '__main__':
    main()