import pytest
import sqlalchemy
from unmagic import use

from corehq.apps.project_db.table_ddl import get_project_db_engine

PROVISION_SQL = 'SELECT projectdb_provision_role(:name, :password)'
DROP_SQL = 'SELECT projectdb_drop_role(:name)'


def provision_role(conn, name, password='secret'):
    conn.execute(sqlalchemy.text(PROVISION_SQL), {'name': name, 'password': password})


def drop_role(conn, name):
    conn.execute(sqlalchemy.text(DROP_SQL), {'name': name})


def can_login(conn, name):
    """Return the role's LOGIN attribute, or None if the role does not exist"""
    return conn.execute(
        sqlalchemy.text('SELECT rolcanlogin FROM pg_roles WHERE rolname = :name'),
        {'name': name},
    ).scalar()


@use('db')
def test_role_lifecycle():
    # Roles are cluster-wide rather than per-database, so this test must clean
    # up after itself; teardown of the test database would not.
    role = 'projectdb_test_lifecycle'
    with get_project_db_engine().begin() as conn:
        provision_role(conn, role)
        try:
            assert can_login(conn, role) is True
        finally:
            drop_role(conn, role)
        assert can_login(conn, role) is None


@use('db')
def test_provision_role_refuses_existing_role():
    # Callers must check whether the role exists, or tolerate this error
    role = 'projectdb_test_exists'
    with get_project_db_engine().begin() as conn:
        provision_role(conn, role)
        with pytest.raises(sqlalchemy.exc.ProgrammingError, match='already exists'):
            provision_role(conn, role)
        # The failure aborts the transaction, so the role is never committed


@use('db')
def test_drop_role_ignores_absent_role():
    with get_project_db_engine().begin() as conn:
        drop_role(conn, 'projectdb_test_never_created')


@use('db')
@pytest.mark.parametrize('sql', [PROVISION_SQL, DROP_SQL])
def test_role_functions_refuse_other_roles(sql):
    with get_project_db_engine().begin() as conn:
        with pytest.raises(sqlalchemy.exc.InternalError, match='refusing to manage role'):
            conn.execute(sqlalchemy.text(sql), {'name': 'some_other_role', 'password': 'secret'})
