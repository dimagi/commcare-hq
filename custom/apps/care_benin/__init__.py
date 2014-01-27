from .reports import MandE, Nurse, Relais, Outcomes, DangerSigns, Referrals, HealthCenter

CUSTOM_REPORTS = (
    ('CARE Benin Reports', (
        MandE,
        Nurse,
        Relais,
        Outcomes,
        DangerSigns,
        Referrals,
        HealthCenter,
    )),
)
