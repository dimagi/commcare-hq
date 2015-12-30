import re

from django.contrib.auth.models import User

from corehq.apps.locations.models import SQLLocation, Location

from corehq.apps.sms.mixin import PhoneNumberInUseException, VerifiedNumber
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tanzania.reminders import REGISTER_HELP, Languages, \
    REGISTRATION_CONFIRM_DISTRICT, REGISTRATION_CONFIRM, Roles
from custom.logistics.commtrack import add_location


DISTRICT_PREFIXES = ['d', 'm', 'tb', 'tg', 'dm', 'mz', 'mt', 'mb', 'ir', 'tb', 'ms']


class RegisterHandler(KeywordHandler):
    DISTRICT_REG_DELIMITER = ":"

    def help(self):
        self.respond(REGISTER_HELP)

    def _get_facility_location(self, domain, msd_code):
        return Location.by_site_code(domain, msd_code)

    def _get_district_location(self, domain, sp):
        return SQLLocation.objects.filter(
            domain=domain,
            location_type__name="DISTRICT",
            name=sp,
        )[0].couch_location

    def handle(self):
        text = ' '.join(self.msg.text.split()[1:])
        is_district = False
        sp = ""
        msd_code = ""

        if text.find(self.DISTRICT_REG_DELIMITER) != -1:
            phrases = [x.strip() for x in text.split(":")]
            if len(phrases) != 2:
                self.respond(REGISTER_HELP)
                return
            name = phrases[0]
            sp = phrases[1]
            role = Roles.DISTRICT_PHARMACIST
            message = REGISTRATION_CONFIRM_DISTRICT
            params = {}
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
                return
            else:
                [msd_code] = msd_codes

            role = Roles.IN_CHARGE
            message = REGISTRATION_CONFIRM
            params = {
                "msd_code": msd_code
            }

        if not self.user:
            domains = [config.domain for config in ILSGatewayConfig.get_all_configs()]
            for domain in domains:
                if is_district:
                    loc = self._get_district_location(domain, sp)
                else:
                    loc = self._get_facility_location(domain, msd_code)
                if not loc:
                    continue
                splited_name = name.split(' ', 1)
                first_name = splited_name[0]
                last_name = splited_name[1] if len(splited_name) > 1 else ""
                clean_name = name.replace(' ', '.')
                username = "%s@%s.commcarehq.org" % (clean_name, domain)
                password = User.objects.make_random_password()
                user = CommCareUser.create(domain=domain, username=username, password=password,
                                           commit=False)
                user.first_name = first_name
                user.last_name = last_name
                try:
                    user.set_default_phone_number(self.msg.phone_number.replace('+', ''))
                    user.save_verified_number(domain, self.msg.phone_number.replace('+', ''), True, self.msg.backend_api)
                except PhoneNumberInUseException as e:
                    v = VerifiedNumber.by_phone(self.msg.phone_number, include_pending=True)
                    v.delete()
                    user.save_verified_number(domain, self.msg.phone_number.replace('+', ''), True, self.msg.backend_api)
                except CommCareUser.Inconsistent:
                    continue
                user.language = Languages.DEFAULT
                params.update({
                    'sdp_name': loc.name,
                    'contact_name': name
                })

                user.user_data = {
                    'role': role
                }

                dm = user.get_domain_membership(domain)
                dm.location_id = loc.location_id
                user.save()
                add_location(user, loc.location_id)
        if params:
            self.respond(message, **params)
