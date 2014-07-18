import uuid
import sqlalchemy
from sqlalchemy import *
from django.conf import settings
from sqlalchemy.engine.url import make_url
from datetime import date, timedelta, datetime
from corehq.apps.callcenter.utils import get_case_mapping, get_case_ownership_mapping
from corehq.apps.sofabed.models import FormData

metadata = sqlalchemy.MetaData()


def get_table(mapping):
    return Table(mapping.table_name, metadata, extend_existing=True, *[c.sql_column for c in mapping.columns])


def get_formdata(days_ago, domain, user_id, xmlns=None, duration=1):
    now = datetime.now()
    return FormData(
        doc_type='XFormInstance',
        domain=domain,
        user_id=user_id,
        time_end=now - timedelta(days=days_ago),
        received_on=now,
        instance_id=uuid.uuid4(),
        time_start=now,
        duration=duration*1000,  # convert to ms
        xmlns=xmlns
    )


def create_call_center_tables(engine, domain):
    case_table = get_table(get_case_mapping(domain))
    case_ownership_table = get_table(get_case_ownership_mapping(domain))
    case_table.drop(engine, checkfirst=True)
    case_ownership_table.drop(engine, checkfirst=True)
    metadata.create_all()

    return case_table, case_ownership_table


def load_data(domain, user_id):
    engine = create_engine(make_url(settings.SQL_REPORTING_DATABASE_URL))
    metadata.bind = engine

    case_table, case_ownership_table = create_call_center_tables(engine, domain)

    form_data = [
        get_formdata(0, domain, user_id),
        get_formdata(3, domain, user_id),
        get_formdata(7, domain, user_id),
        get_formdata(8, domain, user_id),
        get_formdata(9, domain, user_id),
        get_formdata(11, domain, user_id),
        get_formdata(14, domain, user_id),
        get_formdata(15, domain, user_id),
    ]

    def case_row(days_ago, case_id):
        return {
            "date": date.today() - timedelta(days=days_ago),
            "user_id": user_id,
            "case_type": 'person',
            'action_type': 'update',
            'case_id': case_id,
            'action_count': 1
        }

    case_data = [
        case_row(0, '1'),
        case_row(10, '2'),
        case_row(29, '3'),
        case_row(30, '4'),
        case_row(31, '5'),
        case_row(45, '6'),
        case_row(55, '7'),
        case_row(56, '8'),
        case_row(59, '9'),
    ]

    def get_ownership_row(case_type, open_cases):
        return {'user_id': user_id, 'case_type': case_type, 'open_cases': open_cases, 'closed_cases': 0},

    case_ownership_data = [
        {'user_id': user_id, 'case_type': 'person', 'open_cases': 10, 'closed_cases': 3},
        {'user_id': user_id, 'case_type': 'dog', 'open_cases': 2, 'closed_cases': 1}
    ]

    connection = engine.connect()
    try:
        connection.execute(case_table.delete())
        connection.execute(case_ownership_table.delete())
        connection.execute(case_table.insert(), case_data)
        connection.execute(case_ownership_table.insert(), case_ownership_data)
        FormData.objects.bulk_create(form_data)
    finally:
        connection.close()
        engine.dispose()


def load_custom_data(domain, user_id, xmlns):
    engine = create_engine(make_url(settings.SQL_REPORTING_DATABASE_URL))
    metadata.bind = engine

    create_call_center_tables(engine, domain)

    engine.dispose()

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

    FormData.objects.bulk_create(form_data)
