import re

from corehq.apps.locations.models import SQLLocation

from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import REGISTER_HELP, \
    REGISTRATION_CONFIRM_DISTRICT, REGISTRATION_CONFIRM, Roles, REGISTER_UNKNOWN_DISTRICT, REGISTER_UNKNOWN_CODE

DISTRICT_PREFIXES = ['d', 'm', 'tb', 'tg', 'dm', 'mz', 'mt', 'mb', 'ir', 'tb', 'ms']


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
        ).couch_location

    def _get_district_location(self, domain, sp):
        return SQLLocation.objects.get(
            domain=domain,
            location_type__name="DISTRICT",
            name__iexact=sp,
        ).couch_location

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
            location_regex = '^({prefs})\d+'.format(prefs='|'.join(p.lower() for p in DISTRICT_PREFIXES))
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

        self.user.set_location(loc)
        split_name = name.split(' ', 2)
        first_name = ''
        last_name = ''
        if len(split_name) == 2:
            first_name, last_name = split_name
        elif split_name:
            first_name = split_name[0]

        self.user.first_name = first_name
        self.user.last_name = last_name
        self.user.is_active = True
        self.user.user_data['role'] = role
        self.user.save()
        params['contact_name'] = name

        if params:
            self.respond(message, **params)
        return True
