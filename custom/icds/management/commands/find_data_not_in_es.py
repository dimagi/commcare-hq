from __future__ import absolute_import
from __future__ import unicode_literals

from __future__ import print_function
import csv342 as csv
from datetime import date
from io import open

from django.core.management import BaseCommand
from dateutil.relativedelta import relativedelta

from corehq.apps.es import CaseES, FormES
from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from couchforms.const import DEVICE_LOG_XMLNS


class Command(BaseCommand):
    """https://manage.dimagi.com/default.asp?277644
    https://trello.com/c/gLN9bxOt/389-backfill-missing-data-in-es
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            help="File path for csv file",
        )

    def handle(self, csv_file, **options):
        self.domain = 'icds-cas'
        with open(csv_file, "w", encoding='utf-8') as csv_file:
            field_names = ('date', 'doc_type', 'in_sql', 'in_es', 'diff')

            csv_writer = csv.DictWriter(csv_file, field_names, extrasaction='ignore')
            csv_writer.writeheader()

            current_date = date(2017, 1, 1)

            while current_date <= date.today():
                cases_in_sql = self._get_sql_cases_modified_on_date(current_date)
                cases_in_es = self._get_es_cases_modified_on_date(current_date)
                properties = {
                    "date": current_date,
                    "doc_type": "CommCareCase",
                    "in_sql": cases_in_sql,
                    "in_es": cases_in_es,
                    "diff": cases_in_sql - cases_in_es,
                }
                csv_writer.writerow(properties)
                print(properties)

                forms_in_sql = self._get_sql_forms_received_on_date(current_date)
                forms_in_es = self._get_es_forms_received_on_date(current_date)
                properties = {
                    "date": current_date,
                    "doc_type": "XFormInstance",
                    "in_sql": forms_in_sql,
                    "in_es": forms_in_es,
                    "diff": forms_in_sql - forms_in_es
                }
                csv_writer.writerow(properties)
                print(properties)

                current_date += relativedelta(months=1)

    def _get_sql_cases_modified_on_date(self, date):
        num_cases = 0
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            num_cases += (
                CommCareCaseSQL.objects
                .using(db)
                .filter(server_modified_on__gte=date, server_modified_on__lt=date + relativedelta(months=1))
                .count()
            )

        return num_cases

    def _get_es_cases_modified_on_date(self, date):
        return CaseES().server_modified_range(gte=date, lt=date + relativedelta(months=1)).count()

    def _get_sql_forms_received_on_date(self, date):
        num_forms = 0
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            num_forms += (
                XFormInstanceSQL.objects
                .using(db)
                .filter(received_on__gte=date, received_on__lt=date + relativedelta(months=1))
                .exclude(xmlns=DEVICE_LOG_XMLNS)
                .count()
            )

        return num_forms

    def _get_es_forms_received_on_date(self, date):
        return FormES().remove_default_filter('is_xform_instance').submitted(gte=date, lt=date + relativedelta(months=1)).count()
