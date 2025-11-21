// Variables globales
let lignesSelectionnees = new Set();
let menuContextuel = null;
let dernierePositionClick = null;

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    menuContextuel = document.getElementById('contextMenu');
    
    if (!menuContextuel) {
        console.error('Élément contextMenu non trouvé');
        return;
    }
    
    initialiserContextMenu();
    initialiserSelectionLignes();
});

function initialiserContextMenu() {
    const tableau = document.querySelector('.table-fiche');
    
    if (!tableau) {
        console.warn('Tableau .table-fiche non trouvé');
        return;
    }
    
    tableau.addEventListener('contextmenu', function(e) {
        const ligne = e.target.closest('tr');
        if (ligne && !ligne.classList.contains('lot-header') && 
            !ligne.classList.contains('total-general')) {
            
            e.preventDefault();
            dernierePositionClick = { x: e.clientX, y: e.clientY };
            
            // La sélection est gérée uniquement par les clics gauches
            // On ajoute simplement la ligne courante si elle n'est pas déjà sélectionnée
            if (!lignesSelectionnees.has(ligne)) {
                selectionnerLigne(ligne);
            }
            
            // Afficher le menu
            afficherMenuContextuel(e.clientX, e.clientY);
        }
    });
    
    // Cacher le menu en cliquant ailleurs
    document.addEventListener('click', function(e) {
        if (menuContextuel && !menuContextuel.contains(e.target)) {
            cacherMenuContextuel();
        }
    });
    
    // Fermer avec Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            cacherMenuContextuel();
            deselectionnerToutesLignes();
        }
    });
}

function initialiserSelectionLignes() {
    const tableau = document.querySelector('.table-fiche');
    
    if (!tableau) return;
    
    // Clic normal pour sélection/désélection
    tableau.addEventListener('click', function(e) {
        const ligne = e.target.closest('tr');

        // Ne pas gérer la sélection si c'est un clic droit
        if (e.button === 2) return;

        gererClicLigne(e, ligne);
    });
}

function gererClicLigne(e, ligne) {
    if (!ligne || ligne.classList.contains('lot-header') || 
        ligne.classList.contains('total-general')) {
        return;
    }
    
    // Ctrl+clic : ajoute/retire de la sélection
    if (e.ctrlKey || e.metaKey) {
        if (lignesSelectionnees.has(ligne)) {
            deselectionnerLigne(ligne);
        } else {
            selectionnerLigne(ligne);
        }
    }
    // Shift+clic : sélectionne une plage
    else if (e.shiftKey && lignesSelectionnees.size > 0) {
        selectionnerPlage(ligne);
    }
    // Clic normal
    else {
        if (lignesSelectionnees.has(ligne) && lignesSelectionnees.size === 1) {
            deselectionnerToutesLignes();
        } else {
            deselectionnerToutesLignes();
            selectionnerLigne(ligne);
        }
    }
}

function selectionnerPlage(ligneCible) {
    const toutesLignes = Array.from(document.querySelectorAll('.table-fiche tbody tr:not(.lot-header):not(.total-general)'));
    const derniereLigneSelectionnee = Array.from(lignesSelectionnees).pop();
    
    if (!derniereLigneSelectionnee) {
        selectionnerLigne(ligneCible);
        return;
    }
    
    const indexDerniere = toutesLignes.indexOf(derniereLigneSelectionnee);
    const indexCible = toutesLignes.indexOf(ligneCible);
    
    if (indexDerniere === -1 || indexCible === -1) return;
    
    const start = Math.min(indexDerniere, indexCible);
    const end = Math.max(indexDerniere, indexCible);
    
    for (let i = start; i <= end; i++) {
        selectionnerLigne(toutesLignes[i]);
    }
}
function selectionnerLigne(ligne) {
    ligne.classList.add('ligne-selectionnee');
    lignesSelectionnees.add(ligne);
}

function deselectionnerLigne(ligne) {
    ligne.classList.remove('ligne-selectionnee');
    lignesSelectionnees.delete(ligne);
}

function deselectionnerToutesLignes() {
    lignesSelectionnees.forEach(ligne => {
        ligne.classList.remove('ligne-selectionnee');
    });
    lignesSelectionnees.clear();
}

function afficherMenuContextuel(x, y) {
    if (!menuContextuel) return;
    
    menuContextuel.classList.remove('hidden');
    
    // Ajuster la position pour ne pas dépasser de l'écran
    const menuRect = menuContextuel.getBoundingClientRect();
    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;
    
    let finalX = x;
    let finalY = y;
    
    if (x + menuRect.width > windowWidth) {
        finalX = windowWidth - menuRect.width - 10;
    }
    
    if (y + menuRect.height > windowHeight) {
        finalY = windowHeight - menuRect.height - 10;
    }
    
    menuContextuel.style.left = finalX + 'px';
    menuContextuel.style.top = finalY + 'px';
}

