from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
import six

from casexml.apps.case.mock import CaseBlock
import uuid
from xml.etree import cElementTree as ElementTree
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.callcenter.const import CALLCENTER_USER
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from dimagi.utils.couch import CriticalSection
from django.core.cache import cache


class _UserCaseHelper(object):

    CASE_SOURCE_ID = __name__ + "._UserCaseHelper."

    def __init__(self, domain, owner_id):
        self.domain = domain
        self.owner_id = owner_id

    def _submit_case_block(self, caseblock, source):
        device_id = self.CASE_SOURCE_ID + source
        casexml = ElementTree.tostring(caseblock.as_xml()).decode('utf-8')
        submit_case_blocks(casexml, self.domain, device_id=device_id)

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
        if _domain_has_new_fields(self.domain, field_names):
            add_inferred_export_properties.delay(
                'UserSave',
                self.domain,
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


def _sync_user_case(commcare_user, case_type, owner_id, case=None):
    """
    Each time a CommCareUser is saved this method gets called and creates or updates
    a case associated with the user with the user's details.

    This is also called to create user cases when the usercase is used for the
    first time.
    """
    with CriticalSection(['user_case_%s_for_%s' % (case_type, commcare_user._id)]):
        domain = commcare_user.domain
        fields = _get_user_case_fields(commcare_user, case_type, owner_id)
        case = case or CaseAccessors(domain).get_case_by_domain_hq_user_id(commcare_user._id, case_type)
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
        'hq_user_id': commcare_user.get_id,
        'first_name': commcare_user.first_name or '',
        'last_name': commcare_user.last_name or '',
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
    config = user.project.call_center_config
    if config.enabled and config.config_is_valid():
        case, owner_id = _get_call_center_case_and_owner(user)
        _sync_user_case(user, config.case_type, owner_id, case)


CallCenterCaseAndOwner = namedtuple('CallCenterCaseAndOwner', 'case owner_id')


def _get_call_center_case_and_owner(user):
    """
    Return the appropriate owner id for the given users call center case.
    """
    config = user.project.call_center_config
    case = CaseAccessors(user.domain).get_case_by_domain_hq_user_id(
        user._id, config.case_type
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


def sync_usercase(user):
    if user.project.usercase_enabled:
        _sync_user_case(
            user,
            USERCASE_TYPE,
            user.get_id
        )
