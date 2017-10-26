import csv
import uuid

from django.core.management import BaseCommand

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

from custom.enikshay.private_sector_datamigration.factory import EPISODE_CASE_TYPE, PRESCRIPTION_CASE_TYPE
from custom.enikshay.private_sector_datamigration.models import (
    EpisodePrescription_Jul7,
    EpisodePrescription_Jul19,
    Voucher_Jul19,
)


class Command(BaseCommand):

    case_id_headers = [
        'case_id',
        'extension_case_id',
    ]

    case_properties = [
        'date_ordered',
        'name',
        'number_of_days_prescribed',
        'migration_comment',
        'migration_created_case',
        'migration_created_from_record',
        'date_fulfilled',
    ]

    headers = case_id_headers + case_properties

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('log_filename')
        parser.add_argument('case_ids', nargs='*')
        parser.add_argument('--exclude_case_ids', nargs='+')
        parser.add_argument('--commit', action='store_true')

    def handle(self, domain, log_filename, case_ids, **options):
        self.domain = domain
        self.commit = options['commit']
        case_accessor = CaseAccessors(domain)

        case_ids = set(case_ids or case_accessor.get_case_ids_in_domain(type=EPISODE_CASE_TYPE))
        if options['exclude_case_ids']:
            case_ids = case_ids - set(options['exclude_case_ids'])

        with open(log_filename, 'w') as log_file:
            self.writer = csv.writer(log_file)
            self.writer.writerow(self.headers)

            for episode_case in case_accessor.iter_cases(with_progress_bar(case_ids)):
                if self.should_run_incremental_migration(episode_case):
                    for prescription in self.get_incremental_prescriptions(episode_case):
                        self.add_prescription(episode_case.case_id, prescription)

    @staticmethod
    def should_run_incremental_migration(episode_case):
        case_properties = episode_case.dynamic_case_properties()
        return (
            case_properties.get('enrolled_in_private') == 'true' and
            case_properties.get('migration_created_case') == 'true' and
            case_properties.get('migration_comment') in [
                'july_7',
                'july_7-unassigned',
                'july_7_unassigned',
            ]
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
                'case_id': uuid.uuid4().hex,
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

        self.record_to_log_file(kwargs)

        if self.commit:
            CaseFactory(self.domain).create_or_update_cases([CaseStructure(**kwargs)])

    def record_to_log_file(self, kwargs):
        self.writer.writerow(
            [kwargs['attrs']['case_id'], kwargs['indices'][0].related_structure.case_id]
            + [kwargs['attrs']['update'].get(case_prop, '') for case_prop in self.case_properties]
        )
