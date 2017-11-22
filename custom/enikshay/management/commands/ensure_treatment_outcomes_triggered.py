import csv
from django.core.management.base import BaseCommand

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from custom.enikshay.case_utils import get_person_case_from_episode
from custom.enikshay.integrations.nikshay.repeaters import valid_nikshay_patient_registration
from custom.enikshay.integrations.utils import is_valid_archived_submission
from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
    TREATMENT_OUTCOME,
)
from custom.enikshay.integrations.nikshay.field_mappings import (
    treatment_outcome
)
DOMAIN = "enikshay"
from custom.enikshay.exceptions import NikshayLocationNotFound


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        accessor = CaseAccessors(DOMAIN)
        with open('ensure_treatment_outcomes.csv', 'w') as csv_file:
            writer = csv.writer(csv_file)
            for episode_case_id in self.iter_episode_case_ids():
                episode_case = accessor.get_case(episode_case_id)
                try:
                    if self.treatment_outcome_notifiable(episode_case):
                        if episode_case.get_case_property('treatment_outcome_nikshay_registered') != 'true':
                            writer.writerow([episode_case_id, episode_case.get_case_property('treatment_outcome_date'),
                                             episode_case.get_case_property('migration_created_case'),
                                             episode_case.get_case_property('treatment_outcome_nikshay_error')
                                             ])
                            print("Episode: %s treatment not notified" % episode_case_id)
                except NikshayLocationNotFound:
                    person_case = get_person_case_from_episode(episode_case.domain, episode_case)
                    writer.writerow([episode_case_id, episode_case.get_case_property('treatment_outcome_date'),
                                     episode_case.get_case_property('migration_created_case'),
                                     episode_case.get_case_property('treatment_outcome_nikshay_error'),
                                     person_case.owner_id
                                     ])

    @staticmethod
    def treatment_outcome_notifiable(episode_case):
        episode_case_properties = episode_case.dynamic_case_properties()
        return (
            not (episode_case_properties.get(ENROLLED_IN_PRIVATE) == 'true') and
            (  # has a nikshay id already or is a valid submission probably waiting notification
                episode_case_properties.get('nikshay_id') or
                valid_nikshay_patient_registration(episode_case_properties)
            ) and
            episode_case_properties.get(TREATMENT_OUTCOME) in treatment_outcome.keys() and
            is_valid_archived_submission(episode_case)
        )

    @staticmethod
    def iter_episode_case_ids():
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            case_ids = (
                CommCareCaseSQL.objects
                .using(db)
                .filter(domain=DOMAIN, type="episode")
                .values_list('case_id', flat=True)
            )
            num_case_ids = len(case_ids)
            for i, case_id in enumerate(case_ids):
                yield case_id
                if i % 1000 == 0:
                    print("processed %d / %d docs from db %s" % (i, num_case_ids, db))
