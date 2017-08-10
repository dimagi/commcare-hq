import pytz
from collections import defaultdict
from corehq.apps.sms.models import SMS
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.smsbackends.icds_nic.models import SQLICDSBackend
from corehq.util.argparse_types import date_type
from corehq.util.timezones.conversions import UserTime
from couchexport.export import export_raw
from datetime import datetime, timedelta, time
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ""

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('start_date', type=date_type)
        parser.add_argument('end_date', type=date_type)

    def get_recipient_details(self, sms):
        details = {
            'case_type': None,
            'case_name': None,
            'location_id': None,
        }

        if sms.couch_recipient:
            if sms.couch_recipient in self.recipient_details:
                return self.recipient_details[sms.couch_recipient]

            recipient = sms.recipient
            if is_commcarecase(recipient):
                details['case_name'] = recipient.name
                details['case_type'] = recipient.type

                if recipient.type == 'commcare-user':
                    user = CommCareUser.get_by_user_id(recipient.owner_id)
                    if user:
                        details['location_id'] = user.location_id
                else:
                    details['location_id'] = recipient.owner_id

            self.recipient_details[sms.couch_recipient] = details

        return details

    def get_location_details(self, location_id):
        result = defaultdict(dict)

        if not location_id:
            return result

        if location_id in self.location_details:
            return self.location_details[location_id]

        location = SQLLocation.by_location_id(location_id)
        if location:
            rows = location.get_ancestors(include_self=True).values_list('location_type__code',
                'location_id', 'name')
            for row in rows:
                location_type_code, location_id, name = row
                result[location_type_code] = {
                    'location_id': location_id,
                    'name': name,
                }

        self.location_details[location_id] = result
        return result

    def get_indicator_slug(self, sms):
        if not isinstance(sms.custom_metadata, dict):
            return 'unknown'

        return sms.custom_metadata.get('icds_indicator', 'unknown')

    def get_records(self, domain, start_timestamp, end_timestamp):
        for sms in SMS.objects.filter(
            domain=domain,
            date__gt=start_timestamp,
            date__lte=end_timestamp,
            backend_api=SQLICDSBackend.get_api_id(),
            direction='O',
            processed=True,
        ):
            recipient_details = self.get_recipient_details(sms)
            location_details = self.get_location_details(recipient_details['location_id'])
            indicator_slug = self.get_indicator_slug(sms)
            yield (
                sms.date.strftime('%Y-%m-%d %H:%M:%S'),
                indicator_slug,
                sms.phone_number,
                recipient_details['case_type'],
                sms.couch_recipient,
                recipient_details['case_name'],
                location_details['awc'].get('name'),
                location_details['supervisor'].get('name'),
                location_details['district'].get('name'),
                location_details['block'].get('name'),
                location_details['state'].get('name'),
                sms.text,
                location_details['awc'].get('location_id'),
                location_details['supervisor'].get('location_id'),
                location_details['district'].get('location_id'),
                location_details['block'].get('location_id'),
                location_details['state'].get('location_id'),
            )

    def handle(self, domain, start_date, end_date, **options):
        self.recipient_details = {}
        self.location_details = {}

        start_timestamp = UserTime(
            datetime.combine(start_date, time(0, 0)),
            pytz.timezone('Asia/Kolkata')
        ).server_time().done().replace(tzinfo=None)

        end_timestamp = UserTime(
            datetime.combine(end_date, time(0, 0)),
            pytz.timezone('Asia/Kolkata')
        ).server_time().done().replace(tzinfo=None)

        # end_date is inclusive
        end_timestamp += timedelta(days=1)

        with open('icds-sms-export.xlsx', 'wb') as f:
            headers = (
                'Date',
                'Indicator',
                'Phone Number',
                'Recipient Case Type',
                'Recipient Case Id',
                'Recipient Case Name',
                'AWC Name',
                'LS Name',
                'District Name',
                'Block Name',
                'State Name',
                'Text',
                'AWC Id',
                'LS Id',
                'District Id',
                'Block Id',
                'State Id',
            )

            data = tuple(self.get_records(domain, start_timestamp, end_timestamp))

            export_raw(
                (('icds-sms-export', headers), ),
                (('icds-sms-export', data), ),
                f
            )
