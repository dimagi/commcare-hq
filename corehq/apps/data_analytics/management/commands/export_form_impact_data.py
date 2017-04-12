import csv

import dateutil
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand

from corehq.apps.data_analytics.esaccessors import get_forms_for_users
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser


class Command(BaseCommand):
    """
        Export form impact data to given csv file
        e.g. ./manage.py export_form_impact_data February-2017 example.csv
    """
    help = 'Export form impact data to given csv file'

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
                buckets_dict = get_forms_for_users(domain_object.name, user_ids, start_date, end_date)
                for user_id, bucket in buckets_dict.iteritems():
                    has_case = bool(
                        filter(
                            lambda h: h.get('form', {}).get('case'),
                            bucket.top_hits_user_submissions.hits
                        )
                    )
                    has_two_or_more_different_forms_submitted = len(
                        [
                            hit.get('form', {}).get('@xmlns')
                            for hit in bucket.top_hits_user_submissions.hits
                            if hit.get('form', {}).get('@xmlns')
                        ]
                    ) >= 2
                    writer.writerow([
                        domain_name,
                        user_id,
                        bucket.doc_count,
                        has_case,
                        has_two_or_more_different_forms_submitted
                    ])
