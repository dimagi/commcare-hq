
import csv
from datetime import datetime

from django.core.management import BaseCommand
from django.db.models import Min
from dateutil.relativedelta import relativedelta

from corehq.apps.es import CaseES, FormES
from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from couchforms.const import DEVICE_LOG_XMLNS


class Command(BaseCommand):
    """https://manage.dimagi.com/default.asp?277644
    https://trello.com/c/gLN9bxOt/389-backfill-missing-data-in-es
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            'csv_file',
            help="File path for csv file",
        )

    def handle(self, domain, csv_file, **options):
        self.domain = domain
        if not should_use_sql_backend(domain):
            print("This domain doesn't use SQL backend, exiting!")
            return

        current_date = self.first_form_received_on()
        if not current_date:
            print("No submissions in this domain yet, exiting!")
            return

        with open(csv_file, "w", encoding='utf-8') as csv_file:
            field_names = ('date', 'doc_type', 'in_sql', 'in_es', 'diff')

            csv_writer = csv.DictWriter(csv_file, field_names, extrasaction='ignore')
            csv_writer.writeheader()

            while current_date <= datetime.today():
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

    def first_form_received_on(self):
        min_date = datetime(2200, 1, 1)
        for db in get_db_aliases_for_partitioned_query():
            result = XFormInstanceSQL.objects.using(db).filter(
                domain=self.domain).aggregate(Min('received_on'))
            date = result.get('received_on__min')
            if date and date < min_date:
                min_date = date
        if min_date.year == 2200:
            return None
        else:
            return min_date

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
                .filter(state=XFormInstanceSQL.NORMAL)
                .exclude(xmlns=DEVICE_LOG_XMLNS)
                .count()
            )

        return num_forms

    def _get_es_forms_received_on_date(self, date):
        return FormES().submitted(gte=date, lt=date + relativedelta(months=1)).count()
