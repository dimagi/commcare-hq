from django.core.management.base import BaseCommand

from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.util.log import with_progress_bar

from custom.enikshay.case_utils import get_all_episode_ids, iter_all_active_person_episode_cases


class ENikshayBatchCaseUpdaterCommand(BaseCommand):

    @property
    def updater(self):
        raise NotImplementedError("No updater class set")

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        batch_size = 100
        updates = []
        errors = []

        case_ids = get_all_episode_ids(domain)
        cases = iter_all_active_person_episode_cases(domain, case_ids)

        for person, episode in with_progress_bar(cases, len(case_ids)):
            update_json = {}
            for updater in self.updaters:
                try:
                    update_json.update(updater(self.domain, episode).update_json())
                except Exception as e:
                    error = [episode.case_id, episode.domain, updater.__name__, e]
                    errors.append(error)
                    print "{}: {} - {}".format(*error)
            if update_json:
                updates.append((episode.case_id, update_json, False))
            if len(updates) >= batch_size:
                bulk_update_cases(domain, updates)
                updates = []

        if len(updates) > 0:
            bulk_update_cases(domain, updates)
