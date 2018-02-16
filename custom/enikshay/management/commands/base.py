from __future__ import absolute_import
from __future__ import print_function
import csv

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

        parser.add_argument(
            '--commit',
            action='store_true',
        )

    def handle(self, domain, **options):
        print("Running {}".format(self.updater.__name__))
        if options['commit']:
            print("Committing changes")
        else:
            print("Dry Run")

        batch_size = 100
        updates = []
        errors = []

        case_ids = get_all_episode_ids(domain)
        cases = iter_all_active_person_episode_cases(domain, case_ids)

        for person, episode in with_progress_bar(cases, len(case_ids), oneline=False):
            try:
                update_json = self.updater(domain, person, episode).update_json()
            except Exception as e:
                errors.append([person.case_id, episode.case_id, episode.domain, e])
                continue

            if update_json:
                updates.append((episode.case_id, update_json, False))
            if len(updates) >= batch_size:
                if options['commit']:
                    bulk_update_cases(domain, updates, self.__module__)
                updates = []

        if len(updates) > 0:
            if options['commit']:
                bulk_update_cases(domain, updates, self.__module__)

        self.write_errors(errors)

    @property
    def log_filename(self):
        return "{}_errors.csv".format(self.updater.__name__)

    def write_errors(self, errors):
        if not errors:
            return None

        with open(self.log_filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(['Person ID', 'Episode ID', 'Domain', 'Error'])
            writer.writerows(errors)
