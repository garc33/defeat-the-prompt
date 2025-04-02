# Modification pour la Paramétrisation du Modèle LLM

## Objectif
Permettre de spécifier le modèle LLM à utiliser via un paramètre en ligne de commande, plutôt que d'avoir le modèle "llama3.2:3b" codé en dur dans l'application.

## Modifications Techniques

### 1. Modification du Parser d'Arguments
```python
parser.add_argument('--model', 
                   default='llama3.2:3b',
                   help='Nom du modèle LLM à utiliser (par défaut: llama3.2:3b)')
```

### 2. Modification de la Classe GameServer
```python
def __init__(self, hidden_word: str, output_file: str, model_name: str):
    self.model_name = model_name
    logger.info(f"Initialisation du modèle {self.model_name}...")
    try:
        ollama.pull(self.model_name)
        logger.info(f"Modèle {self.model_name} téléchargé avec succès")
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement du modèle: {e}")
        raise
```

### 3. Mise à Jour de l'Appel à Ollama.generate()
```python
response = ollama.generate(model=self.model_name, prompt=prompt)
```

## Exemple d'Utilisation

### Commande de Base (comportement par défaut)
```bash
python backend/main.py --word "mot_secret" --output "data/resultats.csv"
```

### Commande avec Modèle Personnalisé
```bash
python backend/main.py --word "mot_secret" --output "data/resultats.csv" --model "llama2:13b"
```

## Impact sur l'Architecture
Cette modification n'a pas d'impact majeur sur l'architecture existante. Elle ajoute simplement de la flexibilité en permettant de choisir le modèle LLM au démarrage de l'application.

## Points d'Attention
1. Le modèle spécifié doit être disponible via Ollama
2. Les performances peuvent varier selon le modèle choisi
3. La compatibilité avec le format de prompt existant doit être maintenue

## Prochaines Étapes
1. Implémenter les modifications dans main.py
2. Tester avec différents modèles disponibles
3. Mettre à jour la documentation principale du projet