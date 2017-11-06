import csv
from datetime import date, timedelta

from django.core.management import BaseCommand

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from dimagi.utils.chunked import chunked

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

from custom.enikshay.private_sector_datamigration.factory import ADHERENCE_CASE_TYPE, EPISODE_CASE_TYPE
from custom.enikshay.private_sector_datamigration.models import (
    Adherence_Jul7,
    Adherence_Jul19,
    Episode_Jul7,
)

CHUNKSIZE = 150


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
        commit = options['commit']
        case_accessor = CaseAccessors(domain)

        case_ids = set(case_ids or case_accessor.get_case_ids_in_domain(type=EPISODE_CASE_TYPE))
        if options['exclude_case_ids']:
            case_ids = case_ids - set(options['exclude_case_ids'])

        with open(log_filename, 'w') as log_file:
            self.writer = csv.writer(log_file)
            self.writer.writerow(self.headers)

            for adherence_cases in chunked(self.new_adherences(domain, case_ids), CHUNKSIZE):
                for adherence_case in adherence_cases:
                    self.record_to_log_file(adherence_case.case_id, adherence_case.attrs, adherence_case.indices)
                if commit:
                    CaseFactory(domain).create_or_update_cases(list(adherence_cases))

    def new_adherences(self, domain, case_ids):
        for episode_case in CaseAccessors(domain).iter_cases(with_progress_bar(case_ids)):
            if self._should_run_incremental_migration(episode_case):
                for adherence in self._get_incremental_adherences(episode_case):
                    yield self._add_adherence(episode_case.case_id, adherence)

    def record_to_log_file(self, case_id, attrs, indices):
        self.writer.writerow(
            [case_id, indices[0].related_structure.case_id]
            + [attrs['update'].get(case_prop, '') for case_prop in self.case_properties]
        )

    @staticmethod
    def _should_run_incremental_migration(episode_case):
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
    def _get_incremental_adherences(episode_case):
        beneficiary_id = episode_case.dynamic_case_properties()['migration_created_from_record']
        assert beneficiary_id.isdigit()
        episodes = Episode_Jul7.objects.filter(beneficiaryID=beneficiary_id).order_by('-episodeDisplayID')
        if episodes:
            episode_id = episodes[0].episodeID
            assert episode_id.isdigit()
        else:
            return []

        new_adherences = Adherence_Jul19.objects.filter(episodeId=episode_id)
        old_adherences = Adherence_Jul7.objects.filter(episodeId=episode_id)

        old_adherence_ids = [old_adherence.id for old_adherence in old_adherences]

        return [
            new_adherence for new_adherence in new_adherences
            if new_adherence.id not in old_adherence_ids
        ]

    @staticmethod
    def _add_adherence(episode_case_id, adherence):
        kwargs = {
            'attrs': {
                'case_type': ADHERENCE_CASE_TYPE,
                'create': True,
                'date_opened': adherence.creationDate,
                'owner_id': '-',
                'update': {
                    'adherence_date': adherence.doseDate.date(),
                    'adherence_report_source': adherence.adherence_report_source,
                    'adherence_source': adherence.adherence_source,
                    'adherence_value': adherence.adherence_value,
                    'name': adherence.doseDate.date(),

                    'migration_comment': 'incremental_adherence',
                    'migration_created_case': 'true',
                    'migration_created_from_record': adherence.adherenceId,
                }
            },
            'indices': [CaseIndex(
                CaseStructure(case_id=episode_case_id, walk_related=False),
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=EPISODE_CASE_TYPE,
            )],
        }

        if date.today() - adherence.doseDate.date() > timedelta(days=30):
            kwargs['attrs']['close'] = True
            kwargs['attrs']['update']['adherence_closure_reason'] = 'historical'
        else:
            kwargs['attrs']['close'] = False

        return CaseStructure(**kwargs)
