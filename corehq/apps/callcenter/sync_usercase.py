import uuid
from collections import namedtuple
from itertools import chain

from django.core.cache import cache

from lxml import etree

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.couch import CriticalSection

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.callcenter.const import CALLCENTER_USER
from corehq.apps.domain.models import Domain
from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.util import user_location_data
from corehq.form_processor.models import CommCareCase
from corehq.toggles import USH_USERCASES_FOR_WEB_USERS


class _UserCaseHelper:

    CASE_SOURCE_ID = __name__ + "._UserCaseHelper."

    def __init__(self, domain, owner_id, user_id):
        self.domain = domain
        self.owner_id = owner_id
        self.user_id = user_id
        self.case_blocks = []
        self.tasks = []

    @classmethod
    def commit(cls, helpers):
        case_blocks = list(chain.from_iterable([h.case_blocks for h in helpers]))
        if not case_blocks:
            assert not any(h.tasks for h in helpers), [h.tasks for h in helpers]
            return
        assert len({h.user_id for h in helpers}) == 1
        assert len({h.domain for h in helpers}) == 1

        case_blocks = [cb.as_text() for cb in case_blocks]
        submit_case_blocks(case_blocks, helpers[0].domain, device_id=cls.CASE_SOURCE_ID)
        for task, task_args in chain.from_iterable([h.tasks for h in helpers]):
            task.delay(*task_args)

    @staticmethod
    def re_open_case(case):
        transactions = case.get_closing_transactions()
        for transaction in transactions:
            transaction.form.archive()

    def create_usercase(self, fields):
        self.case_blocks.append(CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            owner_id=fields.pop('owner_id'),
            user_id=CALLCENTER_USER,
            case_type=fields.pop('case_type'),
            case_name=fields.pop('name', None),
            update=fields
        ))
        self._user_case_changed(fields)

    def update_user_case(self, case, fields, close):
        kwargs = {}
        if 'owner_id' in fields:
            kwargs['owner_id'] = fields.pop('owner_id')
        if 'case_type' in fields:
            kwargs['case_type'] = fields.pop('case_type')
        if 'name' in fields:
            kwargs['case_name'] = fields.pop('name')
        self.case_blocks.append(CaseBlock(
            create=False,
            case_id=case.case_id,
            close=close,
            update=fields,
            **kwargs,
        ))
        self._user_case_changed(fields)

    def _user_case_changed(self, fields):
        field_names = list(fields)
        if _domain_has_new_fields(self.domain, field_names):
            self.tasks.append((add_inferred_export_properties, (
                'UserSave',
                self.domain,
                USERCASE_TYPE,
                field_names,
            )))


def _domain_has_new_fields(domain, field_names):
    cache_key = f'user_case_fields_{domain}'
    cached_fields = cache.get(cache_key)
    new_field_set = set(field_names)
    if cached_fields != new_field_set:
        cache.set(cache_key, new_field_set)
        return True

    return False


def _get_sync_usercase_helper(user, domain, case_type, owner_id, case=None):
    fields = _get_user_case_fields(user, case_type, owner_id, domain)
    case = case or CommCareCase.objects.get_case_by_external_id(domain, user.user_id, case_type)
    close = user.to_be_deleted() or not user.is_active
    user_case_helper = _UserCaseHelper(domain, owner_id, user.user_id)

    def case_should_be_reopened(case, user_case_should_be_closed):
        return case and case.closed and not user_case_should_be_closed

    if not case:
        user_case_helper.create_usercase(fields)
    else:
        if case_should_be_reopened(case, close):
            user_case_helper.re_open_case(case)
        changed_fields = _get_changed_fields(case, fields)
        close_case = close and not case.closed
        if changed_fields or close_case:
            user_case_helper.update_user_case(case, changed_fields, close_case)
    return user_case_helper


def _get_user_case_fields(user, case_type, owner_id, domain):

    def valid_element_name(name):
        try:
            etree.Element(name)
            return True
        except ValueError:
            return False

    # remove any keys that aren't valid XML element names
    fields = {k: v for k, v in user.get_user_data(domain).items() if
              valid_element_name(k)}

    if user.is_web_user:
        fields['commcare_location_id'] = user.get_location_id(domain)
        fields['commcare_location_ids'] = user_location_data(user.get_location_ids(domain))

    # language or phone_number can be null and will break
    # case submission
    fields.update({
        'name': user.name or user.raw_username,
        'username': user.raw_username,
        'email': user.email,
        'language': user.language or '',
        'phone_number': user.phone_number or '',
        'last_device_id_used': user.devices[0].device_id if user.devices else '',
        'owner_id': owner_id,
        'case_type': case_type,
        'hq_user_id': user.get_id,
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
    })

    return fields


def _get_changed_fields(case, fields):
    def _to_unicode(val):
        if isinstance(val, bytes):
            return val.decode('utf8')
        elif not isinstance(val, str):
            return str(val)
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


def _iter_call_center_case_helpers(user):
    if user.is_web_user():
        return
    config = user.project.call_center_config
    if config.enabled and config.config_is_valid():
        case, owner_id = _get_call_center_case_and_owner(user, user.project)
        yield _get_sync_usercase_helper(user, user.domain, config.case_type, owner_id, case)


CallCenterCaseAndOwner = namedtuple('CallCenterCaseAndOwner', 'case owner_id')


def _get_call_center_case_and_owner(user, domain_obj):
    """
    Return the appropriate owner id for the given users call center case.
    """
    config = domain_obj.call_center_config
    case = CommCareCase.objects.get_case_by_external_id(
        domain_obj.name, user.user_id, config.case_type
    )
    if config.use_user_location_as_owner:
        owner_id = _call_center_location_owner(user, config.user_location_ancestor_level)
    elif case and case.owner_id:
        owner_id = case.owner_id
    else:
        owner_id = config.case_owner_id
    return CallCenterCaseAndOwner(case, owner_id)


def _call_center_location_owner(user, ancestor_level):
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


def _iter_sync_usercase_helpers(user, domain_obj):
    if (domain_obj.usercase_enabled
            and USH_USERCASES_FOR_WEB_USERS.enabled(domain_obj.name) or not user.is_web_user()):
        yield _get_sync_usercase_helper(
            user,
            domain_obj.name,
            USERCASE_TYPE,
            user.get_id
        )


def sync_usercases(user, domain, sync_call_center=True):
    """
    Each time a user is saved this method gets called and creates or updates
    a case associated with the user with the user's details.

    This is also called to create usercases when the usercase is used for the
    first time.
    """
    with CriticalSection([f"sync_user_case_for_{user.user_id}_{domain}"]):
        domain_obj = Domain.get_by_name(domain)
        helpers = list(chain(
            _iter_sync_usercase_helpers(user, domain_obj),
            _iter_call_center_case_helpers(user) if sync_call_center else [],
        ))
        _UserCaseHelper.commit(helpers)
