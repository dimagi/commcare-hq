from collections import namedtuple
from datetime import datetime, timedelta

import attr
import pytz

from corehq.apps.domain.models import Domain
from corehq.apps.es import filters
from corehq.apps.es.domains import DomainES
from corehq.form_processor.models import CommCareCase
from corehq.util.quickcache import quickcache
from corehq.util.timezones.conversions import ServerTime, UserTime


@attr.s
class DomainLite(object):
    name = attr.ib()
    default_timezone = attr.ib()
    cc_case_type = attr.ib()
    use_fixtures = attr.ib()
    form_datasource_enabled = attr.ib(default=True)
    case_datasource_enabled = attr.ib(default=True)
    case_actions_datasource_enabled = attr.ib(default=True)

    def midnights(self, utcnow=None):
        """Returns a list containing two datetimes in UTC that corresponds to midnight
        in the domains timezone on either side of the current UTC datetime.
        i.e. [<previous midnight in TZ>, <next midnight in TZ>]

        >>> d = DomainLite('', 'Asia/Kolkata', '', True)
        >>> d.midnights(datetime(2015, 8, 27, 18, 30, 0  ))
        [datetime.datetime(2015, 8, 26, 18, 30), datetime.datetime(2015, 8, 27, 18, 30)]
        >>> d.midnights(datetime(2015, 8, 27, 18, 31, 0  ))
        [datetime.datetime(2015, 8, 27, 18, 30), datetime.datetime(2015, 8, 28, 18, 30)]
        """
        utcnow = utcnow or datetime.utcnow()
        tz = pytz.timezone(self.default_timezone)
        current_time_tz = ServerTime(utcnow).user_time(tz).done()
        midnight_tz1 = current_time_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_tz_utc1 = UserTime(midnight_tz1).server_time().done()
        midnight_tz_utc2 = midnight_tz_utc1 + timedelta(days=(1 if midnight_tz_utc1 < utcnow else -1))
        return sorted([midnight_tz_utc1, midnight_tz_utc2])


class CallCenterCase(namedtuple('CallCenterCase', 'case_id hq_user_id')):
    @classmethod
    def from_case(cls, case):
        if not case:
            return

        hq_user_id = case.get_case_property('hq_user_id')
        if hq_user_id:
            return CallCenterCase(case_id=case.case_id, hq_user_id=hq_user_id)


def is_midnight_for_domain(midnight_form_domain, error_margin=15, current_time=None):
    current_time = current_time or datetime.utcnow()
    diff = current_time - midnight_form_domain
    return diff.days >= 0 and diff < timedelta(minutes=error_margin)


def get_call_center_domains():
    result = (
        DomainES()
        .is_active()
        .filter(filters.term('call_center_config.enabled', True))
        .source([
            'name',
            'default_timezone',
            'call_center_config.case_type',
            'call_center_config.case_owner_id',
            'call_center_config.use_user_location_as_owner',
            'call_center_config.use_fixtures'])
        .run()
    )

    def to_domain_lite(hit):
        config = hit.get('call_center_config', {})
        case_type = config.get('case_type', None)
        case_owner_id = config.get('case_owner_id', None)
        use_user_location_as_owner = config.get('use_user_location_as_owner', None)
        if case_type and (case_owner_id or use_user_location_as_owner):
            # see CallCenterProperties.config_is_valid()
            return DomainLite(
                name=hit['name'],
                default_timezone=hit['default_timezone'],
                cc_case_type=case_type,
                use_fixtures=config.get('use_fixtures', True),
                form_datasource_enabled=config.get('form_datasource_enabled', True),
                case_datasource_enabled=config.get('case_datasource_enabled', True),
                case_actions_datasource_enabled=config.get('case_actions_datasource_enabled', True),
            )
    return [_f for _f in [to_domain_lite(hit) for hit in result.hits] if _f]


def get_call_center_cases(domain_name, case_type, user=None):
    all_cases = []

    if user:
        case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type(
            domain_name, case_type=case_type, owner_ids=user.get_owner_ids(domain_name))
    else:
        case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type(
            domain_name, case_type=case_type)

    for case in CommCareCase.objects.iter_cases(case_ids, domain_name):
        cc_case = CallCenterCase.from_case(case)
        if cc_case:
            all_cases.append(cc_case)
    return all_cases


@quickcache(['domain'])
def get_call_center_case_type_if_enabled(domain):
    domain_object = Domain.get_by_name(domain)
    if not domain_object:
        return

    config = domain_object.call_center_config
    if config.enabled and config.config_is_valid():
        return config.case_type
