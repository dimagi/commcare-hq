from datetime import date, timedelta

from django.core.management import BaseCommand

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.private_sector_datamigration.factory import ADHERENCE_CASE_TYPE, EPISODE_CASE_TYPE
from custom.enikshay.private_sector_datamigration.models import (
    Adherence_Jul7,
    Adherence_Jul19,
    Episode_Jul7,
)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        self.domain = domain
        case_accessor = CaseAccessors(domain)
        for episode_case_id in case_accessor.get_case_ids_in_domain(type=EPISODE_CASE_TYPE):
            episode_case = case_accessor.get_case(episode_case_id)
            if self.should_run_incremental_migration(episode_case):
                for adherence in self.get_incremental_adherences(episode_case):
                    self.add_adherence(episode_case_id, adherence)

    @staticmethod
    def should_run_incremental_migration(episode_case):
        case_properties = episode_case.dynamic_case_properties()
        return (
            case_properties.get('enrolled_in_private') == 'true' and
            case_properties.get('migration_created_case') == 'true' and
            case_properties.get('migration_comment') == 'jul7'  # TODO - double check
        )

    @staticmethod
    def get_incremental_adherences(episode_case):
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

    def add_adherence(self, episode_case_id, adherence):
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

        CaseFactory(self.domain).create_or_update_cases([CaseStructure(**kwargs)])
