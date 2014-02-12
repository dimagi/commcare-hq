from .reports import MandE, Nurse, Relais, Outcomes, DangerSigns, Referrals, HealthCenter

CUSTOM_REPORTS = (
    ('CARE Benin Reports', (
        MandE,
        Nurse,
        Relais,
        DangerSigns,
        Referrals,
        HealthCenter,
    )),
    ('CARE Benin Special Reports', (
        Outcomes,
    )),
)
