from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
import re
import uuid

class GWorkCalendar(models.Model):
    """Calendrier de travail (jours ouvrés, exceptions)."""
    
    nom = models.CharField(_("Nom"), max_length=100)
    jours_ouvres = models.JSONField(_("Jours ouvrés"), default=list, help_text=_("Ex: [1,2,3,4,5] pour lundi-vendredi"),)
    heures_par_jour = models.DecimalField(_("Heures/jour"), max_digits=5, decimal_places=2, default=8,)
    # exceptions = models.JSONField(_("Jours fériés"), default=list, help_text=_("[{'date': 'YYYY-MM-DD', 'heures': 0}]"),)
    is_default = models.BooleanField(_("Par défaut"), default=False)

    # @property
    # def exceptions_count(self):
    #     return self.exceptions.count()

    @property
    def workday_chips(self):
        """Liste [(iso, label)] pour affichage 7 pastilles L→D."""
        return [
            (1, "Lundi"), (2, "Mardi"), (3, "Mercredi"),
            (4, "Jeudi"), (5, "Vendredi"), (6, "Samedi"), (7, "Dimanche"),
        ]
    class Meta:
        verbose_name = _("Calendrier de travail")

    def __str__(self):
        return self.nom


class GCalendarException(models.Model):
    """Exception ponctuelle à un calendrier.
    heures == 0   → jour chômé
    heures  > 0   → jour ouvré exceptionnel (ex : samedi travaillé)
    """
    calendrier = models.ForeignKey(
        GWorkCalendar, on_delete=models.CASCADE,
        related_name="exceptions",
    )
    date = models.DateField(_("Date"))
    heures = models.DecimalField(
        _("Heures"), max_digits=5, decimal_places=2, default=0,
    )

    class Meta:
        verbose_name = _("Exception calendrier")
        verbose_name_plural = _("Exceptions calendrier")
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["calendrier", "date"],
                name="goplan_calendar_unique_exception_date",
            ),
        ]

    def __str__(self):
        return f"{self.date.isoformat()} ({self.heures} h)"


class GPlan(models.Model):
    """Planification d'un ensemble de tâches."""
    nom = models.CharField(_("Nom"), max_length=200)
    description = models.TextField(_("Description"), blank=True)
    date_debut = models.DateField(_("Date de début"))
    date_fin_cible = models.DateField(_("Date de fin cible"), null=True, blank=True)
    date_etat = models.DateField(
        _("Date d'état"), null=True, blank=True,
        help_text=_("Date à laquelle l'avancement est mesuré (StatusDate MS Project)."),
    )
    calendrier = models.ForeignKey(
        GWorkCalendar, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Calendrier"),
    )
    gantt_arrondi = models.CharField(
        _("Arrondi des barres"), max_length=12, default="arrondi",
        choices=[("rectangle", _("Rectangle")), ("arrondi", _("Arrondi")), ("capsule", _("Capsule"))],
    )
    gantt_epaisseur = models.CharField(
        _("Épaisseur des barres"), max_length=8, default="normale",
        choices=[("fine", _("Fine")), ("normale", _("Normale")), ("epaisse", _("Épaisse"))],
    )
    gantt_groupe = models.CharField(
        _("Forme des groupes"), max_length=8, default="crochets",
        choices=[("crochets", _("Crochets")), ("bande", _("Bande simple"))],
    )
    gantt_jalon = models.CharField(
        _("Forme des jalons"), max_length=8, default="losange",
        choices=[("losange", _("Losange")), ("cercle", _("Cercle")), ("triangle", _("Triangle"))],
    )
    gantt_liaison = models.CharField(
        _("Style des liaisons"), max_length=12, default="angles",
        choices=[
            ("angles", _("Angles droits")), ("arrondis", _("Angles arrondis")),
            ("tirets", _("Tirets")), ("pointilles", _("Pointillés")),
        ],
    )
    gantt_couleur_liaison = models.CharField(
        _("Couleur des liaisons"), max_length=7, default="#527889",
        validators=[RegexValidator(r"\A#[0-9a-fA-F]{6}\Z", _("Choisissez une couleur au format #RRGGBB."))],
    )

    # Lien générique optionnel (ex: vers Projet de GoProjet)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True,)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source_object = GenericForeignKey('content_type', 'object_id')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Plan")
        ordering = ['-created_at']

    def __str__(self):
        return self.nom


