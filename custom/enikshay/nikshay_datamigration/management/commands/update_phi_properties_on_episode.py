from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseFactory

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.nikshay_datamigration.factory import get_nikshay_codes_to_location
from custom.enikshay.nikshay_datamigration.models import PatientDetail


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--write',
            action='store_true',
            default=False,
        )

    def handle(self, domain, write, **options):
        nikshay_ids = NIKSHAY_IDS.split()
        nikshay_codes_to_location = get_nikshay_codes_to_location(domain)

        for nikshay_id in nikshay_ids:
            update_properties_by_nikshay_id(nikshay_id, domain, nikshay_codes_to_location, write)


def get_phi_location_id(patient_detail, nikshay_code_to_phi):
    nikshay_code = '%s-%s-%d-%d' % (
        patient_detail.scode,
        patient_detail.Dtocode,
        patient_detail.Tbunitcode,
        patient_detail.PHI,
    )

    return nikshay_code_to_phi[nikshay_code].location_id


def update_properties_by_nikshay_id(nikshay_id, domain, nikshay_code_to_phi, write):
    case_accessor = CaseAccessors(domain)
    episode_cases_by_nikshay_id = case_accessor.get_cases_by_external_id(nikshay_id, case_type='episode')
    assert len(episode_cases_by_nikshay_id) == 1
    episode_case = episode_cases_by_nikshay_id[0]
    assert episode_case.dynamic_case_properties()['migration_created_case'] == 'true'

    patient_detail = PatientDetail.objects.get(PregId=nikshay_id)

    for prop in [
        'diagnosing_facility_id',
        'treatment_initiating_facility_id',
    ]:
        if prop not in episode_case.dynamic_case_properties():
            if write:
                CaseFactory(domain=domain).update_case(
                    episode_case.case_id,
                    update={prop: get_phi_location_id(patient_detail, nikshay_code_to_phi)}
                )
        else:
            print 'skip %s for %s' % (prop, nikshay_id)


NIKSHAY_IDS = """
MH-PRL-03-16-0133
"""
