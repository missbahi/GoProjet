# goplan/services/calendar.py
"""Calculs de dates en jours ouvrés selon un GWorkCalendar."""
from bisect import bisect_left, bisect_right
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
        # On conserve `self.exceptions` (clés ISO str) pour compatibilité (ex: export MSPDI)
        # et on indexe aussi par `datetime.date` pour éviter `d.isoformat()` dans les boucles.
        self.exceptions: dict[str, float] = {}
        self._exceptions_by_date: dict[date, float] = {}
        if calendar and calendar.pk:
            for exc in calendar.exceptions.all():
                self._validate_hours(exc.heures)
                hours = float(exc.heures)
                self._exceptions_by_date[exc.date] = hours
                self.exceptions[exc.date.isoformat()] = hours
        self._sorted_exc_dates: tuple[date, ...] = tuple(sorted(self._exceptions_by_date))

    @staticmethod
    def _validate_hours(value, *, positive=False):
        try:
            hours = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValidationError("Les heures du calendrier sont invalides.") from error
        if not hours.is_finite() or not 0 <= hours <= 24 or (positive and not hours):
            raise ValidationError("Les heures doivent être comprises entre 0 et 24 (journée normale > 0).")

    @staticmethod
    def _next_date(day: date) -> date:
        try:
            return day + timedelta(days=1)
        except OverflowError as error:
            raise ValidationError("Le calcul dépasse la plage de dates disponible.") from error

    @staticmethod
    def _step_date(day: date, days: int) -> date:
        try:
            return day + timedelta(days=days)
        except OverflowError as error:
            raise ValidationError("Le calcul dépasse la plage de dates disponible.") from error

    # ──────────────────────────────────────────────────────
    def is_working_day(self, d: date) -> bool:
        exc_hours = self._exceptions_by_date.get(d)
        if exc_hours is not None:
            return exc_hours > 0
        return d.isoweekday() in self.jours_ouvres

    def next_working_day(self, d: date) -> date:
        while not self.is_working_day(d):
            d = self._next_date(d)
        return d

    def shift_working_days(self, day: date, offset: int) -> date:
        """Déplace `day` de `offset` jours ouvrés (positif ou négatif) avec saut de semaines."""
        if offset == 0:
            return day
        direction = 1 if offset > 0 else -1
        remaining = abs(offset)
        workdays_per_week = len(self.jours_ouvres)
        sorted_exc = self._sorted_exc_dates

        while remaining > 0:
            if remaining >= workdays_per_week * 2 and workdays_per_week > 0:
                weeks = (remaining - 1) // workdays_per_week
                if weeks > 0:
                    target = self._step_date(day, direction * 7 * weeks)
                    if not sorted_exc:
                        safe_weeks = weeks
                    elif direction > 0:
                        next_day = self._step_date(day, 1)
                        idx = bisect_left(sorted_exc, next_day)
                        if idx == len(sorted_exc) or sorted_exc[idx] > target:
                            safe_weeks = weeks
                        else:
                            safe_weeks = max(0, (sorted_exc[idx] - day).days - 1) // 7
                    else:
                        prev_day = self._step_date(day, -1)
                        idx = bisect_right(sorted_exc, prev_day) - 1
                        if idx < 0 or sorted_exc[idx] < target:
                            safe_weeks = weeks
                        else:
                            safe_weeks = max(0, (day - sorted_exc[idx]).days - 1) // 7

                    if safe_weeks > 0:
                        day = self._step_date(day, direction * 7 * safe_weeks)
                        remaining -= safe_weeks * workdays_per_week
                        continue

            day = self._step_date(day, direction)
            if self.is_working_day(day):
                remaining -= 1
        return day

    def add_working_days(self, start: date, days: int | Decimal) -> date:
        """Ajoute `days` jours ouvrés à partir de `start` (inclus)."""
        if not Decimal(str(days)).is_finite() or days < 0:
            raise ValidationError("La durée doit être positive ou nulle.")
        if days == 0:
            return start
        current = self.next_working_day(start)
        remaining = ceil(days) - 1
        if remaining <= 0:
            return current
        return self.shift_working_days(current, remaining)

    def working_days_between(self, start: date, end: date) -> int:
        """Compte les jours ouvrés entre start et end (inclus) en O(1 + exceptions)."""
        if end < start:
            return 0
        total_days = (end - start).days + 1
        full_weeks, rem = divmod(total_days, 7)
        workdays = self.jours_ouvres
        count = full_weeks * len(workdays)

        start_iso = start.isoweekday()
        for offset in range(rem):
            if ((start_iso + offset - 1) % 7 + 1) in workdays:
                count += 1

        sorted_exc = self._sorted_exc_dates
        if sorted_exc:
            left = bisect_left(sorted_exc, start)
            right = bisect_right(sorted_exc, end)
            exc_by_date = self._exceptions_by_date
            for idx in range(left, right):
                exc_date = sorted_exc[idx]
                is_base = exc_date.isoweekday() in workdays
                is_working_exc = exc_by_date[exc_date] > 0
                if is_working_exc and not is_base:
                    count += 1
                elif not is_working_exc and is_base:
                    count -= 1
        return count

    def to_dict(self) -> dict:
        """Sérialisation pour envoi au frontend (contrat JS inchangé)."""
        return {
            "jours_ouvres": sorted(self.jours_ouvres),
            "exceptions": {k: v for k, v in sorted(self.exceptions.items())},
        }


def get_calendar_for_plan(plan) -> WorkCalendarService:
    """Retourne le service pour un plan, avec fallback sur le calendrier par défaut et cache d'instance."""
    if plan is not None:
        cache_key = (plan.calendrier_id, id(plan.calendrier) if plan.calendrier_id else None)
        if getattr(plan, "_calendar_service_cache_key", None) == cache_key:
            return plan._calendar_service_cache

        if plan.calendrier_id:
            service = WorkCalendarService(plan.calendrier)
        else:
            default = GWorkCalendar.objects.prefetch_related("exceptions").filter(is_default=True).first()
            service = WorkCalendarService(default)

        plan._calendar_service_cache_key = cache_key
        plan._calendar_service_cache = service
        return service

    default = GWorkCalendar.objects.prefetch_related("exceptions").filter(is_default=True).first()
    return WorkCalendarService(default)