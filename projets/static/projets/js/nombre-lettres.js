// static/projets/js/nombre-lettres.js

function nombreEnLettres(nombre) {
    const unite = ['', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf'];
const dizaine = ['', 'dix', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante', 'soixante', 'quatre-vingt', 'quatre-vingt-dix'];
const exceptions = {
    11: 'onze',
    12: 'douze',
    13: 'treize',
    14: 'quatorze',
    15: 'quinze',
    16: 'seize',
    17: 'dix-sept',
    18: 'dix-huit', 
    19: 'dix-neuf',
    71: 'soixante et onze',
    72: 'soixante-douze',
    73: 'soixante-treize',
    74: 'soixante-quatorze',
    75: 'soixante-quinze',
    76: 'soixante-seize',
    77: 'soixante-dix-sept',
    78: 'soixante-dix-huit',
    79: 'soixante-dix-neuf',
    80: 'quatre-vingts',
    81: 'quatre-vingt-un',
    82: 'quatre-vingt-deux',
    83: 'quatre-vingt-trois',
    84: 'quatre-vingt-quatre',
    85: 'quatre-vingt-cinq',
    86: 'quatre-vingt-six',
    87: 'quatre-vingt-sept',
    88: 'quatre-vingt-huit',
    89: 'quatre-vingt-neuf',
    90: 'quatre-vingt-dix',
    91: 'quatre-vingt-onze',
    92: 'quatre-vingt-douze',
    93: 'quatre-vingt-treize',
    94: 'quatre-vingt-quatorze',
    95: 'quatre-vingt-quinze',
    96: 'quatre-vingt-seize',
    97: 'quatre-vingt-dix-sept',
    98: 'quatre-vingt-dix-huit',
    99: 'quatre-vingt-dix-neuf'
};
    if (nombre === 0) return 'zéro';
    if (nombre < 0) return 'moins ' + nombreEnLettres(Math.abs(nombre));

    let resultat = '';

    // Millions
    if (nombre >= 1000000) {
        const millions = Math.floor(nombre / 1000000);
        resultat += (millions === 1 ? 'un million' : nombreEnLettres(millions) + ' millions');
        nombre %= 1000000;
        if (nombre > 0) resultat += ' ';
    }

    // Milliers
    if (nombre >= 1000) {
        const milliers = Math.floor(nombre / 1000);
        if (milliers === 1) {
            resultat += 'mille';
        } else {
            resultat += nombreEnLettres(milliers) + ' mille';
        }
        nombre %= 1000;
        if (nombre > 0) resultat += ' ';
    }

    // Centaines
    if (nombre >= 100) {
        const centaines = Math.floor(nombre / 100);
        if (centaines === 1) {
            resultat += 'cent';
        } else {
            resultat += unite[centaines] + ' cent';
        }
        nombre %= 100;
        if (nombre > 0) resultat += ' ';
    }

    // Dizaines et unités
    if (nombre > 0) {
        if (exceptions[nombre]) {
            resultat += exceptions[nombre];
        } else {
            const d = Math.floor(nombre / 10);
            const u = nombre % 10;

            if (d === 7 || d === 9) {
                // Soixante-dix et quatre-vingt-dix
                resultat += dizaine[d];
                if (u === 1) {
                    resultat += ' et ' + unite[u];
                } else if (u > 1) {
                    resultat += '-' + unite[u];
                }
            } else {
                if (d > 0) {
                    resultat += dizaine[d];
                    if (u === 1 && d !== 8) {
                        resultat += ' et ' + unite[u];
                    } else if (u > 0) {
                        resultat += (d === 8 ? '' : '-') + unite[u];
                    } else if (d === 8) {
                        resultat += 's'; // Quatre-vingts
                    }
                } else {
                    resultat += unite[u];
                }
            }
        }
    }

    return resultat;
}

function montantEnLettres(montant) {
    // Séparer partie entière et décimale
    const parties = montant.toFixed(2).split('.');
    const entiere = parseInt(parties[0]);
    const decimale = parseInt(parties[1]);
    
    let resultat = nombreEnLettres(entiere) + ' dirham';
    
    // Accord pluriel
    if (entiere > 1) resultat += 's';
    
    // Ajouter les centimes
    if (decimale > 0) {
        resultat += ' et ' + nombreEnLettres(decimale) + ' centime';
        if (decimale > 1) resultat += 's';
    }
    
    return resultat.charAt(0).toUpperCase() + resultat.slice(1);
}

// Functions utilities for Handsontable 
function showSumSelectedCells(hot) {
    const selection = hot.getSelected();
    if (!selection || selection.length === 1) {
        return;
    }
    
    const [startRow, startCol, endRow, endCol] = selection[0];
    let sum = 0;
    let cellCount = 0;
    
    // Retur
    for (let row = startRow; row <= endRow; row++) {
        for (let col = startCol; col <= endCol; col++) {
            const value = hot.getDataAtCell(row, col);
            const numericValue = parseFloat(value);
            if (!isNaN(numericValue)) {
                sum += numericValue;
                cellCount++;
            }
        }
    }
    return { sum, cellCount };
}

// Exporter les fonctions pour une utilisation globale
window.nombreEnLettres = nombreEnLettres;
window.montantEnLettres = montantEnLettres;
window.showSumSelectedCells = showSumSelectedCells;