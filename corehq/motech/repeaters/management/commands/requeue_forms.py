import csv
import datetime
import sys
import time
from corehq.apps.es import AppES, FormES
from dimagi.utils.chunked import chunked
from corehq.apps.app_manager.models import Application
from corehq.apps.data_interfaces.utils import operate_on_payloads
from corehq.motech.repeaters.models import RepeatRecord
from django.core.management.base import BaseCommand

SLEEP_DURATION = 30


class Command(BaseCommand):
    help = "Requeue forms by inputting appi_id, form_name and submission times"

    def add_arguments(self, parser):
        parser.add_argument(
            '--soft-run',
            action='store_true',
            help='Perform a soft run which prints form counts without requeuing the forms',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            """
            Paste your data in CSV format (Ctrl+D to finish):
                Each row must have exactly 7 fields:
                extra, domain, app_id, form_name, startdate, enddate, repeater_id.
                extra is just any text to identify the row, can be empty
            """)
        csv_data = sys.stdin.read()

        try:
            data = self.parse_csv_data(csv_data)
        except Exception as e:
            self.stderr.write(f"Error parsing CSV data: {e}")
            return

        try:
            requeue_forms = self.get_requeue_form_xmlns(data)
            self.process_requeue_forms(requeue_forms, soft_run=options['soft_run'])
        except Exception as e:
            self.stderr.write(f"Error processing requeue forms: {e}")

    def parse_csv_data(self, csv_data):
        """
        Parses the input CSV data, stripping any extra spaces around values.
        """
        reader = csv.reader(csv_data.strip().splitlines())
        data = []
        for row in reader:
            cleaned_row = [value.strip() for value in row]  # Strip spaces from each value
            if len(cleaned_row) != 7:
                raise ValueError(
                    "Each row must have exactly 7 fields: extra, domain, app_id, form_name, startdate, enddate, repeater_id."
                    "extra is just any text to identify the row, can be empty"
                )
            data.append(cleaned_row)
        return data

    def get_requeue_form_xmlns(self, data):
        requeue_forms = []
        for extra, domain, app_id, form_name, startdate, enddate, repeater_id in data:
            app = Application.get(app_id)
            assert app.domain == domain
            requeue_form_xmlns = []
            for form in app.get_forms():
                if form.name["en"] == form_name:
                    requeue_form_xmlns.append([extra, domain, app_id, form.name, form["xmlns"], startdate, enddate, repeater_id])
            if not requeue_form_xmlns:
                raise Exception(f"Unable to find {form_name} in {domain} app_id {app_id}")
            elif len(requeue_form_xmlns) > 1:
                raise Exception(f"Found multiple {form_name} in {domain} app_id {app_id}")
            else:
                requeue_forms += requeue_form_xmlns
        return requeue_forms

    def process_requeue_forms(self, requeue_forms, soft_run=True):
        for extra, domain, app_id, form_name, form_xmlns, startdate, enddate, repeater_id in requeue_forms:
            startdate = datetime.datetime.strptime(startdate, "%d-%m-%Y").date()
            enddate = datetime.datetime.strptime(enddate, "%d-%m-%Y").date()
            query = (FormES()
                     .domain(domain)
                     .app(app_id).xmlns(form_xmlns)
                     .submitted(gte=startdate, lte=enddate))
            self.stdout.write(f"Form Count {extra}, {domain}, {app_id}: {query.count()}")
            if not soft_run:
                form_ids = query.get_ids()
                self.stdout.write(f"Requeuing {extra}, {domain}, {app_id}, {form_name}, {form_xmlns}, {startdate}, {enddate}, {repeater_id}")
                for form_id_chunk in chunked(form_ids, 100):
                    records_ids = RepeatRecord.objects.filter(domain=domain, repeater_id=repeater_id, payload_id__in=form_id_chunk).values_list('id', flat=True)
                    response = operate_on_payloads(records_ids, domain, "requeue")
                    self.stdout.write(str(response["messages"]["success_count_msg"]))
                    time.sleep(SLEEP_DURATION)
        self.stdout.write(f"Finished Requeuing (Soft Run: {soft_run})")
