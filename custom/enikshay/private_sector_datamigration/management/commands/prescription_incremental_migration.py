from django.core.management import BaseCommand

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.app_manager.models import CaseIndex
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.private_sector_datamigration.factory import EPISODE_CASE_TYPE, PRESCRIPTION_CASE_TYPE
from custom.enikshay.private_sector_datamigration.models import (
    EpisodePrescription_Jul7,
    EpisodePrescription_Jul19,
    Voucher_Jul19)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        self.domain = domain
        case_accessor = CaseAccessors(domain)
        for episode_case_id in case_accessor.get_case_ids_in_domain(type=EPISODE_CASE_TYPE):
            episode_case = case_accessor.get_case(episode_case_id)
            if self.should_run_incremental_migration(episode_case):
                for prescription in self.get_incremental_prescriptions(episode_case):
                    self.add_prescription(episode_case_id, prescription)

    @staticmethod
    def should_run_incremental_migration(episode_case):
        case_properties = episode_case.dynamic_case_properties()
        return (
            case_properties.get('enrolled_in_private') == 'true' and
            case_properties.get('migration_created_case') == 'true' and
            case_properties.get('migration_comment') == 'jul7'  # TODO - double check
        )

    @staticmethod
    def get_incremental_prescriptions(episode_case):
        beneficiary_id = episode_case.dynamic_case_properties()['migration_created_from_record']
        assert beneficiary_id.isdigit()

        new_prescriptions = EpisodePrescription_Jul19.objects.filter(beneficiaryId=beneficiary_id)
        old_prescriptions = EpisodePrescription_Jul7.objects.filter(beneficiaryId=beneficiary_id)

        old_prescription_ids = [old_prescription.id for old_prescription in old_prescriptions]

        return [
            new_prescription for new_prescription in new_prescriptions
            if new_prescription.id not in old_prescription_ids
        ]

    def add_prescription(self, episode_case_id, prescription):
        kwargs = {
            'attrs': {
                'case_type': PRESCRIPTION_CASE_TYPE,
                'close': True,
                'create': True,
                'owner_id': '-',
                'update': {
                    'date_ordered': prescription.creationDate.date(),
                    'name': prescription.productName,
                    'number_of_days_prescribed': prescription.numberOfDaysPrescribed,

                    'migration_comment': 'incremental_prescription',
                    'migration_created_case': 'true',
                    'migration_created_from_record': prescription.prescriptionID,
                }
            },
            'indices': [CaseIndex(
                CaseStructure(case_id=episode_case_id, walk_related=False),
                identifier='episode_of_prescription',
                relationship=CASE_INDEX_EXTENSION,
                related_type=EPISODE_CASE_TYPE,
            )],
        }

        try:
            voucher = Voucher_Jul19.objects.get(voucherNumber=prescription.voucherID)
            if voucher.voucherStatusId == '3':
                kwargs['attrs']['update']['date_fulfilled'] = voucher.voucherUsedDate.date()
        except Voucher_Jul19.DoesNotExist:
            pass

        CaseFactory(self.domain).create_or_update_cases([CaseStructure(**kwargs)])
