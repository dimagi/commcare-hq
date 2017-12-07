import csv
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMessage

from django.conf import settings

from custom.enikshay.const import ENROLLED_IN_PRIVATE

DOMAIN = "enikshay"


class BaseModelReconciliationCommand(BaseCommand):
    email_subject = None
    result_file_name_prefix = None
    result_file_headers = None

    def __init__(self, *args, **kwargs):
        super(BaseModelReconciliationCommand, self).__init__(*args, **kwargs)
        self.commit = False
        self.log_progress = None
        self.recipient = None
        self.result_file_name = None

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--recipient', type=str)
        parser.add_argument('--log_progress', action='store_true')

    def handle(self, *args, **options):
        raise CommandError(
            "This is the base reconciliation class and should not be run. "
            "One of it's inherited commands should be run.")

    def public_app_case(self, person_case):
        return person_case.get_case_property(ENROLLED_IN_PRIVATE) != 'true'

    def email_report(self):
        csv_file = open(self.result_file_name)
        email = EmailMessage(
            subject=self.email_subject,
            body="Please find attached report for a %s run finished at %s." %
                 ('real' if self.commit else 'mock', datetime.now()),
            to=self.recipient,
            from_email=settings.DEFAULT_FROM_EMAIL
        )
        email.attach(filename=self.result_file_name, content=csv_file.read())
        csv_file.close()
        email.send()

    def setup_result_file(self):
        file_name = "{file_name_prefix}_{timestamp}.csv".format(
            file_name_prefix=self.result_file_name_prefix,
            timestamp=datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
        )
        with open(file_name, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.result_file_headers)
            writer.writeheader()
        return file_name

    def writerow(self, row):
        with open(self.result_file_name, 'a') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.result_file_headers)
            writer.writerow(row)

    @staticmethod
    def get_first_opened_case(all_cases):
        return sorted(all_cases, key=lambda x: x.opened_on)[0]
