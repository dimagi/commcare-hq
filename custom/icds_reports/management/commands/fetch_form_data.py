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
    "Register Household": "add_household",
    "Add Member": "add_person",
    "Post Natal Care": "pnc",
    "Exclusive Breast Feeding": "ebf",
    "Growth Monitoring": "gmp"
}

forms = {
    "Register Household": "static-usage_forms",
    "Add Member": "static-usage_forms",
    "Add pregnancy": "static-dashboard_add_pregnancy_form",
    "Availing services": "static-availing_service_form",
    "Daily feeding": "static-daily_feeding_forms",
    "Birth Preparedness": "static-dashboard_birth_preparedness_forms",
    "Delivery": "static-child_delivery_forms",
    "Post Natal Care": "static-usage_forms",
    "Exclusive Breast Feeding": "static-usage_forms",
    "Complementary Feeding": "static-complementary_feeding_forms",
    "Growth Monitoring": "static-usage_forms",
    "Additional Growth Monitoring": "static-dashboard_growth_monitoring_forms",  # special case
    "THR Distribution": "static-dashboard_thr_forms",
    "Infratructure Details": "static-infrastructure_form_v2",
    "VHSND Survey": "static-vhnd_form",
    "Visitor Register": "static-visitorbook_forms",
    "AWC Visit Form": "static-awc_mgt_forms",
    "Beneficiary Feedback": "static-ls_home_visit_forms_filled",
    "VHSND observation Form": "static-ls_vhnd_form",
}

dates = [
    date(2019, 9, 29),
    date(2019, 10, 6),
    date(2019, 10, 13),
    date(2019, 10, 20),
    date(2019, 10, 27),
    date(2019, 11, 3),
    date(2019, 11, 10),
    date(2019, 11, 17),
    date(2019, 11, 24),
    date(2019, 12, 1),
    date(2019, 12, 8),
    date(2019, 12, 15),
    date(2019, 12, 22),
]


@transaction.atomic
def _run_custom_sql_script(command):
    data = {}
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return data
    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)
        data = cursor.fetchall()
        return dict(data)


def fetch_data(table_name, start_date, end_date, usage_field_name=''):
    if usage_field_name != '':
        data = _run_custom_sql_script(
            query_usage.format(table_name=table_name, start_date=start_date, end_date=end_date,
                               usage_field_name=usage_field_name))
    else:
        data = _run_custom_sql_script(query.format(table_name=table_name, start_date=start_date, end_date=end_date))
    return data


class Command(BaseCommand):
    def handle(self, **options):
        states = {}
        locations = AwcLocation.objects.filter(state_is_test=0).values('state_id', 'state_name')
        for loc in locations:
            states[loc['state_id']] = loc['state_name']
        csv_dict = {}
        for state_id, state_name in states.items():
            for dat in dates:
                dummy_dict = {
                    'state_name': state_name,
                    'date': dat
                }
                for form in forms.keys():
                    dummy_dict[form] = 0
                csv_dict[f'{state_id}_{dat.strftime("%Y-%m-%d")}'] = dummy_dict

        for form_name, form_id in forms.items():
            table_name = get_table_name('icds-cas', form_id)
            for dat in dates:
                start_date = dat
                end_date = start_date + relativedelta(days=7)
                if form_id == 'static-usage_forms':
                    usage_field_name = usage_forms[form_name]
                    rows = fetch_data(table_name, start_date, end_date, usage_field_name)
                else:
                    rows = fetch_data(table_name, start_date, end_date)
                # normal usage query
                for row in rows:
                    state_id = row['state_id']
                    csv_dict[f'{state_id}_{start_date.strftime("%Y-%m-%d")}'][form_name] = row['form_count']
        csv_dict = list(csv_dict.values())
        csv_columns = csv_dict[0].keys()
        with open('form_data.csv', 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for data in csv_dict:
                writer.writerow(data)