class GResource(models.Model):
    """Ressource planifiable (personne, équipe, matériel)."""

    class Type(models.TextChoices):
        PERSONNE = 'PERSONNE', _('Personne')
        EQUIPE = 'EQUIPE', _('Équipe')
        MATERIEL = 'MATERIEL', _('Matériel')
        ATELIER = 'ATELIER', _('Atelier')
        AUTRE = 'AUTRE', _('Autre')

    nom = models.CharField(_("Nom"), max_length=150)
    type_ressource = models.CharField(
        _("Type"), max_length=20, choices=Type.choices, default=Type.PERSONNE,
    )
    capacite_jour = models.DecimalField(
        _("Capacité/jour (h)"), max_digits=5, decimal_places=2, default=8,
    )
    cout_horaire = models.DecimalField(
        _("Coût horaire"), max_digits=10, decimal_places=2, default=0,
    )
    calendrier = models.ForeignKey(
        GWorkCalendar, on_delete=models.SET_NULL, null=True, blank=True,
    )

    # Lien générique optionnel (vers Personnel, Materiel, etc.)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = _("Ressource")

    def __str__(self):
        return self.nom


class GTask(models.Model):
    """Tâche planifiée."""

    class Type(models.TextChoices):
        TACHE = 'TACHE', _('Tâche')
        JALON = 'JALON', _('Jalon')
        GROUPE = 'GROUPE', _('Groupe')
        RECURRENTE = 'RECUR', _('Récurrente')

    class Contrainte(models.TextChoices):
        ASAP = 'ASAP', _('Au plus tôt')
        ALAP = 'ALAP', _('Au plus tard')
        DEBUT_FIXE = 'FIXE_DEBUT', _('Début fixe')
        FIN_FIXE = 'FIXE_FIN', _('Fin fixe')
        DEBUT_MIN = 'DEBUT_MIN', _('Début au plus tôt le')
        DEBUT_MAX = 'DEBUT_MAX', _('Début au plus tard le')
        FIN_MIN = 'FIN_MIN', _('Fin au plus tôt le')
        FIN_MAX = 'FIN_MAX', _('Fin au plus tard le')

    plan = models.ForeignKey(GPlan, on_delete=models.CASCADE, related_name='taches',)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sous_taches',)
    code = models.CharField(_("Code"), max_length=50, blank=True)
    nom = models.CharField(_("Nom"), max_length=255)
    description = models.TextField(blank=True)
    type_tache = models.CharField(_("Type"), max_length=10, choices=Type.choices, default=Type.TACHE,)
    duree = models.DecimalField(_("Durée (jours)"), max_digits=10, decimal_places=2, default=1, )
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    contrainte = models.CharField(_("Contrainte"), max_length=20, choices=Contrainte.choices, default=Contrainte.ASAP,)
    date_contrainte = models.DateField(_("Date de contrainte"), null=True, blank=True)
    ordre = models.PositiveIntegerField(default=0)
    avancement = models.DecimalField(_("Avancement (%)"), max_digits=5, decimal_places=2, default=0, )
    # Marge calculée (pour chemin critique)
    marge_totale = models.DecimalField(_("Marge totale (j)"), max_digits=10, decimal_places=2, null=True, blank=True, editable=False,)
    est_critique = models.BooleanField(_("Critique"), default=False, editable=False)
    couleur = models.CharField(_("Couleur"), max_length=20, blank=True, help_text=_("Couleur personnalisée (optionnel)"), )
    recurrence_rule = models.CharField(max_length=255, blank=True)
    # Identifiant stable pour l'échange MSPDI
    uid = models.UUIDField(_("UID"), default=uuid.uuid4, editable=False, unique=True, 
                           help_text=_("Identifiant stable pour l'échange MS Project"),)
    # Code WBS hiérarchique (ex: '1.2.3')
    wbs = models.CharField(_("WBS"), max_length=50, blank=True, editable=False, default="", 
                           help_text=_("Code hiérarchique calculé (ex: 1.2.3)"), )
    # État d'affichage partagé par l'éditeur, le Gantt et l'aperçu ; exclu des contrôles de concurrence.
    replie = models.BooleanField(_("Groupe replié"), default=False,
                                 help_text=_("Sous-tâches masquées à l'écran et, en option, à l'impression."))
    # Réservé à une prochaine version (masquer une ligne) : pas encore utilisé par l'interface.
    masquee = models.BooleanField(_("Ligne masquée"), default=False)
    DISPLAY_STATE_FIELDS = ("replie",)

    class Meta:
        verbose_name = _("Tâche planifiée")
        ordering = ['plan', 'ordre', 'id']

    def __str__(self):
        return f"{self.code} {self.nom}".strip()

    @property
    def niveau(self):
        """Calcule le niveau hiérarchique (profondeur depuis la racine)."""
        level = 0
        current = self.parent
        visited = set()
        while current and current.pk not in visited:
            visited.add(current.pk)
            level += 1
            current = current.parent
        return level

    def validate_task_type(self, children_count):
        """Validate against the effective children, not a stale database tree."""
        errors = {}

        if self.type_tache in ('JALON', 'RECUR') and children_count:
            errors['type_tache'] = "Un jalon ne peut pas avoir de sous-tâches."
            if self.type_tache == 'RECUR':
                errors['type_tache'] = "Une tâche récurrente ne peut pas avoir de sous-tâches."

        if self.type_tache == 'GROUPE' and not children_count:
            errors['type_tache'] = "Un groupe doit avoir au moins une sous-tâche."

        if errors:
            raise ValidationError(errors)

    def validate_constraint_dates(self, start, end):
        fixed = {
            self.Contrainte.DEBUT_FIXE: start,
            self.Contrainte.FIN_FIXE: end,
        }
        if self.contrainte in fixed and self.date_contrainte and fixed[self.contrainte]:
            if fixed[self.contrainte] != self.date_contrainte:
                raise ValidationError({"date_contrainte": "La date de la tâche doit correspondre à la date fixe."})
        bounds = {
            self.Contrainte.DEBUT_MIN: (start, "min"),
            self.Contrainte.DEBUT_MAX: (start, "max"),
            self.Contrainte.FIN_MIN: (end, "min"),
            self.Contrainte.FIN_MAX: (end, "max"),
        }
        if self.contrainte in bounds:
            if self.date_contrainte is None:
                raise ValidationError({"date_contrainte": "Renseignez la date de contrainte."})
            value, direction = bounds[self.contrainte]
            if value and ((direction == "min" and value < self.date_contrainte)
                          or (direction == "max" and value > self.date_contrainte)):
                raise ValidationError({"date_contrainte": "Les dates de la tâche ne respectent pas la contrainte."})


