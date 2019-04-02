from __future__ import absolute_import
from __future__ import unicode_literals
import re
import uuid
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.util import strip_plus
from corehq.apps.users.forms import clean_mobile_worker_username
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.util import format_username
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import REGISTER_HELP, \
    REGISTRATION_CONFIRM_DISTRICT, REGISTRATION_CONFIRM, Roles, REGISTER_UNKNOWN_DISTRICT, REGISTER_UNKNOWN_CODE
from dimagi.utils.couch import CriticalSection
from six.moves import range

DISTRICT_PREFIXES = [
    'd', 'dm', 'dr',
    'ir',
    'm', 'mb', 'ms', 'mt', 'mz',
    'tb', 'tg',
]


def generate_username(domain, first_name, last_name):
    if first_name and last_name:
        username = '%s_%s' % (first_name, last_name)
    elif first_name:
        username = first_name
    else:
        username = 'user_' + uuid.uuid4().hex[:8]

    username = re.sub(r'[^\w]', '', username)
    username = username[:40]

    if CouchUser.username_exists(format_username(username, domain)):
        for i in range(2, 10000):
            tmp_username = '%s-%s' % (username, i)
            if not CouchUser.username_exists(format_username(tmp_username, domain)):
                username = tmp_username
                break

    # Perform standard validation
    return clean_mobile_worker_username(domain, username)


class RegisterHandler(KeywordHandler):
    DISTRICT_REG_DELIMITER = ":"

    def help(self):
        self.respond(REGISTER_HELP)
        return True

    def _get_facility_location(self, domain, msd_code):
        return SQLLocation.objects.get(
            domain=domain,
            location_type__name="FACILITY",
            site_code__iexact=msd_code
        )

    def _get_district_location(self, domain, sp):
        return SQLLocation.objects.get(
            domain=domain,
            location_type__name="DISTRICT",
            name__iexact=sp,
        )

    def handle(self):
        text = ' '.join(self.msg.text.split()[1:])
        is_district = False
        sp = ""
        msd_code = ""
        params = {}

        if text.find(self.DISTRICT_REG_DELIMITER) != -1:
            phrases = [x.strip() for x in text.split(":")]
            if len(phrases) != 2:
                self.respond(REGISTER_HELP)
                return True
            name = phrases[0]
            sp = phrases[1]
            role = Roles.DISTRICT_PHARMACIST
            message = REGISTRATION_CONFIRM_DISTRICT
            is_district = True
        else:
            names = []
            msd_codes = []
            location_regex = r'^({prefs})\d+'.format(prefs='|'.join(p.lower() for p in DISTRICT_PREFIXES))
            for the_string in self.args:
                if re.match(location_regex, the_string.strip().lower()):
                    msd_codes.append(the_string.strip().lower())
                else:
                    names.append(the_string)

            name = " ".join(names)
            if len(msd_codes) != 1:
                self.respond(REGISTER_HELP)
                return True
            else:
                [msd_code] = msd_codes

            role = Roles.IN_CHARGE
            message = REGISTRATION_CONFIRM

        if is_district:
            try:
                loc = self._get_district_location(self.domain, sp)
                params['sdp_name'] = loc.name
            except SQLLocation.DoesNotExist:
                self.respond(REGISTER_UNKNOWN_DISTRICT, name=sp)
                return True
        else:
            try:
                loc = self._get_facility_location(self.domain, msd_code)
                params['sdp_name'] = loc.name
                params['msd_code'] = loc.site_code
            except SQLLocation.DoesNotExist:
                self.respond(REGISTER_UNKNOWN_CODE, msd_code=msd_code)
                return True

        split_name = name.split(' ', 2)
        first_name = ''
        last_name = ''
        if len(split_name) == 2:
            first_name, last_name = split_name
        elif split_name:
            first_name = split_name[0]

        if not self.user:
            key = 'generating ils username for %s, %s, %s' % (self.domain, first_name, last_name)
            with CriticalSection([key]):
                username = generate_username(self.domain, first_name, last_name)
                password = uuid.uuid4().hex
                self.user = CommCareUser.create(
                    self.domain,
                    username,
                    password,
                    phone_number=strip_plus(self.msg.phone_number)
                )
            self.verified_contact = self.user.get_or_create_phone_entry(self.msg.phone_number)
            self.verified_contact.set_two_way()
            self.verified_contact.set_verified()
            self.verified_contact.save()
            # As per earlier ILSGateway system, set language by default to Swahili
            self.user.language = 'sw'

        if first_name or last_name:
            self.user.first_name = first_name
            self.user.last_name = last_name
        self.user.set_location(loc)
        self.user.is_active = True
        self.user.user_data['role'] = role
        self.user.save()
        params['contact_name'] = name

        if params:
            self.respond(message, **params)
        return True
