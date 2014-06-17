from casexml.apps.case.signals import cases_received
from custom.succeed.utils import SUCCEED_DOMAIN, update_patient_target_dates


def update_patient_cases(sender, xform, cases, **kwargs):
    for case in cases:
        if case.domain == SUCCEED_DOMAIN and case.type == 'participant':
            update_patient_target_dates(case)


cases_received.connect(update_patient_cases)