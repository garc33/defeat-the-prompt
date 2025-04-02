# Architecture du Jeu de Devinette

## Vue d'ensemble
Ce document décrit l'architecture d'un jeu de type "Qui est-ce?" où les joueurs interagissent avec une IA pour deviner un mot caché.

## Architecture Globale

```mermaid
graph TD
    A[Frontend - HTML/JS] <--> B[Backend - Python/aiohttp]
    B <--> C[Ollama LLM]
    B --> D[(Fichier CSV)]
    
    subgraph Frontend
    A1[Page d'Accueil] --> A2[Page de Jeu]
    A2 --> A3[Popup Victoire]
    end
    
    subgraph Backend
    B1[Serveur SSE] --> B2[Gestion LLM]
    B2 --> B3[Gestion Sessions]
    B3 --> B4[Stockage Données]
    end
```

## Structure du Projet
```
defeat-the-prompt/
├── backend/
│   ├── main.py           # Application principale (routes, gestion du jeu, LLM)
│   └── templates/        # Templates (si nécessaire)
├── frontend/
│   ├── index.html        # Page d'accueil
│   ├── game.html         # Page de jeu avec logique JavaScript intégrée
│   └── css/
│       └── styles.css    # Styles de l'application
└── data/
    └── resultats.csv    # Stockage des résultats de jeu
```

## Flux de Données

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant F as Frontend
    participant B as Backend
    participant L as LLM
    participant CSV as Fichier CSV

    U->>F: Saisie informations
    F->>B: POST /start
    B->>CSV: Enregistre joueur
    B->>F: Session créée
    
    U->>F: Pose question
    F->>B: SSE /chat
    B->>L: Prompt + Question
    L->>B: Réponse
    B->>F: Stream réponse
    
    U->>F: Propose solution
    F->>B: POST /verify
    B->>F: Confirmation victoire
    B->>CSV: Enregistre résultat
```

## Spécifications Techniques

### Backend (Python/aiohttp)
- **Routes principales** :
  - GET `/` : Page d'accueil
  - GET `/game` : Page de jeu
  - POST `/start` : Démarrage partie
  - GET `/stream` : Configuration SSE
  - POST `/stream` : Envoi des messages au LLM
  - POST `/verify` : Vérification réponse
  - GET `/static/*` : Fichiers statiques

### Système LLM
- **Modèle** : Configurable via Ollama (par défaut: llama3.2:3b)
- **Configuration** : Le modèle peut être spécifié au démarrage via l'argument `--model`
- **Prompt System** :
```
Tu est une IA qui joue à un jeu de devinette.
Le joueur doit deviner un mot en posant des questions.
Le mot à deviner est '{mot_caché}'.

Historique de la conversation:
<historique>
{historique_questions_reponses}
</historique>

Le joueur dit:
<message>
{question}
</message>

<instructions>
Si c'est une question fermée, réponds par oui ou non.
Si c'est une question ouverte, réponds par une phrase.
Ne donne JAMAIS une description complète du mot.
NE DONNE JAMAIS LE MOT EN ENTIER.
</instructions>

Base ta réponse en tenant compte de l'historique des questions précédentes.
```

### Stockage des Données (resultats.csv)
Format CSV :
```csv
date,nom,prenom,email,mot_cache,resultat,temps_partie
```

États possibles du résultat :
- 'en_cours' : Partie en cours
- 'victoire' : Mot trouvé (TODO: à implémenter)
- 'abandon' : Partie abandonnée (TODO: à implémenter)

### Sécurité
- Validation des entrées utilisateur
- Protection CSRF
- Sanitization des données

### Démarrage Application
```bash
python backend/main.py --word "mot_secret" --output "data/resultats.csv" [--model "nom_du_modele"]
```

### Fonctionnalités à Implémenter
1. Mise à jour du CSV avec le résultat de la partie (victoire/abandon)
2. Calcul et enregistrement du temps de partie
3. Route POST `/end` pour l'abandon de partie