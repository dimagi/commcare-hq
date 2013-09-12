from __future__ import absolute_import
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
import uuid
from xml.etree import ElementTree
from corehq.apps.hqcase.utils import submit_case_blocks, get_case_by_domain_hq_user_id
from couchdbkit.exceptions import MultipleResultsFound
from ctable.models import SqlExtractMapping, ColumnDef, KeyMatcher, NOT_EQUAL


MAPPING_NAME_FORMS = 'cc_form_submissions'
MAPPING_NAME_CASES = 'cc_case_updates'
MAPPING_NAME_CASE_OWNERSHIP = 'cc_case_ownership'


def sync_user_cases(commcare_user):
    domain = commcare_user.project
    if not (domain and domain.call_center_config.enabled):
        return

    # language or phone_number can be null and will break
    # case submission
    fields = {
        'name': commcare_user.name,
        'email': commcare_user.email,
        'language': commcare_user.language or '',
        'phone_number': commcare_user.phone_number or ''
    }
    # fields comes second to prevent custom user data overriding
    fields = dict(commcare_user.user_data, **fields)

    found = False
    try:
        case = get_case_by_domain_hq_user_id(domain.name, commcare_user._id, include_docs=True)
        found = bool(case)
    except MultipleResultsFound:
        return

    close = commcare_user.to_be_deleted() or not commcare_user.is_active

    if found:
        caseblock = CaseBlock(
            create=False,
            case_id=case._id,
            version=V2,
            owner_id=domain.call_center_config.case_owner_id,
            case_type=domain.call_center_config.case_type,
            close=close,
            update=fields
        )
    else:
        fields['hq_user_id'] = commcare_user._id
        caseblock = CaseBlock(
            create=True,
            case_id=uuid.uuid4().hex,
            owner_id=domain.call_center_config.case_owner_id,
            user_id=commcare_user._id,
            version=V2,
            case_type=domain.call_center_config.case_type,
            update=fields
        )

    casexml = ElementTree.tostring(caseblock.as_xml())
    submit_case_blocks(casexml, domain, commcare_user.username, commcare_user._id)


def bootstrap_callcenter(domain):
    if not (domain and domain.name and domain.call_center_config.enabled):
        return

    create_form_mapping(domain)
    create_case_mapping(domain)
    create_case_ownership_mapping(domain)


def create_form_mapping(domain):
    mapping = get_or_create_mapping(domain, MAPPING_NAME_FORMS)

    mapping.couch_view = 'formtrends/form_duration_by_user'
    mapping.couch_key_prefix = ['dux', domain.name]
    mapping.columns = [
        ColumnDef(name="date", data_type="date", value_source="key", value_index=2,
                  date_format="%Y-%m-%dT%H:%M:%S.%fZ"),
        ColumnDef(name="user_id", data_type="string", value_source="key", value_index=3),
        ColumnDef(name="xmlns", data_type="string", value_source="key", value_index=4),
        ColumnDef(name="duration_sum", data_type="integer", value_source="value",
                  value_attribute='sum'),
        ColumnDef(name="sumbission_count", data_type="integer", value_source="value",
                  value_attribute='count'),
    ]
    mapping.save()


def create_case_mapping(domain):
    mapping = get_or_create_mapping(domain, MAPPING_NAME_CASES)

    mapping.couch_view = 'callcenter/case_actions_by_user'
    mapping.couch_key_prefix = [domain.name]
    mapping.columns = [
        ColumnDef(name="date", data_type="date", value_source="key", value_index=1,
                  date_format="%Y-%m-%dT%H:%M:%SZ"),
        ColumnDef(name="user_id", data_type="string", value_source="key", value_index=2),
        ColumnDef(name="case_type", data_type="string", value_source="key", value_index=3),
        ColumnDef(name="action_type", data_type="string", value_source="key", value_index=4),
        ColumnDef(name="case_id", data_type="string", value_source="key", value_index=5),
        ColumnDef(name="action_count", data_type="integer", value_source="value"),
    ]
    mapping.save()


def create_case_ownership_mapping(domain):
    mapping = get_or_create_mapping(domain, MAPPING_NAME_CASE_OWNERSHIP, date_range=None)

    mapping.couch_view = 'case/by_date_modified_owner'
    mapping.couch_key_prefix = [domain.name]
    mapping.couch_group_level = 4
    mapping.columns = [
        ColumnDef(name="user_id", data_type="string", value_source="key", value_index=3),
        ColumnDef(name="case_type", data_type="string", value_source="key", value_index=2),
        ColumnDef(name="open_cases", data_type="integer", value_source="value",
                  match_keys=[KeyMatcher(index=1, value='open'),
                              KeyMatcher(index=2, value='{}', operator=NOT_EQUAL)]),
        ColumnDef(name="closed_cases", data_type="integer", value_source="value",
                  match_keys=[KeyMatcher(index=1, value='closed'),
                              KeyMatcher(index=2, value='{}', operator=NOT_EQUAL)]),
    ]
    mapping.save()


def get_or_create_mapping(domain, mapping_name, date_range=2):
    mapping = SqlExtractMapping.by_name(domain.name, mapping_name)
    if not mapping:
        mapping = SqlExtractMapping()

    mapping.auto_generated = True
    mapping.domains = [domain.name]
    mapping.name = mapping_name
    mapping.active = True
    mapping.couch_date_range = date_range

    return mapping
