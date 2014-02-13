from .reports import MandE, Nurse, Relais, Outcomes, DangerSigns, Referrals, HealthCenter

CUSTOM_REPORTS = (
    ('CARE Benin Special Reports', (
        MandE,
        Nurse,
        Relais,
        DangerSigns,
        Referrals,
        HealthCenter,
        Outcomes,
    )),
)
