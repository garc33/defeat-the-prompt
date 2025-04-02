# Modification de l'Interface de Jeu

## Contexte
Actuellement, l'interface de jeu contient deux zones d'input séparées :
1. Un input pour poser des questions avec un bouton "Envoyer"
2. Un input pour proposer une réponse avec un bouton "Deviner"

## Objectif
Fusionner les deux zones en une seule avec :
- Un seul champ input partagé
- Les deux boutons (Envoyer et Deviner) côte à côte

## Modifications Techniques

### HTML
Remplacer les sections actuelles :
```html
<div class="input-container">
    <input type="text" id="messageInput" placeholder="Tapez votre question..." />
    <button id="btnEnvoyer" class="btn-send">Envoyer</button>
</div>

<div class="guess-container">
    <input type="text" id="guessInput" placeholder="Je pense que le mot est..." />
    <button id="btnDeviner" class="btn-guess">Deviner</button>
</div>
```

Par :
```html
<div class="unified-input-container">
    <input type="text" id="sharedInput" placeholder="Tapez votre message..." />
    <div class="buttons-container">
        <button id="btnEnvoyer" class="btn-send">Envoyer</button>
        <button id="btnDeviner" class="btn-guess">Deviner</button>
    </div>
</div>
```

### CSS
Ajouter les styles suivants :
```css
.unified-input-container {
    padding: 1rem;
    background: #f1f1f1;
    border-top: 1px solid #ddd;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.buttons-container {
    display: flex;
    gap: 1rem;
}

/* Responsive */
@media (max-width: 768px) {
    .buttons-container {
        flex-direction: column;
    }
}
```

### JavaScript
Modifier les event listeners pour utiliser le nouvel input partagé :
```javascript
const sharedInput = document.getElementById('sharedInput');

document.getElementById('btnEnvoyer').addEventListener('click', async () => {
    const question = sharedInput.value.trim();
    // ... reste du code existant ...
});

document.getElementById('btnDeviner').addEventListener('click', async () => {
    const guess = sharedInput.value.trim();
    // ... reste du code existant ...
});

sharedInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        const activeButton = e.shiftKey ? 'btnDeviner' : 'btnEnvoyer';
        document.getElementById(activeButton).click();
    }
});
```

## Comportement
- Un seul champ de saisie pour les deux actions
- Touche Entrée : envoie une question
- Touche Shift + Entrée : propose une réponse
- Interface responsive préservée