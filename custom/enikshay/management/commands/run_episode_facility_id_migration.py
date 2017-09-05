from django.core.management import BaseCommand

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.apps.hqcase.utils import update_case
from custom.enikshay.exceptions import ENikshayCaseNotFound
from custom.enikshay.model_migration_sets import EpisodeFacilityIDMigration


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('episode_case_ids', nargs='*')

    def handle(self, domain, episode_case_ids, **options):
        case_accessor = CaseAccessors(domain)

        if not episode_case_ids:
            episode_case_ids = case_accessor.get_case_ids_in_domain(type='episode')

        errorred_case_ids = []

        for episode_case_id in episode_case_ids:
            print episode_case_id
            try:
                episode_case = case_accessor.get_case(episode_case_id)
                try:
                    updater = EpisodeFacilityIDMigration(domain, episode_case)
                except ENikshayCaseNotFound:
                    continue
                update_json = updater.update_json()
                if update_json:
                    update_case(domain, episode_case_id, update_json)
            except:
                errorred_case_ids.append(episode_case_id)
        print len(errorred_case_ids)
        print errorred_case_ids
