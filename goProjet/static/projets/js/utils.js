// static/js/utils.js - Fonctions utilitaires réutilisables

/**
 * Formatage des nombres selon les standards français
 * @param {number} number - Le nombre à formater
 * @param {number} decimals - Nombre de décimales (défaut: 2)
 * @param {boolean} forceDecimals - Forcer l'affichage des décimales même si .00
 * @returns {string} Nombre formaté
 */
function formatNumber(number, decimals = 2, forceDecimals = false) {
    if (number === null || number === undefined || isNaN(number)) {
        return forceDecimals ? `0,${'0'.repeat(decimals)}` : '0';
    }
    
    const options = {
        minimumFractionDigits: forceDecimals ? decimals : 0,
        maximumFractionDigits: decimals,
        useGrouping: true
    };
    
    return new Intl.NumberFormat('fr-FR', options).format(number);
}

/**
 * Formatage des montants en DH
 * @param {number} amount - Le montant à formater
 * @param {number} decimals - Nombre de décimales (défaut: 2)
 * @returns {string} Montant formaté avec devise
 */
function formatCurrency(amount, decimals = 2) {
    return `${formatNumber(amount, decimals, true)} DH`;
}

/**
 * Formatage des quantités (3 décimales)
 * @param {number} quantity - La quantité à formater
 * @returns {string} Quantité formatée
 */
function formatQuantity(quantity) {
    return formatNumber(quantity, 3, false);
}

/**
 * Conversion d'une string en nombre français
 * @param {string} str - String à convertir (ex: "1 234,56")
 * @returns {number} Nombre converti
 */
function parseFrenchNumber(str) {
    if (!str) return 0;
    
    // Remplacer les espaces de séparation et virgules décimales
    const cleaned = str.toString()
        .replace(/\s/g, '')      // Supprimer les espaces
        .replace(/,/g, '.');     // Remplacer virgule par point
    
    return parseFloat(cleaned) || 0;
}

/**
 * Calcul du montant à partir de quantité et prix unitaire
 * @param {number} quantity - Quantité
 * @param {number} unitPrice - Prix unitaire
 * @returns {number} Montant calculé
 */
function calculateAmount(quantity, unitPrice) {
    const qte = parseFrenchNumber(quantity) || 0;
    const pu = parseFrenchNumber(unitPrice) || 0;
    return qte * pu;
}

/**
 * Validation d'un email
 * @param {string} email - Email à valider
 * @returns {boolean} True si email valide
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Formatage de date en français
 * @param {Date|string} date - Date à formater
 * @returns {string} Date formatée
 */
function formatDate(date) {
    if (!date) return '';
    
    const d = new Date(date);
    if (isNaN(d.getTime())) return '';
    
    return d.toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
}

/**
 * Tronquer un texte avec ellipse
 * @param {string} text - Texte à tronquer
 * @param {number} maxLength - Longueur maximale
 * @returns {string} Texte tronqué
 */
function truncateText(text, maxLength = 50) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

/**
 * Capitaliser la première lettre
 * @param {string} str - Chaîne à capitaliser
 * @returns {string} Chaîne capitalisée
 */
function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

/**
 * Générer un ID unique
 * @returns {string} ID unique
 */
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// Exporter les fonctions pour usage dans d'autres fichiers
if (typeof module !== 'undefined' && module.exports) {
    // Node.js
    module.exports = {
        formatNumber,
        formatCurrency,
        formatQuantity,
        parseFrenchNumber,
        calculateAmount,
        isValidEmail,
        formatDate,
        truncateText,
        capitalizeFirst,
        generateId
    };
}