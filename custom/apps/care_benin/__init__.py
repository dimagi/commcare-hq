from .reports import MandE, Nurse, Outcomes, DangerSigns, Referrals, HealthCenter

CUSTOM_REPORTS = (
    ('CARE Benin Reports', (
        MandE,
        Nurse,
        Outcomes,
        DangerSigns,
        Referrals,
        HealthCenter,
    )),
)
