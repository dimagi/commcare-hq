from collections import namedtuple
import uuid
import sqlalchemy
from sqlalchemy import *
from django.conf import settings
from sqlalchemy.engine.url import make_url
from datetime import date, timedelta, datetime
from corehq.apps.sofabed.models import FormData, CaseData

metadata = sqlalchemy.MetaData()


def get_table(mapping):
    return Table(mapping.table_name, metadata, extend_existing=True, *[c.sql_column for c in mapping.columns])


def get_formdata(days_ago, domain, user_id, xmlns=None, duration=1):
    now = datetime.utcnow()
    time_end = now - timedelta(days=days_ago)
    time_start = time_end - timedelta(seconds=duration)
    return {
        '_id': uuid.uuid4().hex,
        'doc_type': 'XFormInstance',
        'domain': domain,
        'form': {
            'meta': {
                'userID': user_id,
                'timeStart': time_start,
                'timeEnd': time_end
            }
        },
        'received_on': now,
        'xmlns': xmlns
    }


CaseInfo = namedtuple('CaseInfo', 'id, days_ago, case_type, is_closed')


def get_casedata(case_info, domain, user_id, owner_id, opened_by, closed_by):
    now = datetime.utcnow()
    date_ago = now - timedelta(days=case_info.days_ago)
    return CaseData(
        case_id=case_info.id,
        type=case_info.case_type,
        domain=domain,
        owner_id=owner_id,
        user_id=user_id,
        opened_on=date_ago,
        opened_by=opened_by or user_id,
        modified_on=now,
        closed=case_info.is_closed,
        closed_on=(date_ago if case_info.is_closed else None),
        closed_by=(closed_by or user_id) if case_info.is_closed else None,
        case_owner=(owner_id or user_id)
    )
    return case


def add_case_action(case):
    case.actions.create(
        index=1,
        action_type='update',
        date=case.opened_on,
        user_id=case.user_id,
        domain=case.domain,
        case_owner=case.case_owner,
        case_type=case.type
    )


def load_data(domain, form_user_id, case_user_id=None,
              case_owner_id=None, case_opened_by=None, case_closed_by=None):
    form_data = [
        get_formdata(0, domain, form_user_id),
        get_formdata(3, domain, form_user_id),
        get_formdata(7, domain, form_user_id),
        get_formdata(8, domain, form_user_id),
        get_formdata(9, domain, form_user_id),
        get_formdata(11, domain, form_user_id),
        get_formdata(14, domain, form_user_id),
        get_formdata(15, domain, form_user_id),
    ]

    case_user_id = case_user_id or form_user_id
    case_owner_id = case_owner_id or case_user_id

    case_infos = [
        CaseInfo('1', 0, 'person', False),
        CaseInfo('2', 10, 'person', False),
        CaseInfo('3', 29, 'person', True),
        CaseInfo('4', 30, 'person', True),
        CaseInfo('5', 31, 'dog', True),
        CaseInfo('6', 45, 'dog', False),
        CaseInfo('7', 55, 'dog', False),
        CaseInfo('8', 56, 'dog', True),
        CaseInfo('9', 59, 'dog', False),
    ]

    case_data = [
        get_casedata(info, domain, case_user_id, case_owner_id, case_opened_by, case_closed_by)
        for info in case_infos
    ]

    _insert_form_data(domain, form_data)

    CaseData.objects.bulk_create(case_data)

    for case in case_data:
        add_case_action(case)


def _insert_form_data(domain, form_data):
    from corehq.apps.callcenter.data_source import get_report_data_sources_for_domain
    adapter = get_report_data_sources_for_domain(domain).forms
    adapter.rebuild_table()
    for data in form_data:
        adapter.save(data)


def load_custom_data(domain, user_id, xmlns):
    form_data = [
        get_formdata(0, domain, user_id, xmlns=xmlns, duration=3),
        get_formdata(1, domain, user_id, xmlns=xmlns, duration=2),
        get_formdata(3, domain, user_id, xmlns=xmlns, duration=4),
        get_formdata(7, domain, user_id, xmlns=xmlns, duration=3),
        get_formdata(8, domain, user_id, xmlns=xmlns, duration=4),
        get_formdata(13, domain, user_id, xmlns=xmlns, duration=5),
        get_formdata(14, domain, user_id, xmlns=xmlns, duration=2),
        get_formdata(17, domain, user_id, xmlns=xmlns, duration=1),
        get_formdata(29, domain, user_id, xmlns=xmlns, duration=12),
        get_formdata(30, domain, user_id, xmlns=xmlns, duration=1),
    ]

    _insert_form_data(domain, form_data)


def clear_data():
    FormData.objects.all().delete()
    CaseData.objects.all().delete()
