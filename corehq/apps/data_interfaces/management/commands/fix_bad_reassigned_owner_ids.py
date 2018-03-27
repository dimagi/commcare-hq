from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import itertools
from six.moves import map

from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseFactory
from corehq.apps.domain.models import Domain
from corehq.apps.es.users import UserES
from corehq.apps.es.groups import GroupES, is_case_sharing
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.util.log import with_progress_bar


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domains',
            metavar='domain',
            nargs='*',
        )
        parser.add_argument(
            '--execute',
            action='store_true',
        )
        parser.add_argument(
            '--log_filename',
            default='fix_bad_reassigned_owner_ids.txt',
        )

    def handle(self, domains, **options):
        execute = options['execute']
        log_filename = options['log_filename']
        if not domains:
            domains = Domain.get_all_names()

        with open(log_filename, 'w') as log_file:
            for domain in with_progress_bar(domains):
                valid_owner_ids = get_valid_owner_ids(domain)
                for case in get_affected_cases(domain):
                    if case.owner_id in valid_owner_ids:
                        continue

                    matching_owner_ids = [
                        valid_owner_id for valid_owner_id in valid_owner_ids
                        if case.owner_id in valid_owner_id
                    ]
                    if len(matching_owner_ids) == 1:
                        matched_owner_id = matching_owner_ids[0]
                        print('%s: Assign case %s to owner %s' % (domain, case.case_id, matched_owner_id), file=log_file)
                        if execute:
                            CaseFactory(domain).update_case(case.case_id, update={'owner_id': matched_owner_id})
                    elif len(matching_owner_ids) == 0:
                        print('%s: No owner found for case %s' % (domain, case.case_id), file=log_file)
                    elif len(matching_owner_ids) > 1:
                        print('%s: Impossible to determine owner for case %s' % (domain, case.case_id), file=log_file)


def get_valid_owner_ids(domain):
    return list(itertools.chain(
        get_case_sharing_group_ids(domain),
        get_location_ids(domain),
        get_user_ids(domain)
    ))


def get_affected_cases(domain):
    form_accessor = FormAccessors(domain)
    for form_id in form_accessor.iter_form_ids_by_xmlns('http://commcarehq.org/cloudcare/custom-edit'):
        case_id = form_accessor.get_form(form_id).form_data['case']['@case_id']
        yield CaseAccessors(domain).get_case(case_id)


def get_case_sharing_group_ids(domain):
    return map(
        lambda result: result['_id'],
        GroupES().domain(domain).filter(is_case_sharing()).not_deleted().fields('_id').run().hits
    )


def get_location_ids(domain):
    return map(
        lambda result: result['location_id'],
        SQLLocation.active_objects.filter(domain=domain).values('location_id')
    )


def get_user_ids(domain):
    return map(
        lambda result: result['_id'],
        UserES().domain(domain).fields('_id').run().hits
    )