class GTaskDependency(models.Model):
    """Lien de dépendance entre 2 tâches."""

    class Type(models.TextChoices):
        FS = 'FS', _('Fin → Début')
        SS = 'SS', _('Début → Début')
        FF = 'FF', _('Fin → Fin')
        SF = 'SF', _('Début → Fin')

    predecesseur = models.ForeignKey(
        GTask, on_delete=models.CASCADE, related_name='dependances_sortantes',
    )
    successeur = models.ForeignKey(
        GTask, on_delete=models.CASCADE, related_name='dependances_entrantes',
    )
    type_lien = models.CharField(
        _("Type"), max_length=2, choices=Type.choices, default=Type.FS,
    )
    decalage_jours = models.IntegerField(_("Décalage (j)"), default=0)

    class Meta:
        verbose_name = _("Dépendance")
        unique_together = [['predecesseur', 'successeur']]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(predecesseur=models.F('successeur')),
                name='goplan_no_self_dependency',
            ),
        ]


class GTaskAssignment(models.Model):
    """Affectation d'une ressource à une tâche."""
    tache = models.ForeignKey(
        GTask, on_delete=models.CASCADE, related_name='assignations',
    )
    ressource = models.ForeignKey(
        GResource, on_delete=models.CASCADE, related_name='assignations',
    )
    charge = models.DecimalField(
        _("Charge (h)"), max_digits=10, decimal_places=2, default=0,
    )
    taux_affectation = models.DecimalField(
        _("Taux (%)"), max_digits=5, decimal_places=2, default=100,
    )

    class Meta:
        verbose_name = _("Affectation")
        unique_together = [['tache', 'ressource']]


