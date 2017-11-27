from __future__ import absolute_import
from __future__ import print_function
import csv

from django.core.management.base import BaseCommand
from datetime import datetime, date

from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID

from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.const import PERSON_CASE_2B_VERSION
from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_TEST,
)
from custom.enikshay.case_utils import update_case

DOMAIN = "enikshay"


class Command(BaseCommand):
    """
    Iterate over cases for a particular case type to make required modifications
    """
    person_case_relevant_props = [
        'aadhaar_number',
        'age',
        'age_entered',
        'dob',
        'referred_by_id',
        'referred_outside_enikshay_by_id',
    ]

    episode_case_relevant_props = [
        'treatment_outcome',
        'close_reason',
        'episode_type',
        'case_definition',
        'dstb_to_drtb_transition_no_initiation',
        'treatment_initiated',
    ]

    test_case_relevant_props = [
        'rft_general',
        'result_recorded',
        'date_tested',
    ]

    def add_arguments(self, parser):
        parser.add_argument('case_type')
        parser.add_argument('--dry_run', action='store_true')

    def handle(self, case_type, *args, **options):
        self.dry_run = options.get('dry_run')
        accessor = CaseAccessors(DOMAIN)
        result_file_path = "{case_type}_cases_update_report_{timestamp}.csv".format(
            case_type=case_type, timestamp=datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        )
        if case_type == "all":
            case_types = ['person', 'episode', 'test']
        else:
            case_types = [case_type]
        with open(result_file_path, 'w') as output_buffer:
            writer = csv.DictWriter(output_buffer, fieldnames=self._get_headers(case_types))
            writer.writeheader()
            for person_case_id in self._get_person_case_ids_to_process():
                person_case = accessor.get_case(person_case_id)
                if person_case.dynamic_case_properties().get('case_version') == PERSON_CASE_2B_VERSION:
                    # reset all collections for next iteration
                    occurrence_cases = []

                    if "person" in case_types:
                        case_status = self.get_case_status(person_case)
                        case_status = self.update_case(person_case.get_id, case_status)
                        writer.writerow(case_status)

                    if "episode" in case_types:
                        occurrence_cases = [case for case in accessor.get_reverse_indexed_cases([person_case_id])
                                            if case.type == CASE_TYPE_OCCURRENCE]
                        for occurrence_case in occurrence_cases:
                            episode_cases = [case for case in
                                             accessor.get_reverse_indexed_cases([occurrence_case.get_id])
                                             if case.type == CASE_TYPE_EPISODE]
                            for episode_case in episode_cases:
                                case_status = self.get_case_status(episode_case, episode_cases=episode_cases)
                                case_status = self.update_case(episode_case.get_id, case_status)
                                writer.writerow(case_status)

                    if "test" in case_types:
                        if not occurrence_cases:
                            occurrence_cases = [case for case in
                                                accessor.get_reverse_indexed_cases([person_case_id])
                                                if case.type == CASE_TYPE_OCCURRENCE]
                        for occurrence_case in occurrence_cases:
                            test_cases = [case for case in
                                          accessor.get_reverse_indexed_cases([occurrence_case.get_id])
                                          if case.type == CASE_TYPE_TEST]
                            recently_opened_episode_case = None
                            for test_case in test_cases:
                                # For tests that are DSTB follow up tests, rft_general = follow_up_dstb
                                # and result_recorded = yes
                                recently_opened_episode_case, case_status = self.get_case_status(
                                    test_case, recently_opened_episode_case=recently_opened_episode_case,
                                    occurrence_case=occurrence_case)
                                case_status = self.update_case(test_case.get_id, case_status)
                                writer.writerow(case_status)

    def update_case(self, case_id, case_status):
        """
        :param case_id: id of case to be updated
        :param case_status: case update status which has updates dict and other information about case update
        :return: update case status
        """
        case_updates = case_status.get('updates')
        if case_updates:
            case_updates['datamigration_20_to_21'] = 'yes'
            if not self.dry_run:
                if case_updates.get('debug'):
                    to_update = case_updates.copy()
                    del to_update['debug']
                    update_case(DOMAIN, case_id, to_update)
                else:
                    update_case(DOMAIN, case_id, case_updates)
            case_status['updated'] = 'yes'
        else:
            case_status['updated'] = 'no'
        return case_status

    def _get_headers(self, case_types):
        headers = ['case_type', 'case_id']
        if 'person' in case_types:
            headers += (self.person_case_relevant_props + ['owner_id'])
        if 'episode' in case_types:
            headers += self.episode_case_relevant_props
        if 'test' in case_types:
            headers += self.test_case_relevant_props
        headers += ['updates', 'updated']
        return headers

    def get_case_status(self, case, episode_cases=None, recently_opened_episode_case=None, occurrence_case=None):
        if case.type == "person":
            return self.get_person_case_status(case)
        elif case.type == "episode":
            return self.get_episode_case_status(case, episode_cases)
        elif case.type == "test":
            return self.get_test_case_status(
                case, recently_opened_episode_case, occurrence_case)

    def get_person_case_status(self, person_case):
        person_case_props = person_case.dynamic_case_properties()
        props_status = {'case_type': 'person', 'case_id': person_case.get_id}
        for prop in self.person_case_relevant_props:
            props_status[prop] = person_case_props.get(prop)
        props_status['owner_id'] = person_case.owner_id
        props_status['updates'] = self.person_case_updates(person_case)
        return props_status

    def get_episode_case_status(self, episode_case, episode_cases):
        episode_case_props = episode_case.dynamic_case_properties()
        props_status = {'case_type': 'episode', 'case_id': episode_case.get_id}
        for prop in self.episode_case_relevant_props:
            props_status[prop] = episode_case_props.get(prop)
        props_status['updates'] = self.episode_case_updates(episode_case, episode_cases)
        return props_status

    def get_test_case_status(self, test_case, recently_opened_episode_case, occurrence_case):
        test_case_props = test_case.dynamic_case_properties()
        props_status = {'case_type': 'test', 'case_id': test_case.get_id}
        for prop in self.test_case_relevant_props:
            props_status[prop] = test_case_props.get(prop)
        recently_opened_episode_case, props_status['updates'] = self.test_case_updates(
            test_case, recently_opened_episode_case, occurrence_case)
        return recently_opened_episode_case, props_status

    @staticmethod
    def person_case_updates(person_case):
        # person.case_minor_version = 21
        props_to_update = {
            'case_minor_version': '21',
        }

        person_case_props = person_case.dynamic_case_properties()

        # If person.aadhaar_number != '', save person.aadhaar_number_obfuscated which is
        # person.aadhaar number masked with *s except the last 4 digits
        aadhar_num = person_case_props.get('aadhaar_number')
        if aadhar_num:
            # mask everything except last 4 digits
            aadhar_num_length = len(aadhar_num)
            props_to_update['aadhaar_number_obfuscated'] = '*' * (aadhar_num_length - 4) + aadhar_num[-4:]

        # if person.age is blank/null and person.age_entered != blank/null
        # then set person.age = person.age_entered.
        # else if person.age = '' and person.dob != '', person.age = int((today() - person.dob) / 365.25)
        if not person_case_props.get('age') and person_case_props.get('age_entered'):
            props_to_update['age'] = person_case_props.get('age_entered')
        elif not person_case_props.get('age') and person_case_props.get('dob'):
            props_to_update['age'] = int(
                (date.today() - datetime.strptime(person_case_props.get('dob'), "%Y-%m-%d").date()).days / 365.25
            )

        # Set person.referred_outside_enikshay_by_id = person.referred_by_id if person.referred_by_id exists
        if person_case_props.get('referred_by_id'):
            props_to_update['referred_outside_enikshay_by_id'] = person_case_props.get('referred_by_id')

        # if the owner id is not _archive_ set person.referred_outside_enikshay_date and
        # person.referred_outside_enikshay_by_id to blank
        if person_case.owner_id != ARCHIVED_CASE_OWNER_ID:
            props_to_update['referred_outside_enikshay_date'] = ""
            props_to_update['referred_outside_enikshay_by_id'] = ""

        return props_to_update

    @staticmethod
    def episode_case_updates(episode_case, episode_cases):
        def any_other_confirmed_drtb_episode(this_case, all_cases):
            for a_case in all_cases:
                if a_case.get_id != this_case.get_id:
                    if a_case.dynamic_case_properties().get('episode_type') == 'confirmed_drtb':
                        return True

        props_to_update = {}
        episode_case_props = episode_case.dynamic_case_properties()
        # if treatment_outcome = duplicate or treatment_outcome = invalid_registration we should blank the
        # treatment_outcome and instead set episode.close_reason = the value of treatment_outcome
        # (Reverse the treatment_status / outcome change from Remove Person)
        if episode_case_props.get('treatment_outcome') in ['duplicate', 'invalid_registration']:
            props_to_update['close_reason'] = episode_case_props.get('treatment_outcome')
            props_to_update['treatment_outcome'] = ""

        # Set episode.case_definition = microbiological if episode_type = confirmed_drtb
        if episode_case_props.get('episode_type') == "confirmed_drtb":
            props_to_update['case_definition'] = 'microbiological'

        # episode.dstb_to_drtb_transition_no_initiation = yes
        # IF episode_type = confirmed_tb AND (treatment_initiated = 'no' or treatment_initiated = '')
        # AND there exists another episode with episode_type=confirmed_drtb for the same occurrence
        if (episode_case_props.get('episode_type') == "confirmed_tb" and
                episode_case_props.get('treatment_initiated', "") in ["no", ""] and
                any_other_confirmed_drtb_episode(episode_case, episode_cases)):
            props_to_update['dstb_to_drtb_transition_no_initiation'] = 'yes'
        return props_to_update

    @staticmethod
    def test_case_updates(test_case, recently_opened_episode_case, occurrence_case):
        def get_recently_opened_episode_case(occ_case):
            accessor = CaseAccessors(DOMAIN)
            episode_cases = [case for case in accessor.get_reverse_indexed_cases([occ_case.get_id])
                             if case.type == CASE_TYPE_EPISODE and
                             case.dynamic_case_properties().get('episode_type') == "confirmed_tb"]
            episode_cases.sort(key=lambda x: x.opened_on, reverse=True)
            if episode_cases:
                return episode_cases[0]

        props_to_update = {}
        test_case_props = test_case.dynamic_case_properties()
        if (test_case_props.get('rft_general') == "follow_up_dstb" and
                test_case_props.get('result_recorded') == "yes"):
            if not recently_opened_episode_case:
                recently_opened_episode_case = get_recently_opened_episode_case(occurrence_case)
            if recently_opened_episode_case:
                props_to_update['debug'] = {'episode_case_id': recently_opened_episode_case.get_id}
                treatment_initiation_date = (recently_opened_episode_case.dynamic_case_properties()
                                             .get('treatment_initiation_date'))
                props_to_update['debug']['treatment_initiation_date'] = treatment_initiation_date
                date_tested = test_case_props.get('date_tested')
                props_to_update['debug']['date_tested'] = date_tested
                if treatment_initiation_date and date_tested:
                    d1 = datetime.strptime(date_tested, "%Y-%m-%d")
                    d2 = datetime.strptime(treatment_initiation_date, "%Y-%m-%d")
                    props_to_update['rft_dstb_follow_up_treatment_month'] = (
                        (d1.year - d2.year) * 12 + d1.month - d2.month)
        return recently_opened_episode_case, props_to_update

    @staticmethod
    def _get_person_case_ids_to_process():
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            case_ids = (
                CommCareCaseSQL.objects
                .using(db)
                .filter(domain=DOMAIN, type="person")
                .values_list('case_id', flat=True)
            )
            num_case_ids = len(case_ids)
            print("processing %d docs from db %s" % (num_case_ids, db))
            for i, case_id in enumerate(case_ids):
                yield case_id
                if i % 1000 == 0:
                    print("processed %d / %d docs from db %s" % (i, num_case_ids, db))