function cacherMenuContextuel() {
    if (menuContextuel) {
        menuContextuel.classList.add('hidden');
    }
}

// ACTIONS DU MENU CONTEXTUEL
function masquerLignesSelectionnees() {
    if (lignesSelectionnees.size > 0) {
        lignesSelectionnees.forEach(ligne => {
            ligne.classList.add('ligne-masquee');
        });
        showNotification(`${lignesSelectionnees.size} ligne(s) masquée(s)`, 'success');
        deselectionnerToutesLignes();
    }
    cacherMenuContextuel();
}

function afficherLignesMasquees() {
    if (!dernierePositionClick) return;
    
    // Trouver les lignes masquées proches du click
    const toutesLignes = document.querySelectorAll('.table-fiche tbody tr.ligne-masquee');
    const lignesProches = [];
    
    toutesLignes.forEach(ligne => {
        const rect = ligne.getBoundingClientRect();
        const distance = Math.sqrt(
            Math.pow(rect.top - dernierePositionClick.y, 2) + 
            Math.pow(rect.left - dernierePositionClick.x, 2)
        );
        
        if (distance < 300) { // Rayon de 300px
            lignesProches.push(ligne);
        }
    });
    
    // Afficher les lignes proches
    lignesProches.forEach(ligne => {
        ligne.classList.remove('ligne-masquee');
    });
    
    if (lignesProches.length > 0) {
        showNotification(`${lignesProches.length} ligne(s) masquée(s) affichée(s)`, 'success');
    } else {
        showNotification('Aucune ligne masquée à proximité', 'info');
    }
    
    cacherMenuContextuel();
}

function supprimerLignesSelectionnees() {
    if (lignesSelectionnees.size > 0) {
        if (confirm(`Voulez-vous vraiment supprimer ${lignesSelectionnees.size} ligne(s) ?`)) {
            lignesSelectionnees.forEach(ligne => {
                ligne.remove();
            });
            showNotification(`${lignesSelectionnees.size} ligne(s) supprimée(s)`, 'success');
            deselectionnerToutesLignes();
        }
    }
    cacherMenuContextuel();
}

function copierContenuLigne() {
    if (lignesSelectionnees.size > 0) {
        let contenu = '';
        
        lignesSelectionnees.forEach(ligne => {
            const cells = ligne.querySelectorAll('td');
            const ligneContenu = Array.from(cells).map(cell => cell.textContent.trim()).join('\t');
            contenu += ligneContenu + '\n';
        });
        
        // Copier dans le presse-papier
        navigator.clipboard.writeText(contenu).then(() => {
            showNotification('Contenu copié dans le presse-papier', 'success');
        }).catch(() => {
            // Fallback pour les navigateurs sans clipboard API
            const textarea = document.createElement('textarea');
            textarea.value = contenu;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            showNotification('Contenu copié dans le presse-papier', 'success');
        });
    }
    cacherMenuContextuel();
}

function changerHauteurLigne(type) {
    if (lignesSelectionnees.size > 0) {
        // Supprimer les classes de hauteur existantes
        const classesHauteur = ['hauteur-compact', 'hauteur-large'];
        
        lignesSelectionnees.forEach(ligne => {
            ligne.classList.remove(...classesHauteur);
            
            switch(type) {
                case 'compact':
                    ligne.classList.add('hauteur-compact');
                    break;
                case 'large':
                    ligne.classList.add('hauteur-large');
                    break;
                // 'normale' - on ne fait rien, c'est la hauteur par défaut
            }
        });
        
        const typesNoms = {
            'compact': 'compacte',
            'normale': 'normale', 
            'large': 'large'
        };
        
        showNotification(`Hauteur ${typesNoms[type]} appliquée`, 'success');
    }
    cacherMenuContextuel();
}

// Fonction de notification simple
function showNotification(message, type = 'info') {
    // Créer une notification temporaire
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-4 py-2 rounded-lg z-50 ${
        type === 'success' ? 'bg-green-600' : 
        type === 'error' ? 'bg-red-600' : 'bg-blue-600'
    } text-white font-semibold`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Raccourcis clavier
document.addEventListener('keydown', function(e) {
    if (e.ctrlKey || e.metaKey) {
        switch(e.key) {
            case 'h': // Ctrl+H pour masquer
                e.preventDefault();
                masquerLignesSelectionnees();
                break;
            case 'd': // Ctrl+D pour supprimer
                e.preventDefault();
                supprimerLignesSelectionnees();
                break;
            case 'c': // Ctrl+C pour copier
                if (lignesSelectionnees.size > 0) {
                    e.preventDefault();
                    copierContenuLigne();
                }
                break;
        }
    }
});
