from .reports import MEGeneral, MEMedical, Nurse, Outcomes, DangerSigns, Referrals, HealthCenter

CUSTOM_REPORTS = (
    ('CARE Benin Reports', (
        MEGeneral,
        MEMedical,
        Nurse,
        Outcomes,
        DangerSigns,
        Referrals,
        HealthCenter,
    )),
)
