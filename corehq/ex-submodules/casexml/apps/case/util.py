from __future__ import generator_stop

import datetime
import uuid
from collections import defaultdict, namedtuple

from django.utils.dateparse import parse_datetime

from iso8601 import iso8601

from casexml.apps.case.const import CASE_ACTION_CREATE, CASE_ACTION_UPDATE
from casexml.apps.case.exceptions import PhoneDateValueError
from casexml.apps.phone.models import delete_synclogs
from casexml.apps.phone.xml import get_case_xml

from corehq.form_processor.models import XFormInstance
from corehq.util.soft_assert import soft_assert


def validate_phone_datetime(datetime_string, none_ok=False, form_id=None):
    if isinstance(datetime_string, datetime.datetime):
        return datetime_string

    if none_ok:
        if datetime_string is None:
            return None
        if not datetime_string != '':
            soft_assert('@'.join(['droberts', 'dimagi.com']))(
                False,
                'phone datetime should never be empty',
                {'form_id': form_id}
            )
            return None
    try:
        return iso8601.parse_date(datetime_string)
    except iso8601.ParseError:
        raise PhoneDateValueError('{!r}'.format(datetime_string))


def create_real_cases_from_dummy_cases(cases):
    """
    Takes as input a list of unsaved CommCareCase objects

    that don't have any case actions, etc.
    and creates them through the official channel of submitting forms, etc.

    returns a tuple of two lists: forms posted and cases created

    """
    from corehq.apps.hqcase.utils import submit_case_blocks
    posted_cases = []
    posted_forms = []
    case_blocks_by_domain = defaultdict(list)
    for case in cases:
        if not case.modified_on:
            case.modified_on = datetime.datetime.utcnow()
        if not case._id:
            case._id = uuid.uuid4().hex
        case_blocks_by_domain[case.domain].append(get_case_xml(
            case, (CASE_ACTION_CREATE, CASE_ACTION_UPDATE), version='2.0'))
    for domain, case_blocks in case_blocks_by_domain.items():
        form, cases = submit_case_blocks(case_blocks, domain=domain)
        posted_forms.append(form)
        posted_cases.extend(cases)
    return posted_forms, posted_cases


def prune_previous_log(sync_log):
    if sync_log.previous_log_id:
        delete_synclogs(sync_log)
        sync_log.previous_log_id = None
        return True
    return False


def primary_actions(case):
    return [a for a in case.actions if not a.is_case_rebuild]


def property_changed_in_action(domain, case_transaction, case_id, case_property_name):
    from casexml.apps.case.xform import get_case_updates
    PropertyChangedInfo = namedtuple("PropertyChangedInfo", 'transaction new_value modified_on')
    include_create_fields = case_property_name in ['owner_id', 'name', 'external_id']

    case_updates = get_case_updates(case_transaction.form)

    actions = []
    for update in case_updates:
        if update.id == case_id:
            actions.append((update.modified_on_str, update.get_update_action(), case_transaction))
            if include_create_fields and case_transaction.is_case_create:
                actions.append((update.modified_on_str, update.get_create_action(), case_transaction))

    for (modified_on, action, case_transaction) in actions:
        if action:
            property_changed = action.dynamic_properties.get(case_property_name)
            if include_create_fields and not property_changed:
                property_changed = getattr(action, case_property_name, None)

            if property_changed is not None:
                return PropertyChangedInfo(case_transaction, property_changed, modified_on)

    return False


def get_latest_property_change_to_value(case, case_property_name, value):
    """Returns a PropertyChangedInfo namedtuple for the last time case_property_name changed to "value"
    """
    case_transactions = case.actions
    for i, case_transaction in enumerate(case_transactions):
        property_changed_info = property_changed_in_action(
            case.domain,
            case_transaction,
            case.case_id,
            case_property_name
        )
        if property_changed_info and property_changed_info.new_value == value:
            return property_changed_info


def get_datetime_case_property_changed(case, case_property_name, value):
    """Returns the datetime a particular case property was changed to a specific value

    Not performant!
    """
    property_changed_info = get_latest_property_change_to_value(case, case_property_name, value)
    if property_changed_info:
        # get the date that case_property changed
        return parse_datetime(property_changed_info.modified_on)


def get_all_changes_to_case_property(case, case_property_name):
    case_property_changes = []
    case_transactions = case.actions
    for transaction in case_transactions:
        property_changed_info = property_changed_in_action(
            case.domain,
            transaction,
            case.case_id,
            case_property_name
        )
        if property_changed_info:
            case_property_changes.append(property_changed_info)

    return case_property_changes


def get_paged_changes_to_case_property(case, case_property_name, start=0, per_page=50):
    """Return paged changes to case properties, and last transaction index checked
    """

    def iter_transactions(transactions):
        for i, transaction in enumerate(transactions):
            property_changed_info = property_changed_in_action(
                case.domain,
                transaction,
                case.case_id,
                case_property_name
            )
            if property_changed_info:
                yield property_changed_info, i + start

    num_actions = len(case.actions)
    if start > num_actions:
        return [], -1

    case_transactions = iter_transactions(
        sorted(case.actions, key=lambda t: t.server_date, reverse=True)[start:]
    )

    infos = []
    last_index = 0
    while len(infos) < per_page:
        try:
            info, last_index = next(case_transactions)
            infos.append(info)
        except StopIteration:
            last_index = -1
            break

    return infos, last_index


def get_case_history(case):
    from casexml.apps.case.xform import extract_case_blocks
    from corehq.apps.reports.display import xmlns_to_name
    from corehq.apps.reports.standard.cases.utils import get_user_type

    changes = defaultdict(dict)
    for form in XFormInstance.objects.get_forms(case.xform_ids, case.domain):
        name = xmlns_to_name(case.domain, form.xmlns, form.app_id, form_name=form.form_data.get('@name'))
        defaults = {
            'Form ID': form.form_id,
            'Form Name': name,
            'Form Received On': form.received_on,
            'Form Submitted By': form.metadata.username,
            'Form User Type': get_user_type(form, case.domain),
        }
        case_blocks = extract_case_blocks(form)
        for block in case_blocks:
            if block.get('@case_id') == case.case_id:
                property_changes = defaults.copy()
                property_changes.update(block.get('create', {}))
                property_changes.update(block.get('update', {}))
                changes[form.form_id].update(property_changes)
    return sorted(changes.values(), key=lambda f: f['Form Received On'])
