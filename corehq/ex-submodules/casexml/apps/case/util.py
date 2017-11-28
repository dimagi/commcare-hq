from __future__ import absolute_import
from collections import defaultdict, namedtuple
import uuid

from xml.etree import cElementTree as ElementTree
import datetime

from django.conf import settings
from django.utils.dateparse import parse_datetime
from iso8601 import iso8601
from restkit.errors import ResourceError

from casexml.apps.case.const import CASE_ACTION_UPDATE, CASE_ACTION_CREATE
from casexml.apps.case.dbaccessors import get_indexed_case_ids
from casexml.apps.case.exceptions import PhoneDateValueError
from casexml.apps.phone.models import SyncLogAssertionError, get_properly_wrapped_sync_log
from casexml.apps.phone.xml import get_case_element
from casexml.apps.stock.models import StockReport
from corehq.util.soft_assert import soft_assert
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs


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


def post_case_blocks(case_blocks, form_extras=None, domain=None, user_id=None, device_id=None):
    """
    Post case blocks.

    Extras is used to add runtime attributes to the form before
    sending it off to the case (current use case is sync-token pairing)

    See `device_id` parameter documentation at
    `corehq.apps.hqcase.utils.submit_case_blocks`.
    """
    from corehq.apps.hqcase.utils import submit_case_blocks

    if form_extras is None:
        form_extras = {}

    domain = domain or form_extras.pop('domain', None)
    if getattr(settings, 'UNIT_TESTING', False):
        from casexml.apps.case.tests.util import TEST_DOMAIN_NAME
        domain = domain or TEST_DOMAIN_NAME

    return submit_case_blocks(
        [ElementTree.tostring(case_block) for case_block in case_blocks],
        domain=domain,
        form_extras=form_extras,
        user_id=user_id,
        device_id=device_id,
    )


def create_real_cases_from_dummy_cases(cases):
    """
    Takes as input a list of unsaved CommCareCase objects

    that don't have any case actions, etc.
    and creates them through the official channel of submitting forms, etc.

    returns a tuple of two lists: forms posted and cases created

    """
    posted_cases = []
    posted_forms = []
    case_blocks_by_domain = defaultdict(list)
    for case in cases:
        if not case.modified_on:
            case.modified_on = datetime.datetime.utcnow()
        if not case._id:
            case._id = uuid.uuid4().hex
        case_blocks_by_domain[case.domain].append(get_case_element(
            case, (CASE_ACTION_CREATE, CASE_ACTION_UPDATE), version='2.0'))
    for domain, case_blocks in case_blocks_by_domain.items():
        form, cases = post_case_blocks(case_blocks, domain=domain)
        posted_forms.append(form)
        posted_cases.extend(cases)
    return posted_forms, posted_cases


def get_case_xform_ids(case_id):
    results = XFormInstance.get_db().view('form_case_index/form_case_index',
                                          reduce=False,
                                          startkey=[case_id],
                                          endkey=[case_id, {}])

    # also have to add commtrack forms, which may not appear in the form --> case index
    commtrack_reports = StockReport.objects.filter(stocktransaction__case_id=case_id)
    commtrack_forms = commtrack_reports.values_list('form_id', flat=True).distinct()
    return list(set([row['key'][1] for row in results] + list(commtrack_forms)))


def update_sync_log_with_checks(sync_log, xform, cases, case_db,
                                case_id_blacklist=None):
    assert case_db is not None
    from casexml.apps.case.xform import CaseProcessingConfig

    case_id_blacklist = case_id_blacklist or []
    try:
        sync_log.update_phone_lists(xform, cases)
    except SyncLogAssertionError as e:
        soft_assert('@'.join(['skelly', 'dimagi.com']))(
            False,
            'SyncLogAssertionError raised while updating phone lists',
            {
                'form_id': xform.form_id,
                'cases': [case.case_id for case in cases]
            }
        )
        if e.case_id and e.case_id not in case_id_blacklist:
            form_ids = get_case_xform_ids(e.case_id)
            case_id_blacklist.append(e.case_id)
            for form_id in form_ids:
                if form_id != xform._id:
                    form = XFormInstance.get(form_id)
                    if form.doc_type == 'XFormInstance':
                        from casexml.apps.case.xform import process_cases_with_casedb
                        process_cases_with_casedb(
                            [form],
                            case_db,
                            CaseProcessingConfig(
                                strict_asserts=True,
                                case_id_blacklist=case_id_blacklist
                            )
                        )
            updated_log = get_properly_wrapped_sync_log(sync_log._id)

            update_sync_log_with_checks(updated_log, xform, cases, case_db,
                                        case_id_blacklist=case_id_blacklist)


def prune_previous_log(sync_log):
    previous_log = sync_log.get_previous_log()
    if previous_log:
        try:
            previous_log.delete()
            sync_log.previous_log_removed = True
            sync_log.save()
        except ResourceError:
            pass


def get_indexed_cases(domain, case_ids):
    """
    Given a base list of cases, gets all wrapped cases that they reference
    (parent cases).
    """
    from casexml.apps.case.models import CommCareCase
    return [CommCareCase.wrap(doc) for doc in iter_docs(CommCareCase.get_db(),
                                                        get_indexed_case_ids(domain, case_ids))]


def primary_actions(case):
    return filter(lambda a: not a.is_case_rebuild,
                  case.actions)


def iter_cases(case_ids, strip_history=False, wrap=True):
    from casexml.apps.case.models import CommCareCase
    if not strip_history:
        for doc in iter_docs(CommCareCase.get_db(), case_ids):
            yield CommCareCase.wrap(doc) if wrap else doc
    else:
        for case in CommCareCase.bulk_get_lite(case_ids, wrap=wrap):
            yield case


def property_changed_in_action(case_transaction, case_id, case_property_name):
    from casexml.apps.case.xform import get_case_updates
    PropertyChangedInfo = namedtuple("PropertyChangedInfo", 'transaction new_value modified_on')
    update_actions = [
        (update.modified_on_str, update.get_update_action(), case_transaction)
        for update in get_case_updates(case_transaction.form)
        if update.id == case_id
    ]
    for (modified_on, update_action, case_transaction) in update_actions:
        if update_action:
            property_changed = update_action.dynamic_properties.get(case_property_name)
            if property_changed:
                return PropertyChangedInfo(case_transaction, property_changed, modified_on)
    return False


def get_latest_property_change_to_value(case, case_property_name, value):
    """Returns a PropertyChangedInfo namedtuple for the last time case_property_name changed to "value"
    """
    case_transactions = case.actions
    for i, case_transaction in enumerate(case_transactions):
        property_changed_info = property_changed_in_action(case_transaction, case.case_id, case_property_name)
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
        property_changed_info = property_changed_in_action(transaction, case.case_id, case_property_name)
        if property_changed_info:
            case_property_changes.append(property_changed_info)

    return case_property_changes
