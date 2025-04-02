#!/usr/bin/env python3
import argparse
import aiohttp
from aiohttp import web
import aiohttp_sse
import json
import csv
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameServer:
    def __init__(self, hidden_word: str, output_file: str):
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
        async with aiohttp_sse.sse_response(request) as resp:
            try:
                data = await request.json()
                question = data.get('question', '')
                
                # Appeler Ollama avec la question
                async with aiohttp.ClientSession() as session:
                    async with session.post('http://localhost:11434/api/generate', 
                                          json={
                                              "model": "llama2:3b",
                                              "prompt": f"""Tu est une IA qui joue à un jeu de devinette.
                                                         Le mot à deviner est '{self.hidden_word}'.
                                                         Le joueur pose cette question: {question}
                                                         Si c'est une question fermée, réponds par oui ou non.
                                                         Si c'est une question ouverte, réponds par une phrase
                                                         mais ne donne jamais une description complète du mot.
                                                         NE DONNE JAMAIS LE MOT EN ENTIER.""",
                                              "stream": True
                                          }) as ollama_resp:
                        async for line in ollama_resp.content:
                            if line:
                                try:
                                    response = json.loads(line)
                                    await resp.send(response['response'])
                                except json.JSONDecodeError:
                                    continue
                
                return resp

            except Exception as e:
                logger.error(f"Erreur lors du streaming: {e}")
                raise web.HTTPInternalServerError(text=str(e))

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