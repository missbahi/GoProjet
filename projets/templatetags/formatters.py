# projets/templatetags/formatters.py
from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
@stringfilter
def format_french_number(value, decimals=2):
    """
    Formatage des nombres à la française
    Usage: {{ value|format_french_number }} ou {{ value|format_french_number:3 }}
    """
    try:
        number = float(value)
        return f"{number:,.{decimals}f}".replace(",", " ").replace(".", ",")
    except (ValueError, TypeError):
        return value

@register.filter
def format_currency(value, decimals=2):
    """
    Formatage des montants avec devise
    Usage: {{ value|format_currency }} ou {{ value|format_currency:0 }}
    """
    try:
        number = float(value)
        formatted = f"{number:,.{decimals}f}".replace(",", " ").replace(".", ",")
        return f"{formatted} DH"
    except (ValueError, TypeError):
        return f"0,{'0' * decimals} DH"

@register.filter
def format_quantity(value):
    """
    Formatage des quantités (2 décimales)
    Usage: {{ value|format_quantity }}
    """
    try:
        number = float(value)
        return f"{number:,.2f}".replace(",", " ").replace(".", ",")
    except (ValueError, TypeError):
        return "0,00"

@register.filter
def format_percentage(value):
    """
    Formatage des pourcentages (0 décimales)
    Usage: {{ value|format_percentage }}
    """
    try:
        number = float(value)
        return f"{number:,.0f} %".replace(",", " ").replace(".", ",")
    except (ValueError, TypeError):
        return "0 %"
@register.filter
def calculate_amount(quantity, unit_price):
    """
    Calcul du montant quantité × prix unitaire
    Usage: {{ quantity|calculate_amount:unit_price }}
    """
    try:
        qte = float(quantity) if quantity else 0
        pu = float(unit_price) if unit_price else 0
        return qte * pu
    except (ValueError, TypeError):
        return 0

@register.filter
def amount_ttc(amount_ht, tva_rate=0.2):
    """
    Calcul du montant TTC à partir du montant HT et du taux de TVA
    Usage: {{ amount_ht|amount_ttc }} ou {{ amount_ht|amount_ttc:0.1 }}
    """
    try:
        number = float(amount_ht)*(1 + float(tva_rate)) if amount_ht else 0
        return f"{number:,.2f}".replace(",", " ").replace(".", ",")
    except (ValueError, TypeError):
        return 0.00