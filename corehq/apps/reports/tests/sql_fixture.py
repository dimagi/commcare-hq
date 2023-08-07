from datetime import date

import sqlalchemy
from sqlalchemy import DATE, INT, Column, String, Table

from corehq.sql_db.connections import DEFAULT_ENGINE_ID, connection_manager

metadata = sqlalchemy.MetaData()

user_table = Table(
    'user_report_data',
    metadata,
    Column('user', String(50), primary_key=True, autoincrement=False),
    Column('date', DATE, primary_key=True, autoincrement=False),
    Column('indicator_a', INT),
    Column('indicator_b', INT),
    Column('indicator_c', INT),
    Column('indicator_d', INT),
)

region_table = Table(
    'region_report_data',
    metadata,
    Column('region', String(50), primary_key=True, autoincrement=False),
    Column('sub_region', String(50), primary_key=True, autoincrement=False),
    Column('date', DATE, primary_key=True, autoincrement=False),
    Column('indicator_a', INT),
    Column('indicator_b', INT),
)


def load_data():
    engine = connection_manager.get_engine(DEFAULT_ENGINE_ID)
    metadata.bind = engine
    user_table.drop(engine, checkfirst=True)
    region_table.drop(engine, checkfirst=True)
    metadata.create_all()

    user_data = [
        {
            'user': 'user1',
            'date': date(2013, 1, 1),
            'indicator_a': 1,
            'indicator_b': 0,
            'indicator_c': 1,
            'indicator_d': 1,
        },
        {
            'user': 'user1',
            'date': date(2013, 2, 1),
            'indicator_a': 0,
            'indicator_b': 1,
            'indicator_c': 1,
            'indicator_d': 1,
        },
        {
            'user': 'user2',
            'date': date(2013, 1, 1),
            'indicator_a': 0,
            'indicator_b': 1,
            'indicator_c': 1,
            'indicator_d': 2,
        },
        {
            'user': 'user2',
            'date': date(2013, 2, 1),
            'indicator_a': 1,
            'indicator_b': 0,
            'indicator_c': 1,
            'indicator_d': 2,
        },
    ]

    region_data = [
        {
            'region': 'region1',
            'sub_region': 'region1_a',
            'date': date(2013, 1, 1),
            'indicator_a': 1,
            'indicator_b': 0,
        },
        {
            'region': 'region1',
            'sub_region': 'region1_a',
            'date': date(2013, 2, 1),
            'indicator_a': 1,
            'indicator_b': 1,
        },
        {
            'region': 'region1',
            'sub_region': 'region1_b',
            'date': date(2013, 1, 1),
            'indicator_a': 0,
            'indicator_b': 1,
        },
        {
            'region': 'region1',
            'sub_region': 'region1_b',
            'date': date(2013, 2, 1),
            'indicator_a': 0,
            'indicator_b': 0,
        },
        {
            'region': 'region2',
            'sub_region': 'region2_a',
            'date': date(2013, 1, 1),
            'indicator_a': 0,
            'indicator_b': 1,
        },
        {
            'region': 'region2',
            'sub_region': 'region2_a',
            'date': date(2013, 2, 1),
            'indicator_a': 1,
            'indicator_b': 1,
        },
        {
            'region': 'region2',
            'sub_region': 'region2_b',
            'date': date(2013, 1, 1),
            'indicator_a': 1,
            'indicator_b': 0,
        },
        {
            'region': 'region2',
            'sub_region': 'region2_b',
            'date': date(2013, 2, 1),
            'indicator_a': 0,
            'indicator_b': 0,
        },
    ]

    connection = engine.connect()
    try:
        connection.execute(user_table.delete())
        connection.execute(region_table.delete())
        for d in user_data:
            insert = user_table.insert().values(**d)
            connection.execute(insert)

        for d in region_data:
            insert = region_table.insert().values(**d)
            connection.execute(insert)
    finally:
        connection.close()
        engine.dispose()
