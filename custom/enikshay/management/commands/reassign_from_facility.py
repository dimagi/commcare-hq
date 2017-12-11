from __future__ import absolute_import, print_function

import csv
import datetime

import six
from django.core.management.base import BaseCommand

from casexml.apps.case.util import get_all_changes_to_case_property
from corehq.apps.hqcase.utils import bulk_update_cases
from corehq.util.log import with_progress_bar
from custom.enikshay.case_utils import (
    get_all_episode_ids,
    iter_all_active_person_episode_cases,
)
from dimagi.utils.chunked import chunked

MJK = 'df661f7aaf384e9c98d88beeedb83050'
ALERT_INDIA = 'af50474dd6b747b29a2934b7b0359bdf'


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--commit', action='store_true')

    def handle(self, domain, **options):
        commit = options['commit']

        filename = "reassign_from_facility-{}.csv".format(datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S'))
        columns = ['case_id', 'facility_assigned_to', 'owner_id',
                   'last_owner_id_changed', 'last_facility_assigned_to_changed', 'note']

        case_ids = get_all_episode_ids(domain)
        cases = iter_all_active_person_episode_cases(domain, case_ids, sector='private')
        bad_cases = []
        to_update = []
        for person, _ in with_progress_bar(cases, length=len(case_ids)):
            facility_assigned_to = person.get_case_property('facility_assigned_to')
            owner_id = person.owner_id
            if facility_assigned_to == owner_id:
                continue
            if not facility_assigned_to and owner_id in [MJK, ALERT_INDIA]:
                # cases with a blank facility and owned by MJK or Alert-India are known about already
                continue

            owner_id_changes = sorted(get_all_changes_to_case_property(person, 'owner_id'),
                                      key=lambda c: c.modified_on, reverse=True)
            facility_id_changes = sorted(get_all_changes_to_case_property(person, 'facility_assigned_to'),
                                         key=lambda c: c.modified_on, reverse=True)

            case_dict = {
                'case_id': person.case_id,
                'facility_assigned_to': facility_assigned_to,
                'owner_id': owner_id,
            }
            try:
                case_dict['last_owner_id_changed'] = owner_id_changes[0].modified_on
                case_dict['last_facility_assigned_to_changed'] = facility_id_changes[0].modified_on
                if owner_id_changes[0].modified_on < facility_id_changes[0].modified_on:
                    case_dict['note'] = 'updated'
                    to_update.append((person.case_id, {"owner_id": facility_assigned_to}, False))
                else:
                    case_dict['note'] = 'not updated'
            except IndexError as e:
                case_dict['last_owner_id_changed'] = None
                case_dict['last_facility_assigned_to_changed'] = None
                case_dict['note'] = 'no changes found: {}'.format(six.text_type(e))

            bad_cases.append(case_dict)

        if commit:
            print("Updating: ", len(to_update), " cases")
            for update in chunked(to_update, 100):
                bulk_update_cases(domain, update, self.__module__)
        else:
            print("Would have updated: ", len(to_update), " cases")

        with open(filename, 'w') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for case in bad_cases:
                writer.writerow(case)
