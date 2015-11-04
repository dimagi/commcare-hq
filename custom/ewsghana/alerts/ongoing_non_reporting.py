from collections import defaultdict
from datetime import datetime, timedelta
from django.db.models.aggregates import Max
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from custom.ewsghana.alerts import ONGOING_NON_REPORTING
from custom.ewsghana.alerts.alert import WeeklyAlert


class OnGoingNonReporting(WeeklyAlert):

    message = ONGOING_NON_REPORTING

    def get_sql_locations(self):
        return SQLLocation.active_objects.filter(domain=self.domain, location_type__name='district')

    def program_clause(self, user_program, not_reported_programs):
        return not_reported_programs and (not user_program or user_program in not_reported_programs)

    def get_message(self, user, data):
        date_until = datetime.utcnow() - timedelta(days=21)
        program_id = user.get_domain_membership(self.domain).program_id
        locations = []

        if program_id:
            for location_name, programs_dict in data.iteritems():
                if program_id in programs_dict and \
                        (not programs_dict[program_id] or programs_dict[program_id] < date_until):
                    locations.append(location_name)
        else:
            for location_name, programs_dict in data.iteritems():
                if all([not last_reported or last_reported < date_until
                        for last_reported in programs_dict.values()]):
                    locations.append(location_name)

        if not locations:
            return
        return self.message % ', '.join(sorted(locations))

    def get_data(self, sql_location):
        data = defaultdict(dict)
        for child in sql_location.get_descendants().filter(location_type__administrative=False):
            location_products = set(child.products)
            location_programs = {p.program_id for p in child.products}

            for program_id in location_programs:
                data[child.name][program_id] = None

            states = StockState.objects.filter(
                case_id=child.supply_point_id,
                sql_product__in=location_products,
            ).values('sql_product__program_id').annotate(last_reported=Max('last_modified_date'))
            for state in states:
                data[child.name][state['sql_product__program_id']] = state['last_reported']

        return data
