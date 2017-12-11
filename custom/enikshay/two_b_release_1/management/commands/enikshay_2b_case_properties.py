"""
eNikshay 2B - Release 1 Migration
https://docs.google.com/spreadsheets/d/1GFpMht-C-0cMCQu8rfqQG9lgW9omfYi3y2nUXHR8Pio/edit#gid=0
"""
from __future__ import absolute_import
import datetime
import logging
import phonenumbers
import sys
import uuid
from dimagi.utils.chunked import chunked
from dimagi.utils.decorators.memoized import memoized
from django.core.management import BaseCommand
from casexml.apps.case.const import CASE_INDEX_EXTENSION, CASE_INDEX_CHILD
from casexml.apps.case.mock import CaseStructure, CaseIndex, CaseFactory
from casexml.apps.case.xform import get_case_updates
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.util import strip_plus
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar
from custom.enikshay.case_utils import (
    CASE_TYPE_PERSON, CASE_TYPE_OCCURRENCE, CASE_TYPE_REFERRAL,
    CASE_TYPE_EPISODE, CASE_TYPE_TEST, CASE_TYPE_TRAIL,
    CASE_TYPE_DRTB_HIV_REFERRAL, CASE_TYPE_SECONDARY_OWNER)
from custom.enikshay.const import ENROLLED_IN_PRIVATE, CASE_VERSION
from six.moves import filter
from six.moves import input

logger = logging.getLogger('two_b_datamigration')

TEST_TO_LABEL = {
    'microscopy-zn': "Microscopy-ZN",
    'microscopy-fluorescent': "Microscopy-Fluorescent",
    'other_dst_tests': "Other DST Tests",
    'other_clinical_tests': "Other Clinical Tests",
    'tst': "TST",
    'igra': "IGRA",
    'chest_x-ray': "Chest X-ray",
    'cytopathology': "Cytopathology",
    'histopathology': "Histopathology",
    'cbnaat': "CBNAAT",
    'culture': "Culture",
    'dst': "DST",
    'line_probe_assay': "Line Probe Assay",
    'fl_line_probe_assay': "FL LPA",
    'sl_line_probe_assay': "SL LPA",
    'gene_sequencing': "Gene Sequencing",
    'other_clinical': "Other Clinical",
    'other_dst': "Other DST",
}


class PersonCaseSet(object):
    def __init__(self, person):
        self.person = person
        self.latest_occurrence = None
        self.occurrences = []
        self.episodes = []
        self.tests = []
        self.referrals = []
        self.trails = []
        self.drtb_hiv = []


