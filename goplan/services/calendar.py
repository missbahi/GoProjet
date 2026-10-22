# goplan/services/calendar.py
"""Calculs de dates en jours ouvrés selon un GWorkCalendar."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from math import ceil
from typing import Optional

from django.core.exceptions import ValidationError

from ..models import GWorkCalendar


class WorkCalendarService:
    """
    Convention : isoweekday() → 1=Lundi … 7=Dimanche.
    Compatible avec `jours_ouvres = [1,2,3,4,5]` du modèle.
    """

    DEFAULT_WORKDAYS = {1, 2, 3, 4, 5}

    def __init__(self, calendar: Optional[GWorkCalendar] = None):
        self.calendar = calendar

        # ── Jours ouvrés ──
        if calendar is None:
            self.jours_ouvres = set(self.DEFAULT_WORKDAYS)
        else:
            days = calendar.jours_ouvres
            if (not isinstance(days, list) or not days
                    or any(type(day) is not int or not 1 <= day <= 7 for day in days)):
                raise ValidationError("Le calendrier doit contenir des jours ouvrés ISO valides (1 à 7).")
            self.jours_ouvres = set(days)
            self._validate_hours(calendar.heures_par_jour, positive=True)

        # ── Exceptions : lecture relationnelle (GCalendarException) ──
        # calendar.exceptions est un RelatedManager.
        # ⚠️ Nécessite calendar.pk — une instance non sauvegardée (pk=None)
        # n'a pas d'ID de relation, donc on retourne un dict vide.
        self.exceptions: dict[str, float] = {}
        if calendar and calendar.pk:
            for exc in calendar.exceptions.all():
                self._validate_hours(exc.heures)
                self.exceptions[exc.date.isoformat()] = float(exc.heures)

    @staticmethod
    def _validate_hours(value, *, positive=False):
        try:
            hours = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValidationError("Les heures du calendrier sont invalides.") from error
        if not hours.is_finite() or not 0 <= hours <= 24 or (positive and not hours):
            raise ValidationError("Les heures doivent être comprises entre 0 et 24 (journée normale > 0).")

    @staticmethod
    def _next_date(day):
        try:
            return day + timedelta(days=1)
        except OverflowError as error:
            raise ValidationError("Le calcul dépasse la plage de dates disponible.") from error

    # ──────────────────────────────────────────────────────
    def is_working_day(self, d: date) -> bool:
        iso = d.isoformat()
        if iso in self.exceptions:
            return self.exceptions[iso] > 0
        return d.isoweekday() in self.jours_ouvres

    def next_working_day(self, d: date) -> date:
        while not self.is_working_day(d):
            d = self._next_date(d)
        return d

    def add_working_days(self, start: date, days: int | Decimal) -> date:
        """Ajoute `days` jours ouvrés à partir de `start` (inclus)."""
        if not Decimal(str(days)).is_finite() or days < 0:
            raise ValidationError("La durée doit être positive ou nulle.")
        if days == 0:
            return start
        current = self.next_working_day(start)
        remaining = ceil(days) - 1
        while remaining > 0:
            current = self._next_date(current)
            if self.is_working_day(current):
                remaining -= 1
        return current

    def working_days_between(self, start: date, end: date) -> int:
        """Compte les jours ouvrés entre start et end (inclus)."""
        if end < start:
            return 0
        count = 0
        current = start
        while current <= end:
            if self.is_working_day(current):
                count += 1
            if current == end:
                break
            current = self._next_date(current)
        return count

    def to_dict(self) -> dict:
        """Sérialisation pour envoi au frontend (contrat JS inchangé)."""
        return {
            "jours_ouvres": sorted(self.jours_ouvres),
            "exceptions": {k: v for k, v in sorted(self.exceptions.items())},
        }


def get_calendar_for_plan(plan) -> WorkCalendarService:
    """Retourne le service pour un plan, avec fallback sur le calendrier par défaut."""
    if plan and plan.calendrier_id:
        return WorkCalendarService(plan.calendrier)
    default = GWorkCalendar.objects.filter(is_default=True).first()
    return WorkCalendarService(default)