/* Dates ISO uniquement ; UTC evite les ecarts lies aux changements d'heure. */
(function () {
    'use strict';
    if (window.GoPlanWorkCalendar) return;

    class WorkCalendar {
        constructor(config) {
            if (!config || !Array.isArray(config.jours_ouvres) || !config.jours_ouvres.length
                || config.jours_ouvres.some(day => !Number.isInteger(day) || day < 1 || day > 7)
                || !config.exceptions || typeof config.exceptions !== 'object'
                || Array.isArray(config.exceptions)) {
                throw new Error('Configuration du calendrier ouvré invalide.');
            }
            this.workdays = new Set(config.jours_ouvres);
            this.exceptions = new Map(Object.entries(config.exceptions));
            this.exceptions.forEach((hours, day) => {
                this.parse(day);
                if (!Number.isFinite(hours) || hours < 0) {
                    throw new Error('Exception du calendrier ouvré invalide.');
                }
            });
        }

        parse(value) {
            const date = new Date(`${value}T00:00:00Z`);
            if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(date.getTime())
                || date.toISOString().slice(0, 10) !== value || date.getUTCFullYear() < 1) {
                throw new Error('Date du calendrier invalide.');
            }
            return date;
        }

        nextDate(value) {
            const date = this.parse(value);
            date.setUTCDate(date.getUTCDate() + 1);
            if (date.getUTCFullYear() > 9999) throw new Error('Date hors de la plage disponible.');
            return date.toISOString().slice(0, 10);
        }

        isWorkingDay(value) {
            const date = this.parse(value);
            if (this.exceptions.has(value)) return this.exceptions.get(value) > 0;
            return this.workdays.has(date.getUTCDay() || 7);
        }

        nextWorkingDay(value) {
            while (!this.isWorkingDay(value)) value = this.nextDate(value);
            return value;
        }

        endDate(start, duration) {
            if (!Number.isFinite(duration) || duration < 0) throw new Error('Durée invalide.');
            this.parse(start);
            if (duration === 0) return start;
            let current = this.nextWorkingDay(start);
            for (let remaining = Math.ceil(duration) - 1; remaining > 0;) {
                current = this.nextDate(current);
                if (this.isWorkingDay(current)) remaining--;
            }
            return current;
        }

        workingDaysBetween(start, end) {
            this.parse(start);
            this.parse(end);
            if (end < start) return 0;
            let count = 0;
            for (let current = start;; current = this.nextDate(current)) {
                if (this.isWorkingDay(current)) count++;
                if (current === end) return count;
            }
        }
    }

    window.GoPlanWorkCalendar = WorkCalendar;
})();
