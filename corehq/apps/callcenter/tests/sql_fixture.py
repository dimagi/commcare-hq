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
    return Table(mapping.table_name, metadata, *[c.sql_column for c in mapping.columns])


def load_data(domain, user_id):
    engine = create_engine(make_url(settings.SQL_REPORTING_DATABASE_URL))
    metadata.bind = engine

    case_table = get_table(get_case_mapping(domain))
    case_ownership_table = get_table(get_case_ownership_mapping(domain))
    case_table.drop(engine, checkfirst=True)
    case_ownership_table.drop(engine, checkfirst=True)
    metadata.create_all()

    def get_formdata(days_ago):
        now = datetime.now()
        return FormData(
            doc_type='XFormInstance',
            domain=domain,
            user_id=user_id,
            time_end=now - timedelta(days=days_ago),
            received_on=now,
            instance_id=uuid.uuid4(),
            time_start=now,
            duration=1
        )

    form_data = [
        get_formdata(0),
        get_formdata(3),
        get_formdata(7),
        get_formdata(8),
        get_formdata(9),
        get_formdata(11),
        get_formdata(14),
        get_formdata(15),
    ]

    case_data = [
        {"date": date.today(), "user_id": user_id, "case_type": 'person', 'action_type': 'update', 'case_id': '1', 'action_count': 1},
        {"date": date.today() - timedelta(days=10), "user_id": user_id, "case_type": 'person', 'action_type': 'update', 'case_id': '2', 'action_count': 1},
        {"date": date.today() - timedelta(days=30), "user_id": user_id, "case_type": 'person', 'action_type': 'update', 'case_id': '3', 'action_count': 1},
        {"date": date.today() - timedelta(days=31), "user_id": user_id, "case_type": 'person', 'action_type': 'update', 'case_id': '4', 'action_count': 1},
        {"date": date.today() - timedelta(days=45), "user_id": user_id, "case_type": 'person', 'action_type': 'update', 'case_id': '5', 'action_count': 1},
        {"date": date.today() - timedelta(days=55), "user_id": user_id, "case_type": 'person', 'action_type': 'update', 'case_id': '6', 'action_count': 1},
        {"date": date.today() - timedelta(days=56), "user_id": user_id, "case_type": 'person', 'action_type': 'update', 'case_id': '7', 'action_count': 1},
        {"date": date.today() - timedelta(days=60), "user_id": user_id, "case_type": 'person', 'action_type': 'update', 'case_id': '8', 'action_count': 1},
        {"date": date.today() - timedelta(days=61), "user_id": user_id, "case_type": 'person', 'action_type': 'update', 'case_id': '9', 'action_count': 1},
    ]

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
