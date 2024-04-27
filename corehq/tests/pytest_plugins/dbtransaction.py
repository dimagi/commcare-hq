import pytest
from django.db import connection

# logstart/logfinish will not work because they are executed before/after each
# test function/method. Class-based checks need to be implemented, which may be
# easiest by wrapping pytest_django.plugin._django_setup_unittest and possibly
# also the django_db_blocker fixture.


@pytest.hookimpl
def pytest_runtest_logstart(nodeid, location):
    check_for_transaction(location)


@pytest.hookimpl
def pytest_runtest_logfinish(nodeid, location):
    check_for_transaction(location)


def check_for_transaction(context):
    if connection.in_atomic_block:
        # raise causes internal error in pytest
        # TODO add error to test result/report
        raise UnexpectedTransaction(
            "Was an exception raised in setUpClass() after super().setUpClass() "
            "or in tearDownClass() before super().tearDownClass()? "
            f"Context: {context}"
        )


class UnexpectedTransaction(Exception):
    pass
