import pytest
from sqlalchemy import func, select
from unmagic import fixture, use

from corehq.apps.project_db.table_ddl import CaseTable, get_project_db_engine

from .util import project_db_table

DOMAIN = 'test-projectdb-queries'

# (case_id, first_name, last_name)
CLIENTS = [
    ('c1', 'Sarah', 'Smith'),
    ('c2', 'Sara', 'Smyth'),
    ('c3', 'Saraah', 'Smithe'),
    ('c4', 'John', 'Johnson'),
    ('c5', 'Jon', 'Jonson'),
    ('c6', 'Michael', 'Brown'),
    ('c7', 'Micheal', 'Braun'),
    ('c8', 'Katherine', 'Nguyen'),
    ('c9', 'Catherine', 'Wynn'),
    ('c10', 'Robert', 'Williams'),
]


@fixture(scope='module')
def loaded_clients():
    with project_db_table(DOMAIN, 'client', {
        'first_name': 'plain',
        'last_name': 'plain',
    }):
        table = CaseTable(DOMAIN, 'client').reflect()
        with get_project_db_engine().begin() as conn:
            conn.execute(table.insert(), [
                {'case_id': case_id,
                 'owner_id': 'owner1',
                 'prop__first_name': first_name,
                 'prop__last_name': last_name}
                for case_id, first_name, last_name in CLIENTS
            ])
        yield table


@use('db', loaded_clients)
@pytest.mark.parametrize('query, expected', [
    ('Sara', ['Sara', 'Sarah', 'Saraah']),  # Matches all three, in order
    ('Michael', ['Michael', 'Micheal']),    # Micheal typo scores 0.33
    ('Jon', ['Jon']),                       # John scores 0.29, below threshold
    ('Robert', ['Robert']),                 # exact match, no false positives
])
def test_trigram_matches_typos(query, expected):
    table = loaded_clients()
    with get_project_db_engine().begin() as conn:
        column = table.c['prop__first_name']
        similarity = func.similarity(column, query)
        rows = conn.execute(
            select([column, similarity])
            .where(similarity >= 0.3)
            .order_by(similarity.desc())
        ).fetchall()
    assert [r[0] for r in rows] == expected


@use('db', loaded_clients)
@pytest.mark.parametrize('prop, query, expected', [
    ('last_name', 'Smyth', {'Smith', 'Smyth', 'Smithe'}),   # Smith / Smyth / Smithe -> SM0
    ('first_name', 'Jon', {'John', 'Jon'}),          # John / Jon -> JN
    ('first_name', 'Catherine', {'Catherine', 'Katherine'}),    # Catherine / Katherine -> K0RN
    ('last_name', 'Braun', {'Brown', 'Braun'}),         # Brown / Braun -> PRN
    ('first_name', 'Michael', {'Michael'}),            # Micheal's code (MXL) differs, so misses
])
def test_phonetic_matches(prop, query, expected):
    table = loaded_clients()
    with get_project_db_engine().begin() as conn:
        column = table.c[f'prop__{prop}']
        rows = conn.execute(
            select([column])
            .where(func.dmetaphone(column) == func.dmetaphone(query))
        ).fetchall()
    assert {r[0] for r in rows} == expected
