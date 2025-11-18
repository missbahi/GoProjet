// static/projets/js/numericformatting.js

export function setupNumericFormatting(fieldId, decimals) {
  function parseFrenchNumber(value) {
    if (!value) return NaN;
    return parseFloat(value.replace(/\s/g, '').replace(',', '.'));
  }

  function formatFrenchNumber(num, decimals) {
    if (isNaN(num)) return '';
    return num.toLocaleString('fr-FR', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  const field = document.getElementById(fieldId);
  if (!field) return;

  // Formater la valeur initiale si présente
  const initialNum = parseFrenchNumber(field.value);
  if (!isNaN(initialNum)) {
    field.value = formatFrenchNumber(initialNum, decimals);
  }

  field.addEventListener('focus', function() {
    const num = parseFrenchNumber(this.value);
    this.value = isNaN(num) ? '' : num.toString().replace('.', ',');
  });

  field.addEventListener('blur', function() {
    const num = parseFrenchNumber(this.value);
    this.value = formatFrenchNumber(num, decimals);
  });
}

// Nettoyage des champs avant soumission
export function cleanFieldsBeforeSubmit(formSelector, fieldIds) {
  const form = document.querySelector(formSelector);
  if (!form) return;

  form.addEventListener('submit', function() {
    fieldIds.forEach(fieldId => {
      const field = document.getElementById(fieldId);
      if (field && field.value) {
        field.value = field.value.replace(/\s/g, '').replace(',', '.');
      }
    });
  });
}
