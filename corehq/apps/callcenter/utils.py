from __future__ import absolute_import
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2
import uuid
from xml.etree import ElementTree
from corehq.apps.hqcase.utils import submit_case_blocks
from couchdbkit.exceptions import MultipleResultsFound, NoResultFound
from ctable.models import SqlExtractMapping, ColumnDef, KeyMatcher

MAPPING_NAME = 'call_center'


def sync_user_cases(commcare_user):
    from casexml.apps.case.tests.util import CaseBlock

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
        case = CommCareCase.view('hqcase/by_domain_hq_user_id',
                                 key=[domain.name, commcare_user._id],
                                 reduce=False,
                                 include_docs=True).one()
        found = bool(case)
    except NoResultFound:
        pass
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

    mapping = SqlExtractMapping.by_name(domain.name, MAPPING_NAME)

    if not mapping:
        mapping = SqlExtractMapping()

    mapping.auto_generated = True
    mapping.domains = [domain.name]
    mapping.name = MAPPING_NAME
    mapping.couch_view = 'formtrends/form_duration_by_user'
    mapping.couch_key_prefix = ['dux', domain.name]
    mapping.couch_date_range = 1
    mapping.active = True
    mapping.columns = [
        ColumnDef(name="date", data_type="date", value_source="key", value_index=2,
                  date_format="%Y-%m-%dT%H:%M:%S.%fZ"),
        ColumnDef(name="user_id", data_type="string", value_source="key", value_index=3),
        ColumnDef(name="xmlns", data_type="string", value_source="key", value_index=4),
        ColumnDef(name="duration_sum", data_type="integer", value_source="value",
                  value_attribute='sum', match_keys=[KeyMatcher(index=0, value="dux")]),
        ColumnDef(name="sumbission_count", data_type="integer", value_source="value",
                  value_attribute='count', match_keys=[KeyMatcher(index=0, value="dux")]),
    ]

    mapping.save()
