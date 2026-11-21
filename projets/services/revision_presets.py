from decimal import Decimal


FORMULES_REVISION_PREDEFINIES = (
    {
        "code": "INSTALLATION_CHANTIER",
        "libelle": "Installation de chantier et études d'exécution",
        "k": Decimal("0.15"),
        "est_index_global": True,
        "termes": (("SIMPLE", Decimal("0.85"), "ING", None, None),),
    },
    {
        "code": "VOIRIES",
        "libelle": "Voiries",
        "k": Decimal("0.15"),
        "est_index_global": True,
        "termes": (("SIMPLE", Decimal("0.85"), "TR5Bis", None, None),),
    },
    {
        "code": "ASSAINISSEMENT",
        "libelle": "Assainissement",
        "k": Decimal("0.15"),
        "est_index_global": True,
        "termes": (("SIMPLE", Decimal("0.85"), "TR2", None, None),),
    },
    {
        "code": "ALIMENTATION_EAU_POTABLE",
        "libelle": "Alimentation en eau potable",
        "k": Decimal("0.15"),
        "termes": (
            ("COMPOSITE", Decimal("0.20"), None, "S", "Chtp"),
            ("SIMPLE", Decimal("0.15"), "Mtn", None, None),
            ("SIMPLE", Decimal("0.10"), "Mc3", None, None),
            ("SIMPLE", Decimal("0.30"), "Pg", None, None),
            ("SIMPLE", Decimal("0.10"), "Tpc", None, None),
        ),
    },
    {
        "code": "ELECTRIFICATION_MT_BT",
        "libelle": "Électrification MT/BT",
        "k": Decimal("0.15"),
        "termes": (
            ("COMPOSITE", Decimal("0.20"), None, "S", "Ch"),
            ("SIMPLE", Decimal("0.15"), "Mtn", None, None),
            ("SIMPLE", Decimal("0.11"), "Cu", None, None),
            ("SIMPLE", Decimal("0.22"), "Ap", None, None),
            ("SIMPLE", Decimal("0.12"), "Ale", None, None),
            ("SIMPLE", Decimal("0.05"), "Mc3", None, None),
        ),
    },
    {
        "code": "ECLAIRAGE_EXTERIEUR",
        "libelle": "Éclairage extérieur",
        "k": Decimal("0.15"),
        "termes": (
            ("COMPOSITE", Decimal("0.20"), None, "S", "Ch"),
            ("SIMPLE", Decimal("0.15"), "Mtn", None, None),
            ("SIMPLE", Decimal("0.10"), "Cu", None, None),
            ("SIMPLE", Decimal("0.25"), "Ap", None, None),
            ("SIMPLE", Decimal("0.15"), "Mc3", None, None),
        ),
    },
    {
        "code": "TELECOM_VIDEOSURVEILLANCE",
        "libelle": "Réseau télécom et génie civil de la vidéosurveillance",
        "k": Decimal("0.15"),
        "termes": (
            ("COMPOSITE", Decimal("0.20"), None, "S", "Chtp"),
            ("SIMPLE", Decimal("0.15"), "Mtn", None, None),
            ("SIMPLE", Decimal("0.20"), "Mc3", None, None),
            ("SIMPLE", Decimal("0.20"), "Tpc", None, None),
            ("SIMPLE", Decimal("0.10"), "Cs", None, None),
        ),
    },
    {
        "code": "AMENAGEMENT_DIVERS",
        "libelle": "Travaux d'aménagement divers",
        "k": Decimal("0.15"),
        "est_index_global": True,
        "termes": (("SIMPLE", Decimal("0.85"), "BAT6", None, None),),
    },
)

FORMULES_REVISION_PAR_CODE = {
    formule["code"]: formule for formule in FORMULES_REVISION_PREDEFINIES
}


def decimal_latex(valeur):
    return format(valeur, "f").rstrip("0").rstrip(".") or "0"


def formule_latex(k, termes):
    morceaux = [decimal_latex(k)]
    for type_terme, coefficient, index_simple, index_a, index_b in termes:
        coefficient_latex = decimal_latex(coefficient)
        if type_terme == "COMPOSITE":
            index_a = rf"\mathrm{{{index_a}}}"
            index_b = rf"\mathrm{{{index_b}}}"
            expression = (
                rf"\frac{{{coefficient_latex}{index_a}(1+{index_b})}}"
                rf"{{{index_a}_0(1+{index_b}_0)}}"
            )
        else:
            index = rf"\mathrm{{{index_simple}}}"
            expression = rf"{coefficient_latex}\frac{{{index}}}{{{index}_0}}"
        morceaux.append(rf"+ {expression}")
    return rf"P = P_0\left({ ' '.join(morceaux) }\right)"


for formule_predefinie in FORMULES_REVISION_PREDEFINIES:
    formule_predefinie["latex"] = formule_latex(
        formule_predefinie["k"],
        formule_predefinie["termes"],
    )


def initial_termes_formule(predefinie, index_par_symbole):
    return [
        {
            "type_terme": type_terme,
            "coefficient": coefficient,
            "index_simple": (
                index_par_symbole[index_simple].pk if index_simple else ""
            ),
            "index_composite_a": (
                index_par_symbole[index_a].pk if index_a else ""
            ),
            "index_composite_b": (
                index_par_symbole[index_b].pk if index_b else ""
            ),
        }
        for type_terme, coefficient, index_simple, index_a, index_b
        in predefinie["termes"]
    ]
