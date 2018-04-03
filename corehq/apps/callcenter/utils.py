from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from datetime import datetime, timedelta
import pytz
import six

from casexml.apps.case.mock import CaseBlock
import uuid
from xml.etree import cElementTree as ElementTree
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.callcenter.const import CALLCENTER_USER
from corehq.apps.domain.models import Domain
from corehq.apps.es.domains import DomainES
from corehq.apps.es import filters
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.quickcache import quickcache
from corehq.util.timezones.conversions import UserTime, ServerTime
from dimagi.utils.couch import CriticalSection
from django.core.cache import cache


class DomainLite(namedtuple('DomainLite', 'name default_timezone cc_case_type use_fixtures')):

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


class _UserCaseHelper(object):

    CASE_SOURCE_ID = __name__ + "._UserCaseHelper."

    def __init__(self, domain, owner_id):
        self.domain = domain
        self.owner_id = owner_id

    def _submit_case_block(self, caseblock, source):
        device_id = self.CASE_SOURCE_ID + source
        casexml = ElementTree.tostring(caseblock.as_xml())
        submit_case_blocks(casexml, self.domain.name, device_id=device_id)

    @staticmethod
    def re_open_case(case):
        transactions = case.get_closing_transactions()
        for transaction in transactions:
            transaction.form.archive()

    def create_user_case(self, commcare_user, fields):
        caseblock = CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            owner_id=fields.pop('owner_id'),
            user_id=CALLCENTER_USER,
            case_type=fields.pop('case_type'),
            case_name=fields.pop('name', None),
            update=fields
        )
        self._submit_case_block(caseblock, "create_user_case")
        self._user_case_changed(fields)

    def update_user_case(self, case, fields, close):
        caseblock = CaseBlock(
            create=False,
            case_id=case.case_id,
            owner_id=fields.pop('owner_id', CaseBlock.undefined),
            case_type=fields.pop('case_type', CaseBlock.undefined),
            case_name=fields.pop('name', CaseBlock.undefined),
            close=close,
            update=fields
        )
        self._submit_case_block(caseblock, "update_user_case")
        self._user_case_changed(fields)

    def _user_case_changed(self, fields):
        field_names = list(fields)
        if _domain_has_new_fields(self.domain.name, field_names):
            add_inferred_export_properties.delay(
                'UserSave',
                self.domain.name,
                USERCASE_TYPE,
                field_names,
            )


def _domain_has_new_fields(domain, field_names):
    cache_key = 'user_case_fields_{}'.format(domain)
    cached_fields = cache.get(cache_key)
    new_field_set = set(field_names)
    if cached_fields != new_field_set:
        cache.set(cache_key, new_field_set)
        return True

    return False


class CallCenterCase(namedtuple('CallCenterCase', 'case_id hq_user_id')):
    @classmethod
    def from_case(cls, case):
        if not case:
            return

        hq_user_id = case.get_case_property('hq_user_id')
        if hq_user_id:
            return CallCenterCase(case_id=case.case_id, hq_user_id=hq_user_id)


def sync_user_case(commcare_user, case_type, owner_id, case=None):
    """
    Each time a CommCareUser is saved this method gets called and creates or updates
    a case associated with the user with the user's details.

    This is also called to create user cases when the usercase is used for the
    first time.
    """
    with CriticalSection(['user_case_%s_for_%s' % (case_type, commcare_user._id)]):
        domain = commcare_user.project
        fields = _get_user_case_fields(commcare_user, case_type, owner_id)
        case = case or CaseAccessors(domain.name).get_case_by_domain_hq_user_id(commcare_user._id, case_type)
        close = commcare_user.to_be_deleted() or not commcare_user.is_active
        user_case_helper = _UserCaseHelper(domain, owner_id)

        def case_should_be_reopened(case, user_case_should_be_closed):
            return case and case.closed and not user_case_should_be_closed

        if not case:
            user_case_helper.create_user_case(commcare_user, fields)
        else:
            if case_should_be_reopened(case, close):
                user_case_helper.re_open_case(case)
            changed_fields = _get_changed_fields(case, fields)
            close_case = close and not case.closed
            if changed_fields or close_case:
                user_case_helper.update_user_case(case, changed_fields, close_case)


