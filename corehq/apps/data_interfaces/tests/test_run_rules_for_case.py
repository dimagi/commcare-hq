from datetime import datetime
from unittest.mock import patch

from django.db import connection
from unmagic import use

from corehq.apps.data_interfaces.models import CaseRuleActionResult
from corehq.apps.data_interfaces.utils import run_rules_for_case
from corehq.form_processor.models import CommCareCase
from corehq.util.test_utils import new_db_connection

NOW = datetime(2026, 1, 1)


class ServerDropsConnectionRule:
    """Postgres terminates the connection mid-query.

    Raises OperationalError, as when the server drops a connection in
    production.
    """
    pk = 1

    def run_rule(self, case, now):
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_terminate_backend(pg_backend_pid())')


class ClientClosedConnectionRule:
    """The connection is already closed when a query is attempted.

    Raises InterfaceError, as when an earlier OperationalError happened
    outside ``run_rules_for_case()``'s error handling.
    """
    pk = 2

    def run_rule(self, case, now):
        connection.ensure_connection()
        connection.connection.close()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')


class QueryRule:
    pk = 3

    def __init__(self):
        self.result = None

    def run_rule(self, case, now):
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            self.result = cursor.fetchone()
        return CaseRuleActionResult()


@use('db')
def test_rules_recover_from_dropped_connections():
    case = CommCareCase(domain='test-domain', case_id='abc123')
    after_server_drop = QueryRule()
    after_client_close = QueryRule()
    rules = [
        ServerDropsConnectionRule(),
        after_server_drop,
        ClientClosedConnectionRule(),
        after_client_close,
    ]

    with (
        new_db_connection(),
        patch('corehq.apps.data_interfaces.utils.notify_exception'),
    ):
        result = run_rules_for_case(case, rules, NOW)

    assert after_server_drop.result == (1,)
    assert after_client_close.result == (1,)
    assert result.num_errors == 2
