from corehq.apps.locations.dbaccessors import get_all_users_by_location
from corehq.apps.sms.api import send_sms_to_verified_number


class Alert(object):

    message = None

    def __init__(self, domain):
        self.domain = domain

    def get_sql_locations(self):
        raise NotImplemented()

    def get_users(self, sql_location):
        return [
            user
            for user in get_all_users_by_location(self.domain, sql_location.location_id)
            if user.get_verified_number()
        ]

    def filter_user(self, user):
        raise NotImplemented()

    def program_clause(self, user_program, reported_programs):
        raise NotImplemented()

    def get_message(self, user, data):
        program_id = user.get_domain_membership(self.domain).program_id
        locations = []
        for location_name, programs in data.iteritems():
            if self.program_clause(program_id, programs):
                locations.append(location_name)
        if not locations:
            return
        return self.message % ', '.join(sorted(locations))

    def get_data(self, sql_location):
        raise NotImplemented()

    def send(self):
        for sql_location in self.get_sql_locations():
            data = self.get_data(sql_location)

            for user in self.get_users(sql_location):
                message = self.get_message(user, data)

                if message:
                    send_sms_to_verified_number(user.get_verified_number(), message)