def _get_user_case_fields(commcare_user, case_type, owner_id):

    def valid_element_name(name):
        try:
            ElementTree.fromstring('<{}/>'.format(name))
            return True
        except ElementTree.ParseError:
            return False

    # remove any keys that aren't valid XML element names
    fields = {k: v for k, v in commcare_user.user_data.items() if
              valid_element_name(k)}
    # language or phone_number can be null and will break
    # case submission
    fields.update({
        'name': commcare_user.name or commcare_user.raw_username,
        'username': commcare_user.raw_username,
        'email': commcare_user.email,
        'language': commcare_user.language or '',
        'phone_number': commcare_user.phone_number or '',
        'last_device_id_used': commcare_user.devices[0].device_id if commcare_user.devices else '',
        'owner_id': owner_id,
        'case_type': case_type,
        'hq_user_id': commcare_user.get_id
    })

    return fields


def _get_changed_fields(case, fields):
    def _to_unicode(val):
        if isinstance(val, bytes):
            return val.decode('utf8')
        elif not isinstance(val, six.text_type):
            return six.text_type(val)
        return val

    def _not_same(val1, val2):
        return _to_unicode(val1) != _to_unicode(val2)

    hq_fields = {
        'name': 'name',
        'case_type': 'type',
        'owner_id': 'owner_id'
    }
    changed_fields = {}
    props = case.dynamic_case_properties()
    for field, value in fields.items():
        if field not in hq_fields and _not_same(props.get(field), value):
            changed_fields[field] = value

    for field, attrib in hq_fields.items():
        if _not_same(getattr(case, attrib), fields[field]):
            changed_fields[field] = fields[field]

    return changed_fields


def sync_call_center_user_case(user):
    domain = user.project
    config = domain.call_center_config
    if domain and config.enabled and config.config_is_valid():
        case, owner_id = _get_call_center_case_and_owner(user, domain)
        sync_user_case(user, config.case_type, owner_id, case)


CallCenterCaseAndOwner = namedtuple('CallCenterCaseAndOwner', 'case owner_id')


def _get_call_center_case_and_owner(user, domain):
    """
    Return the appropriate owner id for the given users call center case.
    """
    case = CaseAccessors(domain.name).get_case_by_domain_hq_user_id(
        user._id, domain.call_center_config.case_type
    )
    if domain.call_center_config.use_user_location_as_owner:
        owner_id = call_center_location_owner(user, domain.call_center_config.user_location_ancestor_level)
    elif case and case.owner_id:
        owner_id = case.owner_id
    else:
        owner_id = domain.call_center_config.case_owner_id
    return CallCenterCaseAndOwner(case, owner_id)


def call_center_location_owner(user, ancestor_level):
    if user.location_id is None:
        return ""
    if ancestor_level == 0:
        owner_id = user.location_id
    else:
        location = SQLLocation.objects.get(location_id=user.location_id)
        ancestors = location.get_ancestors(ascending=True, include_self=True).only("location_id")
        try:
            owner_id = ancestors[ancestor_level].location_id
        except IndexError:
            owner_id = ancestors.last().location_id
    return owner_id


def sync_usercase(user):
    domain = user.project
    if domain and domain.usercase_enabled:
        sync_user_case(
            user,
            USERCASE_TYPE,
            user.get_id
        )


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
                use_fixtures=config.get('use_fixtures', True)
            )
    return [_f for _f in [to_domain_lite(hit) for hit in result.hits] if _f]


def get_call_center_cases(domain_name, case_type, user=None):
    all_cases = []

    case_accessor = CaseAccessors(domain_name)

    if user:
        case_ids = [
            case_id for case_id in case_accessor.get_open_case_ids_in_domain_by_type(
                case_type=case_type, owner_ids=user.get_owner_ids()
            )
        ]
    else:
        case_ids = case_accessor.get_open_case_ids_in_domain_by_type(case_type=case_type)

    for case in case_accessor.iter_cases(case_ids):
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
