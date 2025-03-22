import csv
from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.db import connections, transaction

from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.models import AwcLocation
from custom.icds_reports.utils.connections import get_icds_ucr_citus_db_alias

query = """
    SELECT
        state_id, count(*) as form_count
        FROM "{table_name}"
        WHERE inserted_at>='{start_date}'::date AND inserted_at<'{end_date}'::date GROUP BY state_id
"""

query_usage = """
    SELECT
        awc.state_id, count(*) as form_count
        FROM "{table_name}" use
        LEFT JOIN awc_location awc ON (
            awc.doc_id = use.awc_id AND awc.aggregation_level=5
        )
        WHERE use.inserted_at>='{start_date}'::date AND use.inserted_at<'{end_date}'::date AND 
        {usage_field_name}=1 AND awc.aggregation_level=5 GROUP BY awc.state_id
"""

usage_forms = {
    "Due List - child": "due_list_child",
    "Due List - pregnancy": "due_list_ccs"
}

forms = {
    "Due List - child": "static-usage_forms",
    "Due List - pregnancy": "static-usage_forms",
    "Adolescent girls registration/de-registration form": "static-adolescent_girls_reg_form",
    "Primary private school": "static-dashboard_primary_private_school",
}

START_DATE = date(2019, 9, 29)
END_DATE = date(2019, 12, 22)


@transaction.atomic
def _run_custom_sql_script(command):
    data = {}
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return data
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)
        row = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
        return row


def fetch_data(table_name, start_date, end_date, usage_field_name=None):
    if usage_field_name:
        data = _run_custom_sql_script(
            query_usage.format(table_name=table_name, start_date=start_date, end_date=end_date,
                               usage_field_name=usage_field_name))
    else:
        data = _run_custom_sql_script(
            query.format(table_name=table_name, start_date=start_date, end_date=end_date))
    return data


class Command(BaseCommand):
    def handle(self, **options):
        states = {}
        filters = {'state_is_test': 0, 'aggregation_level': 1}
        locations = AwcLocation.objects.filter(**filters).values('state_id', 'state_name')
        for loc in locations:
            states[loc['state_id']] = loc['state_name']
        csv_dict = {}
        for state_id, state_name in states.items():
            start_date = START_DATE
            last_date = END_DATE
            while start_date <= last_date:
                dummy_dict = {
                    'state_name': state_name,
                    'date': start_date
                }
                for form in forms.keys():
                    dummy_dict[form] = 0
                csv_dict[f'{state_id}_{start_date.strftime("%Y-%m-%d")}'] = dummy_dict
                start_date = start_date + relativedelta(days=7)
        for form_name, form_id in forms.items():
            table_name = get_table_name('icds-cas', form_id)
            start_date = START_DATE
            last_date = END_DATE
            while start_date <= last_date:
                end_date = start_date + relativedelta(days=7)
                if form_id == 'static-usage_forms':
                    usage_field_name = usage_forms[form_name]
                    rows = fetch_data(table_name, start_date, end_date, usage_field_name)
                else:
                    rows = fetch_data(table_name, start_date, end_date)
                # normal usage query
                for row in rows:
                    state_id = row['state_id']
                    dict_key = f"{state_id}_{start_date.strftime('%Y-%m-%d')}"
                    if dict_key in csv_dict.keys():
                        csv_dict[dict_key][form_name] = row['form_count']
                start_date = end_date
        csv_dict = list(csv_dict.values())
        csv_columns = csv_dict[0].keys()
        with open('form_data.csv', 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for data in csv_dict:
                writer.writerow(data)
