#!/usr/bin/env python3
import argparse
import aiohttp
from aiohttp import web
import aiohttp_sse
import json
import ollama
import csv
from datetime import datetime
from pathlib import Path
import logging

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
        self.app.router.add_post('/start', self.handle_start)
        self.app.router.add_get('/stream', self.handle_stream)
        self.app.router.add_post('/stream', self.handle_stream)
        self.app.router.add_post('/verify', self.handle_verify)
        self.app.router.add_post('/end', self.handle_end)
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
                              content_type='application/json')

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

                logger.info(f"Envoi de la question à Ollama avec l'historique")
                
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
                                 content_type='application/json')
            else:
                return web.Response(text=json.dumps({'correct': False}),
                                 content_type='application/json')

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
                             content_type='application/json')
                             
        except Exception as e:
            logger.error(f"Erreur lors de l'abandon: {e}")
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