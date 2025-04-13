# Modification de l'API Ollama : Passage à l'API Chat

## Contexte
Actuellement, l'application utilise l'API `generate` d'Ollama qui nécessite de formater manuellement l'historique des conversations dans le prompt. Le passage à l'API `chat` permettra une meilleure gestion de l'historique et une implémentation plus propre.

## Changements Techniques

### 1. Modification du stockage de l'historique
La structure actuelle `self.conversation_history` est déjà compatible avec l'API chat car elle utilise le format :
```python
[
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
]
```

### 2. Adaptation de l'appel Ollama
#### Avant
```python
response = ollama.generate(model=self.model_name, prompt=prompt)
```

#### Après
```python
messages = [
    {"role": "system", "content": self.system_prompt},
    *self.conversation_history
]
response = await ollama.chat(
    model=self.model_name,
    messages=messages
)
```

### 3. Ajustement du prompt system
#### Avant
Le prompt système est reconstruit à chaque requête avec l'historique formaté.

#### Après
Le prompt système sera initialisé une seule fois au démarrage de la partie :
```python
self.system_prompt = f"""Tu est une IA qui joue à un jeu de devinette.
Le joueur doit deviner un mot en posant des questions.
Le mot à deviner est '{self.hidden_word}'.

Instructions:
- Si c'est une question fermée, réponds par oui ou non
- Si c'est une question ouverte, réponds par une phrase
- Ne donne JAMAIS une description complète du mot
- NE DONNE JAMAIS LE MOT EN ENTIER
- Base ta réponse en tenant compte de l'historique des questions précédentes"""
```

## Avantages
1. Gestion native de l'historique par Ollama
2. Code plus propre et plus maintainable
3. Meilleure cohérence dans les réponses
4. Réduction de la complexité du code

## Étapes d'implémentation
1. Ajouter `system_prompt` dans `__init__`
2. Supprimer la construction manuelle du prompt dans `handle_stream`
3. Remplacer `generate` par `chat`
4. Adapter la gestion de la réponse
5. Mettre à jour les tests si nécessaire

## Note de compatibilité
Cette modification nécessite Ollama v0.1.17 ou supérieur qui prend en charge l'API chat.