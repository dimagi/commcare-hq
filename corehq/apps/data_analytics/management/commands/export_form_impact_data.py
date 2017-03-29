from collections import defaultdict

import csv

import dateutil
from dateutil.relativedelta import relativedelta

from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand

from corehq.apps.data_analytics.esaccessors import get_forms_for_users
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser


class Command(BaseCommand):
    """
        Export form impact data to given csv file
        e.g. ./manage.py export_form_impact_data February-2017 example.csv
    """
    help = 'Adds data to MALT table from given files'

    def add_arguments(self, parser):
        parser.add_argument(
            'month_year'
        )
        parser.add_argument(
            'file_path'
        )

    def handle(self, month_year, file_path, **options):
        month_year_parsed = dateutil.parser.parse('1-' + month_year)
        start_date = month_year_parsed.replace(day=1)
        end_date = start_date + relativedelta(day=1, months=+1, microseconds=-1)

        user_id_to_data = defaultdict(lambda: {
            'xmlns_set': set(),
            'has_case': False,
            'forms_count': 0
        })
        with open(file_path, 'wb') as file_object:
            writer = csv.writer(file_object)
            writer.writerow([
                'domain name',
                'user id',
                'total number of forms submitted in a month',
                'used management case?',
                'multiple_form_types?'
            ])

            for domain_object in Domain.get_all():
                domain_name = domain_object.name
                user_ids = CommCareUser.ids_by_domain(domain=domain_name)
                for hit in get_forms_for_users(domain_object.name, user_ids, start_date, end_date).hits:
                    try:
                        form = hit['form']
                        user_id = form['meta']['userID']
                        case = form.get('case')
                        xmlns = form['@xmlns']
                    except KeyError:
                        continue

                    user_data = user_id_to_data[user_id]
                    user_data['forms_count'] += 1

                    if case:
                        user_data['has_case'] = True

                    if xmlns and len(user_data['xmlns_set']) < 2:
                        user_data['xmlns_set'].add(xmlns)

                for user in iter_docs(CommCareUser.get_db(), user_ids):
                    user_id = user['_id']
                    user_data = user_id_to_data[user_id]
                    has_two_or_more_different_forms_submitted = (len(user_data['xmlns_set']) == 2)

                    writer.writerow([
                        domain_name,
                        user_id,
                        user_data['forms_count'],
                        user_data['has_case'],
                        has_two_or_more_different_forms_submitted
                    ])
