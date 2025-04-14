# Protection Simple de la Page de Distribution

## Vue d'ensemble
Implémentation d'une protection par mot de passe simple pour la page de distribution des cadeaux, avec mot de passe configurable au démarrage du serveur.

## Architecture

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant F as Frontend
    participant B as Backend

    U->>F: Accède à /distribution
    F->>F: Vérifie si mot de passe saisi
    alt Pas de mot de passe
        F->>F: Affiche formulaire simple
        U->>F: Saisit mot de passe
        F->>B: POST /distribution/verify
        B->>B: Vérifie mot de passe
        alt Mot de passe correct
            B->>F: OK
            F->>F: Stocke flag accès
            F->>F: Affiche page distribution
        else Mot de passe incorrect
            B->>F: Erreur
            F->>F: Affiche erreur
        end
    else Déjà authentifié
        F->>F: Affiche page distribution
    end
```

## Implémentation

### Backend
- Ajout d'un paramètre `--password` au démarrage du serveur
- Nouvelle route `POST /distribution/verify` qui vérifie le mot de passe

### Frontend
- Formulaire de saisie du mot de passe basique
- Stockage d'un flag `acces_distribution` en localStorage
- Redirection vers le formulaire si pas de flag

## Démarrage du Serveur
```bash
python backend/main.py --word "mot_secret" --output "data/resultats.csv" --password "mot_de_passe_admin"
```

## Étapes d'Implémentation

1. Backend:
   - Ajouter le paramètre password dans l'init de GameServer
   - Créer la route de vérification simple

2. Frontend:
   - Ajouter le formulaire de mot de passe
   - Gérer le stockage du flag d'accès
   - Rediriger si pas authentifié