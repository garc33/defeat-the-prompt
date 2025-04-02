# Projet Web Game

Ce projet est une application web de jeu composée d'une interface utilisateur frontend et d'un backend Python.

## Structure du Projet

- `frontend/` : Contient les fichiers de l'interface utilisateur
  - `index.html` : Page d'accueil
  - `game.html` : Interface du jeu
  - `css/` : Styles CSS
  - `js/` : Scripts JavaScript

- `backend/` : Serveur Python
  - `main.py` : Point d'entrée du serveur
  - `templates/` : Templates pour le rendu côté serveur

- `data/` : Stockage des données
  - `game_results.csv` : Résultats des parties

- `docs/` : Documentation
  - `architecture.md` : Documentation de l'architecture

## Installation

1. Installer les dépendances Python :
```bash
pip install -r requirements.txt
```

2. Lancer le serveur backend :
```bash
python backend/main.py
```

3. Ouvrir `frontend/index.html` dans un navigateur web pour accéder à l'application.