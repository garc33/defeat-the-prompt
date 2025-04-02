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
    def __init__(self, hidden_word: str, output_file: str):
        self.conversation_history = []
        logger.info("Initialisation du modèle llama3.2:3b...")
        try:
            ollama.pull('llama3.2:3b')
            logger.info("Modèle llama3.2:3b téléchargé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement du modèle: {e}")
            raise
            
        self.hidden_word = hidden_word.lower()
        self.output_file = Path(output_file)
        self.app = web.Application()
        self.setup_routes()
        
        # Vérifier/créer le fichier CSV s'il n'existe pas
        if not self.output_file.exists():
            with open(self.output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'nom', 'prenom', 'email', 'mot_cache', 'resultat', 'temps_partie'])

    def setup_routes(self):
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/game', self.handle_game)
        self.app.router.add_post('/start', self.handle_start)
        self.app.router.add_get('/stream', self.handle_stream)
        self.app.router.add_post('/stream', self.handle_stream)
        self.app.router.add_post('/verify', self.handle_verify)
        self.app.router.add_static('/static', Path('frontend'))

    async def handle_index(self, request):
        return web.FileResponse('frontend/index.html')

    async def handle_game(self, request):
        return web.FileResponse('frontend/game.html')
    async def handle_start(self, request):
        try:
            data = await request.json()
            # Valider les données
            required_fields = ['nom', 'prenom', 'email']
            if not all(field in data for field in required_fields):
                raise web.HTTPBadRequest(text='Informations manquantes')

            # Réinitialiser l'historique des conversations
            self.conversation_history = []

            # Sauvegarder les informations du joueur
            now = datetime.now().isoformat()
            with open(self.output_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([now, data['nom'], data['prenom'], data['email'],
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
                
                # Construire l'historique formaté pour le prompt
                history_text = "\n".join([
                    f"{'Joueur' if msg['role'] == 'user' else 'IA'}: {msg['content']}"
                    for msg in self.conversation_history[:-1]  # Exclure la dernière question
                ])
                
                # Appeler Ollama avec la question et l'historique
                prompt = f"""Tu est une IA qui joue à un jeu de devinette.
                           Le joueur doit deviner un mot en posant des questions.
                           Le mot à deviner est '{self.hidden_word}'.
                           
                           Historique de la conversation:
                           <historique>
                           {history_text}
                           </historique>
                           
                           Le joueur dit: 
                           <message>
                           {question}
                           </message>

                           <instructions>
                           Si c'est une question fermée, réponds par oui ou non.
                           Si c'est une question ouverte, réponds par une phrase
                           Ne donne JAMAIS une description complète du mot.
                           NE DONNE JAMAIS LE MOT EN ENTIER.
                           </instructions>

                           Base ta réponse en tenant compte de l'historique des questions précédentes."""

                logger.info(f"Envoi du prompt à Ollama: {prompt}")
                
                full_response = ""
                try:
                    response = ollama.generate(model='llama3.2:3b', prompt=prompt)
                    full_response = response['response']
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
                # Mettre à jour le CSV avec le résultat
                # TODO: Implémenter la mise à jour du CSV
                return web.Response(text=json.dumps({'correct': True}),
                                 content_type='application/json')
            else:
                return web.Response(text=json.dumps({'correct': False}),
                                 content_type='application/json')

        except json.JSONDecodeError:
            raise web.HTTPBadRequest(text='Format JSON invalide')

def main():
    parser = argparse.ArgumentParser(description='Serveur de jeu de devinette')
    parser.add_argument('--word', required=True, help='Le mot à deviner')
    parser.add_argument('--output', required=True, help='Fichier CSV pour les résultats')
    args = parser.parse_args()

    game_server = GameServer(args.word, args.output)
    web.run_app(game_server.app, host='localhost', port=8080)

if __name__ == '__main__':
    main()