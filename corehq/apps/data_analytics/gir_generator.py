import datetime

from collections import namedtuple

from django_countries.data import COUNTRIES

from dimagi.utils.dates import add_months

from corehq.apps.domain.models import Domain
from corehq.apps.data_analytics.esaccessors import (
    get_domain_device_breakdown_es, active_mobile_users, get_possibly_experienced
)
from corehq.apps.data_analytics.models import MALTRow, GIRRow
from corehq.apps.data_analytics.const import (
    TEST_COUCH_TO_SQL_MAP, AMPLIFY_COUCH_TO_SQL_MAP, NOT_SET, BU_MAPPING, NO_BU
)


UserCategories = namedtuple('UserCategories', 'active performing experienced total sms')


class GIRTableGenerator(object):
    """
        Populates SQL table with data for given list of monthly-datespans
        See .models.GIRRow
    """

    def __init__(self, datespan_object_list):
        self.monthspan_list = datespan_object_list

    def build_table(self):
        rows = []
        for domain in Domain.get_all():
            for monthspan in self.monthspan_list:
                gir_dict = GIRTableGenerator.get_gir_dict_for_domain_and_monthspan(domain, monthspan)
                rows.append(gir_dict)
        GIRRow.objects.bulk_create(
            [GIRRow(**gir_row) for gir_row in rows]
        )

    @staticmethod
    def classify_users(domain, monthspan):
        performing_users = []
        experienced_users = []
        all_users, users_dict, sms = active_mobile_users(domain, monthspan.startdate, monthspan.enddate)
        for user in all_users:
            if users_dict.get(user, 0) > domain.internal.performance_threshold:
                performing_users.append(user)
            if len(MALTRow.objects.filter(user_id=user).values('month').distinct()) > \
                    domain.internal.experienced_threshold:
                experienced_users.append(user)
        return UserCategories(set(users_dict.keys()), set(performing_users),
                              set(experienced_users), all_users, sms)

    @staticmethod
    def get_bu(domain):
        if domain.internal.business_unit:
            return domain.internal.business_unit
        elif domain.deployment.countries:
            return BU_MAPPING.get(domain.deployment.countries[0], NO_BU)
        else:
            return NO_BU

    @staticmethod
    def get_active_recent(domain, monthspan):
        months = domain.internal.experienced_threshold - 1
        threshold_month = add_months(monthspan.startdate.year, monthspan.startdate.month, -months)
        first_month = datetime.date(day=1, year=threshold_month[0], month=threshold_month[1])
        all_users, users_dict, sms = active_mobile_users(domain, first_month, monthspan.enddate)
        return set(users_dict.keys()) | sms

    @staticmethod
    def get_max_device(domain, monthspan):
        device_dict = {
            'cloudcare': 0,
            'sms': 0,
            'mobile': 0,
        }
        device_data = get_domain_device_breakdown_es(domain.name, monthspan)
        for device, number in device_data.items():
            if device == 'cloudcare':
                device_dict['cloudcare'] = number
            elif device == 'commconnect':
                device_dict['sms'] = number
            else:
                device_dict['mobile'] += number
        max_number = 0
        max_device = ''
        for device, number in device_dict.items():
            if number > max_number:
                max_device = device
        return max_device

    @staticmethod
    def get_gir_dict_for_domain_and_monthspan(domain, monthspan):
        user_tuple = GIRTableGenerator.classify_users(domain, monthspan)
        max_device = GIRTableGenerator.get_max_device(domain, monthspan)
        possible_experience = get_possibly_experienced(domain, monthspan)
        recently_active = GIRTableGenerator.get_active_recent(domain, monthspan)
        gir_dict = {
            'month': monthspan.startdate,
            'domain_name': domain.name,
            'country':
                ', '.join([unicode(COUNTRIES.get(abbr, abbr)) for abbr in domain.deployment.countries]),
            'sector': domain.internal.area,
            'subsector': domain.internal.sub_area,
            'bu': GIRTableGenerator.get_bu(domain),
            'self_service': domain.internal.self_started,
            'test_domain': TEST_COUCH_TO_SQL_MAP.get(domain.is_test, NOT_SET),
            'start_date': domain.date_created,
            'device_id': max_device,
            'wam': AMPLIFY_COUCH_TO_SQL_MAP.get(domain.internal.amplifies_workers, NOT_SET),
            'pam': AMPLIFY_COUCH_TO_SQL_MAP.get(domain.internal.amplifies_project, NOT_SET),
            'wams_current': len(user_tuple.performing & user_tuple.experienced),
            'active_users': len(user_tuple.active | user_tuple.sms),
            'using_and_performing': len(user_tuple.performing),
            'not_performing': len(user_tuple.active - user_tuple.performing),
            'inactive_experienced':
                len((user_tuple.total - user_tuple.active) & user_tuple.experienced),
            'inactive_not_experienced':
                len((user_tuple.total - user_tuple.active) - user_tuple.experienced),
            'not_experienced': len(user_tuple.performing - user_tuple.experienced),
            'not_performing_not_experienced':
                len(user_tuple.active - user_tuple.performing - user_tuple.experienced),
            'active_ever': len(possible_experience | recently_active),
            'possibly_exp': len(possible_experience),
            'ever_exp': len(user_tuple.experienced),
            'exp_and_active_ever': len(user_tuple.active & user_tuple.experienced),
            'active_in_span': len(recently_active)
        }
        return gir_dict