PRINT_TEXT_VARIABLES = (
    "plan", "description", "date_impression", "date_etat", "periode", "format", "calendrier",
)


def validate_print_text(value):
    unknown = sorted(set(re.findall(r"\{(\w+)\}", value)) - set(PRINT_TEXT_VARIABLES))
    if unknown:
        raise ValidationError(
            _("Variable(s) inconnue(s) : %(names)s. Disponibles : %(allowed)s."),
            params={
                "names": ", ".join("{%s}" % name for name in unknown),
                "allowed": ", ".join("{%s}" % name for name in PRINT_TEXT_VARIABLES),
            },
        )


def points(minimum, maximum):
    return [MinValueValidator(minimum), MaxValueValidator(maximum)]


def row_font_points(row_height_mm):
    """Task-text size of a printed row: the Gantt draws 13px text in 35px rows."""
    return row_height_mm / 25.4 * 72 * 13 / 35


class GPlanPrintSettings(models.Model):
    """Mise en page de l'aperçu imprimable, partagée par planning.

    L'apparence des barres et liaisons reste gérée par GPlan (gantt_*).
    Absence de ligne = valeurs par défaut ; créée au premier enregistrement.
    """

    BACKGROUND_PRESETS = (
        ("#f8f6ef", _("Ivoire (par défaut)")),
        ("#ffffff", _("Blanc")),
        ("#f1f5f9", _("Gris perle")),
        ("#eff6ff", _("Bleu glacier")),
        ("#ecfdf5", _("Vert d'eau")),
        ("#fefce8", _("Jaune pâle")),
        ("#fdf2f8", _("Rose poudré")),
        ("#f5f3ff", _("Lavande")),
    )

    class Format(models.TextChoices):
        A4 = "A4", "A4"
        A3 = "A3", "A3"
        A2 = "A2", "A2"
        A1 = "A1", "A1"
        A0 = "A0", "A0"

    class Orientation(models.TextChoices):
        PORTRAIT = "portrait", _("Portrait")
        PAYSAGE = "landscape", _("Paysage")

    class Echelle(models.TextChoices):
        JOUR = "Day", _("Jour")
        SEMAINE = "Week", _("Semaine")
        MOIS = "Month", _("Mois")

    class Periode(models.TextChoices):
        COMPLETE = "full", _("Toute la période")
        PERSONNALISEE = "custom", _("Personnalisée")
        RELATIVE = "relative", _("Autour de la date d'état")

    class Police(models.TextChoices):
        ARIAL = "arial", "Arial"
        CALIBRI = "calibri", "Calibri"
        VERDANA = "verdana", "Verdana"
        TAHOMA = "tahoma", "Tahoma"
        GEORGIA = "georgia", "Georgia"
        TIMES = "times", "Times New Roman"

    margin_validators = [MinValueValidator(0), MaxValueValidator(30)]


    plan = models.OneToOneField(GPlan, on_delete=models.CASCADE, related_name="print_settings")

    # ── Mise en page ──
    format = models.CharField(_("Format"), max_length=2, choices=Format.choices, default=Format.A4)
    orientation = models.CharField(
        _("Orientation"), max_length=9, choices=Orientation.choices, default=Orientation.PAYSAGE,
    )
    margin_top = models.PositiveSmallIntegerField(_("Marge haute (mm)"), default=8, validators=margin_validators)
    margin_bottom = models.PositiveSmallIntegerField(_("Marge basse (mm)"), default=8, validators=margin_validators)
    margin_left = models.PositiveSmallIntegerField(_("Marge gauche (mm)"), default=8, validators=margin_validators)
    margin_right = models.PositiveSmallIntegerField(_("Marge droite (mm)"), default=8, validators=margin_validators)
    center_vertically = models.BooleanField(_("Centrer verticalement"), default=False)
    vertical_pages = models.PositiveSmallIntegerField(
        _("Pages en hauteur"), default=1, validators=[MaxValueValidator(20)],
        help_text=_("0 = automatique : juste assez de pages pour respecter la taille minimale du texte."),
    )
    min_font_size = models.PositiveSmallIntegerField(
        _("Taille minimale du texte des tâches (pt)"), default=7, validators=points(5, 12),
    )
    max_row_height = models.PositiveSmallIntegerField(
        _("Hauteur maximale des lignes (mm)"), default=7,
        validators=[MinValueValidator(5), MaxValueValidator(15)],
        help_text=_("Fixe la taille maximale du texte des tâches : un grand papier contient plus de lignes."),
    )

    # ── Échelle et période ──
    timescale = models.CharField(_("Échelle de temps"), max_length=5, choices=Echelle.choices, default=Echelle.SEMAINE)
    period_mode = models.CharField(_("Période"), max_length=8, choices=Periode.choices, default=Periode.COMPLETE)
    period_start = models.DateField(_("Début de période"), null=True, blank=True)
    period_end = models.DateField(_("Fin de période"), null=True, blank=True)
    weeks_before = models.PositiveSmallIntegerField(
        _("Semaines avant la date d'état"), default=2, validators=[MaxValueValidator(104)],
    )
    weeks_after = models.PositiveSmallIntegerField(
        _("Semaines après la date d'état"), default=6, validators=[MaxValueValidator(104)],
    )
    outline_level = models.PositiveSmallIntegerField(
        _("Niveau hiérarchique imprimé"), null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_("Vide = tous les niveaux ; 1 = tâches de premier niveau uniquement."),
    )
    respect_collapsed = models.BooleanField(
        _("Respecter les groupes repliés"), default=True,
        help_text=_("Les sous-tâches des groupes repliés dans l'éditeur ou le Gantt ne sont pas imprimées."),
    )

    # ── Colonnes du tableau des tâches (le nom est toujours imprimé) ──
    col_code = models.BooleanField(_("Colonne code"), default=False)
    col_duree = models.BooleanField(_("Colonne durée"), default=False)
    col_debut = models.BooleanField(_("Colonne début"), default=False)
    col_fin = models.BooleanField(_("Colonne fin"), default=False)
    col_avancement = models.BooleanField(_("Colonne avancement"), default=False)
    col_predecesseurs = models.BooleanField(_("Colonne prédécesseurs"), default=False)
    name_max_width = models.PositiveSmallIntegerField(
        _("Largeur max. de la colonne Nom (mm)"), default=0, validators=[MaxValueValidator(250)],
        help_text=_("0 = automatique (nom le plus long). Les noms plus longs sont tronqués « … »."),
    )
    column_max_width = models.PositiveSmallIntegerField(
        _("Largeur max. des autres colonnes (mm)"), default=0, validators=[MaxValueValidator(80)],
        help_text=_("0 = automatique. Les valeurs plus longues sont tronquées « … »."),
    )

    # ── Affichage ──
    background_color = models.CharField(
        _("Couleur de fond du dessin"), max_length=7, default=BACKGROUND_PRESETS[0][0],
        validators=[RegexValidator(r"\A#[0-9a-fA-F]{6}\Z", _("Choisissez une couleur au format #RRGGBB."))],
    )
    show_labels_on_bars = models.BooleanField(_("Noms sur les barres"), default=False)
    show_links = models.BooleanField(_("Liaisons"), default=True)
    show_progress = models.BooleanField(_("Avancement sur les barres"), default=True)
    show_nonworking = models.BooleanField(_("Ombrage des jours non travaillés"), default=True)
    show_grid = models.BooleanField(_("Grille"), default=True)
    show_today_marker = models.BooleanField(_("Marqueur « aujourd'hui »"), default=True)
    show_status_date = models.BooleanField(_("Ligne de date d'état"), default=True)
    show_undated_tasks = models.BooleanField(_("Tâches non datées"), default=True)
    show_warnings = models.BooleanField(_("Avertissements sur la feuille"), default=True)
    show_legend = models.BooleanField(_("Légende"), default=True)
    show_print_date = models.BooleanField(_("Date d'impression"), default=True)
    show_footer = models.BooleanField(_("Pied de page"), default=True)

    # ── Textes (variables : voir PRINT_TEXT_VARIABLES) ──
    header_title = models.CharField(
        _("Titre"), max_length=200, blank=True, default="{plan}", validators=[validate_print_text],
    )
    header_subtitle = models.TextField(
        _("Sous-titre"), max_length=500, blank=True, default="{description}", validators=[validate_print_text],
    )
    header_center = models.TextField(
        _("Texte central de l'en-tête"), max_length=300, blank=True, default="", validators=[validate_print_text],
    )
    footer_text = models.CharField(
        _("Pied de page"), max_length=300, blank=True,
        default="Jours non travaillés ombrés · Durées en jours ouvrés", validators=[validate_print_text],
    )

    # ── Typographie (le texte des tâches suit la hauteur des lignes) ──
    font_family = models.CharField(_("Police"), max_length=8, choices=Police.choices, default=Police.ARIAL)
    title_font_size = models.PositiveSmallIntegerField(_("Taille du titre (pt)"), default=15, validators=points(8, 48))
    title_bold = models.BooleanField(_("Titre en gras"), default=True)
    title_color = models.CharField(
        _("Couleur du titre"), max_length=7, default="#19394a",
        validators=[RegexValidator(r"\A#[0-9a-fA-F]{6}\Z", _("Choisissez une couleur au format #RRGGBB."))],
    )
    subtitle_font_size = models.PositiveSmallIntegerField(
        _("Taille du sous-titre (pt)"), default=9, validators=points(6, 24),
    )
    header_center_font_size = models.PositiveSmallIntegerField(
        _("Taille du texte central (pt)"), default=11, validators=points(6, 36),
    )
    header_center_bold = models.BooleanField(_("Texte central en gras"), default=True)
    footer_font_size = models.PositiveSmallIntegerField(
        _("Taille du pied de page (pt)"), default=8, validators=points(6, 16),
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Paramètres d'impression")
        verbose_name_plural = _("Paramètres d'impression")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(period_start__isnull=True)
                | models.Q(period_end__isnull=True)
                | models.Q(period_end__gte=models.F("period_start")),
                name="goplan_print_period_order",
            ),
        ]

    def __str__(self):
        return f"Impression — {self.plan}"

    def clean(self):
        errors = {}
        if self.period_mode == self.Periode.PERSONNALISEE:
            if not self.period_start or not self.period_end:
                errors["period_start"] = _("Renseignez le début et la fin de la période.")
            elif self.period_end < self.period_start:
                errors["period_end"] = _("La fin doit être postérieure ou égale au début.")
        if self.period_mode == self.Periode.RELATIVE and self.weeks_before + self.weeks_after == 0:
            errors["weeks_after"] = _("La période relative doit couvrir au moins une semaine.")
        if self.max_row_height and self.min_font_size and row_font_points(self.max_row_height) < self.min_font_size:
            errors["max_row_height"] = _(
                "Cette hauteur donne un texte de %(points).1f pt, sous la taille minimale de %(minimum)s pt."
            ) % {"points": row_font_points(self.max_row_height), "minimum": self.min_font_size}
        if 0 < self.name_max_width < 25:
            errors["name_max_width"] = _("Indiquez 0 (automatique) ou au moins 25 mm.")
        if 0 < self.column_max_width < 8:
            errors["column_max_width"] = _("Indiquez 0 (automatique) ou au moins 8 mm.")
        if errors:
            raise ValidationError(errors)