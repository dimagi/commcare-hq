from corehq.apps.sms.models import SMS
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.smsbackends.icds_nic.models import SQLICDSBackend
from corehq.util.argparse_types import utc_timestamp
from couchexport.export import export_raw
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ""

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('start_timestamp', type=utc_timestamp)
        parser.add_argument('end_timestamp', type=utc_timestamp)

    def get_location_id(self, sms):
        location_id = None

        if sms.couch_recipient:
            if sms.couch_recipient in self.recipient_id_to_location_id:
                return self.recipient_id_to_location_id[sms.couch_recipient]

            recipient = sms.recipient
            if is_commcarecase(recipient):
                if recipient.type == 'commcare-user':
                    user = CommCareUser.get_by_user_id(recipient.owner_id)
                    if user:
                        location_id = user.location_id
                else:
                    location_id = recipient.owner_id

            self.recipient_id_to_location_id[sms.couch_recipient] = location_id

        return location_id

    def get_location(self, sms):
        location_id = self.get_location_id(sms)
        if not location_id:
            return None

        if location_id in self.location_id_to_location:
            return self.location_id_to_location[location_id]

        location = SQLLocation.by_location_id(location_id)
        self.location_id_to_location[location_id] = location
        return location

    def get_state_code(self, location):
        if not location:
            return 'unknown'

        if location.location_id in self.location_id_to_state_code:
            return self.location_id_to_state_code[location.location_id]

        state = location.get_ancestors().filter(location_type__code='state').first()
        if not state:
            return 'unknown'

        self.location_id_to_state_code[location.location_id] = state.site_code
        self.state_code_to_name[state.site_code] = state.name
        return state.site_code

    def get_indicator_slug(self, sms):
        if not isinstance(sms.custom_metadata, dict):
            return 'unknown'

        return sms.custom_metadata.get('icds_indicator', 'unknown')

    def handle(self, domain, start_timestamp, end_timestamp, **options):
        self.recipient_id_to_location_id = {}
        self.location_id_to_location = {}
        self.location_id_to_state_code = {}
        self.state_code_to_name = {'unknown': 'Unknown'}

        data = {}

        for sms in SMS.objects.filter(
            domain=domain,
            date__gt=start_timestamp,
            date__lte=end_timestamp,
            backend_api=SQLICDSBackend.get_api_id(),
            direction='O',
            processed=True,
        ):
            location = self.get_location(sms)
            state_code = self.get_state_code(location)
            if state_code not in data:
                data[state_code] = {}

            indicator_slug = self.get_indicator_slug(sms)
            if indicator_slug not in data[state_code]:
                data[state_code][indicator_slug] = 0

            data[state_code][indicator_slug] += 1

        with open('icds-sms-usage.xlsx', 'wb') as f:
            headers = ('State Code', 'State Name', 'Indicator', 'SMS Count')
            excel_data = []

            for state_code, state_data in data.items():
                for indicator_slug, count in state_data.items():
                    excel_data.append((state_code, self.state_code_to_name[state_code], indicator_slug, count))

            export_raw(
                (('icds-sms-usage', headers), ),
                (('icds-sms-usage', excel_data), ),
                f
            )
