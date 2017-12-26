from __future__ import absolute_import
from __future__ import print_function
import csv
import datetime
from django.core.management.base import BaseCommand
from unidecode import unidecode

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.case_search.models import CLAIM_CASE_TYPE
from corehq.apps.locations.models import SQLLocation
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

from custom.enikshay.case_utils import (
    CASE_TYPE_EPISODE,
    CASE_TYPE_INVESTIGATION,
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_PERSON,
    CASE_TYPE_REFERRAL,
    CASE_TYPE_SECONDARY_OWNER,
    CASE_TYPE_TEST,
    CASE_TYPE_TRAIL,
    get_all_vouchers_from_person,
)
from custom.enikshay.duplicate_ids import (
    get_duplicated_case_stubs, ReadableIdGenerator)
from custom.enikshay.user_setup import join_chunked


class Command(BaseCommand):
    help = """
    Finds cases with duplicate IDs and marks all but one of each ID as a duplicate
    """
    logfile_fields = [
        # person-case properties always logged
        'person_case_id', 'person_name', 'dto_name', 'phi_name', 'owner_id',
        'dob', 'phone_number', 'dataset', 'enrolled_in_private',
        # case-specific properties that may be updated
        'case_type', 'case_id', 'name', 'person_id', 'person_id_flat',
        'person_id_deprecated', 'person_id_flat_deprecated',
        'person_id_at_request', 'person_id_flat_at_request',
    ]

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
        )

    def handle(self, domain, **options):
        self.domain = domain
        self.accessor = CaseAccessors(domain)
        commit = options['commit']
        self.id_generator = ReadableIdGenerator(domain, commit)

        filename = '{}-{}.csv'.format(self.__module__.split('.')[-1],
                                      datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S'))
        print("Logging actions to {}".format(filename))
        with open(filename, 'w') as f:
            logfile = csv.DictWriter(f, self.logfile_fields, extrasaction='ignore')
            logfile.writeheader()

            print("Finding duplicates")
            bad_case_stubs = get_duplicated_case_stubs(self.domain, CASE_TYPE_PERSON)
            bad_cases = self.accessor.iter_cases(stub['case_id'] for stub in bad_case_stubs)

            print("Processing duplicate cases")
            for person_case in with_progress_bar(bad_cases, len(bad_case_stubs)):
                if person_case.get_case_property('enrolled_in_private') == 'true':
                    updates = list(filter(None, self.get_private_updates(person_case)))
                else:
                    updates = list(filter(None, self.get_public_updates(person_case)))

                person_info = self.get_person_case_info(person_case)
                for case, update in updates:
                    log = {unidecode(k): unidecode(v)
                           for d in [person_info, update] for k, v in d.items() if v}
                    log['case_type'] = case.type
                    log['case_id'] = case.case_id
                    logfile.writerow(log)

                if commit:
                    update_tuples = [(case.case_id, update, False)
                                     for case, update in updates]
                    bulk_update_cases(self.domain, update_tuples, self.__module__)

    @memoized
    def get_private_phi_and_dto(self, owner_id):
        try:
            owner = SQLLocation.objects.get(domain=self.domain, location_id=owner_id)
            dto_name = (owner.get_ancestors(include_self=True)
                        .get(location_type__code='dto')
                        .name)
            return owner.name, dto_name
        except SQLLocation.DoesNotExist:
            return None, None

    def get_person_case_info(self, person_case):
        """Pull info that we want to log but not update"""
        person = person_case.dynamic_case_properties()
        if person.get('enrolled_in_private') == 'true':
            phi_name, dto_name = self.get_private_phi_and_dto(person_case.owner_id)
        else:
            dto_name = person.get('dto_name')
            phi_name = person.get('phi_name')
        return {
            'person_case_id': person_case.case_id,
            'person_name': ' '.join(filter(None, [person.get('first_name'), person.get('last_name')])),
            'enrolled_in_private': person.get('enrolled_in_private'),
            'dto_name': dto_name,
            'phi_name': phi_name,
            'owner_id': person_case.owner_id,
            'dob': person.get('dob'),
            'phone_number': person.get('phone_number'),
            'dataset': person.get('dataset'),
        }

    def get_public_updates(self, person_case):
        """ Get updates for a public sector person case and a bunch of its children
        https://docs.google.com/document/d/1NS5ozgk7w-2AADsrdTtjgqODkgWIEaCw6eqQ0cLg138/edit#
        """
        old_id = person_case.get_case_property('person_id')
        new_flat_id = self.id_generator.get_next()
        new_id = join_chunked(new_flat_id, 3)
        yield get_case_update(person_case, {
            'person_id_deprecated': old_id,
            'person_id_flat_deprecated': person_case.get_case_property('person_id_flat'),
            'person_id': new_id,
            'person_id_flat': new_flat_id,
        })

        for person_child_case in self.accessor.get_reverse_indexed_cases([person_case.case_id]):

            # Update occurrence and claim names
            if person_child_case.type in (CASE_TYPE_OCCURRENCE, CLAIM_CASE_TYPE):
                yield get_name_update(person_child_case, old_id, new_id)

            # look at all extensions of the occurrence cases
            if person_child_case.type == CASE_TYPE_OCCURRENCE:
                for case in self.accessor.get_reverse_indexed_cases([person_child_case.case_id]):

                    # update the names of episode, secondary_owner, trail, and referral cases
                    if case.type in (CASE_TYPE_EPISODE, CASE_TYPE_SECONDARY_OWNER,
                                     CASE_TYPE_TRAIL, CASE_TYPE_REFERRAL):
                        yield get_name_update(case, old_id, new_id)

                    if case.type == CASE_TYPE_TEST:
                        yield get_case_update(case, {
                            'person_id_at_request': new_id,
                            'person_id_flat_at_request': new_flat_id
                        })

                    if case.type == CASE_TYPE_EPISODE:
                        for investigation_case in self.accessor.get_reverse_indexed_cases([case.case_id]):
                            if investigation_case.type == CASE_TYPE_INVESTIGATION:
                                yield get_name_update(investigation_case, old_id, new_id)

    def get_private_updates(self, person_case):
        """ Get updates for a private sector person case and a bunch of its children
        https://docs.google.com/document/d/1NS5ozgk7w-2AADsrdTtjgqODkgWIEaCw6eqQ0cLg138/edit#
        """
        old_id = person_case.get_case_property('person_id')
        new_flat_id = self.id_generator.get_next()
        new_id = join_chunked(new_flat_id, 3)
        yield get_case_update(person_case, {
            'person_id_deprecated': old_id,
            'person_id_flat_deprecated': person_case.get_case_property('person_id_flat'),
            'person_id': new_id,
            'person_id_flat': new_flat_id,
        })

        for voucher_case in get_all_vouchers_from_person(self.domain, person_case):
            yield get_case_update(voucher_case, {
                'person_id': new_id,
                'person_id_flat': new_flat_id,
            })


def get_case_update(case, update):
    # check that this is actually an update, else return None
    if any(case.get_case_property(k) != v for k, v in update.items()):
        return (case, update)


def get_name_update(case, old_id, new_id):
    if case.get_case_property('name') and old_id:
        new_name = case.get_case_property('name').replace(old_id, new_id)
        return get_case_update(case, {'name': new_name})