def confirm(msg):
    if input(msg + "\n(y/n)") != 'y':
        sys.exit()


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help="The domain to migrate."
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help="actually create the cases. Without this flag, it's a dry run."
        )

    def handle(self, domain, **options):
        commit = options['commit']
        logger.info("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))
        migrator = ENikshay2BMigrator(domain, commit)
        migrator.migrate()
        logger.info("Migrated {} person cases".format(migrator.total_persons))
        logger.info("Migrated {} occurrence cases".format(migrator.total_occurrences))
        logger.info("Migrated {} episode cases".format(migrator.total_episodes))
        logger.info("Migrated {} test cases".format(migrator.total_tests))
        logger.info("Migrated {} referral cases".format(migrator.total_referrals))
        logger.info("Migrated {} trail cases".format(migrator.total_trails))
        logger.info("Created {} secondary_owner cases".format(migrator.total_secondary_owners))
        logger.info("Closed {} drtb_hiv cases".format(migrator.total_drtb_hiv))


class ENikshay2BMigrator(object):
    def __init__(self, domain, commit):
        self.domain = domain
        self.commit = commit
        self.accessor = CaseAccessors(self.domain)
        self.factory = CaseFactory(self.domain)

        self.total_persons = 0
        self.total_occurrences = 0
        self.total_episodes = 0
        self.total_tests = 0
        self.total_referrals = 0
        self.total_trails = 0
        self.total_secondary_owners = 0
        self.total_drtb_hiv = 0

    @property
    @memoized
    def locations(self):
        return {loc.location_id: loc for loc in
                SQLLocation.objects.filter(domain=self.domain).prefetch_related('location_type')}

    @property
    @memoized
    def location_ids_by_pk(self):
        return {loc.pk: loc.location_id for loc in self.locations.values()}

    def get_ancestors_by_type(self, location):
        """Get all direct ancestors found in self.locations"""
        ancestors_by_type = {location.location_type.code: location}
        loc = location
        while loc.parent_id and loc.parent_id in self.location_ids_by_pk:
            parent = self.locations[self.location_ids_by_pk[loc.parent_id]]
            ancestors_by_type[parent.location_type.code] = parent
            loc = parent
        return ancestors_by_type

    def migrate(self):
        person_ids = self.get_relevant_person_case_ids()
        persons = self.get_relevant_person_case_sets(person_ids)
        for person in with_progress_bar(persons, len(person_ids)):
            self.migrate_person_case_set(person)

    def get_relevant_person_case_ids(self):
        return self.accessor.get_case_ids_in_domain(CASE_TYPE_PERSON)

    def get_relevant_person_case_sets(self, person_ids):
        """
        Generator returning all relevant cases for the migration, grouped by person.

        This is a pretty nasty method, but it was the only way I could figure
        out how to group the queries together, rather than performing multiple
        queries per person case.
        """
        for person_chunk in chunked(person_ids, 100):
            person_chunk = list(filter(None, person_chunk))
            all_persons = {}  # case_id: PersonCaseSet
            for person in self.accessor.get_cases(person_chunk):
                # enrolled_in_private is blank/not set AND case_version is blank/not set
                # AND owner_id is within the location set being migrated
                if (person.get_case_property(ENROLLED_IN_PRIVATE) != 'true'
                        and not person.get_case_property(CASE_VERSION)):
                    all_persons[person.case_id] = PersonCaseSet(person)

            referrals_and_occurrences_to_person = {}
            type_to_bucket = {CASE_TYPE_OCCURRENCE: 'occurrences',
                              CASE_TYPE_REFERRAL: 'referrals',
                              CASE_TYPE_TRAIL: 'trails'}
            for case in self.accessor.get_reverse_indexed_cases(
                    [person_id for person_id in all_persons]):
                bucket = type_to_bucket.get(case.type, None)
                if bucket:
                    for index in case.indices:
                        if index.referenced_id in all_persons:
                            getattr(all_persons[index.referenced_id], bucket).append(case)
                            if bucket != 'trails':
                                referrals_and_occurrences_to_person[case.case_id] = index.referenced_id
                            break

            type_to_bucket = {CASE_TYPE_EPISODE: 'episodes',
                              CASE_TYPE_TEST: 'tests',
                              CASE_TYPE_TRAIL: 'trails'}
            episodes_to_person = {}
            for case in self.accessor.get_reverse_indexed_cases(list(referrals_and_occurrences_to_person)):
                bucket = type_to_bucket.get(case.type, None)
                if bucket:
                    for index in case.indices:
                        person_id = referrals_and_occurrences_to_person.get(index.referenced_id)
                        if person_id:
                            getattr(all_persons[person_id], bucket).append(case)
                            if case.type == CASE_TYPE_EPISODE:
                                episodes_to_person[case.case_id] = person_id
                            break

            for case in self.accessor.get_reverse_indexed_cases(list(episodes_to_person)):
                if case.type == CASE_TYPE_DRTB_HIV_REFERRAL:
                    for index in case.indices:
                        person_id = episodes_to_person.get(index.referenced_id)
                        if person_id:
                            all_persons[person_id].drtb_hiv.append(case)
                            break

            for person in all_persons.values():
                if person.occurrences:
                    person.latest_occurrence = max((case.opened_on, case)
                                                   for case in person.occurrences)[1]
                yield person

    def migrate_person_case_set(self, person):
        changes = list(filter(None,
            [self.migrate_person(person.person, person.occurrences, person.episodes)]
            + [self.migrate_occurrence(occurrence, person.episodes) for occurrence in person.occurrences]
            + [self.migrate_episode(episode, person.episodes) for episode in person.episodes]
            + [self.migrate_test(test, person.person, person.episodes) for test in person.tests]
            + [self.migrate_referral(referral, person.latest_occurrence) for referral in person.referrals]
            + [self.migrate_trail(trail, person.latest_occurrence) for trail in person.trails]
            + [self.open_secondary_owners(drtb_hiv, person.person, person.occurrences)
               for drtb_hiv in person.drtb_hiv]
            + [self.close_drtb_hiv(drtb_hiv) for drtb_hiv in person.drtb_hiv]
        ))
        if self.commit:
            self.factory.create_or_update_cases(changes)

    @staticmethod
    def get_open_occurrence(occurrences):
        occurrences = [case for case in occurrences
                       if not case.closed and case.type == CASE_TYPE_OCCURRENCE]
        return occurrences[0] if occurrences else None

    def migrate_person(self, person, occurrences, episodes):
        self.total_persons += 1
        occurrence = self.get_open_occurrence(occurrences)

        if occurrence:
            episodes = [case for case in episodes
                        if not case.closed and case.type == CASE_TYPE_EPISODE
                        and any([index.referenced_id == occurrence.case_id for index in case.indices])]
            episode = episodes[0] if episodes else None
        else:
            episode = None

        props = {
            'updated_by_migration': 'enikshay_2b_case_properties',
            'enrolled_in_private': 'false',
            'case_version': '20',
            'area': person.get_case_property('phi_area'),
            'language_code': 'hin',
            'referred_outside_enikshay_date': person.get_case_property('date_referred_out'),
            'referred_outside_enikshay_by_id': person.get_case_property('referred_by_id'),
        }
        if episode:
            props.update({
                'current_episode_type': episode.get_case_property('episode_type'),
                'alcohol_history': episode.get_case_property('alcohol_history'),
                'alcohol_deaddiction': episode.get_case_property('alcohol_deaddiction'),
                'tobacco_user': episode.get_case_property('tobacco_user'),
                'occupation': episode.get_case_property('occupation'),
                'phone_number_other': episode.get_case_property('phone_number_other'),
            })

        phone_number = person.get_case_property('phone_number')
        if phone_number:
            props['contact_phone_number'] = strip_plus(
                phonenumbers.format_number(
                    phonenumbers.parse(phone_number, "IN"),
                    phonenumbers.PhoneNumberFormat.E164)
            )

        location = self.locations.get(person.owner_id)
        if location:
            dataset = 'real' if location.metadata.get('is_test') == 'no' else 'test'
            props['dataset'] = person.get_case_property('dataset') or dataset

            if location.location_type.code == 'phi':
                props['phi_name'] = location.name
            ancestors_by_type = self.get_ancestors_by_type(location)
            if 'tu' in ancestors_by_type:
                props['tu_name'] = ancestors_by_type['tu'].name
                props['tu_id'] = ancestors_by_type['tu'].location_id
            if 'dto' in ancestors_by_type:
                props['dto_name'] = ancestors_by_type['dto'].name
                props['dto_id'] = ancestors_by_type['dto'].location_id

        return CaseStructure(
            case_id=person.case_id,
            walk_related=False,
            attrs={
                "create": False,
                "owner_id": person.owner_id or '-',
                "update": props,
            },
        )

    def migrate_occurrence(self, occurrence, episodes):
        self.total_occurrences += 1
        episodes = [(case.opened_on, case) for case in episodes
                    if case.type == CASE_TYPE_EPISODE
                    and any([index.referenced_id == occurrence.case_id for index in case.indices])]
        if not episodes:
            return None

        episode = max(episodes)[1]  # Most recently opened episode for the occurrence

        props = {
            'updated_by_migration': 'enikshay_2b_case_properties',
            'current_episode_type': episode.get_case_property('episode_type'),
            'disease_classification': episode.get_case_property('disease_classification'),
            'site_choice': episode.get_case_property('site_choice'),
            'site_detail': episode.get_case_property('site_detail'),
            'key_population_status': episode.get_case_property('key_population_status'),
            'key_populations': episode.get_case_property('key_populations'),
        }

        return CaseStructure(
            case_id=occurrence.case_id,
            walk_related=False,
            attrs={
                "create": False,
                "update": props,
            },
        )

    @staticmethod
    def _get_last_episode_id(indices, episodes):
        def is_episode_of_occurrence(episode, occurrence_id):
            return any(index.referenced_id == occurrence_id for index in episode.indices)

        occurrence_ids = [index.referenced_id for index in indices
                          if index.referenced_type == CASE_TYPE_OCCURRENCE]
        occurrence_id = occurrence_ids[0] if occurrence_ids else None
        episodes = [(case.opened_on, case.case_id) for case in episodes
                    if is_episode_of_occurrence(case, occurrence_id)]
        return max(episodes)[1] if episodes else None

    def migrate_episode(self, episode, episodes):
        self.total_episodes += 1

        latest_episode_id = self._get_last_episode_id(episode.indices, episodes)
        test_type = episode.get_case_property('test_confirming_diagnosis')
        props = {
            'updated_by_migration': 'enikshay_2b_case_properties',
            'is_active': 'yes' if episode.case_id == latest_episode_id and not episode.closed else 'no',
            'dosage_display': episode.get_case_property('full_dosage'),
            'dosage_summary': episode.get_case_property('full_dosage'),
            'rft_general': 'diagnosis_dstb',
            'diagnosis_test_type': test_type,
            'diagnosis_test_type_label': TEST_TO_LABEL.get(test_type, ""),
        }

        treatment_status = episode.get_case_property('treatment_status')
        treatment_initiated = episode.get_case_property('treatment_initiated')
        diagnosing_facility_id = episode.get_case_property('diagnosing_facility_id')
        treatment_initiating_facility_id = episode.get_case_property('treatment_initiating_facility_id')
        if treatment_status == 'second_line_treatment':
            props['treatment_status'] = 'initiated_second_line_treatment'
        # skipping patients who don't have a diagnosing and treatment IDs (so we don't set the wrong status)
        elif treatment_initiated == 'yes_phi' and diagnosing_facility_id and treatment_initiating_facility_id \
                and diagnosing_facility_id != treatment_initiating_facility_id:
            props['treatment_status'] = 'initiated_outside_facility'
        # skipping patients who don't have a diagnosing and treatment IDs (so we don't set the wrong status)
        elif treatment_initiated == 'yes_phi' and diagnosing_facility_id and treatment_initiating_facility_id:
            props['treatment_status'] = 'initiated_first_line_treatment'
        elif treatment_initiated == 'yes_private':
            props['treatment_status'] = 'initiated_outside_rntcp'

        if treatment_status and treatment_status != 'yes_phi' and treatment_status != 'yes_private':
            props['treatment_initiated'] = 'no'

        if not episode.get_case_property('date_of_diagnosis'):
            props['date_of_diagnosis'] = episode.get_case_property('date_reported')

        return CaseStructure(
            case_id=episode.case_id,
            walk_related=False,
            attrs={
                "create": False,
                "update": props,
            },
        )

    @staticmethod
    def _get_result_recorded_form(test):
        """get last form that set result_recorded to yes"""
        for action in reversed(test.actions):
            for update in get_case_updates(action.form):
                if (
                    update.id == test.case_id
                    and update.get_update_action()
                    and update.get_update_action().dynamic_properties.get('result_recorded') == 'yes'
                ):
                    return action.form.form_data

    @staticmethod
    def _get_path(path, form_data):
        block = form_data
        while path:
            block = block.get(path[0], {})
            path = path[1:]
        return block

    def migrate_test(self, test, person, episodes):
        self.total_tests += 1
        props = {
            'updated_by_migration': 'enikshay_2b_case_properties',
            'is_direct_test_entry': 'no',
            'rft_drtb_diagnosis': test.get_case_property('diagnostic_drtb_test_reason'),
            'dataset': person.get_case_property('dataset'),
            'episode_case_id': self._get_last_episode_id(test.indices, episodes),
        }

        if not props['dataset']:
            location = self.locations.get(person.owner_id)
            if location:
                props['dataset'] = 'real' if location.metadata.get('is_test') == 'no' else 'test'

        if test.get_case_property('follow_up_test_reason') == 'private_ntm':
            props['rft_general'] = 'diagnosis_dstb'
            props['rft_dstb_diagnosis'] = 'private_ntm'
        else:
            props['rft_general'] = {
                'diagnostic': 'diagnosis_dstb',
                'diagnosis_dstb': 'diagnosis_dstb',
                'follow_up': 'follow_up_dstb',
                "follow_up_dstb": "follow_up_dstb",
                'diagnosis_drtb': 'diagnosis_drtb',
            }.get(test.get_case_property('purpose_of_testing'), "")
            props['rft_dstb_diagnosis'] = test.get_case_property('diagnostic_test_reason')
            props['rft_dstb_followup'] = test.get_case_property('follow_up_test_reason')

        if test.get_case_property('result') == 'tb_detected':
            detected = 'TB Detected'
        elif test.get_case_property('result') == 'tb_not_detected':
            detected = 'TB Not Detected'
        else:
            detected = None
        bacilli_count = test.get_case_property('max_bacilli_count')
        resistance_display = None

        if (test.get_case_property('test_type_value') == 'cbnaat'
                and test.get_case_property('result_recorded') == 'yes'):
            form_data = self._get_result_recorded_form(test)
            sample_a = self._get_path(
                'update_test_result cbnaat ql_sample_a sample_a_rif_resistance_result'.split(),
                form_data,
            )
            sample_b = self._get_path(
                'update_test_result cbnaat ql_sample_b sample_b_rif_resistance_result'.split(),
                form_data,
            )
            if sample_a == 'detected' or sample_b == 'detected':
                detected = 'TB Detected'
                props['drug_resistance_list'] = 'r'
                resistance_display = 'R: Res'
            elif sample_a == 'not_detected' or sample_b == 'not_detected':
                detected = 'TB Not Detected'
                props['drug_sensitive_list'] = 'r'
            else:
                detected = ''

        props['result_summary_display'] = '\n'.join(filter(None, [
            detected,
            test.get_case_property('result_grade'),
            resistance_display,
            'Count of bacilli: {}'.format(bacilli_count) if bacilli_count else None,
            test.get_case_property('clinical_remarks'),
        ]))

        return CaseStructure(
            case_id=test.case_id,
            walk_related=False,
            attrs={
                "create": False,
                "update": props,
            },
        )

    def migrate_referral(self, referral, occurrence):
        self.total_referrals += 1
        prop = referral.get_case_property
        props = {
            'updated_by_migration': 'enikshay_2b_case_properties',
            'referral_initiated_date': (prop('referral_date') or prop('date_of_referral')),
            'referred_to_name': prop('referred_to_location_name'),
            'referred_by_name': prop('referred_by'),
            'referral_rejection_reason_other_detail': prop('reason_for_refusal_other_detail'),
            'referral_rejection_reason': prop('reason_for_refusal'),
            'referral_closed_date': prop('acceptance_refusal_date'),
            'accepted_by_name': prop('phi'),
        }

        if occurrence:
            index_kwargs = {'indices': [CaseIndex(
                occurrence,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=CASE_TYPE_OCCURRENCE,
            )]}
        else:
            index_kwargs = {}

        return CaseStructure(
            case_id=referral.case_id,
            walk_related=False,
            attrs={
                "create": False,
                "update": props,
            },
            **index_kwargs
        )

    def migrate_trail(self, trail, occurrence):
        self.total_trails += 1
        if occurrence:
            index_kwargs = {'indices': [CaseIndex(
                occurrence,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=CASE_TYPE_OCCURRENCE,
            )]}
        else:
            index_kwargs = {}

        return CaseStructure(
            case_id=trail.case_id,
            walk_related=False,
            attrs={
                "create": False,
                "update": {'updated_by_migration': 'enikshay_2b_case_properties'},
            },
            **index_kwargs
        )

    def open_secondary_owners(self, drtb_hiv, person, occurrences):
        if not occurrences:
            return None

        self.total_secondary_owners += 1

        occurrence = max((case.opened_on, case) for case in occurrences)[1]
        index_kwargs = {'indices': [CaseIndex(
            occurrence,
            identifier='host',
            relationship=CASE_INDEX_EXTENSION,
            related_type=CASE_TYPE_OCCURRENCE,
        )]}

        location = self.locations.get(person.owner_id)
        props = {
            'updated_by_migration': 'enikshay_2b_case_properties',
            'secondary_owner_type': 'drtb-hiv',
            'secondary_owner_name': location.name if location else "",
        }

        return CaseStructure(
            case_id=uuid.uuid4().hex,
            walk_related=False,
            attrs={
                'create': True,
                'case_type': CASE_TYPE_SECONDARY_OWNER,
                'owner_id': drtb_hiv.owner_id,
                'case_name': person.get_case_property('person_id') + "-drtb-hiv",
                'update': props,
            },
            **index_kwargs
        )

    def close_drtb_hiv(self, drtb_hiv):
        self.total_drtb_hiv += 1
        return CaseStructure(
            case_id=drtb_hiv.case_id,
            walk_related=False,
            attrs={
                "create": False,
                "close": True,
                "update": {},
            },
        )
