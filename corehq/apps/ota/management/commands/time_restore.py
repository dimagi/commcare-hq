
import datetime

from django.core.management.base import BaseCommand

import csv342 as csv
from couchdbkit.resource import ResourceNotFound
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_current_app_doc
from corehq.apps.hqadmin.views.users import AdminRestoreView
from corehq.apps.ota.views import get_restore_response
from corehq.apps.users.models import CouchUser
from corehq.util.dates import get_timestamp_for_filename


class Command(BaseCommand):
    help = ("Runs a restore for the passed in user(s) and generates a csv with timing information. Example: "
            "./manage.py time_restore test@ccqa.commcarehq.org,ethan@ccqa.commcarehq.org --app_id=123abc")

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('usernames')
        parser.add_argument('--app_id')

    def handle(self, **options):
        domain = options['domain']
        usernames = options['usernames'].split(',')
        app_id = options['app_id']
        users = [CouchUser.get_by_username(username) for username in usernames]
        for username in usernames:
            if not CouchUser.get_by_username(username):
                print("User '{}' not found".format(username))
                return
        if app_id:
            try:
                get_current_app_doc(domain, app_id)
            except ResourceNotFound:
                print("App '{}' not found".format(app_id))
                return

        headers, rows = _get_headers_and_rows(domain, users, app_id)
        totals_row = _calculate_totals_row(headers, rows)

        filename = "restore_timings_{}.csv".format(get_timestamp_for_filename())
        with open(filename, 'w') as f:
            writer = csv.DictWriter(f, headers)
            writer.writeheader()
            writer.writerows(rows)
            writer.writerow(totals_row)


def _get_headers_and_rows(domain, users, app_id):
    fixture_names = set()
    rows = []
    for user in users:
        response, timing_context = get_restore_response(
            domain, user, app_id=app_id,
        )
        timing_dict = timing_context.to_dict()
        xml_payload = etree.fromstring(b''.join(response.streaming_content))
        stats = AdminRestoreView.get_stats_from_xml(xml_payload)
        row = {
            'timestamp': datetime.datetime.now().isoformat(),
            'username': user.username,
            'total_duration': timing_dict['duration'],
            'num_cases': stats['num_cases'],
            'num_locations': stats['num_locations'],
            'num_v1_reports': stats['num_v1_reports'],
            'num_v2_reports': stats['num_v2_reports'],
            'num_ledger_entries': stats['num_ledger_entries'],
        }
        for provider in timing_dict['subs']:
            row[provider['name']] = provider['duration']
            if provider['name'] == 'FixtureElementProvider':
                for fixture in provider['subs']:
                    fixture_names.add(fixture['name'])
                    row[fixture['name']] = fixture['duration']
        rows.append(row)
        print("Restore for '{}' took {} seconds to generate"
              .format(user.username, timing_dict['duration']))

    headers = [
        'username',
        'timestamp',
        'total_duration',
        'num_cases',
        'num_locations',
        'num_v1_reports',
        'num_v2_reports',
        'num_ledger_entries',
        'RegistrationElementProvider',
        'CasePayloadProvider',
        'SyncElementProvider',
        'FixtureElementProvider',
    ] + sorted(fixture_names)

    return headers, rows


def _calculate_totals_row(headers, rows):
    totals_row = {'username': 'TOTAL', 'timestamp': '---'}
    for header in headers[2:]:
        totals_row[header] = sum(row.get(header, 0) for row in rows)
    return totals_row
