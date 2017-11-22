from __future__ import absolute_import
import csv
from django.core.management.base import BaseCommand
from dimagi.utils.chunked import chunked
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar


from custom.enikshay.case_utils import (
    get_all_episode_confirmed_tb_cases_from_person,
    get_adherence_cases_from_episode,
)


class Command(BaseCommand):
    """Soft deletes adherence cases for a list of beneficiaries
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            'id_file',
            help=("A csv file containing a list of all of the beneficiary ids"
                  " whose adherence cases should be deleted")
        )
        parser.add_argument(
            '--log_file',
            default="deleted_adherence_cases.csv",
            help=("An output file containing a list of all deleted adherence cases")
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help="actually delete the cases. Without this flag, it's a dry run."
        )

    def handle(self, domain, id_file, **options):
        adherence_case_ids = set()
        with open(id_file) as f:
            reader = csv.DictReader(f)
            person_ids = [row['beneficiary_id'] for row in reader]

        with open(options['log_file'], 'w') as f:
            writer = csv.writer(f)
            writer.writerow([
                "beneficiary_id", "person_name", "adherence_id", "adherence_date",
                "adherence_source", "adherence_value", "adherence_confidence",
                "merm_imei", "merm_extra_info"
            ])

            for person_id in person_ids:
                episodes = get_all_episode_confirmed_tb_cases_from_person(domain, person_id)
                for episode in episodes:
                    episode_adherence_cases = get_adherence_cases_from_episode(domain, episode.case_id)
                    dots_adherence_cases = [adherence for adherence in episode_adherence_cases
                                            if adherence.get_case_property('adherence_source') == '99DOTS']
                    writer.writerows([[
                        person_id,
                        adherence.get_case_property('person_name'),
                        adherence.case_id,
                        adherence.get_case_property('adherence_date'),
                        adherence.get_case_property('adherence_source'),
                        adherence.get_case_property('adherence_value'),
                        adherence.get_case_property('adherence_confidence'),
                        adherence.get_case_property('merm_imei'),
                        adherence.get_case_property('merm_extra_info'),
                    ] for adherence in dots_adherence_cases])
                    adherence_case_ids.update(adherence.case_id for adherence in dots_adherence_cases)

        if options['commit']:
            print "Deleting {} cases".format(len(adherence_case_ids))
            for ids in with_progress_bar(
                    chunked(adherence_case_ids, 100), length=len(adherence_case_ids)):
                CaseAccessors(domain).soft_delete_cases(list(ids), deletion_id="delete_99dots_adherence")
