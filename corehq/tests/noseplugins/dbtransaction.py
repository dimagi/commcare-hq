from nose.plugins import Plugin

from django.db import connection


class DatabaseTransactionPlugin(Plugin):
    """Verify database transaction not in progress before/after test context

    A "test context" is a package, module, or test class.
    """

    name = "dbtransaction"
    enabled = True

    def options(self, parser, env):
        """Do not call super (always enabled)"""

    def startContext(self, context):
        check_for_transaction(context)

    def stopContext(self, context):
        check_for_transaction(context)

    def handleError(self, test, err):
        if getattr(test, "error_context", None) in {"setup", "teardown"}:
            check_for_transaction(err[1])


def check_for_transaction(context):
    if connection.in_atomic_block:
        raise UnexpectedTransaction(
            "Was an exception raised in setUpClass() after super().setUpClass() "
            "or in tearDownClass() before super().tearDownClass()? "
            f"Context: {context}"
        )


class UnexpectedTransaction(Exception):
    pass
