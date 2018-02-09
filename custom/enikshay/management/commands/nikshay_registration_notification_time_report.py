from __future__ import absolute_import

import datetime
import csv
import pytz
import six
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.core.mail import EmailMessage
from django.conf import settings

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.repeaters.dbaccessors import iter_repeat_records_by_domain
from casexml.apps.case.util import get_latest_property_change_to_value
from corehq.util.timezones.utils import get_timezone_for_domain


REGISTRATION_REPEATER_ID = "803b375da8d6f261777d339d12f89cdb"
SUCCESS_STATE = "SUCCESS"
DOMAIN = "enikshay"


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('days', type=int)
        parser.add_argument('--email', type=str)

    def handle(self, days, *args, **options):
        email_to = options.get('email')
        # to iterate over repeat records we need time zone independent datetime
        # so find the difference between timezone needed and utc
        # For ex: IST is 5 hours 30 mins ahead of utc, so reduce that time in since
        # datetime to fetch repeat records from midnight IST on since datetime
        timezone = get_timezone_for_domain(DOMAIN)
        self.days = days
        self.till = datetime.datetime.now(tz=timezone)
        self.since = (datetime.datetime(self.till.year, self.till.month, self.till.day)
                      - datetime.timedelta(days=days)
                      - datetime.timedelta(hours=5, minutes=30))

        result_file_name = "nikshay_registration_notification_time_report_from_%s_till_%s.csv" % (
            self.since.strftime('%Y-%m-%d-%H:%M:%S'),
            self.till.strftime('%Y-%m-%d-%H:%M:%S')
        )

        with open(result_file_name, 'w') as csvfile:
            writer = csv.DictWriter(csvfile,
                                    fieldnames=["nikshay id", "form finished on", "form submitted on",
                                                "notification completed on", "form to submission",
                                                "submission to notification", "case id"])
            writer.writeheader()
            case_accessor = CaseAccessors(DOMAIN)
            for repeat_record in iter_repeat_records_by_domain(DOMAIN, repeater_id=REGISTRATION_REPEATER_ID,
                                                               state=SUCCESS_STATE, since=self.since):
                episode_case_id = repeat_record.payload_id
                episode_case = case_accessor.get_case(episode_case_id)
                assert repeat_record.succeeded
                time_of_notification = pytz.utc.localize(repeat_record.last_checked).astimezone(timezone)
                # assert that
                # the last notification was the success one and
                # the time for last notification is same as that for the repeat record
                last_notification_attempt = repeat_record.attempts[-1]
                assert last_notification_attempt.succeeded
                assert repeat_record.last_checked == last_notification_attempt.datetime
                property_changed_info = get_latest_property_change_to_value(episode_case,
                                                                            "treatment_initiated",
                                                                            "yes_phi")
                xform = property_changed_info.transaction.form
                form_received_on = pytz.utc.localize(xform.received_on).astimezone(timezone)
                property_modified_on = parse_datetime(property_changed_info.modified_on).astimezone(timezone)
                writer.writerow({
                    'nikshay id': episode_case.get_case_property('nikshay_id'),
                    'form finished on': property_modified_on.strftime('%Y-%m-%d-%H:%M:%S'),
                    'form submitted on': form_received_on.strftime('%Y-%m-%d-%H:%M:%S'),
                    'notification completed on': time_of_notification.strftime('%Y-%m-%d-%H:%M:%S'),
                    'form to submission': (form_received_on - property_modified_on),
                    'submission to notification': (time_of_notification - form_received_on),
                    'case id': episode_case.case_id
                })

            if email_to:
                email_to = list(email_to) if not isinstance(email_to, six.string_types) else [email_to]
                csvfile = open(result_file_name)
                email = EmailMessage(
                    subject="Nikshay Registration Notification Time Report",
                    body="Report for time taken for registration notifications for %s day(s)" % self.days,
                    to=email_to,
                    from_email=settings.DEFAULT_FROM_EMAIL
                )
                email.attach(filename=result_file_name, content=csvfile.read())
                csvfile.close()
                email.send()
