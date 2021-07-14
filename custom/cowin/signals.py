from django.dispatch import receiver

from casexml.apps.case.signals import case_post_save

from corehq.motech.repeaters.signals import create_repeat_records
from custom.cowin.repeaters import (
    BeneficiaryRegistrationRepeater,
    BeneficiaryVaccinationRepeater,
)


@receiver(case_post_save, dispatch_uid="create_cowin_repeat_records")
def create_cowin_repeat_records(sender, case, **kwargs):
    create_repeat_records(BeneficiaryRegistrationRepeater, case)
    create_repeat_records(BeneficiaryVaccinationRepeater, case)
