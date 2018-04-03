from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from collections import namedtuple

import sqlalchemy
from sqlalchemy import *
from datetime import timedelta, datetime

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
        'xmlns': xmlns or 'http://anything'
    }


CaseInfo = namedtuple('CaseInfo', 'id, days_ago, case_type, is_closed')


def get_casedata(case_info, domain, user_id, owner_id, opened_by, closed_by):
    now = datetime.utcnow()
    date_ago = now - timedelta(days=case_info.days_ago)
    return {
        '_id': case_info.id,
        'doc_type': 'CommCareCase',
        'domain': domain,
        'type': case_info.case_type,
        'owner_id': owner_id,
        'opened_on': date_ago,
        'opened_by': opened_by or user_id,
        'modified_on': now,
        'closed': case_info.is_closed,
        'closed_on': (date_ago if case_info.is_closed else None),
        'closed_by': (closed_by or user_id) if case_info.is_closed else None,
        'actions': {
            'date': date_ago,
        }
    }


def load_data(domain, form_user_id, case_user_id=None,
              case_owner_id=None, case_opened_by=None, case_closed_by=None):
    from corehq.apps.callcenter.data_source import get_sql_adapters_for_domain

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

    data_sources = get_sql_adapters_for_domain(domain)
    _insert_docs(data_sources.forms, form_data)
    _insert_docs(data_sources.cases, case_data)
    _insert_docs(data_sources.case_actions, case_data)


def _insert_docs(data_source_adapter, docs):
    data_source_adapter.rebuild_table()
    for doc in docs:
        data_source_adapter.save(doc)


def load_custom_data(domain, user_id, xmlns):
    from corehq.apps.callcenter.data_source import get_sql_adapters_for_domain
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

    data_sources = get_sql_adapters_for_domain(domain)
    _insert_docs(data_sources.forms, form_data)
    _insert_docs(data_sources.cases, [])  # ensure the table exists
    _insert_docs(data_sources.case_actions, [])


def clear_data(domain):
    from corehq.apps.callcenter.data_source import get_sql_adapters_for_domain
    data_sources = get_sql_adapters_for_domain(domain)
    for data_source in data_sources:
        data_source.drop_table()
