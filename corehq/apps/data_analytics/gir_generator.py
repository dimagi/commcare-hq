from __future__ import absolute_import
from __future__ import unicode_literals
import datetime

from collections import namedtuple, defaultdict

from django_countries.data import COUNTRIES

from dimagi.utils.dates import add_months

from corehq.apps.domain.models import Domain
from corehq.apps.data_analytics.esaccessors import (
    get_domain_device_breakdown_es, active_mobile_users, get_possibly_experienced
)
from corehq.apps.data_analytics.models import MALTRow, GIRRow
from corehq.apps.data_analytics.const import (
    TEST_COUCH_TO_SQL_MAP, AMPLIFY_COUCH_TO_SQL_MAP, NOT_SET, BU_MAPPING, NO_BU,
    DEFAULT_EXPERIENCED_THRESHOLD, DEFAULT_PERFORMANCE_THRESHOLD
)
import six


UserCategories = namedtuple('UserCategories', 'active performing experienced total sms eligible')


class GIRTableGenerator(object):
    """
        Populates SQL table with data for given list of monthly-datespans
        See .models.GIRRow
    """

    def __init__(self, datespan_object_list):
        self.monthspan_list = datespan_object_list

    def build_table(self):

        def fetch_latest_doc(dom1_id, dom2_id):
            dom1 = Domain.get(dom1_id)
            dom2 = Domain.get(dom2_id)
            assert dom1.name == dom2.name
            return dom2 if dom1.last_modified < dom2.last_modified else dom1

        domains_by_name = {}
        rows = []
        # filter out duplicate domain docs
        for domain in Domain.get_all():
            if domain.name in domains_by_name:
                latest_domain = fetch_latest_doc(domain.get_id, domains_by_name[domain.name].get_id)
                domains_by_name[domain.name] = latest_domain
            else:
                domains_by_name[domain.name] = domain
        for _, domain in six.iteritems(domains_by_name):
            for monthspan in self.monthspan_list:
                gir_dict = GIRTableGenerator.get_gir_dict_for_domain_and_monthspan(domain, monthspan)
                rows.append(gir_dict)
        GIRRow.objects.bulk_create(
            [GIRRow(**gir_row) for gir_row in rows]
        )

    @staticmethod
    def classify_users(domain, monthspan):
        performing_users = set()
        experienced_users = set()
        eligible_forms = 0
        all_users, user_forms, sms = active_mobile_users(domain, monthspan.startdate, monthspan.computed_enddate)
        user_query = MALTRow.objects.filter(domain_name=domain).filter(month__lte=monthspan.startdate)\
            .values('user_id', 'month').distinct()
        user_months = defaultdict(int)
        for entry in user_query:
            user_months[entry['user_id']] += 1
        for user in all_users:
            if user_forms.get(user, 0) >= \
                    (domain.internal.performance_threshold or DEFAULT_PERFORMANCE_THRESHOLD):
                performing_users.add(user)
            if user_months.get(user, 0) > \
                    (domain.internal.experienced_threshold or DEFAULT_EXPERIENCED_THRESHOLD):
                experienced_users.add(user)
        for user in performing_users & experienced_users:
            eligible_forms += user_forms.get(user)
        return UserCategories(set(user_forms.keys()), performing_users,
                              experienced_users, all_users, sms, eligible_forms)

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
        months = (domain.internal.experienced_threshold or DEFAULT_EXPERIENCED_THRESHOLD) - 1
        threshold_month = add_months(monthspan.startdate.year, monthspan.startdate.month, -months)
        first_month = datetime.date(day=1, year=threshold_month[0], month=threshold_month[1])
        all_users, users_dict, sms = active_mobile_users(domain, first_month, monthspan.computed_enddate)
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
                max_number = number
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
                ', '.join([six.text_type(COUNTRIES.get(abbr, abbr)) for abbr in domain.deployment.countries]),
            'sector': domain.internal.area,
            'subsector': domain.internal.sub_area,
            'bu': GIRTableGenerator.get_bu(domain),
            'self_service': domain.internal.self_started,
            'test_domain': TEST_COUCH_TO_SQL_MAP.get(domain.is_test, NOT_SET),
            'start_date': domain.date_created,
            'device_id': max_device,
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
            'active_in_span': len(recently_active),
            'eligible_forms': user_tuple.eligible,
            'experienced_threshold': domain.internal.experienced_threshold or DEFAULT_EXPERIENCED_THRESHOLD,
            'performance_threshold': domain.internal.performance_threshold or DEFAULT_PERFORMANCE_THRESHOLD,
        }
        return gir_dict
