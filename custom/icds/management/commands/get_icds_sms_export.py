from __future__ import absolute_import
import pytz
from collections import defaultdict
from corehq.apps.sms.models import SMS
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.smsbackends.icds_nic.models import SQLICDSBackend
from corehq.util.argparse_types import date_type
from corehq.util.timezones.conversions import UserTime, ServerTime
from couchexport.export import export_raw
from datetime import datetime, timedelta, time
from dimagi.utils.decorators.memoized import memoized
from django.core.management.base import BaseCommand


class BaseICDSSMSExportCommand(BaseCommand):
    help = ""

    @property
    @memoized
    def timezone(self):
        return pytz.timezone('Asia/Kolkata')

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('start_date', type=date_type)
        parser.add_argument('end_date', type=date_type)

    def get_recipient_details(self, sms):
        details = {
            'type': None,
            'name': None,
            'location_id': None,
        }

        if sms.couch_recipient:
            if sms.couch_recipient in self.recipient_details:
                return self.recipient_details[sms.couch_recipient]

            recipient = sms.recipient
            if is_commcarecase(recipient):
                details['name'] = recipient.name
                details['type'] = 'case: %s' % recipient.type

                if recipient.type == 'commcare-user':
                    user = CommCareUser.get_by_user_id(recipient.owner_id)
                    if user:
                        details['location_id'] = user.location_id
                else:
                    details['location_id'] = recipient.owner_id
            elif isinstance(recipient, CommCareUser):
                details['name'] = recipient.username
                details['type'] = 'mobile worker'
                details['location_id'] = recipient.location_id

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
            locs = location.get_ancestors(include_self=True).select_related('location_type')
            for loc in locs:
                result[loc.location_type.code] = {
                    'location_id': loc.location_id,
                    'name': loc.name,
                    'site_code': loc.site_code,
                }

        self.location_details[location_id] = result
        return result

    def get_indicator_slug(self, sms):
        if not isinstance(sms.custom_metadata, dict):
            return 'unknown'

        return sms.custom_metadata.get('icds_indicator', 'unknown')

    def format_timestamp(self, utc_timestamp):
        ist_timestamp = ServerTime(utc_timestamp).user_time(self.timezone).done()
        return ist_timestamp.strftime('%Y-%m-%d %H:%M:%S')

    def get_records(self, domain, start_timestamp, end_timestamp, indicator_filter=None, state_filter=None):
        indicator_filter = indicator_filter or []
        state_filter = state_filter or []

        if not isinstance(indicator_filter, list):
            raise TypeError("Expected list for indicator_filter")

        if not isinstance(state_filter, list):
            raise TypeError("Expected list for state_filter")

        for sms in SMS.objects.filter(
            domain=domain,
            date__gt=start_timestamp,
            date__lte=end_timestamp,
            backend_api=SQLICDSBackend.get_api_id(),
            direction='O',
            processed=True,
        ).order_by('date'):
            recipient_details = self.get_recipient_details(sms)
            location_details = self.get_location_details(recipient_details['location_id'])
            indicator_slug = self.get_indicator_slug(sms)

            if indicator_filter and indicator_slug not in indicator_filter:
                continue

            if state_filter and location_details['state'].get('site_code') not in state_filter:
                continue

            yield (
                self.format_timestamp(sms.date),
                sms.phone_number,
                recipient_details['name'],
                location_details['state'].get('name'),
                location_details['district'].get('name'),
                location_details['block'].get('name'),
                location_details['supervisor'].get('name'),
                location_details['awc'].get('name'),
                sms.text,
                recipient_details['type'],
                sms.couch_recipient,
                indicator_slug,
                location_details['state'].get('location_id'),
                location_details['district'].get('location_id'),
                location_details['block'].get('location_id'),
                location_details['supervisor'].get('location_id'),
                location_details['awc'].get('location_id'),
            )

    def get_start_and_end_timestamps(self, start_date, end_date):
        start_timestamp = UserTime(
            datetime.combine(start_date, time(0, 0)),
            self.timezone
        ).server_time().done().replace(tzinfo=None)

        end_timestamp = UserTime(
            datetime.combine(end_date, time(0, 0)),
            self.timezone
        ).server_time().done().replace(tzinfo=None)

        # end_date is inclusive
        end_timestamp += timedelta(days=1)

        return start_timestamp, end_timestamp


class Command(BaseICDSSMSExportCommand):

    def handle(self, domain, start_date, end_date, **options):
        self.recipient_details = {}
        self.location_details = {}
        start_timestamp, end_timestamp = self.get_start_and_end_timestamps(start_date, end_date)

        filename = 'icds-sms-export--%s--%s.xlsx' % (
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
        )

        with open(filename, 'wb') as f:
            headers = (
                'Date (IST)',
                'Phone Number',
                'Recipient Name',
                'State Name',
                'District Name',
                'Block Name',
                'LS Name',
                'AWC Name',
                'Text',
                'Recipient Type',
                'Recipient Id',
                'Indicator',
                'State Id',
                'District Id',
                'Block Id',
                'LS Id',
                'AWC Id',
            )

            data = tuple(self.get_records(domain, start_timestamp, end_timestamp))

            export_raw(
                (('icds-sms-export', headers), ),
                (('icds-sms-export', data), ),
                f
            )
