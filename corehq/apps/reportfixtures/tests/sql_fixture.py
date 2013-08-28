import sqlalchemy
from sqlalchemy import *
from django.conf import settings
from sqlalchemy.engine.url import make_url
from datetime import date, timedelta

metadata = sqlalchemy.MetaData()

call_center_table = Table("call_center",
                          metadata,
                          Column("case", String(50), primary_key=True, autoincrement=False),
                          Column("date", DATE, primary_key=True, autoincrement=False),
                          Column("cases_updated", INT),
                          Column("duration", INT))


def load_data():
    engine = create_engine(make_url(settings.SQL_REPORTING_DATABASE_URL))
    metadata.bind = engine
    call_center_table.drop(engine, checkfirst=True)
    metadata.create_all()

    data = [
        {"case": "123", "date": date.today(), "cases_updated": 1, "duration": 10},
        {"case": "123", "date": date.today() - timedelta(days=2), "cases_updated": 2, "duration": 15},
        {"case": "123", "date": date.today() - timedelta(days=7), "cases_updated": 1, "duration": 6},
        {"case": "123", "date": date.today() - timedelta(days=8), "cases_updated": 4, "duration": 50},
    ]

    connection = engine.connect()
    try:
        connection.execute(call_center_table.delete())
        for d in data:
            insert = call_center_table.insert().values(**d)
            connection.execute(insert)
    finally:
        connection.close()
