"""
eNikshay 2B - Release 1 Migration
https://docs.google.com/spreadsheets/d/1GFpMht-C-0cMCQu8rfqQG9lgW9omfYi3y2nUXHR8Pio/edit#gid=0
"""
import datetime
import logging
from collections import namedtuple
from dimagi.utils.chunked import chunked
from dimagi.utils.decorators.memoized import memoized
from django.core.management import BaseCommand
from casexml.apps.case.mock import CaseStructure, CaseIndex, CaseFactory
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar
from custom.enikshay.case_utils import (
    CASE_TYPE_PERSON, CASE_TYPE_OCCURRENCE, CASE_TYPE_REFERRAL, CASE_TYPE_EPISODE,
    CASE_TYPE_TEST, CASE_TYPE_TRAIL)
from custom.enikshay.const import ENROLLED_IN_PRIVATE, CASE_VERSION

logger = logging.getLogger('two_b_datamigration')

PersonCaseSet = namedtuple('PersonCaseSet', 'person occurrences episodes tests referrals trails')


def confirm(msg):
    if raw_input(msg + "\n(y/n)") != 'y':
        sys.exit()


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help="The domain to migrate."
        )
        parser.add_argument(
            'dto_id',
            help="The id of the dto location to migrate."
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help="actually create the cases. Without this flag, it's a dry run."
        )

    def handle(self, domain, dto_id, **options):
        commit = options['commit']
        logger.info("Starting {} migration on {} at {}".format(
            "real" if commit else "fake", domain, datetime.datetime.utcnow()
        ))
        dto = SQLLocation.objects.get(
            domain=domain, location_id=dto_id, location_type__code='dto')
        num_descendants = dto.get_descendants(include_self=True).count()
        confirm("Do you want to migrate the DTO '{}', which has {} descendants?"
                .format(dto.get_path_display(), num_descendants))
        migrator = ENikshay2BMigrator(domain, dto, commit)


class ENikshay2BMigrator(object):
    def __init__(self, domain, dto, commit):
        self.domain = domain
        self.dto = dto
        self.commit = commit
        self.accessor = CaseAccessors(self.domain)
        self.factory = CaseFactory(self.domain)

    @property
    @memoized
    def locations(self):
        return {loc.location_id: loc for loc in
                self.dto.get_descendants(include_self=True).prefetch_related('location_type')}

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
        location_owners = self.dto.get_descendants(include_self=True).location_ids()
        return self.accessor.get_open_case_ids_in_domain_by_type(CASE_TYPE_PERSON, location_owners)

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
                    all_persons[person.case_id] = PersonCaseSet(
                        person=person,
                        occurrences=[],
                        episodes=[],
                        tests=[],
                        referrals=[],
                        trails=[],
                    )

            referrals_and_occurrences_to_person = {}
            type_to_bucket = {CASE_TYPE_OCCURRENCE: 'occurrences',
                              CASE_TYPE_REFERRAL: 'referrals'}
            for case in self.accessor.get_reverse_indexed_cases(
                    [person_id for person_id in all_persons]):
                bucket = type_to_bucket.get(case.type, None)
                if bucket:
                    for index in case.indices:
                        if index.referenced_id in all_persons:
                            getattr(all_persons[index.referenced_id], bucket).append(case)
                            referrals_and_occurrences_to_person[case.case_id] = index.referenced_id
                            break

            type_to_bucket = {CASE_TYPE_EPISODE: 'episodes',
                              CASE_TYPE_TEST: 'tests',
                              CASE_TYPE_TRAIL: 'trails'}
            for case in self.accessor.get_reverse_indexed_cases(referrals_and_occurrences_to_person.keys()):
                bucket = type_to_bucket.get(case.type, None)
                if bucket:
                    for index in case.indices:
                        person_id = referrals_and_occurrences_to_person.get(index.referenced_id)
                        if person_id:
                            getattr(all_persons[person_id], bucket).append(case)
                            break

            for person_case_set in all_persons.values():
                yield person_case_set

    def migrate_person_case_set(self, person):
        self.factory.create_or_update_cases(filter(None,
            [self.migrate_person(person.person, person.occurrences, person.episodes)]
            + [self.migrate_occurrence(occurrence, person.episodes) for occurrence in person.occurrences]
        ))

    @staticmethod
    def get_open_occurrence(occurrences):
        occurrences = [case for case in occurrences
                       if not case.closed and case.type == CASE_TYPE_OCCURRENCE]
        return occurrences[0] if occurrences else None

    def migrate_person(self, person, occurrences, episodes):
        occurrence = self.get_open_occurrence(occurrences)

        if occurrence:
            episodes = [case for case in episodes
                        if not case.closed and case.type == CASE_TYPE_EPISODE
                        and any([index.referenced_id == occurrence.case_id for index in case.indices])
                        and case.dynamic_case_properties().get('episode_type') == "confirmed_tb"]
            episode = episodes[0] if episodes else None
        else:
            episode = None

        props = {
            'enrolled_in_private': 'false',
            'case_version': '20',
            'area': person.get_case_property('phi_area'),
            'language_code': 'hin',
            'referred_outside_enikshay_date': person.get_case_property('date_referred_out'),
            'referred_outside_enikshay_by_id': person.get_case_property('date_by_id'),
        }
        if episode:
            props.update({
                'current_episode_type': episode.get_case_property('episode_type'),
                'alcohol_history': episode.get_case_property('alcohol_history'),
                'alcohol_deaddiction': episode.get_case_property('alcohol_deaddiction'),
                'tobacco_user': episode.get_case_property('tobacco_user'),
                'occupation': episode.get_case_property('occupation'),
                'nikshay_id': episode.get_case_property('nikshay_id'),
                'phone_number_other': episode.get_case_property('phone_number_other'),
            })

        phone_number = person.get_case_property('phone_number')
        if phone_number:
            # TODO check if it already begins with 91 or has a certain length?
            props['contact_phone_number'] = '91' + phone_number

        location = self.locations.get(person.owner_id)
        if location:
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
        episodes = [(case.opened_on, case) for case in episodes
                    if case.type == CASE_TYPE_EPISODE
                    and any([index.referenced_id == occurrence.case_id for index in case.indices])
                    and case.dynamic_case_properties().get('episode_type') == "confirmed_tb"]
        if not episodes:
            return None

        episode = max(episodes)[1]  # Most recently opened episode for the occurrence

        props = {
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
